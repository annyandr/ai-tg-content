"""
Главный файл запуска приложения - MVP версия с scheduler
"""

import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from src.telegram_bot.handlers import user_interface
from src.telegram_bot.bot import MedicalTelegramBot
from src.telegram_bot.task_queue import TaskQueue
from src.agents.generator_agent import ContentGeneratorAgent
from src.agents.safety_agent import SafetyAgent
from src.services.openrouter import OpenRouterService
from src.scheduler.scheduler import scheduler
from src.scheduler.tasks import SchedulerTasks
from src.core.config import config
from src.core.logger import logger

logging.basicConfig(level=logging.INFO)


async def main():
    """Запуск бота для MVP демонстрации"""
    
    logger.info("=" * 80)
    logger.info("🚀 ЗАПУСК MEDICAL SMM BOT (MVP)")
    logger.info("=" * 80)
    
    # Валидация конфига
    try:
        config.validate()
        logger.info("✅ Конфигурация проверена")
    except ValueError as e:
        logger.error(str(e))
        return
    
    # 1. Инициализация OpenRouter
    openrouter = OpenRouterService(
        api_key=config.OPENROUTER_API_KEY,
        base_url=config.OPENROUTER_BASE_URL
    )
    logger.info("✅ OpenRouter инициализирован")
    
    # 2. Инициализация AI-агентов
    generator_agent = ContentGeneratorAgent(openrouter=openrouter)
    safety_agent = SafetyAgent(openrouter=openrouter)
    logger.info("✅ AI-агенты инициализированы")
    
    # 3. Инициализация очереди задач
    task_queue = TaskQueue()
    logger.info("✅ Очередь задач инициализирована")
    
    # 4. Инициализация Telegram Bot
    telegram_bot = MedicalTelegramBot(bot_token=config.BOT_TOKEN)
    await telegram_bot.start()
    logger.info("✅ Telegram Bot запущен")
    
    # 5. Передаём агентов в handlers
    user_interface.set_agents(generator_agent, safety_agent, telegram_bot)
    logger.info("✅ Агенты подключены к UI")
    
    # 6. Настройка планировщика
    scheduler_tasks = SchedulerTasks(telegram_bot=telegram_bot, task_queue=task_queue)
    
    # Добавляем ежедневные задачи публикации (09:00 и 20:00 MSK)
    scheduler.add_daily_jobs(
        callback=scheduler_tasks.publish_scheduled_posts,
        times=config.POSTING_TIMES
    )
    
    # Добавляем повторные попытки для провалившихся задач (каждые 30 минут)
    scheduler.add_interval_job(
        callback=scheduler_tasks.retry_failed_tasks,
        minutes=30,
        job_id="retry_failed"
    )
    
    # Добавляем health check (каждый час)
    scheduler.add_interval_job(
        callback=scheduler_tasks.health_check,
        minutes=60,
        job_id="health_check"
    )
    
    # Добавляем очистку старых задач (каждую ночь в 03:00)
    from apscheduler.triggers.cron import CronTrigger
    scheduler.scheduler.add_job(
        scheduler_tasks.cleanup_old_tasks,
        trigger=CronTrigger(hour=3, minute=0, timezone=config.TIMEZONE),
        id="cleanup_old_tasks",
        name="Очистка старых задач"
    )
    
    # Запускаем планировщик
    scheduler.start()
    logger.info("✅ Планировщик запущен")
    
    # Выводим список задач
    scheduler.print_jobs()
    
    # 7. Создаём Bot и Dispatcher
    bot = Bot(
        token=config.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    
    dp = Dispatcher()
    dp.include_router(user_interface.router)
    
    logger.info("=" * 80)
    logger.info("🎉 БОТ ПОЛНОСТЬЮ ГОТОВ К РАБОТЕ!")
    logger.info("=" * 80)
    logger.info("📱 Откройте бота и используйте /start")
    logger.info(f"⏰ Автопубликация настроена на: {', '.join(config.POSTING_TIMES)} MSK")
    logger.info("=" * 80)
    
    # 8. Запускаем polling
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    except KeyboardInterrupt:
        logger.info("🛑 Остановка бота...")
    finally:
        scheduler.stop()
        await bot.session.close()
        logger.info("👋 Бот остановлен")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("❌ Бот остановлен пользователем")
