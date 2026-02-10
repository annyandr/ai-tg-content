"""
Сервис автоматической публикации постов.
Полный цикл: планирование -> генерация -> проверка -> публикация.
Без участия пользователя.
"""

import asyncio
import uuid
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any

from src.agents.publishing_planner_agent import PublishingPlannerAgent
from src.agents.generator_agent import ContentGeneratorAgent
from src.agents.safety_agent import SafetyAgent
from src.agents.specialty_loader import SPECIALTY_MAP, get_specialty_config
from src.core.logger import logger
from src.telegram_bot.models import PublishTask, TaskStatus
from src.utils.channel_utils import normalize_channel_id


class AutoPublisher:
    """
    Автоматический издатель контента.
    Полный цикл без участия пользователя:
    1. AI-планировщик составляет план на день (темы, время, кол-во)
    2. Генератор создаёт контент для каждого поста
    3. Safety-агент проверяет безопасность
    4. Посты ставятся в очередь на публикацию в рекомендованное время
    """

    def __init__(
        self,
        planner_agent: PublishingPlannerAgent,
        generator_agent: ContentGeneratorAgent,
        safety_agent: SafetyAgent,
        telegram_bot,
        enabled: bool = True,
        max_retries_per_post: int = 2
    ):
        self.planner = planner_agent
        self.generator = generator_agent
        self.safety = safety_agent
        self.telegram_bot = telegram_bot
        self.enabled = enabled
        self.max_retries = max_retries_per_post

        # Статистика текущего цикла
        self.last_run: Optional[datetime] = None
        self.last_plan: Optional[Dict] = None
        self.stats = {
            "total_runs": 0,
            "total_planned": 0,
            "total_generated": 0,
            "total_published": 0,
            "total_failed": 0,
            "total_safety_rejected": 0
        }

        logger.info("🤖 AutoPublisher инициализирован")

    async def run_daily_cycle(self, specialties: List[str] = None):
        """
        Запускает полный цикл автопубликации на день.
        Вызывается планировщиком автоматически.

        Args:
            specialties: Список специализаций (по умолчанию — все)
        """
        if not self.enabled:
            logger.info("⏸️ AutoPublisher отключён, пропуск цикла")
            return

        logger.info("=" * 60)
        logger.info("🚀 ЗАПУСК АВТОМАТИЧЕСКОГО ЦИКЛА ПУБЛИКАЦИИ")
        logger.info("=" * 60)

        self.stats["total_runs"] += 1
        self.last_run = datetime.now()

        try:
            # 1. Получаем план от AI-планировщика
            plan_result = await self.planner.create_daily_plan(
                target_date=datetime.now(),
                specialties=specialties
            )

            if not plan_result["success"]:
                logger.error(f"Ошибка планирования: {plan_result.get('error')}")
                await self._notify_admins(
                    f"Ошибка автопланирования: {plan_result.get('error')}"
                )
                return

            plan = plan_result["plan"]
            self.last_plan = plan
            posts = plan.get("posts", [])

            logger.info(f"📋 План: {len(posts)} постов на сегодня")
            logger.info(f"💡 Обоснование: {plan.get('reasoning', 'N/A')}")

            self.stats["total_planned"] += len(posts)

            # 2. Генерируем и планируем каждый пост
            scheduled_count = 0
            failed_count = 0

            for i, post_plan in enumerate(posts, 1):
                logger.info(f"--- Пост {i}/{len(posts)} ---")

                try:
                    task_id = await self._process_single_post(post_plan)
                    if task_id:
                        scheduled_count += 1
                        logger.info(f"✅ Пост {i} запланирован: {task_id}")
                    else:
                        failed_count += 1
                        logger.warning(f"⚠️ Пост {i} не прошёл проверку")

                    # Пауза между генерациями (rate limiting OpenRouter)
                    if i < len(posts):
                        await asyncio.sleep(5)

                except Exception as e:
                    failed_count += 1
                    logger.error(f"Ошибка обработки поста {i}: {e}")

            self.stats["total_published"] += scheduled_count
            self.stats["total_failed"] += failed_count

            # 3. Отчёт
            report = (
                f"📊 Автопубликация завершена:\n"
                f"📋 Запланировано: {len(posts)}\n"
                f"✅ Успешно: {scheduled_count}\n"
                f"❌ Ошибки: {failed_count}"
            )
            logger.info(report)
            await self._notify_admins(report)

        except Exception as e:
            logger.error(f"Критическая ошибка автопубликации: {e}", exc_info=True)
            await self._notify_admins(f"Критическая ошибка автопубликации: {e}")

    async def _process_single_post(self, post_plan: Dict) -> Optional[str]:
        """
        Обрабатывает один пост из плана: генерация -> проверка -> планирование.

        Args:
            post_plan: Данные поста из плана
                - specialty: специализация
                - topic: тема
                - post_type: тип поста
                - publish_time: время публикации (HH:MM)

        Returns:
            task_id если успешно, None если не прошёл проверку
        """
        specialty = post_plan["specialty"]
        topic = post_plan["topic"]
        post_type = post_plan.get("post_type", "клинрекомендации")
        publish_time_str = post_plan.get("publish_time", "09:00")

        specialty_config = get_specialty_config(specialty)
        if not specialty_config:
            logger.warning(f"Неизвестная специализация: {specialty}")
            return None

        channel_id = specialty_config["channel"]

        logger.info(
            f"📝 Генерация: [{specialty}] {topic} "
            f"(тип: {post_type}, время: {publish_time_str})"
        )

        # --- Генерация контента ---
        content = None
        for attempt in range(self.max_retries + 1):
            try:
                news = {
                    "title": topic,
                    "content": f"Тема: {topic}. Тип поста: {post_type}.",
                    "source_name": "AI-планировщик",
                    "source_url": ""
                }

                channel = {
                    "name": specialty_config["name"],
                    "specialty": specialty,
                    "emoji": specialty_config["emoji"],
                    "link": specialty_config["link"]
                }

                gen_result = await self.generator.execute(
                    news=news,
                    channel=channel
                )

                if gen_result["success"]:
                    content = gen_result["content"]
                    self.stats["total_generated"] += 1
                    break
                else:
                    logger.warning(
                        f"Попытка {attempt + 1}: ошибка генерации — "
                        f"{gen_result.get('error')}"
                    )

            except Exception as e:
                logger.warning(f"Попытка {attempt + 1}: исключение — {e}")

            if attempt < self.max_retries:
                await asyncio.sleep(3)

        if not content:
            logger.error(f"Не удалось сгенерировать пост для: {topic}")
            return None

        # --- Проверка безопасности ---
        try:
            safety_result = await self.safety.execute(
                content=content,
                specialty=specialty,
                channel_name=specialty_config["name"]
            )

            if safety_result["success"]:
                is_safe = safety_result.get("is_safe", False)
                severity = safety_result.get("severity", "unknown")

                if not is_safe and severity in ("high",):
                    logger.warning(
                        f"🚫 Пост отклонён (severity={severity}): {topic}"
                    )
                    self.stats["total_safety_rejected"] += 1
                    return None

                if not is_safe:
                    logger.info(
                        f"⚠️ Пост с замечаниями (severity={severity}), "
                        f"публикуется: {topic}"
                    )
        except Exception as e:
            logger.warning(f"Ошибка проверки безопасности (пропускаем): {e}")

        # --- Планирование публикации ---
        try:
            hour, minute = map(int, publish_time_str.split(":"))
        except ValueError:
            hour, minute = 9, 0

        now = datetime.now()
        scheduled_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)

        # Если время уже прошло, публикуем через 5 минут
        if scheduled_time <= now:
            scheduled_time = now + timedelta(minutes=5)

        task_id = str(uuid.uuid4())[:8]

        task = PublishTask(
            task_id=task_id,
            channel_id=normalize_channel_id(channel_id),
            text=content,
            scheduled_time=scheduled_time,
            status=TaskStatus.SCHEDULED if scheduled_time > now + timedelta(minutes=1) else TaskStatus.PENDING,
            created_by=0  # 0 = автоматически
        )

        await self.telegram_bot.add_task(task)

        logger.info(
            f"⏰ Пост запланирован: {task_id} -> "
            f"{specialty_config['name']} в {scheduled_time.strftime('%H:%M')}"
        )

        return task_id

    async def _notify_admins(self, text: str):
        """Отправляет уведомление всем админам"""
        from src.core.config import config

        if not config.ADMIN_IDS:
            return

        notification = f"🤖 <b>AutoPublisher</b>\n\n{text}"

        for admin_id in config.ADMIN_IDS:
            try:
                await self.telegram_bot.bot.send_message(
                    admin_id, notification, parse_mode="HTML"
                )
            except Exception as e:
                logger.error(f"Не удалось уведомить админа {admin_id}: {e}")

    def get_stats(self) -> Dict[str, Any]:
        """Статистика автопубликации"""
        return {
            **self.stats,
            "enabled": self.enabled,
            "last_run": self.last_run.strftime("%d.%m.%Y %H:%M") if self.last_run else "никогда",
            "last_plan_posts": self.last_plan.get("total_posts", 0) if self.last_plan else 0
        }

    def enable(self):
        """Включить автопубликацию"""
        self.enabled = True
        logger.info("▶️ AutoPublisher включён")

    def disable(self):
        """Выключить автопубликацию"""
        self.enabled = False
        logger.info("⏸️ AutoPublisher выключен")


__all__ = ["AutoPublisher"]
