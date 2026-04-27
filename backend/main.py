"""
Main Application Entry Point
Run this file to start the server: python main.py
"""
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi.middleware.cors import CORSMiddleware
from backend.routes import webhooks, health
from backend.config import HOST, PORT, CRM_BACKEND_URL, MASTER_NOVA_API_KEY, REGISTRY_SYNC_INTERVAL
import backend.services.crm as crm_service
import uvicorn
import logging

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print("=" * 60)
    print("Nova Voice Agent Starting...")
    print("=" * 60)
    print(f"Twilio webhook: /webhooks/voice/incoming")
    print(f"Health check: /health")
    print("=" * 60)

    sync_task = None

    # Bootstrap the tenant registry if credentials are configured
    if CRM_BACKEND_URL and MASTER_NOVA_API_KEY:
        from backend.services.tenant_registry import TenantRegistryManager
        registry = TenantRegistryManager(
            crm_url=CRM_BACKEND_URL,
            master_api_key=MASTER_NOVA_API_KEY,
            refresh_interval=REGISTRY_SYNC_INTERVAL,
        )
        success = await registry.bootstrap()
        if success:
            crm_service.registry_manager = registry
            sync_task = asyncio.create_task(registry.start_periodic_sync())
            print(f"Tenant registry loaded: {len(registry.get_all_tenants())} active tenant(s)")
        else:
            logger.warning(
                "Tenant registry bootstrap failed; Nova will run without per-tenant "
                "HMAC authentication until the registry becomes available."
            )
    else:
        logger.info(
            "MASTER_NOVA_API_KEY not set; tenant registry disabled. "
            "Set MASTER_NOVA_API_KEY and CRM_BACKEND_URL to enable multi-tenant support."
        )

    yield

    # Shutdown
    if sync_task is not None:
        sync_task.cancel()
        try:
            await sync_task
        except asyncio.CancelledError:
            pass
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
