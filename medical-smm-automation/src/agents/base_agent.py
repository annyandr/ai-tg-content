"""
Базовый класс для AI-агентов
"""

from typing import Dict, Any
from abc import ABC, abstractmethod

from src.services.openrouter import OpenRouterService


class BaseAgent(ABC):
    """
    Базовый класс для всех AI-агентов
    """
    
    def __init__(self, openrouter: OpenRouterService):
        """
        Args:
            openrouter: Сервис OpenRouter для AI-генерации
        """
        self.openrouter = openrouter
    
    @abstractmethod
    def get_system_prompt(self) -> str:
        """
        Возвращает системный промпт для агента
        
        Returns:
            Системный промпт
        """
        pass
    
    async def generate(
        self,
        user_prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 2000
    ) -> Dict[str, Any]:
        """
        Генерирует ответ через OpenRouter
        
        Args:
            user_prompt: Пользовательский промпт
            temperature: Температура генерации
            max_tokens: Максимум токенов
        
        Returns:
            Результат генерации
        """
        messages = [
            {"role": "system", "content": self.get_system_prompt()},
            {"role": "user", "content": user_prompt}
        ]
        
        return await self.openrouter.generate(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens
        )
    
    @abstractmethod
    async def execute(self, **kwargs) -> Dict[str, Any]:
        """
        Выполняет основную логику агента
        
        Args:
            **kwargs: Параметры для выполнения
        
        Returns:
            Результат выполнения
        """
        pass


__all__ = ["BaseAgent"]
