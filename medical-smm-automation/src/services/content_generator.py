"""
Сервис генерации медицинского контента
Обновлено для MVP: добавлена генерация по теме
"""

from typing import Optional, Dict

from src.agents.specialty_loader import get_specialty_config, get_specialty_prompt
from src.services.openrouter import OpenRouterService
from src.services.validator import PostValidator
from src.core.logger import logger
from src.core.config import config


class ContentGeneratorService:
    """Сервис для генерации медицинских постов"""

    def __init__(
        self,
        openrouter: Optional[OpenRouterService] = None,
        validator: Optional[PostValidator] = None,
        auto_validate: bool = True
    ):
        self.openrouter = openrouter or OpenRouterService(
            api_key=config.openrouter_api_key,
        )
        self.validator = validator
        self.auto_validate = auto_validate

        self.stats = {
            "total_generated": 0,
            "successful": 0,
            "failed": 0,
            "by_specialty": {}
        }

    async def generate_post(
        self,
        news: Dict,
        channel_key: str,
        specialty: str,
        max_retries: int = 3
    ) -> str:
        """
        Генерация поста из новости (существующий метод)

        Args:
            news: Данные новости
            channel_key: Ключ канала (gynecology, pediatrics и т.д.)
            specialty: Специализация
            max_retries: Количество попыток

        Returns:
            Сгенерированный пост
        """
        logger.info(f"Генерация поста из новости для {specialty}")

        # Получаем специализированный промпт
        specialty_prompt = get_specialty_prompt(specialty)
        if not specialty_prompt:
            raise ValueError(f"Неизвестная специализация: {specialty}")

        # Формируем промпт
        system_prompt = f"""{specialty_prompt}

Создай пост на основе медицинской новости.
"""

        user_prompt = f"""Новость:
Заголовок: {news.get('title', 'Без заголовка')}
Текст: {news.get('content', '')}
Источник: {news.get('source', 'Неизвестно')}

Создай качественный пост для канала, используя шаблоны из промпта специализации.
"""

        # Генерируем
        result = await self.openrouter.generate_with_prompts(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.7
        )

        if result["success"]:
            post_content = result["content"]

            # Валидация если включена
            if self.auto_validate and self.validator:
                is_valid = self.validator.validate_post(post_content)
                if not is_valid and max_retries > 0:
                    logger.warning("Пост не прошёл валидацию, перегенерация...")
                    return await self.generate_post(news, channel_key, specialty, max_retries - 1)

            self._update_stats(specialty, success=True)
            return post_content
        else:
            self._update_stats(specialty, success=False)
            raise Exception(f"Ошибка генерации: {result.get('error')}")

    async def generate_from_topic(
        self,
        topic: str,
        specialty: str,
        post_type: str = "клинрекомендации",
        max_length: int = 2000
    ) -> str:
        """
        🆕 НОВЫЙ МЕТОД: Генерация поста по теме (для MVP)

        Args:
            topic: Тема поста (например, "Новые критерии ГСД 2026")
            specialty: Специализация (гинекология, педиатрия и т.д.)
            post_type: Тип поста (клинрекомендации/исследование/клинический_случай)
            max_length: Максимальная длина поста

        Returns:
            Сгенерированный текст поста
        """
        logger.info(f"🆕 Генерация поста по теме: {specialty} | {topic}")

        # Получаем конфигурацию специализации
        specialty_config = get_specialty_config(specialty)
        if not specialty_config:
            raise ValueError(f"Неизвестная специализация: {specialty}")

        specialty_prompt = specialty_config["prompt"]
        emoji = specialty_config["emoji"]
        channel_link = specialty_config["link"]

        # Формируем системный промпт
        system_prompt = f"""{specialty_prompt}

ДОПОЛНИТЕЛЬНЫЕ ТРЕБОВАНИЯ:
- Длина поста: максимум {max_length} символов
- Обязательно используй эмодзи {emoji} в начале
- Добавь ссылку на канал {channel_link} в конце
- Следуй шаблону "{post_type}" из промпта
- Пиши понятно и для врачей, и для пациентов
- Используй актуальные данные (февраль 2026)
"""

        user_prompt = f"""Создай пост для медицинского Telegram-канала на тему:

📌 ТЕМА: {topic}

ТИП ПОСТА: {post_type}

ТРЕБОВАНИЯ:
1. Используй актуальные данные и исследования (2026 год)
2. Укажи конкретные источники (клинрекомендации, исследования)
3. Добавь практическую ценность для врачей
4. Структурируй по шаблону из промпта специализации
5. Не превышай {max_length} символов
6. Обязательно начни с эмодзи {emoji}
7. В конце добавь ссылку: {channel_link}

Создай готовый к публикации пост."""

        try:
            # Генерируем через OpenRouter
            result = await self.openrouter.generate_with_prompts(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=0.7
            )

            if result["success"]:
                post_content = result["content"]

                # Обновляем статистику
                self._update_stats(specialty, success=True)

                logger.info(f"✅ Пост сгенерирован: {len(post_content)} символов")
                return post_content
            else:
                self._update_stats(specialty, success=False)
                raise Exception(f"Ошибка генерации: {result.get('error')}")

        except Exception as e:
            logger.error(f"❌ Ошибка генерации поста: {e}")
            self._update_stats(specialty, success=False)
            raise

    async def regenerate_post(
        self,
        post: str,
        feedback: str
    ) -> str:
        """
        Перегенерация поста с учётом обратной связи

        Args:
            post: Исходный пост
            feedback: Обратная связь

        Returns:
            Улучшенный пост
        """
        system_prompt = """Ты редактор медицинского контента.
Улучши пост согласно обратной связи, сохраняя стиль и структуру."""

        user_prompt = f"""ИСХОДНЫЙ ПОСТ:
{post}

ОБРАТНАЯ СВЯЗЬ:
{feedback}

Перепиши пост с учётом замечаний."""

        result = await self.openrouter.generate_with_prompts(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.7
        )

        if result["success"]:
            return result["content"]
        else:
            raise Exception(f"Ошибка регенерации: {result.get('error')}")

    def _update_stats(self, specialty: str, success: bool):
        """Обновление статистики генерации"""
        self.stats["total_generated"] += 1

        if success:
            self.stats["successful"] += 1
        else:
            self.stats["failed"] += 1

        if specialty not in self.stats["by_specialty"]:
            self.stats["by_specialty"][specialty] = {"total": 0, "successful": 0, "failed": 0}

        self.stats["by_specialty"][specialty]["total"] += 1
        if success:
            self.stats["by_specialty"][specialty]["successful"] += 1
        else:
            self.stats["by_specialty"][specialty]["failed"] += 1

    def get_stats(self) -> Dict:
        """Получить статистику"""
        return self.stats.copy()


__all__ = ["ContentGeneratorService"]
