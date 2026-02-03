"""
Главный файл запуска приложения - поддерживает режимы: bot, api, all
Использование:
    python main.py           # Запуск telegram bot + API (по умолчанию)
    python main.py bot       # Только telegram bot
    python main.py api       # Только API сервер
    python main.py all       # Telegram bot + API сервер
"""
import sys
import asyncio
import uvicorn

from src.core.init import init_services
from src.core.logger import logger
from src.core.config import config
from src.telegram_bot.handlers.user_interface import setup_handlers
from src.scheduler.task_scheduler import TaskScheduler
from src.scheduler.tasks import SchedulerTasks

from aiogram import Dispatcher

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


async def run_telegram_bot():
    """Запуск Telegram бота с планировщиком"""
    global telegram_bot, scheduler, dispatcher

    logger.info("=" * 80)
    logger.info("🚀 ЗАПУСК TELEGRAM BOT")
    logger.info("=" * 80)

    try:
        # Initialize services
        telegram_bot, task_queue, content_generator, generator_agent, safety_agent = await init_services()

        # Setup Dispatcher and handlers
        dispatcher = Dispatcher()

        # Initialize agents in handlers
        from src.telegram_bot.handlers.user_interface import set_agents
        set_agents(generator_agent, safety_agent, telegram_bot)

        # Initialize telegram_bot in admin handlers
        from src.telegram_bot.handlers.admin import set_telegram_bot
        set_telegram_bot(telegram_bot)

        setup_handlers(dispatcher)
        logger.info("✅ Handlers настроены")

        # Initialize scheduler
        scheduler = TaskScheduler()
        scheduler_tasks = SchedulerTasks(
            telegram_bot=telegram_bot,
            task_queue=task_queue
        )

        # Setup scheduled tasks
        logger.info("⏰ Настройка расписания публикаций...")

        for time_str in config.POSTING_TIMES:
            hour, minute = map(int, time_str.split(':'))
            scheduler.add_daily_job(
                scheduler_tasks.publish_scheduled_posts,
                hour=hour,
                minute=minute,
                job_id=f"publish_{time_str}"
            )
            logger.info(f"  📅 Публикация в {time_str} MSK")

        scheduler.add_interval_job(
            scheduler_tasks.retry_failed_tasks,
            minutes=60,
            job_id="retry_failed"
        )
        logger.info("  🔄 Повтор ошибок: каждый час")

        scheduler.add_interval_job(
            scheduler_tasks.health_check,
            minutes=30,
            job_id="health_check"
        )
        logger.info("  🏥 Health check: каждые 30 минут")

        scheduler.add_daily_job(
            lambda: scheduler_tasks.cleanup_old_tasks(days=30),
            hour=3,
            minute=0,
            job_id="cleanup"
        )
        logger.info("  🧹 Очистка старых задач: 03:00 MSK")

        scheduler.start()
        logger.info("✅ Планировщик запущен")

        logger.info("=" * 80)
        logger.info("🎉 TELEGRAM BOT ГОТОВ К РАБОТЕ!")
        logger.info("=" * 80)
        logger.info("📱 Откройте бота и используйте /start")
        logger.info(f"⏰ Автопубликация: {', '.join(config.POSTING_TIMES)} MSK")
        logger.info("💬 Ожидание сообщений...")
        logger.info("=" * 80)

        # Start polling
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


async def run_api_server():
    """Запуск API сервера"""
    global telegram_bot

    logger.info("=" * 80)
    logger.info("🚀 ЗАПУСК API SERVER")
    logger.info("=" * 80)

    try:
        # Initialize services
        telegram_bot, task_queue, content_generator, generator_agent, safety_agent = await init_services()

        # Initialize API dependencies
        from api.dependencies import init_dependencies
        init_dependencies(telegram_bot, task_queue, content_generator)

        logger.info("=" * 80)
        logger.info("🎉 API SERVER ГОТОВ К РАБОТЕ!")
        logger.info("=" * 80)
        logger.info("📡 API: http://0.0.0.0:8000")
        logger.info("📚 Docs: http://0.0.0.0:8000/api/docs")
        logger.info("=" * 80)

        # Import and run FastAPI app
        from api.main import app

        config_uvicorn = uvicorn.Config(
            app,
            host="0.0.0.0",
            port=8000,
            log_level="info"
        )
        server = uvicorn.Server(config_uvicorn)
        await server.serve()

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


async def run_all():
    """Запуск Telegram бота и API сервера одновременно"""
    global telegram_bot

    logger.info("=" * 80)
    logger.info("🚀 ЗАПУСК TELEGRAM BOT + API SERVER")
    logger.info("=" * 80)

    try:
        # Initialize services once for both
        telegram_bot, task_queue, content_generator, generator_agent, safety_agent = await init_services()

        # Initialize API dependencies
        from api.dependencies import init_dependencies
        init_dependencies(telegram_bot, task_queue, content_generator)

        # Setup bot handlers and scheduler
        dispatcher = Dispatcher()

        from src.telegram_bot.handlers.user_interface import set_agents
        set_agents(generator_agent, safety_agent, telegram_bot)

        from src.telegram_bot.handlers.admin import set_telegram_bot
        set_telegram_bot(telegram_bot)

        setup_handlers(dispatcher)

        scheduler = TaskScheduler()
        scheduler_tasks = SchedulerTasks(
            telegram_bot=telegram_bot,
            task_queue=task_queue
        )

        for time_str in config.POSTING_TIMES:
            hour, minute = map(int, time_str.split(':'))
            scheduler.add_daily_job(
                scheduler_tasks.publish_scheduled_posts,
                hour=hour,
                minute=minute,
                job_id=f"publish_{time_str}"
            )

        scheduler.add_interval_job(scheduler_tasks.retry_failed_tasks, minutes=60, job_id="retry_failed")
        scheduler.add_interval_job(scheduler_tasks.health_check, minutes=30, job_id="health_check")
        scheduler.add_daily_job(lambda: scheduler_tasks.cleanup_old_tasks(days=30), hour=3, minute=0, job_id="cleanup")

        scheduler.start()

        logger.info("=" * 80)
        logger.info("🎉 СИСТЕМА ПОЛНОСТЬЮ ГОТОВА К РАБОТЕ!")
        logger.info("=" * 80)
        logger.info("📱 Telegram Bot: активен")
        logger.info("📡 API Server: http://0.0.0.0:8000")
        logger.info("📚 API Docs: http://0.0.0.0:8000/api/docs")
        logger.info("=" * 80)

        # Run both bot and API concurrently
        from api.main import app

        config_uvicorn = uvicorn.Config(app, host="0.0.0.0", port=8000, log_level="info")
        server = uvicorn.Server(config_uvicorn)

        await asyncio.gather(
            dispatcher.start_polling(telegram_bot.bot),
            server.serve()
        )

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
    # Определяем режим запуска
    mode = sys.argv[1] if len(sys.argv) > 1 else "all"

    if mode not in ["bot", "api", "all"]:
        print(f"❌ Неизвестный режим: {mode}")
        print("Использование: python main.py [bot|api|all]")
        print("  bot  - только Telegram bot")
        print("  api  - только API сервер")
        print("  all  - Telegram bot + API (по умолчанию)")
        sys.exit(1)

    try:
        if mode == "bot":
            asyncio.run(run_telegram_bot())
        elif mode == "api":
            asyncio.run(run_api_server())
        else:  # "all"
            asyncio.run(run_all())
    except KeyboardInterrupt:
        logger.info("👋 Остановка по Ctrl+C")

