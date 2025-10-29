"""
services/conversation_agent_service/main.py

Conversation Agent Service - Main Application

FastAPI application with SSE streaming, LangChain orchestration, and full observability.

Run:
    uvicorn main:app --host 0.0.0.0 --port 8002 --reload
"""

import sys
import os
from contextlib import asynccontextmanager
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import time

from shared.common.logging import setup_logging, get_logger, set_trace_context, clear_trace_context
from shared.common.exceptions import BaseAppException
from shared.common.models import HealthCheckResponse, HealthStatus
from shared.database import init_database, close_database, check_database_connection
from shared.security import init_rate_limiter

from config import get_settings
from app.api.routes import conversation
from app.dependencies import init_redis, init_session_service, get_redis_client, close_redis

# Load settings
settings = get_settings()

# Setup logging
setup_logging(
    service_name=settings.SERVICE_NAME,
    log_level=settings.LOG_LEVEL,
    log_format=settings.LOG_FORMAT
)

logger = get_logger(__name__)


# Application startup time
_startup_time = datetime.utcnow()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.

    Handles startup and shutdown logic.
    """
    # ========================================================================
    # STARTUP
    # ========================================================================
    logger.info("Starting Conversation Agent Service", extra={
        "version": settings.SERVICE_VERSION,
        "environment": settings.ENVIRONMENT
    })

    try:
        # Initialize database
        logger.info("Initializing database connection...")
        init_database(
            database_url=settings.DATABASE_URL,
            pool_size=settings.DATABASE_POOL_SIZE,
            max_overflow=settings.DATABASE_MAX_OVERFLOW,
            echo=not settings.is_production
        )
        logger.info("Database initialized successfully")

        # Initialize Redis
        logger.info("Initializing Redis connection...")
        redis_client = init_redis(settings.REDIS_URL)
        await redis_client.ping()  # Test connection
        logger.info("Redis initialized successfully")

        # Initialize session service
        init_session_service(redis_client, settings.SESSION_TTL_SECONDS)

        # Initialize rate limiter
        init_rate_limiter(redis_client)
        logger.info("Rate limiter initialized")

        logger.info("Conversation Agent Service started successfully", extra={
            "host": settings.HOST,
            "port": settings.PORT
        })

    except Exception as e:
        logger.critical("Failed to start service", extra={"error": str(e)}, exc_info=True)
        raise

    yield

    # ========================================================================
    # SHUTDOWN
    # ========================================================================
    logger.info("Shutting down Conversation Agent Service...")

    try:
        # Close Redis
        await close_redis()

        # Close database
        await close_database()

        logger.info("Conversation Agent Service shut down successfully")

    except Exception as e:
        logger.error("Error during shutdown", extra={"error": str(e)}, exc_info=True)


# Create FastAPI app
app = FastAPI(
    title="Conversation Agent Service",
    description="Enterprise-grade AI conversation orchestration with SSE streaming",
    version=settings.SERVICE_VERSION,
    lifespan=lifespan,
    docs_url="/docs" if not settings.is_production else None,
    redoc_url="/redoc" if not settings.is_production else None
)


# ============================================================================
# Middleware
# ============================================================================

@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    """Add request ID and trace context."""
    request_id = request.headers.get("X-Request-ID", f"req_{int(time.time() * 1000)}")

    # Set trace context
    user_id = request.headers.get("X-User-ID")
    set_trace_context(trace_id=request_id, user_id=user_id)

    # Add to response headers
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id

    # Clear trace context
    clear_trace_context()

    return response


@app.middleware("http")
async def security_headers_middleware(request: Request, call_next):
    """Add security headers to all responses."""
    response = await call_next(request)

    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

    return response


@app.middleware("http")
async def logging_middleware(request: Request, call_next):
    """Log all requests and responses."""
    start_time = time.time()

    # Log request
    logger.info("Request received", extra={
        "method": request.method,
        "path": request.url.path,
        "client_ip": request.client.host,
        "user_agent": request.headers.get("user-agent")
    })

    # Process request
    response = await call_next(request)

    # Calculate duration
    duration_ms = int((time.time() - start_time) * 1000)

    # Log response
    logger.info("Request completed", extra={
        "method": request.method,
        "path": request.url.path,
        "status_code": response.status_code,
        "duration_ms": duration_ms
    })

    response.headers["X-Response-Time"] = f"{duration_ms}ms"

    return response


# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID", "X-Response-Time"]
)


# ============================================================================
# Exception Handlers
# ============================================================================

@app.exception_handler(BaseAppException)
async def app_exception_handler(request: Request, exc: BaseAppException):
    """Handle application exceptions."""
    logger.error("Application error", extra={
        "error_code": exc.error_code,
        "message": exc.message,
        "details": exc.details
    })

    return JSONResponse(
        status_code=exc.status_code,
        content=exc.to_dict()
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle unexpected exceptions."""
    logger.error("Unexpected error", extra={"error": str(exc)}, exc_info=True)

    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "An unexpected error occurred" if settings.is_production else str(exc)
            }
        }
    )


# ============================================================================
# Routes
# ============================================================================

# Include routers
app.include_router(conversation.router)


# Health check endpoints
@app.get("/health", response_model=HealthCheckResponse)
async def health_check():
    """
    Health check endpoint.

    Checks:
    - Database connection
    - Redis connection
    - Service uptime
    """
    checks = {}

    # Check database
    try:
        db_healthy = await check_database_connection()
        checks["database"] = "healthy" if db_healthy else "unhealthy"
    except Exception as e:
        logger.error("Database health check failed", extra={"error": str(e)})
        checks["database"] = "unhealthy"

    # Check Redis
    try:
        redis = get_redis_client()
        await redis.ping()
        checks["redis"] = "healthy"
    except Exception as e:
        logger.error("Redis health check failed", extra={"error": str(e)})
        checks["redis"] = "unhealthy"

    # Determine overall status
    all_healthy = all(status == "healthy" for status in checks.values())
    overall_status = HealthStatus.HEALTHY if all_healthy else HealthStatus.UNHEALTHY

    # Calculate uptime
    uptime_seconds = (datetime.utcnow() - _startup_time).total_seconds()

    return HealthCheckResponse(
        status=overall_status,
        service=settings.SERVICE_NAME,
        version=settings.SERVICE_VERSION,
        timestamp=datetime.utcnow(),
        checks=checks,
        uptime_seconds=uptime_seconds
    )


@app.get("/ready")
async def readiness_check():
    """
    Readiness check for Kubernetes.

    Returns 200 if service is ready to accept traffic.
    """
    try:
        # Check critical dependencies
        db_healthy = await check_database_connection()
        redis = get_redis_client()
        await redis.ping()

        if db_healthy:
            return {"status": "ready"}
        else:
            return Response(status_code=503, content="Service not ready")

    except Exception:
        return Response(status_code=503, content="Service not ready")


@app.get("/live")
async def liveness_check():
    """
    Liveness check for Kubernetes.

    Returns 200 if service is alive (even if not ready).
    """
    return {"status": "alive"}


@app.get("/")
async def root():
    """Root endpoint with service info."""
    return {
        "service": settings.SERVICE_NAME,
        "version": settings.SERVICE_VERSION,
        "environment": settings.ENVIRONMENT,
        "status": "running",
        "docs": "/docs" if not settings.is_production else None
    }


# ============================================================================
# Entry Point
# ============================================================================

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=not settings.is_production,
        log_level=settings.LOG_LEVEL.lower(),
        access_log=True
    )
