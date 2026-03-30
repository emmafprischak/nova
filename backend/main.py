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
import uvicorn

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print("=" * 60)
    print("Nova Voice Agent Starting...")
    print("=" * 60)
    print(f"Twilio webhook: /webhooks/voice/incoming")
    print(f"Health check: /health")
    print("=" * 60)
    yield
    # Shutdown
    print("Nova shutting down...")

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
    print(f"Starting server on {HOST}:{PORT}")
    uvicorn.run(
        "main:app",
        host=HOST,
        port=PORT,
        reload=True
    )
