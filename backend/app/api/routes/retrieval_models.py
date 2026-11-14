from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.api.routes.model_providers import CredentialSafeRoute
from app.db.session import get_db
from app.schemas.retrieval_models import RetrievalModelsResponse, RetrievalModelsUpdate, VectorStoreTestInput, VectorStoreTestResponse
from app.services.retrieval_models import list_settings, probe_pgvector, save_settings


router = APIRouter(route_class=CredentialSafeRoute)


@router.get("", response_model=RetrievalModelsResponse)
def get_retrieval_models(request: Request, db: Session = Depends(get_db)) -> RetrievalModelsResponse:
    return list_settings(db, request.app.state.retrieval_model_revisions, request.app.state.retrieval_model_error)


@router.put("", response_model=RetrievalModelsResponse)
def put_retrieval_models(
    payload: RetrievalModelsUpdate, request: Request, db: Session = Depends(get_db),
) -> RetrievalModelsResponse:
    save_settings(db, payload)
    return get_retrieval_models(request, db)


@router.post("/test-vector-store", response_model=VectorStoreTestResponse)
def test_vector_store(
    payload: VectorStoreTestInput, db: Session = Depends(get_db),
) -> VectorStoreTestResponse:
    return probe_pgvector(db)
