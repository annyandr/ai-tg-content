"""FastAPI application entry point"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from api.routers import tasks, content, channels, system
from src.core.logger import logger


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup/shutdown events"""
    logger.info("🚀 Starting Medical SMM Bot API...")
    logger.info("✅ API ready")
    yield
    logger.info("🛑 Shutting down API...")


# Create FastAPI app
app = FastAPI(
    title="Medical SMM Bot API",
    description="REST API for Medical SMM Automation Bot",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5000",
        "http://127.0.0.1:5000"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(tasks.router)
app.include_router(content.router)
app.include_router(channels.router)
app.include_router(system.router)


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Medical SMM Bot API",
        "version": "1.0.0",
        "docs": "/api/docs"
    }
