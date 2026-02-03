"""
🚀 Medical SMM Bot - MVP для конференции
Точка входа приложения с интерактивным UI
"""

import asyncio
import sys
from pathlib import Path

# Добавляем корень проекта в PYTHONPATH
sys.path.insert(0, str(Path(__file__).parent))

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from src.telegram_bot.bot import MedicalTelegramBot
from src.telegram_bot.api.server import create_api_server
from src.telegram_bot.handlers import admin, user_interface  # 🆕 Новый UI
from src.services.content_generator import ContentGeneratorService
from src.services.openrouter import OpenRouterService
from src.core.config import settings
from src.core.logger import logger


async def main():
    """Главная функция запуска"""
    logger.info("="*60)
    logger.info("🚀 Запуск Medical SMM Bot (MVP)")
    logger.info("="*60)

    try:
        # ====================================================================
        # 1. ИНИЦИАЛИЗАЦИЯ СЕРВИСОВ
        # ====================================================================

        logger.info("📦 Инициализация сервисов...")

        # OpenRouter для генерации
        openrouter = OpenRouterService(
            api_key=settings.openrouter_api_key,
            model=settings.openrouter_model
        )
        logger.info("✅ OpenRouter сервис готов")

        # Генератор контента
        content_generator = ContentGeneratorService(openrouter=openrouter)
        logger.info("✅ Content Generator готов")

        # Telegram Bot (планировщик публикаций)
        telegram_bot = MedicalTelegramBot(bot_token=settings.telegram_bot_token)
        await telegram_bot.start()
        logger.info("✅ Telegram Bot (планировщик) запущен")

        # ====================================================================
        # 2. НАСТРОЙКА AIOGRAM БОТА (UI)
        # ====================================================================

        logger.info("🤖 Настройка UI бота...")

        # Инициализация aiogram бота
        bot = Bot(token=settings.telegram_bot_token)
        storage = MemoryStorage()
        dp = Dispatcher(storage=storage)

        # Регистрация роутеров
        dp.include_router(admin.router)  # Команды /stats, /health
        dp.include_router(user_interface.router)  # 🆕 Новый UI

        # Инициализация сервисов в UI
        user_interface.init_services(
            generator=content_generator,
            bot=telegram_bot
        )

        logger.info("✅ UI роутеры зарегистрированы")

        # ====================================================================
        # 3. ЗАПУСК API СЕРВЕРА (опционально)
        # ====================================================================

        if settings.enable_api:
            logger.info("🌐 Запуск API сервера...")
            api_server = create_api_server(telegram_bot)
            api_task = asyncio.create_task(
                api_server.start(
                    host=settings.api_host,
                    port=settings.api_port
                )
            )
            logger.info(f"✅ API запущен: http://{settings.api_host}:{settings.api_port}")

        # ====================================================================
        # 4. ЗАПУСК БОТА
        # ====================================================================

        logger.info("="*60)
        logger.info("✅ ВСЕ СЕРВИСЫ ЗАПУЩЕНЫ!")
        logger.info("="*60)
        logger.info(f"🤖 Бот: @{(await bot.get_me()).username}")
        logger.info("📱 UI: Интерактивные меню с кнопками")
        logger.info("⏰ Планировщик: Активен")
        logger.info("🎨 Специализации: 5 (Гинекология, Педиатрия, Эндокринология, Терапия, Дерматология)")
        logger.info("="*60)

        # Запуск polling
        logger.info("🔄 Запуск polling...")
        await dp.start_polling(bot, skip_updates=True)

    except KeyboardInterrupt:
        logger.info("\n🛑 Получен сигнал остановки...")
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}", exc_info=True)
        raise
    finally:
        logger.info("🧹 Остановка сервисов...")
        if telegram_bot:
            await telegram_bot.stop()
        if 'bot' in locals():
            await bot.session.close()
        logger.info("👋 Бот остановлен")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("\n👋 Бот остановлен пользователем")
    except Exception as e:
        logger.error(f"❌ Ошибка запуска: {e}", exc_info=True)
        sys.exit(1)
