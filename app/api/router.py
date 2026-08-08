from fastapi import APIRouter
from app.api.endpoints import health

api_router = APIRouter()

# Include endpoint routers. 
# The health check router exposes GET /health
api_router.include_router(health.router)
