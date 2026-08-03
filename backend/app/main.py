from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.db.models import Base
from app.db.session import engine


def create_app() -> FastAPI:
    app = FastAPI(title=settings.app_name, version="0.1.0")
    app.add_middleware(CORSMiddleware,
        allow_origins=[s.strip() for s in settings.cors_origins.split(",") if s.strip()],
        allow_credentials=True, allow_methods=["*"], allow_headers=["*"])


    @app.get("/health")
    async def health():
        return {"status": "ok", "app": settings.app_name}

    @app.on_event("startup")
    async def create_tables():
        Base.metadata.create_all(bind=engine)

    return app


app = create_app()
