"""
Агент генерации медицинского контента
"""

from typing import Dict, Any

from src.agents.base_agent import BaseAgent
from src.agents.generator_prompts import (
    GENERATOR_SYSTEM_PROMPT,
    USER_PROMPT_TEMPLATE
)
from src.agents.specialty_loader import get_specialty_config
from src.core.logger import logger


class ContentGeneratorAgent(BaseAgent):
    """
    Агент для генерации медицинского контента
    """
    
    def get_system_prompt(self) -> str:
        """Возвращает системный промпт генератора"""
        return GENERATOR_SYSTEM_PROMPT
    
    async def execute(
        self,
        news: Dict[str, Any],
        channel: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Генерирует пост на основе новости
        
        Args:
            news: Словарь с новостью
                - title: Заголовок
                - content: Содержание
                - source_name: Название источника
                - source_url: URL источника
            channel: Словарь с данными канала
                - name: Название канала
                - specialty: Специализация
                - emoji: Эмодзи канала
                - link: Ссылка на канал
        
        Returns:
            Dict с результатом генерации
        """
        logger.info(f"🤖 Генерация поста для {channel.get('name')}")
        
        # Получаем специализированные инструкции
        specialty = channel.get("specialty", "")
        specialty_config = get_specialty_config(specialty)
        
        custom_instructions = ""
        if specialty_config:
            custom_instructions = specialty_config.get("prompt", "")
        
        # Формируем user prompt
        user_prompt = USER_PROMPT_TEMPLATE.format(
            news_title=news.get("title", ""),
            news_content=news.get("content", ""),
            news_source=news.get("source_name", ""),
            news_url=news.get("source_url", ""),
            channel_name=channel.get("name", ""),
            specialty=channel.get("specialty", ""),
            channel_emoji=channel.get("emoji", ""),
            channel_link=channel.get("link", ""),
            custom_instructions=custom_instructions
        )
        
        # Генерируем контент
        result = await self.generate(
            user_prompt=user_prompt,
            temperature=0.7,
            max_tokens=2000
        )
        
        if not result["success"]:
            logger.error(f"❌ Ошибка генерации: {result.get('error')}")
            return result
        
        content = result["content"].strip()
        
        logger.info(f"✅ Пост сгенерирован ({len(content)} символов)")
        
        return {
            "success": True,
            "content": content,
            "metadata": {
                "specialty": specialty,
                "channel": channel.get("name"),
                "length": len(content)
            }
        }


__all__ = ["ContentGeneratorAgent"]
