from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.db.models import Base
from app.db.session import engine
from app.api.routes import repos, workspaces, code_graph, webhooks, rag, knowledge, search, project_index, issues, pull_requests, ci, reports, action_drafts
from app.services.rag.vector_store import MilvusUnavailableError
from fastapi.responses import JSONResponse


def create_app() -> FastAPI:
    app = FastAPI(title=settings.app_name, version="0.4.0")
    app.add_middleware(CORSMiddleware,
        allow_origins=[s.strip() for s in settings.cors_origins.split(",") if s.strip()],
        allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
    @app.exception_handler(MilvusUnavailableError)
    async def milvus_unavailable_handler(_request, exc):
        return JSONResponse(status_code=503, content={"detail": str(exc), "service": "milvus", "status": "degraded"})

    app.include_router(repos.router, prefix="/api/repos", tags=["repos"])
    app.include_router(workspaces.router, prefix="/api/workspaces", tags=["workspaces"])
    app.include_router(code_graph.router, prefix="/api", tags=["code_graph"])
    app.include_router(webhooks.router, prefix="/api/webhooks", tags=["webhooks"])
    app.include_router(rag.router, prefix="/api/rag", tags=["rag"])
    app.include_router(knowledge.router, prefix="/api/repos", tags=["knowledge"])
    app.include_router(search.router, prefix="/api/search", tags=["search"])
    app.include_router(project_index.router, prefix="/api/repos", tags=["project_index"])
    app.include_router(issues.router, prefix="/api", tags=["issues"])
    app.include_router(pull_requests.router, prefix="/api", tags=["pull_requests"])
    app.include_router(ci.router, prefix="/api", tags=["ci"])
    app.include_router(reports.router, prefix="/api/reports", tags=["reports"])
    app.include_router(action_drafts.router, prefix="/api/action-drafts", tags=["action_drafts"])

    @app.get("/health")
    async def health():
        return {"status": "ok", "app": settings.app_name}

    @app.on_event("startup")
    async def create_tables():
        Base.metadata.create_all(bind=engine)

    return app


app = create_app()
