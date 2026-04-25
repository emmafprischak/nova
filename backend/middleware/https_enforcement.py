"""
HTTPS Enforcement Middleware
Validates that requests come via HTTPS when in production
"""
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from backend.services.logger import StructuredLogger

logger = StructuredLogger(__name__)


class HTTPSEnforcementMiddleware(BaseHTTPMiddleware):
    """
    Enforces HTTPS for production environments.
    Checks X-Forwarded-Proto header (set by ngrok/reverse proxies).
    """
    
    def __init__(self, app, webhook_base_url: str = ""):
        super().__init__(app)
        self.webhook_base_url = webhook_base_url
        self.enforce_https = webhook_base_url.startswith("https://") if webhook_base_url else False
        
        if self.enforce_https:
            logger.info("HTTPS enforcement enabled", webhook_url=webhook_base_url)
        else:
            logger.info("HTTPS enforcement disabled (development mode)")
    
    async def dispatch(self, request: Request, call_next):
        # Skip enforcement for local development
        if request.url.hostname in ["localhost", "127.0.0.1", "0.0.0.0"]:
            return await call_next(request)
        
        # Skip enforcement if not configured for HTTPS
        if not self.enforce_https:
            return await call_next(request)
        
        # Check X-Forwarded-Proto header (set by ngrok, nginx, etc.)
        forwarded_proto = request.headers.get("X-Forwarded-Proto", "").lower()
        
        if forwarded_proto != "https":
            logger.warning(
                "HTTPS enforcement failed - rejecting HTTP request",
                path=request.url.path,
                forwarded_proto=forwarded_proto or "none",
                client_ip=request.client.host if request.client else "unknown"
            )
            
            return JSONResponse(
                status_code=400,
                content={
                    "error": "HTTPS required",
                    "message": "This endpoint only accepts HTTPS requests"
                }
            )
        
        # Request is HTTPS, proceed
        return await call_next(request)
