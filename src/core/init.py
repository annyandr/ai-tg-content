"""Shared initialization logic for both bot and API"""
import ssl
import os
from typing import Tuple

# Отключаем проверку SSL сертификатов глобально (для корпоративных сетей)
os.environ['PYTHONHTTPSVERIFY'] = '0'
# noinspection PyProtectedMember
ssl._create_default_https_context = ssl._create_unverified_context  # noqa

from src.core.config import config
from src.core.logger import logger
from src.services.openrouter import OpenRouterService
from src.services.content_generator import ContentGeneratorService
from src.agents.generator_agent import ContentGeneratorAgent
from src.agents.reviewer_agent import ReviewerAgent
from src.agents.safety_agent import SafetyAgent
from src.telegram_bot.bot import MedicalTelegramBot
from src.telegram_bot.task_queue import TaskQueue


async def init_services() -> Tuple[
    MedicalTelegramBot,
    TaskQueue,
    ContentGeneratorService,
    ContentGeneratorAgent,
    SafetyAgent
]:
    """
    Initialize all core services

    Returns:
        Tuple of (telegram_bot, task_queue, content_generator, generator_agent, safety_agent)
    """
    logger.info("🔧 Инициализация сервисов...")

    # Validate config
    config.validate()
    logger.info("✅ Конфигурация проверена")

    # Initialize OpenRouter
    openrouter = OpenRouterService(
        api_key=config.OPENROUTER_API_KEY,
        base_url=config.OPENROUTER_BASE_URL
    )
    logger.info("✅ OpenRouter инициализирован")

    # Initialize AI agents
    generator_agent = ContentGeneratorAgent(openrouter=openrouter)
    reviewer_agent = ReviewerAgent(openrouter=openrouter)
    safety_agent = SafetyAgent(openrouter=openrouter)
    logger.info("✅ AI-агенты инициализированы")

    # Initialize content generator service
    content_generator = ContentGeneratorService(
        openrouter=openrouter,
        generator_agent=generator_agent,
        reviewer_agent=reviewer_agent
    )
    logger.info("✅ Content generator service инициализирован")

    # Initialize task queue
    task_queue = TaskQueue()
    logger.info("✅ Очередь задач инициализирована")

    # Initialize Telegram Bot
    telegram_bot = MedicalTelegramBot(
        bot_token=config.BOT_TOKEN,
        task_queue=task_queue
    )
    await telegram_bot.start()
    logger.info("✅ Telegram bot инициализирован")

    return telegram_bot, task_queue, content_generator, generator_agent, safety_agent
