from fastapi import APIRouter
from app.core.config import settings

router = APIRouter()

@router.get("/health")
async def health_check():
    """
    Simple health-check endpoint to verify that the service is running.
    """
    return {
        "status": "healthy",
        "app_name": settings.app_name,
        "app_env": settings.app_env,
    }
