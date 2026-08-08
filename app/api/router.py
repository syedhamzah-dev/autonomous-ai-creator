from fastapi import APIRouter
from app.api.endpoints import health, agent

api_router = APIRouter()

# Include endpoint routers. 
# The health check router exposes GET /health
api_router.include_router(health.router)
api_router.include_router(agent.router, prefix="/api/agent")
