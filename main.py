"""
Главный файл запуска приложения - MVP версия с scheduler
"""
import os
import ssl
import asyncio
import signal
import logging
from datetime import datetime

# Отключаем проверку SSL сертификатов глобально (для корпоративных сетей)
os.environ['PYTHONHTTPSVERIFY'] = '0'
# noinspection PyProtectedMember
ssl._create_default_https_context = ssl._create_unverified_context  # noqa

from src.core.config import config
from src.core.logger import logger
from src.core.exceptions import BotError, PublishError
from src.services.openrouter import OpenRouterService
from src.agents.generator_agent import ContentGeneratorAgent
from src.agents.reviewer_agent import ReviewerAgent
from src.agents.safety_agent import SafetyAgent
from src.telegram_bot.bot import MedicalTelegramBot
from src.telegram_bot.task_queue import TaskQueue
from src.telegram_bot.handlers.user_interface import setup_handlers
from src.scheduler.task_scheduler import TaskScheduler
from src.scheduler.tasks import SchedulerTasks

from aiogram import Dispatcher
from aiogram.enums import ParseMode

# Настройка базового логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# Глобальные переменные для graceful shutdown
telegram_bot = None
scheduler = None
dispatcher = None



async def shutdown(signal_type=None):
    """Graceful shutdown"""
    logger.info("🛑 Получен сигнал остановки...")
    
    if telegram_bot:
        await telegram_bot.stop()
    
    if scheduler:
        scheduler.stop()
    
    logger.info("👋 Бот остановлен")


async def main():
    """Запуск бота для MVP демонстрации"""
    global telegram_bot, scheduler, dispatcher
    
    logger.info("=" * 80)
    logger.info("🚀 ЗАПУСК MEDICAL SMM BOT (MVP)")
    logger.info("=" * 80)
    
    try:
        # 1. Валидация конфига
        config.validate()
        logger.info("✅ Конфигурация проверена")
        
        # 2. Инициализация OpenRouter
        openrouter = OpenRouterService(
            api_key=config.OPENROUTER_API_KEY,
            base_url=config.OPENROUTER_BASE_URL
        )
        logger.info("✅ OpenRouter инициализирован")
        
        # 3. Инициализация AI-агентов
        generator_agent = ContentGeneratorAgent(openrouter=openrouter)
        reviewer_agent = ReviewerAgent(openrouter=openrouter)
        safety_agent = SafetyAgent(openrouter=openrouter)
        logger.info("✅ AI-агенты инициализированы")
        
        # 4. Инициализация очереди задач
        task_queue = TaskQueue()
        logger.info("✅ Очередь задач инициализирована")
        
        # 5. Инициализация Telegram Bot
        telegram_bot = MedicalTelegramBot(
            bot_token=config.BOT_TOKEN,
            task_queue=task_queue
        )
        await telegram_bot.start()
        
        # 6. Настройка Dispatcher и handlers
        dispatcher = Dispatcher()

        # Инициализируем агенты в handlers (для user_interface.py)
        from src.telegram_bot.handlers.user_interface import set_agents
        set_agents(generator_agent, safety_agent, telegram_bot)

        setup_handlers(dispatcher)
        logger.info("✅ Handlers настроены")
        
        # 7. Инициализация планировщика
        scheduler = TaskScheduler()
        scheduler_tasks = SchedulerTasks(
            telegram_bot=telegram_bot,
            task_queue=task_queue
        )
        
        # Добавляем задачи в планировщик
        logger.info("⏰ Настройка расписания публикаций...")
        
        # Публикация в установленное время (09:00 и 20:00)
        for time_str in config.POSTING_TIMES:
            hour, minute = map(int, time_str.split(':'))
            scheduler.add_daily_job(
                scheduler_tasks.publish_scheduled_posts,
                hour=hour,
                minute=minute,
                job_id=f"publish_{time_str}"
            )
            logger.info(f"  📅 Публикация в {time_str} MSK")
        
        # Повтор провалившихся задач каждый час
        scheduler.add_interval_job(
            scheduler_tasks.retry_failed_tasks,
            minutes=60,
            job_id="retry_failed"
        )
        logger.info("  🔄 Повтор ошибок: каждый час")
        
        # Health check каждые 30 минут
        scheduler.add_interval_job(
            scheduler_tasks.health_check,
            minutes=30,
            job_id="health_check"
        )
        logger.info("  🏥 Health check: каждые 30 минут")
        
        # Очистка старых задач раз в день в 03:00
        scheduler.add_daily_job(
            lambda: scheduler_tasks.cleanup_old_tasks(days=30),
            hour=3,
            minute=0,
            job_id="cleanup"
        )
        logger.info("  🧹 Очистка старых задач: 03:00 MSK")
        
        # Запускаем планировщик
        scheduler.start()
        logger.info("✅ Планировщик запущен")
        
        # 8. Выводим итоговую информацию
        logger.info("=" * 80)
        logger.info("🎉 БОТ ПОЛНОСТЬЮ ГОТОВ К РАБОТЕ!")
        logger.info("=" * 80)
        logger.info("📱 Откройте бота и используйте /start")
        logger.info(f"⏰ Автопубликация: {', '.join(config.POSTING_TIMES)} MSK")
        logger.info(f"🌍 Часовой пояс: {config.TIMEZONE}")
        logger.info("💬 Ожидание сообщений...")
        logger.info("=" * 80)
        
        # 9. Запускаем polling
        await dispatcher.start_polling(telegram_bot.bot)
    
    except ValueError as e:
        logger.error(f"❌ Ошибка конфигурации: {e}")
        return
    
    except KeyboardInterrupt:
        logger.info("⚠️ Получен сигнал прерывания (Ctrl+C)")
    
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}", exc_info=True)
        raise
    
    finally:
        await shutdown()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("👋 Остановка по Ctrl+C")
