"""
Конфигурация приложения
"""

import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Основная конфигурация"""
    
    # Telegram Bot
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    ADMIN_IDS = list(map(int, os.getenv("ADMIN_IDS", "").split(","))) if os.getenv("ADMIN_IDS") else []
    
    # OpenRouter API
    OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
    OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
    
    # AI Models
    DEFAULT_MODEL = "anthropic/claude-3.5-sonnet"
    TEMPERATURE = 0.7
    MAX_TOKENS = 2000
    
    # Database
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./data/database/medical_smm.db")
    
    # Scheduling
    POSTING_TIMES = ["09:00", "20:00"]  # MSK
    TIMEZONE = "Europe/Moscow"
    
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
