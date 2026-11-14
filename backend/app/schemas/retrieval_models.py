from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, SecretStr, StringConstraints, field_validator, model_validator

from app.schemas.model_providers import normalize_base_url


ModelName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=240, pattern=r"^\S+$")]
Endpoint = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]
VectorBackend = Literal["milvus", "pgvector"]


class EmbeddingSettings(BaseModel):
    provider: Literal["openai_compatible", "local"]
    model: ModelName
    dimensions: int = Field(ge=64, le=4096)
    base_url: Endpoint | None = None
    vector_backend: VectorBackend = "milvus"
    milvus_uri: Endpoint | None = None


class EmbeddingSettingsInput(EmbeddingSettings):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)
    api_key: SecretStr | None = Field(default=None, max_length=4096)
    milvus_token: SecretStr | None = Field(default=None, max_length=4096)
    clear_api_key: bool = False
    clear_milvus_token: bool = False

    @field_validator("base_url")
    @classmethod
    def validate_api_url(cls, value: str | None) -> str | None:
        return normalize_base_url(value).removesuffix("/embeddings") if value is not None else None

    @field_validator("milvus_uri")
    @classmethod
    def validate_milvus_url(cls, value: str | None) -> str | None:
        return normalize_base_url(value) if value is not None else None

    @model_validator(mode="after")
    def require_service_urls(self):
        if self.provider == "openai_compatible" and not self.base_url:
            raise ValueError("请填写向量模型的 API 地址。")
        if self.vector_backend == "milvus" and not self.milvus_uri:
            raise ValueError("请填写 Milvus 地址。")
        return self


class VectorStoreTestInput(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)
    vector_backend: Literal["pgvector"]


class VectorStoreTestResponse(BaseModel):
    ready: bool
    message: str


class RerankSettings(BaseModel):
    model: ModelName
    base_url: Endpoint


class RerankSettingsInput(RerankSettings):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)
    api_key: SecretStr | None = Field(default=None, max_length=4096)
    clear_api_key: bool = False

    @field_validator("base_url")
    @classmethod
    def validate_api_url(cls, value: str) -> str:
        return normalize_base_url(value).removesuffix("/reranks")


class RetrievalModelsUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)
    embedding: EmbeddingSettingsInput | None = None
    rerank: RerankSettingsInput | None = None


class EmbeddingSettingsResponse(EmbeddingSettings):
    has_api_key: bool
    has_milvus_token: bool


class RerankSettingsResponse(RerankSettings):
    has_api_key: bool


class RetrievalModelsResponse(BaseModel):
    embedding: EmbeddingSettingsResponse | None = None
    rerank: RerankSettingsResponse | None = None
    restart_required: bool = False
    activation_error: str | None = None
