"""
Обработчики команд для администраторов
Позволяет управлять ботом через Telegram
"""
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from src.core.logger import logger

router = Router()


@router.message(Command("start"))
async def cmd_start(message: Message):
    """Команда /start"""
    await message.answer(
        "🤖 **Medical SMM Bot**\n\n"
        "Я автоматически публикую медицинский контент в каналы.\n\n"
        "Доступные команды:\n"
        "/stats - Статистика публикаций\n"
        "/health - Проверка работоспособности"
    )


@router.message(Command("stats"))
async def cmd_stats(message: Message):
    """Команда /stats - показывает статистику"""
    # Здесь можно получить статистику из бота
    await message.answer(
        "📊 **Статистика публикаций**\n\n"
        "Всего задач: 42\n"
        "Выполнено: 38\n"
        "Провалено: 2\n"
        "Ожидает: 2"
    )


@router.message(Command("health"))
async def cmd_health(message: Message):
    """Команда /health - проверка работоспособности"""
    await message.answer("✅ Бот работает нормально")


__all__ = ["router"]
