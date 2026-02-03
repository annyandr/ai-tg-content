"""Dependency injection setup for FastAPI"""
from typing import Optional
from src.telegram_bot.bot import MedicalTelegramBot
from src.telegram_bot.task_queue import TaskQueue
from src.services.content_generator import ContentGeneratorService

# Global instances (initialized at startup)
_telegram_bot: Optional[MedicalTelegramBot] = None
_task_queue: Optional[TaskQueue] = None
_content_generator: Optional[ContentGeneratorService] = None


def init_dependencies(
    telegram_bot: MedicalTelegramBot,
    task_queue: TaskQueue,
    content_generator: ContentGeneratorService
):
    """Initialize global dependencies (called from api/main.py)"""
    global _telegram_bot, _task_queue, _content_generator
    _telegram_bot = telegram_bot
    _task_queue = task_queue
    _content_generator = content_generator


def get_telegram_bot() -> MedicalTelegramBot:
    """Get telegram bot instance"""
    if _telegram_bot is None:
        raise RuntimeError("Telegram bot not initialized")
    return _telegram_bot


def get_task_queue() -> TaskQueue:
    """Get task queue instance"""
    if _task_queue is None:
        raise RuntimeError("Task queue not initialized")
    return _task_queue


def get_content_generator() -> ContentGeneratorService:
    """Get content generator instance"""
    if _content_generator is None:
        raise RuntimeError("Content generator not initialized")
    return _content_generator
