from typing import Literal

from pydantic import BaseModel, ConfigDict, StrictBool


class AgentDescriptor(BaseModel):
    id: str
    name: str
    description: str
    group: Literal["coordination", "analysis", "support"]
    implementation: Literal["model", "rules", "tools", "workflow"]
    availability: Literal["available", "not_integrated"]
    enabled: bool
    configurable: bool
    required: bool
    capabilities: list[str]
    used_in: list[str]
    note: str


class AgentListResponse(BaseModel):
    agents: list[AgentDescriptor]
    total: int


class AgentSettingUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    enabled: StrictBool
