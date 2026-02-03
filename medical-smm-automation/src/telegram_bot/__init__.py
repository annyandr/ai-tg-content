"""
Telegram Bot module
Модуль для публикации постов в Telegram каналы
"""
from src.telegram_bot.bot import MedicalTelegramBot
from src.telegram_bot.models import PublishTask, TaskStatus
from src.telegram_bot.task_queue import TaskQueue

__all__ = [
    "MedicalTelegramBot",
    "PublishTask",
    "TaskStatus",
    "TaskQueue"
]
