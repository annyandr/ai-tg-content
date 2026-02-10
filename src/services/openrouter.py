"""
Сервис для работы с OpenRouter API
"""

import asyncio
import ssl
import aiohttp
from typing import Dict, Any, List, Optional
from src.core.logger import logger
from src.core.config import config


class OpenRouterService:
    """Клиент для OpenRouter API"""
    
    def __init__(
        self,
        api_key: str,
        base_url: str = "https://openrouter.ai/api/v1"
    ):
        self.api_key = api_key
        self.base_url = base_url
        self.session: Optional[aiohttp.ClientSession] = None
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    async def generate_with_prompts(
            self,
            system_prompt: str,
            user_prompt: str,
            model: str = None,
            temperature: float = None,
            max_tokens: int = None,
            timeout: int = 120
    ) -> Dict[str, Any]:
        """
        Удобная обертка для генерации с system_prompt и user_prompt

        Args:
            system_prompt: Системный промпт
            user_prompt: Пользовательский промпт
            model: Модель (по умолчанию из config)
            temperature: Температура (по умолчанию из config)
            max_tokens: Макс токенов (по умолчанию из config)
            timeout: Таймаут запроса в секундах

        Returns:
            Dict с результатом {"success": bool, "content": str, "error": str}
        """
        # Формируем messages в формате OpenAI Chat Completions API
        messages = [
            {"role": "system", "content": system_prompt.strip()},
            {"role": "user", "content": user_prompt.strip()}
        ]

        return await self.generate(
            messages=messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=timeout
        )

    async def generate(
        self,
        messages: List[Dict[str, str]],
        model: str = None,
        temperature: float = None,
        max_tokens: int = None,
        timeout: int = 120
    ) -> Dict[str, Any]:
        """
        Генерация через OpenRouter API
        
        Args:
            messages: Список сообщений [{"role": "user", "content": "..."}]
            model: Модель (по умолчанию из config)
            temperature: Температура (по умолчанию из config)
            max_tokens: Макс токенов (по умолчанию из config)
        
        Returns:
            Dict с результатом {"success": bool, "content": str, "error": str}
        """
        
        if not self.session:
            # Создаём SSL context без проверки сертификатов
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE

            connector = aiohttp.TCPConnector(ssl=ssl_context)
            self.session = aiohttp.ClientSession(connector=connector)
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/annyandr/ai-tg-content",
        }
        
        data = {
            "model": model or config.DEFAULT_MODEL,
            "messages": messages,
            "temperature": temperature or config.TEMPERATURE,
            "max_tokens": max_tokens or config.MAX_TOKENS
        }
        
        logger.info(f"🔄 OpenRouter запрос: model={data['model']}, messages={len(messages)}, max_tokens={data['max_tokens']}")

        try:
            async with self.session.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=data,
                timeout=aiohttp.ClientTimeout(total=timeout)
            ) as response:

                if response.status == 200:
                    result = await response.json()
                    content = result["choices"][0]["message"]["content"]

                    logger.info(f"✅ OpenRouter: успешная генерация ({len(content)} символов)")

                    return {
                        "success": True,
                        "content": content,
                        "model": data["model"],
                        "usage": result.get("usage", {})
                    }
                else:
                    error_text = await response.text()

                    # Проверяем, не HTML ли это (блокировка firewall)
                    if '<!DOCTYPE' in error_text or '<html' in error_text:
                        logger.error(f"❌ Доступ заблокирован корпоративным firewall")
                        return {
                            "success": False,
                            "content": None,
                            "error": "API заблокирован. Попробуйте с другой машины или используйте VPN"
                        }

                    logger.error(f"❌ OpenRouter error {response.status}: {error_text[:200]}")

                    return {
                        "success": False,
                        "content": None,
                        "error": f"API error {response.status}: {error_text[:200]}"
                    }
        
        except asyncio.TimeoutError as e:
            logger.error(f"❌ OpenRouter timeout ({timeout}с): {repr(e)}", exc_info=True)
            return {
                "success": False,
                "content": None,
                "error": f"Timeout: запрос к API превысил {timeout}с"
            }
        except Exception as e:
            logger.error(f"❌ OpenRouter exception: type={type(e).__name__}, msg={e}, repr={repr(e)}", exc_info=True)
            return {
                "success": False,
                "content": None,
                "error": f"{type(e).__name__}: {repr(e)}"
            }
    
    async def close(self):
        """Закрытие сессии"""
        if self.session:
            await self.session.close()


__all__ = ["OpenRouterService"]
