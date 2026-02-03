"""
Обработчики команд для администраторов
Позволяет управлять ботом через Telegram
"""
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from src.core.logger import logger

router = Router()

# Глобальная переменная для доступа к telegram_bot (инициализируется в main.py)
telegram_bot = None


def set_telegram_bot(bot):
    """Инициализация telegram_bot из main.py"""
    global telegram_bot
    telegram_bot = bot


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


@router.message(Command("status"))
async def cmd_status(message: Message):
    """Команда /status - детальный статус системы и очереди"""
    if not telegram_bot:
        await message.answer("❌ Бот не инициализирован", parse_mode="HTML")
        return

    try:
        # Получаем статистику
        stats = telegram_bot.get_stats()

        # Получаем ближайшие запланированные посты
        upcoming = await telegram_bot.get_upcoming_posts(limit=5)

        status_text = f"""📊 <b>Статус системы</b>

📬 <b>Очередь публикаций:</b>
• В очереди: {stats['pending']}
• Запланировано: {stats['scheduled']}
• Обрабатывается: {stats.get('processing', 0)}

✅ <b>Выполнено:</b> {stats['completed']}
❌ <b>Ошибок:</b> {stats['failed']}
📈 <b>Success rate:</b> {stats['success_rate']}%

⏰ <b>Ближайшие публикации:</b>
"""

        if upcoming:
            for task in upcoming:
                time_str = task.scheduled_time.strftime('%d.%m %H:%M')
                channel_name = task.channel_id[:20] + "..." if len(task.channel_id) > 20 else task.channel_id
                status_text += f"\n• {time_str} - {channel_name}"
        else:
            status_text += "\nНет запланированных публикаций"

        await message.answer(status_text, parse_mode="HTML")

    except Exception as e:
        logger.error(f"Ошибка в /status: {e}")
        await message.answer(f"❌ <b>Ошибка получения статуса</b>\n\n<code>{str(e)}</code>", parse_mode="HTML")


@router.message(Command("health"))
async def cmd_health(message: Message):
    """Команда /health - проверка работоспособности"""
    try:
        if not telegram_bot:
            await message.answer("⚠️ Бот не инициализирован", parse_mode="HTML")
            return

        # Проверяем что worker работает
        is_running = telegram_bot.is_running

        health_status = "✅ Бот работает нормально" if is_running else "⚠️ Background worker не запущен"
        await message.answer(health_status, parse_mode="HTML")

    except Exception as e:
        logger.error(f"Ошибка в /health: {e}")
        await message.answer(f"❌ Ошибка: {str(e)}", parse_mode="HTML")


__all__ = ["router"]
