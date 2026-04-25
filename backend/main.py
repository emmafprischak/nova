"""
Main Application Entry Point
Run this file to start the server: python main.py
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi.middleware.cors import CORSMiddleware
from backend.routes import webhooks, health
from backend.config import HOST, PORT
from backend.services.logger import StructuredLogger
import uvicorn

# Initialize logger
logger = StructuredLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Nova Voice Agent Starting", webhooks=["/webhooks/voice/incoming"], health_endpoint="/health")
    yield
    # Shutdown
    logger.info("Nova shutting down")

# Initialize rate limiter
limiter = Limiter(key_func=get_remote_address)

# Create FastAPI app
app = FastAPI(
    title="Nova Voice Agent",
    description="AI Voice Agent for Orbyn.ai",
    version="1.0.0",
    lifespan=lifespan
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Add CORS middleware
# Restrict to Twilio and trusted origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://api.twilio.com",
        "https://*.twilio.com",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# Register routes
app.include_router(health.router, tags=["Health"])
app.include_router(webhooks.router, prefix="/webhooks", tags=["Webhooks"])

if __name__ == "__main__":
    logger.info("Starting server", host=HOST, port=PORT)
    uvicorn.run(
        "main:app",
        host=HOST,
        port=PORT,
        reload=True
    )
