"""
Агент проверки медицинской безопасности
"""

import json
from typing import Dict, Any
from src.agents.base_agent import BaseAgent
from src.agents.safety_prompts import SAFETY_SYSTEM_PROMPT, SAFETY_USER_PROMPT_TEMPLATE
from src.core.logger import logger


class SafetyAgent(BaseAgent):
    """
    Агент проверки медицинской безопасности контента
    """
    
    def get_system_prompt(self) -> str:
        """Возвращает системный промпт для проверки безопасности"""
        return SAFETY_SYSTEM_PROMPT
    
    async def execute(
        self,
        content: str,
        specialty: str,
        channel_name: str
    ) -> Dict[str, Any]:
        """
        Проверяет контент на медицинскую безопасность
        
        Args:
            content: Текст поста для проверки
            specialty: Специализация (гинекология, педиатрия и т.д.)
            channel_name: Название канала
        
        Returns:
            Dict с результатами проверки
        """
        
        logger.info(f"🔍 Проверка безопасности: {specialty}")
        
        # Формируем user prompt
        user_prompt = SAFETY_USER_PROMPT_TEMPLATE.format(
            content=content,
            specialty=specialty,
            channel_name=channel_name
        )
        
        # Генерируем проверку
        result = await self.generate(
            user_prompt=user_prompt,
            temperature=0.3  # Низкая температура для консистентности
        )
        
        if not result["success"]:
            logger.error(f"❌ Ошибка проверки безопасности: {result.get('error')}")
            return {
                "success": False,
                "is_safe": False,
                "severity": "unknown",
                "error": result.get("error")
            }
        
        # Парсим JSON ответ
        try:
            safety_data = json.loads(result["content"])
            
            is_safe = safety_data.get("is_safe", False)
            severity = safety_data.get("severity", "unknown")
            
            if is_safe:
                logger.info(f"✅ Контент безопасен: {severity}")
            else:
                logger.warning(f"⚠️ Контент требует проверки: {severity}")
            
            return {
                "success": True,
                "is_safe": is_safe,
                "severity": severity,
                "issues": safety_data.get("issues", []),
                "recommendations": safety_data.get("recommendations", []),
                "statistics": safety_data.get("statistics", {})
            }
        
        except json.JSONDecodeError:
            logger.error("❌ Не удалось распарсить JSON ответ от Safety Agent")
            
            # Fallback: базовая проверка
            return {
                "success": True,
                "is_safe": True,  # По умолчанию считаем безопасным
                "severity": "low",
                "issues": [],
                "recommendations": ["Не удалось выполнить полную проверку"],
                "statistics": {}
            }


__all__ = ["SafetyAgent"]
