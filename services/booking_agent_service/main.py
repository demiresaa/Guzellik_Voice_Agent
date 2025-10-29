# services/booking_agent_service/main.py

"""
Main FastAPI Application - Booking Agent Service
Staff Engineer principle: Production-ready, observable, secure.

Features:
- All 9 tools exposed as REST API
- Security middleware (auth, rate limiting, validation)
- CORS support
- Health checks
- API documentation (Swagger/ReDoc)
- Structured logging
- Error handling
"""

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import time

from .config import settings
from .api.routes import customer, booking, marketing, notification
from .security import rate_limit_middleware, validation_middleware
from .utils.logger import get_logger
from .utils.exceptions import BookingAgentException, exception_to_http
from .repositories.base import db

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan events.

    Startup:
    - Initialize database
    - Log startup info

    Shutdown:
    - Cleanup resources
    - Log shutdown info
    """
    # Startup
    logger.info(
        "Starting Booking Agent Service",
        version=settings.APP_VERSION,
        debug=settings.DEBUG
    )

    # Database is already initialized via singleton
    logger.info(f"Database initialized with {len(db.get_services())} services")

    yield

    # Shutdown
    logger.info("Shutting down Booking Agent Service")


# Create FastAPI app
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="""
    ## Güzellik Salonu Booking Agent Service

    **Enterprise-Grade Agentic AI Tool API**

    ### Features:
    - 🔐 Secure API key authentication
    - 🚦 Rate limiting & DDoS protection
    - ✅ Input validation & sanitization
    - 📊 Structured logging & audit trail
    - 🎯 9 specialized tools for salon management

    ### Tool Categories:
    1. **Customer Management** (Tool #1-2)
       - Customer lookup & identification
       - Customer creation & updates

    2. **Booking Management** (Tool #3-5)
       - Availability checking (complex algorithm)
       - Appointment creation (conflict detection)
       - Appointment cancellation (business rules)

    3. **Marketing & Sales** (Tool #6-7)
       - Service suggestions (upselling)
       - Personalized campaigns (revenue optimization)

    4. **Notifications & Payment** (Tool #8-9)
       - SMS sending (template-based)
       - Payment link generation (secure)

    ### Security:
    - All endpoints require `X-API-Key` header
    - Rate limiting: 60 req/min per IP
    - SMS rate limiting: 10/hour per phone
    - GDPR/KVKK compliant

    ### For Conversation Agent:
    Use these endpoints to power your LLM with specialized tools.
    Each response includes natural language summaries optimized for LLM consumption.
    """,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
    debug=settings.DEBUG
)

# CORS middleware (configure for production)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Security middlewares
app.middleware("http")(rate_limit_middleware)
app.middleware("http")(validation_middleware)


# Global exception handler
@app.exception_handler(BookingAgentException)
async def booking_agent_exception_handler(request: Request, exc: BookingAgentException):
    """Handle custom booking agent exceptions"""
    logger.error(
        "BookingAgentException caught",
        exception=exc.__class__.__name__,
        message=exc.message,
        path=request.url.path
    )
    http_exc = exception_to_http(exc)
    return JSONResponse(
        status_code=http_exc.status_code,
        content=http_exc.detail
    )


# Request timing middleware
@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    """Add response time header for monitoring"""
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(process_time)

    # Log slow requests
    if process_time > 1.0:  # > 1 second
        logger.warning(
            "Slow request detected",
            path=request.url.path,
            method=request.method,
            process_time=f"{process_time:.2f}s"
        )

    return response


# Include routers
app.include_router(customer.router)
app.include_router(booking.router)
app.include_router(marketing.router)
app.include_router(notification.router)


# Health check endpoints
@app.get(
    "/health",
    tags=["Health"],
    summary="Health Check",
    description="Simple health check endpoint"
)
async def health_check():
    """Basic health check"""
    return {
        "status": "healthy",
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION
    }


@app.get(
    "/health/detailed",
    tags=["Health"],
    summary="Detailed Health Check",
    description="Detailed health check with component status"
)
async def detailed_health_check():
    """Detailed health check with all components"""
    from .security.rate_limiter import rate_limiter

    return {
        "status": "healthy",
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "components": {
            "database": {
                "status": "healthy",
                "type": settings.DATABASE_TYPE,
                "customers": len(db.get_customers()),
                "appointments": len(db.get_appointments()),
                "services": len(db.get_services())
            },
            "rate_limiter": {
                "status": "healthy",
                "enabled": settings.RATE_LIMIT_ENABLED,
                "stats": rate_limiter.get_stats()
            },
            "external_services": {
                "sms_provider": {
                    "configured": bool(settings.SMS_PROVIDER_URL),
                    "status": "simulated"  # Would check actual provider
                },
                "payment_provider": {
                    "configured": bool(settings.PAYMENT_PROVIDER_URL),
                    "status": "simulated"  # Would check actual provider
                }
            }
        },
        "configuration": {
            "log_level": settings.LOG_LEVEL,
            "debug": settings.DEBUG,
            "rate_limit_per_minute": settings.RATE_LIMIT_PER_MINUTE
        }
    }


# Root endpoint
@app.get(
    "/",
    tags=["Root"],
    summary="API Root",
    description="API information and available endpoints"
)
async def root():
    """API root with information"""
    return {
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "description": "Enterprise Booking Agent Service for Agentic AI",
        "documentation": {
            "swagger": "/docs",
            "redoc": "/redoc"
        },
        "endpoints": {
            "customer": "/api/customer/*",
            "booking": "/api/booking/*",
            "marketing": "/api/marketing/*",
            "notification": "/api/notification/*"
        },
        "health": {
            "basic": "/health",
            "detailed": "/health/detailed"
        },
        "tools": [
            {"id": 1, "name": "getCustomerInfoByPhone", "endpoint": "/api/customer/get-by-phone"},
            {"id": 2, "name": "createOrUpdateCustomer", "endpoint": "/api/customer/create-or-update"},
            {"id": 3, "name": "checkAvailability", "endpoint": "/api/booking/check-availability"},
            {"id": 4, "name": "createAppointment", "endpoint": "/api/booking/create"},
            {"id": 5, "name": "cancelAppointment", "endpoint": "/api/booking/cancel"},
            {"id": 6, "name": "getComplementaryServiceSuggestions", "endpoint": "/api/marketing/suggestions"},
            {"id": 7, "name": "getActiveCampaignsForCustomer", "endpoint": "/api/marketing/campaigns"},
            {"id": 8, "name": "sendSmsNotification", "endpoint": "/api/notification/send-sms"},
            {"id": 9, "name": "requestPrepayment", "endpoint": "/api/notification/prepayment"}
        ]
    }


# Run with uvicorn
if __name__ == "__main__":
    import uvicorn

    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}")

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8001,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower()
    )
