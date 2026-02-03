"""
Middleware для аутентификации и безопасности
"""
from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, User

from src.core.config import settings
from src.core.logger import logger


class AuthMiddleware(BaseMiddleware):
    """
    Middleware для проверки прав доступа
    Разрешает взаимодействие только администраторам
    """
    
    def __init__(self, admin_ids: list[int]):
        """
        Args:
            admin_ids: Список ID администраторов Telegram
        """
        self.admin_ids = admin_ids
        super().__init__()
        logger.info(f"AuthMiddleware инициализирован. Админы: {admin_ids}")
    
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        """Проверяет права доступа перед обработкой"""
        user: User = data.get("event_from_user")
        
        if user and user.id not in self.admin_ids:
            logger.warning(
                f"⚠️ Неавторизованный доступ: "
                f"user_id={user.id}, username={user.username}"
            )
            return  # Игнорируем запросы от неавторизованных
        
        # Пользователь авторизован, продолжаем обработку
        return await handler(event, data)


class RateLimitMiddleware(BaseMiddleware):
    """
    Middleware для ограничения частоты запросов
    Защита от спама
    """
    
    def __init__(self, rate_limit: int = 5):
        """
        Args:
            rate_limit: Максимум запросов в минуту
        """
        self.rate_limit = rate_limit
        self.user_requests: Dict[int, list] = {}
        super().__init__()
    
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        """Проверяет лимит запросов"""
        from datetime import datetime, timedelta
        
        user: User = data.get("event_from_user")
        if not user:
            return await handler(event, data)
        
        user_id = user.id
        now = datetime.utcnow()
        
        # Инициализируем список запросов пользователя
        if user_id not in self.user_requests:
            self.user_requests[user_id] = []
        
        # Удаляем старые запросы (старше 1 минуты)
        self.user_requests[user_id] = [
            req_time for req_time in self.user_requests[user_id]
            if now - req_time < timedelta(minutes=1)
        ]
        
        # Проверяем лимит
        if len(self.user_requests[user_id]) >= self.rate_limit:
            logger.warning(f"Rate limit exceeded for user {user_id}")
            return  # Игнорируем
        
        # Добавляем текущий запрос
        self.user_requests[user_id].append(now)
        
        return await handler(event, data)


__all__ = ["AuthMiddleware", "RateLimitMiddleware"]
