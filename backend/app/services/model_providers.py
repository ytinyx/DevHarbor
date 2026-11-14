"""Persisted provider configuration; credentials never enter public response models."""

import os
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit
from uuid import UUID

import httpx
from cryptography.fernet import Fernet
from sqlalchemy import select
from sqlalchemy.exc import OperationalError, ProgrammingError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import decrypt_token, encrypt_token
from app.db import session as db_session
from app.db.models import ModelProvider, ModelProviderSelection
from app.schemas.model_providers import (
    ActiveModel, DiscoverModels, EnvironmentModel, ProviderCreate, ProviderListResponse,
    ProviderResponse, ProviderUpdate,
)

DEFAULT_KEY_PATH = Path(__file__).resolve().parents[3] / ".data" / "model-providers.key"


class ModelProviderError(RuntimeError):
    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


@dataclass(frozen=True)
class ResolvedModelConfig:
    provider_id: str | None
    name: str
    base_url: str
    api_key: str | None = field(repr=False)
    model: str
    enabled: bool
    source: str


def _key_secret(*, create: bool) -> str:
    configured = settings.token_encryption_key.strip()
    if configured and configured != "change-me-in-local-dev" and not settings.desktop_mode:
        return configured
    key_path = Path(os.environ.get("DEVHARBOR_PROVIDER_KEY_FILE") or DEFAULT_KEY_PATH)
    if create:
        try:
            key_path.parent.mkdir(parents=True, exist_ok=True)
            descriptor = os.open(key_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError:
            pass
        except OSError as exc:
            raise ModelProviderError("无法创建本机密钥文件，请检查数据目录的写入权限。", 503) from exc
        else:
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(Fernet.generate_key())
    try:
        secret = key_path.read_text(encoding="ascii").strip()
        Fernet(secret.encode("ascii"))
        return secret
    except (OSError, ValueError, UnicodeError) as exc:
        raise ModelProviderError("本机密钥文件不可用，请恢复密钥文件或检查数据目录。密钥文件缺失时，可重新填写并保存供应商密钥。", 503) from exc


def encrypt_provider_key(api_key: str | None) -> str | None:
    if not api_key:
        return None
    return encrypt_token(api_key, _key_secret(create=True))


def decrypt_provider_key(encrypted_key: str | None) -> str | None:
    if not encrypted_key:
        return None
    token = decrypt_token(encrypted_key, _key_secret(create=False))
    if token is None:
        raise ModelProviderError("无法解密已保存的供应商密钥，请重新填写密钥并保存。", 503)
    return token


def _decrypt(provider: ModelProvider) -> str | None:
    return decrypt_provider_key(provider.api_key_encrypted)


def _input_key(value) -> str | None:
    if value is None:
        return None
    return value.get_secret_value().strip() or None


def provider_response(provider: ModelProvider) -> ProviderResponse:
    return ProviderResponse(
        id=provider.id, name=provider.name, base_url=provider.base_url,
        protocol=provider.protocol, models=provider.models, default_model=provider.default_model,
        has_api_key=bool(provider.api_key_encrypted), created_at=provider.created_at,
    )


def get_provider(db: Session, provider_id: UUID) -> ModelProvider:
    provider = db.get(ModelProvider, provider_id)
    if provider is None:
        raise ModelProviderError("未找到这个模型供应商，请刷新列表。", 404)
    return provider


def environment_model() -> EnvironmentModel:
    # Environment URLs may have been configured outside the validated settings UI.
    try:
        parsed = urlsplit(settings.llm_base_url)
        host = parsed.hostname or ""
        host = f"[{host}]" if ":" in host else host
        authority = f"{host}:{parsed.port}" if parsed.port is not None else host
        base_url = urlunsplit((parsed.scheme, authority, parsed.path, "", "")) if parsed.scheme in {"http", "https"} else None
    except ValueError:
        base_url = None
    return EnvironmentModel(configured=bool(settings.llm_api_key), model=settings.llm_model or None, base_url=base_url)


def get_active(db: Session) -> ActiveModel:
    selected = db.get(ModelProviderSelection, 1)
    return ActiveModel(provider_id=selected.provider_id, model=selected.model) if selected and selected.provider_id else ActiveModel()


def list_providers(db: Session) -> ProviderListResponse:
    providers = db.scalars(select(ModelProvider).order_by(ModelProvider.created_at, ModelProvider.name)).all()
    return ProviderListResponse(providers=[provider_response(provider) for provider in providers], active=get_active(db), environment=environment_model())


def create_provider(db: Session, payload: ProviderCreate) -> ProviderResponse:
    provider = ModelProvider(
        name=payload.name, base_url=payload.base_url, protocol=payload.protocol,
        models=payload.models, default_model=payload.default_model,
        api_key_encrypted=encrypt_provider_key(_input_key(payload.api_key)),
    )
    db.add(provider)
    db.commit()
    db.refresh(provider)
    return provider_response(provider)


def update_provider(db: Session, provider_id: UUID, payload: ProviderUpdate) -> ProviderResponse:
    provider = get_provider(db, provider_id)
    replacement_key = _input_key(payload.api_key)
    if replacement_key and payload.clear_api_key:
        raise ModelProviderError("不能同时填写新密钥并选择清除密钥。")
    next_url = payload.base_url if payload.base_url is not None else provider.base_url
    if next_url != provider.base_url and provider.api_key_encrypted and not (replacement_key or payload.clear_api_key):
        raise ModelProviderError("API 地址已改变。请重新填写密钥，或明确清除旧密钥后保存。")
    models = payload.models if payload.models is not None else provider.models
    default_model = payload.default_model if payload.default_model is not None else provider.default_model
    if default_model not in models:
        raise ModelProviderError("默认模型必须在模型目录中。")
    selected = db.get(ModelProviderSelection, 1)
    # Preserve the active model if possible; otherwise follow the edited provider's default.
    if selected and selected.provider_id == provider.id and selected.model not in models:
        selected.model = default_model
    for name in ("name", "protocol"):
        value = getattr(payload, name)
        if value is not None:
            setattr(provider, name, value)
    provider.base_url = next_url
    provider.models = models
    provider.default_model = default_model
    if replacement_key:
        provider.api_key_encrypted = encrypt_provider_key(replacement_key)
    elif payload.clear_api_key:
        provider.api_key_encrypted = None
    db.commit()
    db.refresh(provider)
    return provider_response(provider)


def activate_model(db: Session, provider_id: UUID, model: str) -> ActiveModel:
    provider = get_provider(db, provider_id)
    if model not in provider.models:
        raise ModelProviderError("请先将这个模型添加到供应商的模型目录中。")
    _decrypt(provider)  # Fail visibly before selecting an unreadable credential.
    selection = db.get(ModelProviderSelection, 1)
    if selection is None:
        selection = ModelProviderSelection(id=1)
        db.add(selection)
    selection.provider_id = provider.id
    selection.model = model
    db.commit()
    return ActiveModel(provider_id=provider.id, model=model)


def reset_active(db: Session) -> ActiveModel:
    selection = db.get(ModelProviderSelection, 1)
    if selection:
        selection.provider_id = None
        selection.model = None
        db.commit()
    return ActiveModel()


def delete_provider(db: Session, provider_id: UUID) -> None:
    provider = get_provider(db, provider_id)
    selection = db.get(ModelProviderSelection, 1)
    if selection and selection.provider_id == provider.id:
        selection.provider_id = None
        selection.model = None
        db.flush()
    db.delete(provider)
    db.commit()


def _environment_config() -> ResolvedModelConfig:
    return ResolvedModelConfig(
        provider_id=None, name="环境配置", base_url=settings.llm_base_url.rstrip("/"),
        api_key=settings.llm_api_key or None, model=settings.llm_model,
        enabled=bool(settings.llm_api_key), source="environment",
    )


def _selection_tables_missing(exc: OperationalError | ProgrammingError) -> bool:
    message = str(exc.orig).lower()
    return (
        "model_provider_selection" in message
        and ("no such table" in message or ("relation" in message and "does not exist" in message))
    )


def resolve_model_config(db: Session | None = None) -> ResolvedModelConfig:
    if db is None:
        with db_session.SessionLocal() as session:
            return resolve_model_config(session)
    try:
        selection = db.get(ModelProviderSelection, 1)
    except (OperationalError, ProgrammingError) as exc:
        # Existing isolated tests create only their needed tables. Other DB failures are real errors.
        if _selection_tables_missing(exc):
            db.rollback()
            return _environment_config()
        raise
    if selection is None or selection.provider_id is None:
        return _environment_config()
    provider = db.get(ModelProvider, selection.provider_id)
    if provider is None or not selection.model or selection.model not in provider.models:
        raise ModelProviderError("默认模型配置无效，请在设置中重新选择供应商和模型。", 503)
    return ResolvedModelConfig(
        provider_id=str(provider.id), name=provider.name, base_url=provider.base_url,
        api_key=_decrypt(provider), model=selection.model, enabled=True, source="provider",
    )


async def discover_models(db: Session, payload: DiscoverModels) -> list[str]:
    api_key = _input_key(payload.api_key)
    if payload.provider_id:
        provider = get_provider(db, payload.provider_id)
        if not api_key and provider.api_key_encrypted:
            if provider.base_url != payload.base_url:
                raise ModelProviderError("API 地址已改变，请重新填写密钥后获取模型。")
            api_key = _decrypt(provider)
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=False) as client:
            response = await client.get(f"{payload.base_url}/models", headers=headers)
        if response.status_code in {401, 403}:
            raise ModelProviderError("供应商拒绝访问，请检查 API 密钥及其模型访问权限。", 502)
        if 300 <= response.status_code < 400:
            raise ModelProviderError("API 地址返回了跳转，请直接填写供应商的最终 API 根地址。", 502)
        if response.status_code == 404:
            raise ModelProviderError("该地址没有模型列表接口。请确认 API 根地址，或手动添加模型标识。", 502)
        if response.status_code == 429:
            raise ModelProviderError("供应商请求过于频繁或额度不足，请稍后重试。", 502)
        response.raise_for_status()
        body = response.json()
        if not isinstance(body, dict) or not isinstance(body.get("data"), list):
            raise ModelProviderError("返回内容不符合兼容接口的模型列表格式，请手动添加模型。", 502)
        models = sorted({
            item["id"].strip() for item in body["data"]
            if isinstance(item, dict) and isinstance(item.get("id"), str)
            and item["id"].strip() and len(item["id"].strip()) <= 300
            and not any(char.isspace() for char in item["id"].strip())
            and (not api_key or api_key not in item["id"])
        })[:200]
        if not models:
            raise ModelProviderError("接口连接成功，但没有返回可用模型，请手动添加模型标识。", 502)
        return models
    except httpx.TimeoutException as exc:
        raise ModelProviderError("连接供应商超时，请检查地址和网络后重试。", 502) from exc
    except (httpx.HTTPError, ValueError) as exc:
        raise ModelProviderError("无法读取模型列表，请检查 API 地址、网络和接口协议，或手动添加模型。", 502) from exc
