from contextlib import asynccontextmanager
from app.rag.agent import agent_lifespan
from fastapi import FastAPI
from app.logging import logger

@asynccontextmanager
async def app_lifespan(app: FastAPI):
    logger.info(event="Startup backend")
    async with agent_lifespan(app):
        yield
    logger.info(event="Shutdown backend")