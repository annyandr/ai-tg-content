import uuid
import hashlib
import json
import asyncio
import logging
import os
from functools import wraps

logger = logging.getLogger(__name__)

def generate_id() -> str:
    """Генерирует уникальный ID."""
    return str(uuid.uuid4())

def hash_content(content: str) -> str:
    """Создает хеш контента для проверки дубликатов."""
    return hashlib.md5(content.encode('utf-8')).hexdigest()

def load_json_file(filepath: str):
    """Загружает данные из JSON файла."""
    if not os.path.exists(filepath):
        logger.error(f"File not found: {filepath}")
        return []
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading JSON {filepath}: {e}")
        return []

def retry_async(retries=3, delay=2):
    """Декоратор для повторных попыток выполнения асинхронной функции."""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(retries):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    logger.warning(f"Attempt {attempt + 1}/{retries} failed for {func.__name__}: {e}")
                    await asyncio.sleep(delay)
            logger.error(f"All {retries} attempts failed for {func.__name__}")
            raise last_exception
        return wrapper
    return decorator
