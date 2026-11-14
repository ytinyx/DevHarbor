from datetime import datetime
from typing import Literal
from urllib.parse import urlsplit, urlunsplit
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator, model_validator


def normalize_base_url(value: str) -> str:
    value = value.strip()
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError as exc:
        raise ValueError("API 地址格式无效，请填写完整的 http:// 或 https:// 地址。") from exc
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("API 地址必须以 http:// 或 https:// 开头并包含主机名。")
    if parsed.username is not None or parsed.password is not None or parsed.query or parsed.fragment or any(char.isspace() for char in value):
        raise ValueError("API 地址不能包含用户名、密码、查询参数、空格或片段。")
    if parsed.path.rstrip("/").lower().endswith(("/chat/completions", "/models", "/responses", "/messages")):
        raise ValueError("请填写 API 根地址，不要添加 /chat/completions、/models 或其他接口路径。")
    host = parsed.hostname.lower()
    host = f"[{host}]" if ":" in host else host
    authority = f"{host}:{port}" if port is not None else host
    return urlunsplit((parsed.scheme, authority, parsed.path.rstrip("/"), "", ""))


def normalize_models(values: list[str]) -> list[str]:
    normalized = list(dict.fromkeys(value.strip() for value in values if value.strip()))
    if not normalized:
        raise ValueError("请至少添加一个模型。")
    if len(normalized) > 200 or any(len(value) > 300 or any(char.isspace() for char in value) for value in normalized):
        raise ValueError("最多保存 200 个模型，模型标识不能包含空格且不能超过 300 个字符。")
    return normalized


class ProviderCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)
    name: str = Field(min_length=1, max_length=120)
    base_url: str = Field(min_length=1, max_length=2000)
    protocol: Literal["openai_compatible"] = "openai_compatible"
    api_key: SecretStr | None = None
    models: list[str] = Field(min_length=1, max_length=200)
    default_model: str = Field(min_length=1, max_length=300)

    @field_validator("name", "default_model")
    @classmethod
    def trim_required(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("此项不能为空。")
        return value

    @field_validator("base_url")
    @classmethod
    def validate_url(cls, value: str) -> str:
        return normalize_base_url(value)

    @field_validator("models")
    @classmethod
    def validate_models(cls, values: list[str]) -> list[str]:
        return normalize_models(values)

    @model_validator(mode="after")
    def default_in_catalog(self):
        if self.default_model not in self.models:
            raise ValueError("默认模型必须在模型目录中。")
        return self


class ProviderUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)
    name: str | None = Field(default=None, min_length=1, max_length=120)
    base_url: str | None = Field(default=None, min_length=1, max_length=2000)
    protocol: Literal["openai_compatible"] | None = None
    api_key: SecretStr | None = None
    clear_api_key: bool = False
    models: list[str] | None = Field(default=None, min_length=1, max_length=200)
    default_model: str | None = Field(default=None, min_length=1, max_length=300)

    @field_validator("name", "default_model")
    @classmethod
    def trim_optional(cls, value: str | None) -> str | None:
        if value is None:
            return value
        value = value.strip()
        if not value:
            raise ValueError("此项不能为空。")
        return value

    @field_validator("base_url")
    @classmethod
    def validate_url(cls, value: str | None) -> str | None:
        return normalize_base_url(value) if value is not None else None

    @field_validator("models")
    @classmethod
    def validate_models(cls, value: list[str] | None) -> list[str] | None:
        return normalize_models(value) if value is not None else None


class ProviderResponse(BaseModel):
    id: UUID
    name: str
    base_url: str
    protocol: str
    models: list[str]
    default_model: str
    has_api_key: bool
    created_at: datetime


class ActiveModel(BaseModel):
    provider_id: UUID | None = None
    model: str | None = None


class EnvironmentModel(BaseModel):
    configured: bool
    model: str | None = None
    base_url: str | None = None


class ProviderListResponse(BaseModel):
    providers: list[ProviderResponse]
    active: ActiveModel
    environment: EnvironmentModel


class ActivateModel(BaseModel):
    model_config = ConfigDict(extra="forbid")
    provider_id: UUID
    model: str = Field(min_length=1, max_length=300)


class DiscoverModels(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)
    provider_id: UUID | None = None
    base_url: str = Field(min_length=1, max_length=2000)
    api_key: SecretStr | None = None

    @field_validator("base_url")
    @classmethod
    def validate_url(cls, value: str) -> str:
        return normalize_base_url(value)


class DiscoveredModels(BaseModel):
    models: list[str]
