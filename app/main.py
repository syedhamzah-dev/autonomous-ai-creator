from fastapi import FastAPI
from app.core.config import settings
from app.api.router import api_router

app = FastAPI(
    title=settings.app_name,
    description="Autonomous AI Creator - Project Foundation",
    version="0.1.0"
)

# Register API Router
app.include_router(api_router)
