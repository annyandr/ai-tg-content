"""
Агент планирования автоматических публикаций.
Рекомендует количество постов, темы и оптимальное время публикации.
"""

import json
from datetime import datetime
from typing import Dict, Any, List

from src.agents.base_agent import BaseAgent
from src.agents.specialty_loader import SPECIALTY_MAP
from src.core.logger import logger


PLANNER_SYSTEM_PROMPT = """Ты — AI-планировщик контента для сети медицинских Telegram-каналов.

Твоя задача — составить план публикаций на день для каждого канала.

ДОСТУПНЫЕ КАНАЛЫ И СПЕЦИАЛИЗАЦИИ:
{channels_info}

ПРАВИЛА ПЛАНИРОВАНИЯ:
1. Каждый канал получает от {min_posts} до {max_posts} постов в день
2. Оптимальное время публикации для медицинских каналов:
   - Утро: 08:00-10:00 (врачи перед сменой)
   - Обед: 12:00-14:00 (перерыв)
   - Вечер: 18:00-20:00 (после работы)
   - Поздний вечер: 21:00-22:00 (домашнее чтение)
3. Между постами в одном канале — минимум 2 часа
4. Темы должны быть актуальными, полезными для практикующих врачей
5. Чередуй типы постов: клинрекомендации, исследования, клинические случаи, разбор препаратов
6. Учитывай день недели: в выходные — легче контент, в будни — больше клинических данных

ТИПЫ ПОСТОВ:
- клинрекомендации — обзор клинических рекомендаций и протоколов
- исследование — разбор последних научных исследований
- клинический_случай — интересный клинический случай с разбором
- разбор_препарата — обзор лекарственного препарата
- дифференциальная_диагностика — алгоритм дифдиагностики
- практический_совет — краткий практический совет для врачей

ФОРМАТ ОТВЕТА (строго JSON):
{{
  "plan_date": "YYYY-MM-DD",
  "day_of_week": "понедельник",
  "posts": [
    {{
      "specialty": "гинекология",
      "topic": "Конкретная тема поста",
      "post_type": "клинрекомендации",
      "publish_time": "09:00",
      "priority": 1
    }}
  ],
  "total_posts": 5,
  "reasoning": "Краткое обоснование плана"
}}"""


class PublishingPlannerAgent(BaseAgent):
    """
    Агент для автоматического планирования публикаций.
    Определяет количество постов, темы и оптимальное время.
    """

    def __init__(self, openrouter, min_posts_per_channel: int = 1, max_posts_per_channel: int = 3):
        super().__init__(openrouter=openrouter)
        self.min_posts = min_posts_per_channel
        self.max_posts = max_posts_per_channel

    def get_system_prompt(self) -> str:
        """Возвращает системный промпт планировщика"""
        channels_info = ""
        for specialty, cfg in SPECIALTY_MAP.items():
            channels_info += f"- {cfg['emoji']} {cfg['name']} ({specialty}): канал {cfg['link']}\n"

        return PLANNER_SYSTEM_PROMPT.format(
            channels_info=channels_info,
            min_posts=self.min_posts,
            max_posts=self.max_posts
        )

    async def execute(self, **kwargs) -> Dict[str, Any]:
        """
        Создаёт план публикаций на день.

        Args:
            target_date: Дата планирования (по умолчанию — сегодня)
            specialties: Список специализаций (по умолчанию — все)

        Returns:
            Dict с планом публикаций
        """
        target_date = kwargs.get("target_date", datetime.now())
        specialties = kwargs.get("specialties", list(SPECIALTY_MAP.keys()))

        return await self.create_daily_plan(target_date, specialties)

    async def create_daily_plan(
        self,
        target_date: datetime = None,
        specialties: List[str] = None
    ) -> Dict[str, Any]:
        """
        Создаёт план публикаций на день.

        Args:
            target_date: Дата планирования
            specialties: Список специализаций для планирования

        Returns:
            Dict с планом публикаций
        """
        if target_date is None:
            target_date = datetime.now()

        if specialties is None:
            specialties = list(SPECIALTY_MAP.keys())

        days_ru = {
            0: "понедельник", 1: "вторник", 2: "среда",
            3: "четверг", 4: "пятница", 5: "суббота", 6: "воскресенье"
        }
        day_name = days_ru.get(target_date.weekday(), "понедельник")

        specialties_text = ", ".join(specialties)

        user_prompt = f"""Составь план публикаций на {target_date.strftime('%d.%m.%Y')} ({day_name}).

Активные специализации: {specialties_text}

Текущее время: {datetime.now().strftime('%H:%M')}
Планируй публикации только на БУДУЩЕЕ время (после текущего).

Создай оптимальный план с актуальными медицинскими темами."""

        logger.info(f"📋 Создание плана публикаций на {target_date.strftime('%d.%m.%Y')}")

        result = await self.generate(
            user_prompt=user_prompt,
            temperature=0.8,
            max_tokens=2000
        )

        if not result["success"]:
            logger.error(f"Ошибка создания плана: {result.get('error')}")
            return {"success": False, "error": result.get("error")}

        # Парсим JSON ответ
        try:
            response_content = result["content"].strip()

            # Извлечение JSON из markdown
            if "```json" in response_content:
                start = response_content.find("```json") + 7
                end = response_content.find("```", start)
                if end != -1:
                    response_content = response_content[start:end].strip()
            elif "```" in response_content:
                start = response_content.find("```") + 3
                end = response_content.find("```", start)
                if end != -1:
                    response_content = response_content[start:end].strip()

            first_brace = response_content.find('{')
            last_brace = response_content.rfind('}')
            if first_brace != -1 and last_brace != -1:
                response_content = response_content[first_brace:last_brace + 1]

            plan = json.loads(response_content)

            # Валидация плана
            posts = plan.get("posts", [])
            validated_posts = []
            for post in posts:
                specialty = post.get("specialty", "")
                if specialty in SPECIALTY_MAP:
                    validated_posts.append(post)
                else:
                    logger.warning(f"Пропущена неизвестная специализация в плане: {specialty}")

            plan["posts"] = validated_posts
            plan["total_posts"] = len(validated_posts)

            logger.info(
                f"📋 План создан: {plan['total_posts']} постов "
                f"на {target_date.strftime('%d.%m.%Y')}"
            )

            return {
                "success": True,
                "plan": plan
            }

        except json.JSONDecodeError as e:
            logger.error(f"Ошибка парсинга плана: {e}")
            logger.error(f"Raw: {result['content'][:500]}")
            return {"success": False, "error": f"JSON parse error: {e}"}


__all__ = ["PublishingPlannerAgent"]
