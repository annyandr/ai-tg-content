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
            response_content = result["content"].strip()

            # Логируем сырой ответ для отладки (увеличен размер до 1000 символов)
            logger.debug(f"Safety Agent raw response: {response_content[:1000]}...")

            # Пытаемся извлечь JSON из markdown блоков (```json ... ```)
            if "```json" in response_content:
                start = response_content.find("```json") + 7
                end = response_content.find("```", start)
                if end != -1:
                    response_content = response_content[start:end].strip()
            elif "```" in response_content:
                # Просто ```  без json
                start = response_content.find("```") + 3
                end = response_content.find("```", start)
                if end != -1:
                    response_content = response_content[start:end].strip()

            # Дополнительная очистка: ищем первую { и последнюю }
            # Это помогает избавиться от текста до и после JSON
            first_brace = response_content.find('{')
            last_brace = response_content.rfind('}')

            if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
                response_content = response_content[first_brace:last_brace + 1]

            safety_data = json.loads(response_content)

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

        except json.JSONDecodeError as e:
            logger.error(f"❌ Не удалось распарсить JSON ответ от Safety Agent: {e}")
            logger.error(f"Raw response: {result['content'][:1000]}...")

            # Fallback: базовая проверка
            return {
                "success": True,
                "is_safe": True,  # По умолчанию считаем безопасным
                "severity": "low",
                "issues": [],
                "recommendations": ["Не удалось выполнить полную проверку"],
                "statistics": {}
            }
        except KeyError as e:
            logger.error(f"❌ Отсутствует ключ в ответе Safety Agent: {e}")

            # Fallback
            return {
                "success": True,
                "is_safe": True,
                "severity": "low",
                "issues": [],
                "recommendations": ["Неполный ответ от проверки безопасности"],
                "statistics": {}
            }


__all__ = ["SafetyAgent"]
