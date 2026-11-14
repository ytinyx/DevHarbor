from uuid import UUID

from fastapi import APIRouter, Depends, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.model_providers import (
    ActivateModel, ActiveModel, DiscoverModels, DiscoveredModels,
    ProviderCreate, ProviderListResponse, ProviderResponse, ProviderUpdate,
)
from app.services import model_providers as service


class CredentialSafeRoute(APIRoute):
    """Never include the request's API key in framework validation errors."""

    def get_route_handler(self):
        original = super().get_route_handler()

        async def safe_handler(request: Request):
            try:
                return await original(request)
            except RequestValidationError as exc:
                details = [{"loc": list(error["loc"]), "msg": error["msg"], "type": error["type"]} for error in exc.errors()]
                return JSONResponse(status_code=422, content={"detail": details})

        return safe_handler


router = APIRouter(route_class=CredentialSafeRoute)


@router.get("", response_model=ProviderListResponse)
def list_model_providers(db: Session = Depends(get_db)) -> ProviderListResponse:
    return service.list_providers(db)


@router.post("", response_model=ProviderResponse, status_code=201)
def create_model_provider(payload: ProviderCreate, db: Session = Depends(get_db)) -> ProviderResponse:
    return service.create_provider(db, payload)


@router.post("/activate", response_model=ActiveModel)
def activate_model_provider(payload: ActivateModel, db: Session = Depends(get_db)) -> ActiveModel:
    return service.activate_model(db, payload.provider_id, payload.model)


@router.post("/reset-active", response_model=ActiveModel)
def reset_active_model_provider(db: Session = Depends(get_db)) -> ActiveModel:
    return service.reset_active(db)


@router.post("/discover-models", response_model=DiscoveredModels)
async def discover_provider_models(payload: DiscoverModels, db: Session = Depends(get_db)) -> DiscoveredModels:
    return DiscoveredModels(models=await service.discover_models(db, payload))


@router.patch("/{provider_id}", response_model=ProviderResponse)
def update_model_provider(provider_id: UUID, payload: ProviderUpdate, db: Session = Depends(get_db)) -> ProviderResponse:
    return service.update_provider(db, provider_id, payload)


@router.delete("/{provider_id}")
def delete_model_provider(provider_id: UUID, db: Session = Depends(get_db)) -> dict[str, bool]:
    service.delete_provider(db, provider_id)
    return {"deleted": True}
