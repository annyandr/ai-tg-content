"""
Конфигурация приложения
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Явно указываем путь к .env
BASE_DIR = Path(__file__).resolve().parent.parent.parent
dotenv_path = BASE_DIR / '.env'

# Загружаем .env с явным путём
load_dotenv(dotenv_path=dotenv_path, override=True)

print(f"🔍 Загрузка .env из: {dotenv_path}")
print(f"🔍 Файл существует: {dotenv_path.exists()}")
print(f"🔍 BOT_TOKEN загружен: {bool(os.getenv('BOT_TOKEN'))}")


class Config:
    """Основная конфигурация"""
    
    # Telegram Bot
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    ADMIN_IDS = list(map(int, os.getenv("ADMIN_IDS", "").split(","))) if os.getenv("ADMIN_IDS") else []
    
    # OpenRouter API
    OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
    OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
    
    # AI Models
    DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "anthropic/claude-3.5-sonnet")
    TEMPERATURE = float(os.getenv("TEMPERATURE", "0.7"))
    MAX_TOKENS = int(os.getenv("MAX_TOKENS", "2000"))
    
    # Database
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./data/database/medical_smm.db")
    
    # Scheduling
    POSTING_TIMES = os.getenv("POSTING_TIMES", "09:00,20:00").split(",")
    TIMEZONE = os.getenv("TIMEZONE", "Europe/Moscow")
    
    # Auto-publishing
    AUTO_PUBLISH_ENABLED = os.getenv("AUTO_PUBLISH_ENABLED", "true").lower() == "true"
    AUTO_PUBLISH_TIME = os.getenv("AUTO_PUBLISH_TIME", "07:00")  # Время запуска планирования
    AUTO_PUBLISH_MIN_POSTS = int(os.getenv("AUTO_PUBLISH_MIN_POSTS", "1"))
    AUTO_PUBLISH_MAX_POSTS = int(os.getenv("AUTO_PUBLISH_MAX_POSTS", "3"))

    # Channels configuration
    CHANNELS_CONFIG_PATH = "./data/channels.json"
    
    # Validation
    def validate(self):
        """Проверка обязательных параметров"""
        if not self.BOT_TOKEN:
            raise ValueError("❌ BOT_TOKEN не задан в .env")
        if not self.OPENROUTER_API_KEY:
            raise ValueError("❌ OPENROUTER_API_KEY не задан в .env")
        if not self.ADMIN_IDS:
            print("⚠️ ADMIN_IDS не задан - доступ будет открыт для всех")


config = Config()

__all__ = ["config"]
