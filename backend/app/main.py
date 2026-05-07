from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.api.v1 import auth


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print(f"🚀 {settings.APP_NAME} starting up...")
    yield
    # Shutdown
    print(f"🛑 {settings.APP_NAME} shutting down...")


app = FastAPI(
    title=settings.APP_NAME,
    description="AI-powered student progress tracking system",
    version="0.0.1",
    lifespan=lifespan,
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API Routes
app.include_router(auth.router, prefix="/api/v1/auth", tags=["Auth"])


@app.get("/health")
async def health_check():
    return {"status": "ok", "version": "0.0.1"}


@app.get("/")
async def root():
    return {
        "name": settings.APP_NAME,
        "version": "0.0.1",
        "docs": "/docs",
    }
