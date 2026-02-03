"""
Сервис для работы с OpenRouter API
"""

import aiohttp
import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class OpenRouterService:
    """Клиент для OpenRouter API"""

    BASE_URL = "https://openrouter.ai/api/v1"

    def __init__(self, api_key: str, model: str = "anthropic/claude-3.5-sonnet"):
        self.api_key = api_key
        self.model = model
        self.session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Получить или создать HTTP сессию"""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                }
            )
        return self.session

    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 2500
    ) -> Dict:
        """
        Генерация текста через OpenRouter

        Args:
            system_prompt: Системный промпт
            user_prompt: Запрос пользователя
            temperature: Температура генерации (0.0-1.0)
            max_tokens: Максимум токенов в ответе

        Returns:
            Dict с результатом
        """
        try:
            session = await self._get_session()

            payload = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                "temperature": temperature,
                "max_tokens": max_tokens
            }

            async with session.post(
                f"{self.BASE_URL}/chat/completions",
                json=payload
            ) as response:

                if response.status == 200:
                    data = await response.json()
                    content = data["choices"][0]["message"]["content"]

                    return {
                        "success": True,
                        "content": content,
                        "model": self.model,
                        "tokens": data.get("usage", {})
                    }
                else:
                    error_text = await response.text()
                    logger.error(f"OpenRouter API error: {response.status} - {error_text}")

                    return {
                        "success": False,
                        "error": f"API error {response.status}: {error_text}"
                    }

        except Exception as e:
            logger.error(f"Ошибка генерации через OpenRouter: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    async def close(self):
        """Закрыть сессию"""
        if self.session and not self.session.closed:
            await self.session.close()


__all__ = ["OpenRouterService"]
