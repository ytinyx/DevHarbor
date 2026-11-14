from uuid import UUID, uuid4

from pydantic import SecretStr
from sqlalchemy import select, update
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import KnowledgeBaseConfig, RetrievalModelSetting
from app.schemas.retrieval_models import (
    EmbeddingSettings, EmbeddingSettingsInput, EmbeddingSettingsResponse,
    RerankSettings, RerankSettingsInput, RerankSettingsResponse,
    RetrievalModelsResponse, RetrievalModelsUpdate,
    VectorStoreTestResponse,
)
from app.services.model_providers import ModelProviderError, decrypt_provider_key, encrypt_provider_key
from app.services.rag.pgvector_store import PgvectorNotReadyError, PgvectorStore


def list_settings(db: Session, active: dict[str, UUID], activation_error: str | None) -> RetrievalModelsResponse:
    rows = {row.kind: row for row in db.scalars(select(RetrievalModelSetting))}
    embedding = rows.get("embedding")
    rerank = rows.get("rerank")
    return RetrievalModelsResponse(
        embedding=EmbeddingSettingsResponse(
            **embedding.configuration,
            has_api_key=bool(embedding.api_key_encrypted),
            has_milvus_token=bool(embedding.milvus_token_encrypted),
        ) if embedding and embedding.configuration is not None else None,
        rerank=RerankSettingsResponse(
            **rerank.configuration,
            has_api_key=bool(rerank.api_key_encrypted),
        ) if rerank and rerank.configuration is not None else None,
        restart_required=any(active.get(kind) != row.revision for kind, row in rows.items()),
        activation_error=activation_error,
    )


def probe_pgvector(db: Session) -> VectorStoreTestResponse:
    bind = db.get_bind()
    engine = bind if isinstance(bind, Engine) else bind.engine
    try:
        PgvectorStore(engine, settings.pgvector_collection, settings.embedding_dimensions).probe(db=db)
    except PgvectorNotReadyError as exc:
        return VectorStoreTestResponse(ready=False, message=str(exc))
    except Exception:
        return VectorStoreTestResponse(ready=False, message="无法连接 PostgreSQL，请检查应用的数据库连接和权限。")
    return VectorStoreTestResponse(ready=True, message="PostgreSQL 已连接，pgvector 可用。")


def _save_credential(
    previous: str | None,
    replacement: SecretStr | None,
    clear: bool,
    *,
    same_endpoint: bool,
    label: str,
    required: bool = False,
) -> str | None:
    value = replacement.get_secret_value().strip() if replacement else ""
    if value and clear:
        raise ModelProviderError(f"请为{label}选择填写新值或清除。")
    if value:
        return encrypt_provider_key(value)
    if previous and not same_endpoint and not clear:
        raise ModelProviderError(f"服务地址已更改，请重新填写{label}。")
    encrypted = previous if not clear else None
    if required and not encrypted:
        raise ModelProviderError(f"请填写{label}。")
    return encrypted


def _save_profile(db: Session, kind: str, payload: EmbeddingSettingsInput | RerankSettingsInput | None) -> None:
    row = db.scalar(select(RetrievalModelSetting).where(RetrievalModelSetting.kind == kind).with_for_update())
    if row is None:
        if payload is None:
            return
        row = RetrievalModelSetting(kind=kind)
        db.add(row)

    configuration = None
    api_key = None
    milvus_token = None
    existing = row.configuration or {}
    if isinstance(payload, EmbeddingSettingsInput):
        configuration = payload.model_dump(include=set(EmbeddingSettings.model_fields))
        if payload.provider == "openai_compatible":
            api_key = _save_credential(
                row.api_key_encrypted, payload.api_key, payload.clear_api_key,
                same_endpoint=existing.get("base_url") == payload.base_url,
                label="向量模型 API 密钥", required=True,
            )
        else:
            configuration["base_url"] = None
        if payload.vector_backend == "milvus":
            milvus_token = _save_credential(
                row.milvus_token_encrypted, payload.milvus_token, payload.clear_milvus_token,
                same_endpoint=existing.get("milvus_uri") == payload.milvus_uri,
                label="Milvus Token",
            )
        else:
            configuration["milvus_uri"] = None
        previous_config = {"vector_backend": "milvus", **existing}
        same_vector_space = all(previous_config.get(name) == value for name, value in configuration.items())
        previous_collection = existing.get("collection") if same_vector_space else None
        configuration["collection"] = previous_collection or f"devharbor_embedding_{uuid4().hex}"
    elif isinstance(payload, RerankSettingsInput):
        configuration = payload.model_dump(include=set(RerankSettings.model_fields))
        api_key = _save_credential(
            row.api_key_encrypted, payload.api_key, payload.clear_api_key,
            same_endpoint=existing.get("base_url") == payload.base_url,
            label="重排模型 API 密钥", required=True,
        )

    if (configuration, api_key, milvus_token) == (row.configuration, row.api_key_encrypted, row.milvus_token_encrypted):
        return
    row.configuration = configuration
    row.api_key_encrypted = api_key
    row.milvus_token_encrypted = milvus_token
    row.revision = uuid4()


def save_settings(db: Session, payload: RetrievalModelsUpdate) -> None:
    if payload.embedding and payload.embedding.vector_backend == "pgvector":
        result = probe_pgvector(db)
        if not result.ready:
            raise ModelProviderError(result.message)
    for kind in ("embedding", "rerank"):
        if kind in payload.model_fields_set:
            _save_profile(db, kind, getattr(payload, kind))
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ModelProviderError("配置刚刚在另一个窗口更新，请刷新后重试。", 409) from exc


def apply_saved_settings(db: Session) -> tuple[dict[str, UUID], dict[str, object], str | None]:
    """Apply one stable retrieval configuration before the server accepts requests."""
    active: dict[str, UUID] = {}
    overrides: dict[str, object] = {}
    failures: list[str] = []
    for row in db.scalars(select(RetrievalModelSetting)):
        try:
            api_key = decrypt_provider_key(row.api_key_encrypted)
            milvus_token = decrypt_provider_key(row.milvus_token_encrypted)
        except ModelProviderError:
            failures.append("向量模型" if row.kind == "embedding" else "重排模型")
            if row.kind == "embedding":
                overrides.update(embedding_provider="disabled", embedding_model="disabled", embedding_dimensions=128, milvus_enabled=False)
            else:
                overrides.update(rerank_base_url=None, rerank_api_key=None)
            continue
        if row.kind == "embedding":
            if row.configuration is not None:
                config = EmbeddingSettings.model_validate(row.configuration)
                overrides.update(
                    embedding_provider=config.provider, embedding_model=config.model,
                    embedding_dimensions=config.dimensions, embedding_base_url=config.base_url,
                    embedding_api_key=api_key, vector_backend=config.vector_backend,
                )
                if config.vector_backend == "pgvector":
                    overrides["pgvector_collection"] = row.configuration["collection"]
                else:
                    overrides.update(
                        milvus_uri=config.milvus_uri, milvus_token=milvus_token,
                        milvus_enabled=True, milvus_collection=row.configuration["collection"],
                    )
            # Reconcile legacy per-repository metadata, keeping retrieval preferences and document rows.
            fields = ("embedding_provider", "embedding_model", "embedding_dimensions")
            values = {name: overrides.get(name, getattr(settings, name)) for name in fields}
            db.execute(update(KnowledgeBaseConfig).where(
                (KnowledgeBaseConfig.embedding_provider != values["embedding_provider"])
                | (KnowledgeBaseConfig.embedding_model != values["embedding_model"])
                | (KnowledgeBaseConfig.embedding_dimensions != values["embedding_dimensions"])
            ).values(**values))
        elif row.kind == "rerank":
            if row.configuration is not None:
                config = RerankSettings.model_validate(row.configuration)
                overrides.update(qwen_rerank_model=config.model, rerank_base_url=config.base_url, rerank_api_key=api_key)
            model = overrides.get("qwen_rerank_model", settings.qwen_rerank_model)
            db.execute(update(KnowledgeBaseConfig).where(
                KnowledgeBaseConfig.rerank_provider == "qwen_api",
                KnowledgeBaseConfig.rerank_model != model,
            ).values(rerank_model=model))
        active[row.kind] = row.revision
    db.commit()
    previous = {name: getattr(settings, name) for name in overrides}
    for name, value in overrides.items():
        setattr(settings, name, value)
    activation_error = f"无法解密已保存的{'、'.join(failures)}凭据，请重新填写密钥并保存后重启。" if failures else None
    return active, previous, activation_error
