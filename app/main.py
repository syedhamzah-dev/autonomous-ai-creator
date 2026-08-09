from contextlib import asynccontextmanager
import logging
import os
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException
from app.core.config import settings
from app.api.router import api_router

logger = logging.getLogger("uvicorn")

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

# CORS configuration setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global Production Exception Handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    if isinstance(exc, StarletteHTTPException):
        # Pass standard HTTPExceptions through untouched (e.g. 404, 405)
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail}
        )
    # Log the traceback locally on the server
    logger.exception(f"Unhandled server exception: {exc}")
    # Return a safe, clean message without leaking paths, credentials, or traces
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal Server Error. Please contact server administration."}
    )

# Register API Router
app.include_router(api_router)

# Mount Static Files for the Evaluator UI Dashboard
from fastapi.staticfiles import StaticFiles

static_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
if not os.path.exists(static_path):
    os.makedirs(static_path)

app.mount("/", StaticFiles(directory=static_path, html=True), name="static")

