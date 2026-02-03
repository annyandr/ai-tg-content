"""
Агент проверки медицинской безопасности
"""
from typing import Dict, Any, List
from src.agents.base_agent import BaseAgent
from src.services.openrouter import OpenRouterService
from src.core.logger import logger

# Импортируем промпты
from src.prompts.agents.safety_prompts import (
    SAFETY_SYSTEM_PROMPT,
    SAFETY_USER_PROMPT_TEMPLATE
)


class SafetyAgent(BaseAgent):
    """
    Агент для проверки медицинской безопасности контента
    """
    
    # Критичные паттерны для всех специализаций
    CRITICAL_PATTERNS = [
        r'гарантиру(ю|ет|ем)\s+излечение',
        r'100%\s+эффективн',
        r'обязательно\s+принимайте',
        r'назначьте\s+себе',
        r'можете\s+не\s+обращаться\s+к\s+врачу',
        r'замените\s+врача',
    ]
    
    def __init__(self, openrouter: OpenRouterService):
        super().__init__(
            name="SafetyAgent",
            openrouter=openrouter,
            default_temperature=0.3  # Низкая температура для точности
        )
    
    def get_system_prompt(self) -> str:
        """Возвращает детальный системный промпт для проверки безопасности"""
        return SAFETY_SYSTEM_PROMPT
    
    async def execute(
        self,
        content: str,
        specialty: str = "общая медицина",
        channel_name: str = "медицинский канал"
    ) -> Dict[str, Any]:
        """
        Проверяет контент на безопасность
        
        Args:
            content: Текст для проверки
            specialty: Специализация
            channel_name: Название канала
            
        Returns:
            Dict с результатами проверки
        """
        logger.info(f"Проверка безопасности контента ({specialty})")
        
        # Сначала быстрая проверка критичных паттернов
        critical_issues = self._quick_safety_check(content)
        
        if critical_issues:
            logger.warning(f"❌ Найдены критичные проблемы: {critical_issues}")
            return {
                "is_safe": False,
                "severity": "critical",
                "issues": [
                    {
                        "type": "critical_pattern",
                        "severity": "critical",
                        "description": issue,
                        "location": "",
                        "recommendation": "Удалите прямые медицинские назначения"
                    }
                    for issue in critical_issues
                ],
                "recommendations": ["Полностью переписать контент", "Удалить прямые назначения"],
                "statistics": {
                    "total_issues": len(critical_issues),
                    "critical_issues": len(critical_issues),
                    "high_issues": 0,
                    "medium_issues": 0,
                    "low_issues": 0
                }
            }
        
        # Затем AI проверка с детальным промптом
        user_prompt = SAFETY_USER_PROMPT_TEMPLATE.format(
            content=content,
            specialty=specialty,
            channel_name=channel_name
        )
        
        result = await self.openrouter.generate_json(
            system_prompt=self.get_system_prompt(),
            user_prompt=user_prompt
        )
        
        if result["success"] and "parsed_json" in result:
            safety_result = result["parsed_json"]
            
            if not safety_result.get("is_safe"):
                logger.warning(f"⚠️ Контент не прошёл проверку безопасности")
            else:
                logger.info("✅ Контент безопасен")
            
            return safety_result
        else:
            logger.error("Ошибка проверки безопасности")
            return {
                "is_safe": False,
                "severity": "unknown",
                "issues": [{"description": "Не удалось выполнить проверку"}],
                "recommendations": ["Повторите проверку"],
                "statistics": {"total_issues": 1, "critical_issues": 0}
            }
    
    def _quick_safety_check(self, content: str) -> List[str]:
        """Быстрая проверка критичных паттернов"""
        import re
        issues = []
        
        for pattern in self.CRITICAL_PATTERNS:
            if re.search(pattern, content, re.IGNORECASE):
                match = re.search(pattern, content, re.IGNORECASE)
                issues.append(f"Критичная фраза: '{match.group()}'")
        
        return issues


__all__ = ["SafetyAgent"]
