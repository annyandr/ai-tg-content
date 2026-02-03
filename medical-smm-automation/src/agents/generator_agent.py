"""
Универсальный агент генерации контента для ЛЮБОГО канала
"""
from typing import Dict, Any
from src.agents.base_agent import BaseAgent
from src.services.openrouter import OpenRouterService
from src.core.logger import logger

# Импортируем промпты
from src.prompts.agents.generator_prompts import (
    GENERATOR_SYSTEM_PROMPT,
    USER_PROMPT_TEMPLATE,
    REGENERATION_PROMPT_TEMPLATE
)
from src.prompts.channels.gynecology_prompts import GYNECOLOGY_SPECIALTY_PROMPT
from src.prompts.channels.pediatrics_prompts import PEDIATRICS_SPECIALTY_PROMPT
from src.prompts.channels.endocrinology_prompts import ENDOCRINOLOGY_SPECIALTY_PROMPT


class ContentGeneratorAgent(BaseAgent):
    """
    Универсальный агент генерации для ВСЕХ каналов
    """
    
    # Маппинг специализаций на промпты
    SPECIALTY_PROMPTS = {
        "гинекология": GYNECOLOGY_SPECIALTY_PROMPT,
        "педиатрия": PEDIATRICS_SPECIALTY_PROMPT,
        "эндокринология": ENDOCRINOLOGY_SPECIALTY_PROMPT,
    }
    
    def __init__(self, openrouter: OpenRouterService):
        super().__init__(
            name="ContentGeneratorAgent",
            openrouter=openrouter,
            default_temperature=0.7
        )
    
    def get_system_prompt(self) -> str:
        """Возвращает базовый системный промпт"""
        return GENERATOR_SYSTEM_PROMPT
    
    async def execute(
        self,
        news: Dict[str, Any],
        channel: Dict[str, Any],
        custom_instructions: str = ""
    ) -> Dict[str, Any]:
        """
        Генерирует пост для любого канала
        
        Args:
            news: Новость (title, content, source_name, source_url)
            channel: Канал (name, specialty, emoji, link)
            custom_instructions: Дополнительные инструкции
            
        Returns:
            Dict с результатом генерации
        """
        logger.info(f"Генерация поста для канала: {channel.get('name')}")
        
        # Получаем специализированный промпт
        specialty = channel.get('specialty', 'общая медицина')
        specialty_prompt = self.SPECIALTY_PROMPTS.get(
            specialty.lower(),
            ""  # Если специализация не найдена
        )
        
        # Объединяем с custom_instructions
        all_instructions = f"{specialty_prompt}\n\n{custom_instructions}" if custom_instructions else specialty_prompt
        
        # Формируем user prompt
        user_prompt = USER_PROMPT_TEMPLATE.format(
            channel_name=channel.get('name', ''),
            news_title=news.get('title', ''),
            news_content=news.get('content', ''),
            news_source=news.get('source_name', 'Источник'),
            news_url=news.get('source_url', ''),
            specialty=specialty,
            channel_emoji=channel.get('emoji', ''),
            channel_link=channel.get('link', ''),
            custom_instructions=all_instructions
        )
        
        # Генерируем
        result = await self.generate(
            user_prompt=user_prompt,
            temperature=0.7
        )
        
        if result["success"]:
            logger.info("✅ Пост успешно сгенерирован")
            return {
                "success": True,
                "content": result["content"],
                "metadata": {
                    "channel": channel.get('name'),
                    "specialty": specialty,
                    "news_title": news.get('title')
                }
            }
        else:
            logger.error(f"❌ Ошибка генерации: {result.get('error')}")
            return {
                "success": False,
                "error": result.get("error"),
                "content": None
            }
    
    async def regenerate_with_feedback(
        self,
        original_content: str,
        feedback: str,
        channel: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Регенерирует пост с учётом обратной связи
        """
        logger.info(f"Регенерация с обратной связью: {feedback[:50]}...")
        
        user_prompt = REGENERATION_PROMPT_TEMPLATE.format(
            original_content=original_content,
            feedback=feedback,
            channel_emoji=channel.get('emoji', ''),
            specialty=channel.get('specialty', ''),
            channel_link=channel.get('link', '')
        )
        
        result = await self.generate(
            user_prompt=user_prompt,
            temperature=0.7
        )
        
        if result["success"]:
            logger.info("✅ Пост улучшен")
        
        return result


__all__ = ["ContentGeneratorAgent"]
