from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.core.config import settings
from app.api.router import api_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup lifecycle triggers
    yield
    # Shutdown lifecycle triggers: clean up all active scheduler background tasks
    from app.services.autonomous import agent_scheduler
    agent_scheduler.shutdown()

app = FastAPI(
    title=settings.app_name,
    description="Autonomous AI Creator - Project Foundation",
    version="0.1.0",
    lifespan=lifespan
)

# Register API Router
app.include_router(api_router)
