from fastapi import FastAPI
from app.lifespan import app_lifespan
from app.api.router import router
from app.logging import configure_logging

configure_logging()

app = FastAPI(
    title="RAG API with Ollama",
    lifespan=app_lifespan
)

app.include_router(router, prefix="/api")
