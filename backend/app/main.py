from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse

from app.api.v1 import ai, auth, classes, exams, knowledge, notifications, students, vector, ws
from app.api.v1 import health
from app.core.audit_middleware import AuditMiddleware
from app.core.config import settings
from app.core.event_consumer import start_consumer, stop_consumer
from app.core.exceptions import APIException
from app.core.logging import configure_logging, get_logger, TraceIDMiddleware
from app.core.metrics import metrics_endpoint, PrometheusMiddleware
from app.schemas.common import BaseResponse

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    configure_logging(log_level=getattr(settings, "LOG_LEVEL", "INFO"))
    logger.info(
        "application_startup",
        app_name=settings.APP_NAME,
        environment=settings.APP_ENV,
        debug=settings.DEBUG,
    )
    # Security fix A-003: start notification consumer to decouple Celery from WebSocket
    await start_consumer()
    yield
    # Shutdown
    stop_consumer()
    logger.info("application_shutdown", app_name=settings.APP_NAME)


app = FastAPI(
    title=settings.APP_NAME,
    description="AI-powered student progress tracking system",
    version="0.0.0",  # Security fix V-021: do not expose real version
    lifespan=lifespan,
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
)

# API 安全响应头中间件（最内层，最先处理响应）
@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    # Security fix V-018: Content-Security-Policy header
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: blob:; "
        "font-src 'self'; "
        "connect-src 'self'; "
        "frame-ancestors 'none'; "
        "base-uri 'self';"
    )
    # Only set HSTS on HTTPS responses to avoid warnings on HTTP
    forwarded_proto = request.headers.get("x-forwarded-proto", "")
    if forwarded_proto == "https" or request.url.scheme == "https":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


# Observability middleware (must be early)
app.add_middleware(TraceIDMiddleware)
app.add_middleware(PrometheusMiddleware)

# CORS — 生产环境限制域名
allow_origins = [o.strip() for o in settings.ALLOWED_ORIGINS.split(",") if o.strip()]
# Security: automatically filter out localhost origins in production
if settings.APP_ENV == "production":
    allow_origins = [
        o for o in allow_origins
        if not any(local in o for local in ("localhost", "127.0.0.1", "::1"))
    ]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
    allow_headers=["Content-Type", "Authorization", "X-Request-ID"],
    expose_headers=["X-Request-ID"],
)

# 审计日志中间件（注册在 CORS 之后，路由之前）
app.add_middleware(AuditMiddleware)

# Health checks (mounted at root for probe compatibility)
app.include_router(health.router, tags=["Health"])

# Metrics endpoint
@app.get("/metrics", include_in_schema=False)
async def prometheus_metrics():
    return metrics_endpoint()

# API Routes
app.include_router(auth.router, prefix="/api/v1/auth", tags=["Auth"])
app.include_router(exams.router, prefix="/api/v1/exams", tags=["Exams"])
app.include_router(students.router, prefix="/api/v1/students", tags=["Students"])
app.include_router(classes.router, prefix="/api/v1/classes", tags=["Classes"])
app.include_router(knowledge.router, prefix="/api/v1/knowledge", tags=["Knowledge"])
app.include_router(ai.router, prefix="/api/v1/ai", tags=["AI"])
app.include_router(vector.router, prefix="/api/v1", tags=["Vector Search"])
app.include_router(
    notifications.router, prefix="/api/v1/notifications", tags=["Notifications"]
)
app.include_router(ws.router, prefix="/api/v1")


# Global exception handlers
@app.exception_handler(APIException)
async def api_exception_handler(request: Request, exc: APIException):
    from fastapi.responses import JSONResponse
    return JSONResponse(
        status_code=exc.status_code,
        content={"code": exc.code, "message": exc.detail, "data": None},
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """统一 HTTPException 响应格式为 BaseResponse."""
    from fastapi.responses import JSONResponse
    return JSONResponse(
        status_code=exc.status_code,
        content={"code": exc.status_code, "message": exc.detail, "data": None},
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """捕获所有未处理异常，返回统一 BaseResponse 格式，不暴露栈跟踪."""
    from fastapi.responses import JSONResponse
    logger.exception("unhandled_exception", path=request.url.path, error=str(exc))
    return JSONResponse(
        status_code=500,
        content={"code": 500, "message": "Internal Server Error", "data": None},
    )


@app.get("/", response_class=PlainTextResponse, include_in_schema=False)
async def root():
    # Security fix V-021: do not expose version number
    return settings.APP_NAME
