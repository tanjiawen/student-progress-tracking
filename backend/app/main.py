from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse

from app.api.v1 import ai, auth, classes, exams, knowledge, notifications, students, vector, ws
from app.api.v1 import health
from app.core.audit_middleware import AuditMiddleware
from app.core.config import settings
from app.core.exceptions import APIException
from app.core.logging import configure_logging, get_logger, TraceIDMiddleware
from app.core.metrics import metrics_endpoint, PrometheusMiddleware

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
    yield
    # Shutdown
    logger.info("application_shutdown", app_name=settings.APP_NAME)


app = FastAPI(
    title=settings.APP_NAME,
    description="AI-powered student progress tracking system",
    version="0.0.1",
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
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response


# Observability middleware (must be early)
app.add_middleware(TraceIDMiddleware)
app.add_middleware(PrometheusMiddleware)

# CORS — 生产环境限制域名
allow_origins = [o.strip() for o in settings.ALLOWED_ORIGINS.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
    allow_headers=["*"],
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


@app.get("/", response_class=PlainTextResponse)
async def root():
    return f"{settings.APP_NAME} v0.0.1"
