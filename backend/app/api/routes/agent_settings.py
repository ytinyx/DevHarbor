from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.agent_settings import AgentDescriptor, AgentListResponse, AgentSettingUpdate
from app.services import agent_settings as service

router = APIRouter()


@router.get("", response_model=AgentListResponse)
def list_agents(db: Session = Depends(get_db)) -> AgentListResponse:
    return service.list_agents(db)


@router.patch("/{agent_id}", response_model=AgentDescriptor)
def update_agent(agent_id: str, payload: AgentSettingUpdate, db: Session = Depends(get_db)) -> AgentDescriptor:
    return service.update_agent(db, agent_id, payload.enabled)
