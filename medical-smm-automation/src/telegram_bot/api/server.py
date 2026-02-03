"""
FastAPI сервер для управления telegram-ботом
"""
import asyncio
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from src.telegram_bot.bot import MedicalTelegramBot
from src.telegram_bot.api.routes import create_api_router
from src.core.config import settings
from src.core.logger import logger


# Глобальный экземпляр бота
_bot_instance: Optional[MedicalTelegramBot] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle manager для FastAPI"""
    global _bot_instance
    
    # Startup
    logger.info("🚀 Запуск FastAPI сервера и Telegram бота...")
    
    _bot_instance = MedicalTelegramBot(settings.telegram_bot_token)
    await _bot_instance.start()
    
    logger.info("✅ Сервер и бот готовы к работе")
    
    yield
    
    # Shutdown
    logger.info("⏹️ Остановка сервера и бота...")
    if _bot_instance:
        await _bot_instance.stop()
    logger.info("✅ Сервер остановлен")


def create_app() -> FastAPI:
    """Создаёт и настраивает FastAPI приложение"""
    app = FastAPI(
        title="Medical SMM Telegram Bot API",
        description="API для управления публикациями в медицинских Telegram-каналах",
        version="1.0.0",
        lifespan=lifespan
    )
    
    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    @app.on_event("startup")
    async def startup():
        """Подключаем роуты после создания бота"""
        global _bot_instance
        if _bot_instance:
            router = create_api_router(_bot_instance)
            app.include_router(router)
    
    @app.get("/")
    async def root():
        """Корневой эндпоинт"""
        return {
            "service": "Medical SMM Telegram Bot",
            "version": "1.0.0",
            "status": "running",
            "docs": "/docs"
        }
    
    return app


def get_bot_instance() -> Optional[MedicalTelegramBot]:
    """Возвращает глобальный экземпляр бота"""
    return _bot_instance


async def run_server(host: str = "0.0.0.0", port: int = 5000, reload: bool = False):
    """Запускает FastAPI сервер"""
    config = uvicorn.Config(
        app="src.telegram_bot.api.server:create_app",
        factory=True,
        host=host,
        port=port,
        reload=reload,
        log_level="info"
    )
    
    server = uvicorn.Server(config)
    await server.serve()


__all__ = ["create_app", "run_server", "get_bot_instance"]
