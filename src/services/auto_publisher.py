"""
Сервис автоматической публикации постов.
Цикл: планирование -> генерация -> проверка -> одобрение человеком -> публикация.
"""

import asyncio
import uuid
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field

from src.agents.publishing_planner_agent import PublishingPlannerAgent
from src.agents.generator_agent import ContentGeneratorAgent
from src.agents.safety_agent import SafetyAgent
from src.agents.specialty_loader import SPECIALTY_MAP, get_specialty_config
from src.core.logger import logger
from src.telegram_bot.models import PublishTask, TaskStatus
from src.utils.channel_utils import normalize_channel_id


@dataclass
class PreparedPost:
    """Подготовленный пост, ожидающий одобрения"""
    index: int
    specialty: str
    channel_id: str
    channel_name: str
    channel_emoji: str
    channel_link: str
    topic: str
    post_type: str
    publish_time: str
    content: str
    safety_zone: str  # "green", "yellow", "red"
    safety_severity: str
    safety_issues: List[str] = field(default_factory=list)
    safety_recommendations: List[str] = field(default_factory=list)
    removed: bool = False


@dataclass
class PendingPlan:
    """План публикации, ожидающий одобрения от человека"""
    plan_id: str
    created_at: datetime
    posts: List[PreparedPost]
    reasoning: str = ""
    message_id: Optional[int] = None  # ID сообщения с лентой для обновления

    @property
    def active_posts(self) -> List[PreparedPost]:
        return [p for p in self.posts if not p.removed]

    @property
    def total_active(self) -> int:
        return len(self.active_posts)


class AutoPublisher:
    """
    Автоматический издатель контента с одобрением от человека.

    Цикл:
    1. AI-планировщик составляет план на день (темы, время, кол-во)
    2. Генератор создаёт контент для каждого поста
    3. Safety-агент проверяет безопасность
    4. Лента постов отправляется админу на одобрение
    5. Админ одобряет / правит / удаляет посты
    6. Одобренные посты ставятся в очередь на публикацию
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

        # Хранилище планов, ожидающих одобрения: {admin_id: PendingPlan}
        self.pending_plans: Dict[int, PendingPlan] = {}

        # Статистика
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

    async def prepare_daily_plan(self, specialties: List[str] = None) -> Optional[PendingPlan]:
        """
        Подготавливает план публикации: планирование -> генерация -> проверка.
        НЕ публикует. Возвращает план для одобрения человеком.

        Args:
            specialties: Список специализаций (по умолчанию — все)

        Returns:
            PendingPlan с подготовленными постами или None при ошибке
        """
        if not self.enabled:
            logger.info("⏸️ AutoPublisher отключён")
            return None

        logger.info("=" * 60)
        logger.info("📋 ПОДГОТОВКА ПЛАНА ПУБЛИКАЦИЙ")
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
                return None

            plan = plan_result["plan"]
            self.last_plan = plan
            posts_plan = plan.get("posts", [])
            reasoning = plan.get("reasoning", "")

            logger.info(f"📋 План: {len(posts_plan)} постов")
            self.stats["total_planned"] += len(posts_plan)

            # 2. Генерируем и проверяем каждый пост
            prepared_posts: List[PreparedPost] = []

            for i, post_plan in enumerate(posts_plan):
                logger.info(f"--- Пост {i + 1}/{len(posts_plan)} ---")

                try:
                    prepared = await self._prepare_single_post(i, post_plan)
                    if prepared:
                        prepared_posts.append(prepared)
                    else:
                        logger.warning(f"Пост {i + 1} не удалось подготовить")
                except Exception as e:
                    logger.error(f"Ошибка подготовки поста {i + 1}: {e}")

                # Пауза между генерациями
                if i < len(posts_plan) - 1:
                    await asyncio.sleep(5)

            if not prepared_posts:
                logger.warning("Не удалось подготовить ни одного поста")
                return None

            # 3. Формируем PendingPlan
            pending = PendingPlan(
                plan_id=str(uuid.uuid4())[:8],
                created_at=datetime.now(),
                posts=prepared_posts,
                reasoning=reasoning
            )

            logger.info(
                f"✅ План подготовлен: {len(prepared_posts)} постов "
                f"(plan_id: {pending.plan_id})"
            )

            return pending

        except Exception as e:
            logger.error(f"Критическая ошибка подготовки: {e}", exc_info=True)
            return None

    async def _prepare_single_post(self, index: int, post_plan: Dict) -> Optional[PreparedPost]:
        """
        Подготавливает один пост: генерация + проверка безопасности.
        """
        specialty = post_plan.get("specialty", "")
        topic = post_plan.get("topic", "")
        post_type = post_plan.get("post_type", "клинрекомендации")
        publish_time_str = post_plan.get("publish_time", "09:00")

        specialty_config = get_specialty_config(specialty)
        if not specialty_config:
            logger.warning(f"Неизвестная специализация: {specialty}")
            return None

        logger.info(f"📝 Генерация: [{specialty}] {topic}")

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

                gen_result = await self.generator.execute(news=news, channel=channel)

                if gen_result["success"]:
                    content = gen_result["content"]
                    self.stats["total_generated"] += 1
                    break
                else:
                    logger.warning(f"Попытка {attempt + 1}: {gen_result.get('error')}")
            except Exception as e:
                logger.warning(f"Попытка {attempt + 1}: {e}")

            if attempt < self.max_retries:
                await asyncio.sleep(3)

        if not content:
            logger.error(f"Не удалось сгенерировать: {topic}")
            return None

        # --- Проверка безопасности ---
        safety_zone = "green"
        safety_severity = "safe"
        safety_issues = []
        safety_recommendations = []

        try:
            safety_result = await self.safety.execute(
                content=content,
                specialty=specialty,
                channel_name=specialty_config["name"]
            )

            if safety_result["success"]:
                is_safe = safety_result.get("is_safe", False)
                safety_severity = safety_result.get("severity", "unknown")
                safety_issues = safety_result.get("issues", [])
                safety_recommendations = safety_result.get("recommendations", [])

                if is_safe and safety_severity == "safe":
                    safety_zone = "green"
                elif safety_severity in ("low", "medium"):
                    safety_zone = "yellow"
                else:
                    safety_zone = "red"
        except Exception as e:
            logger.warning(f"Ошибка проверки безопасности: {e}")
            safety_zone = "yellow"
            safety_issues = ["Не удалось выполнить проверку безопасности"]

        return PreparedPost(
            index=index,
            specialty=specialty,
            channel_id=normalize_channel_id(specialty_config["channel"]),
            channel_name=specialty_config["name"],
            channel_emoji=specialty_config["emoji"],
            channel_link=specialty_config["link"],
            topic=topic,
            post_type=post_type,
            publish_time=publish_time_str,
            content=content,
            safety_zone=safety_zone,
            safety_severity=safety_severity,
            safety_issues=safety_issues,
            safety_recommendations=safety_recommendations
        )

    async def regenerate_post(self, plan_id: str, post_index: int, comment: str, admin_id: int) -> bool:
        """
        Перегенерирует конкретный пост из плана с учётом комментария.

        Args:
            plan_id: ID плана
            post_index: Индекс поста в плане
            comment: Комментарий пользователя (что исправить)
            admin_id: ID админа

        Returns:
            True если успешно перегенерирован
        """
        pending = self.pending_plans.get(admin_id)
        if not pending or pending.plan_id != plan_id:
            return False

        if post_index < 0 or post_index >= len(pending.posts):
            return False

        post = pending.posts[post_index]
        if post.removed:
            return False

        logger.info(f"🔄 Перегенерация поста {post_index + 1}: {comment}")

        specialty_config = get_specialty_config(post.specialty)
        if not specialty_config:
            return False

        try:
            # Генерируем с учётом комментария
            news = {
                "title": post.topic,
                "content": (
                    f"Тема: {post.topic}. Тип поста: {post.post_type}.\n\n"
                    f"ВАЖНО — учти комментарий редактора: {comment}"
                ),
                "source_name": "AI-планировщик",
                "source_url": ""
            }
            channel = {
                "name": specialty_config["name"],
                "specialty": post.specialty,
                "emoji": specialty_config["emoji"],
                "link": specialty_config["link"]
            }

            gen_result = await self.generator.execute(news=news, channel=channel)
            if not gen_result["success"]:
                return False

            new_content = gen_result["content"]

            # Повторная проверка безопасности
            safety_result = await self.safety.execute(
                content=new_content,
                specialty=post.specialty,
                channel_name=specialty_config["name"]
            )

            if safety_result["success"]:
                is_safe = safety_result.get("is_safe", False)
                post.safety_severity = safety_result.get("severity", "unknown")
                post.safety_issues = safety_result.get("issues", [])
                post.safety_recommendations = safety_result.get("recommendations", [])

                if is_safe and post.safety_severity == "safe":
                    post.safety_zone = "green"
                elif post.safety_severity in ("low", "medium"):
                    post.safety_zone = "yellow"
                else:
                    post.safety_zone = "red"

            post.content = new_content
            logger.info(f"✅ Пост {post_index + 1} перегенерирован")
            return True

        except Exception as e:
            logger.error(f"Ошибка перегенерации: {e}")
            return False

    async def approve_and_schedule(self, admin_id: int) -> Dict[str, Any]:
        """
        Одобряет план и ставит все активные посты в очередь.

        Args:
            admin_id: ID админа

        Returns:
            Dict с результатами: scheduled_count, failed_count
        """
        pending = self.pending_plans.get(admin_id)
        if not pending:
            return {"success": False, "error": "Нет плана для одобрения"}

        logger.info(f"✅ Одобрение плана {pending.plan_id}: {pending.total_active} постов")

        scheduled_count = 0
        failed_count = 0

        for post in pending.active_posts:
            try:
                # Определяем время
                try:
                    hour, minute = map(int, post.publish_time.split(":"))
                except ValueError:
                    hour, minute = 9, 0

                now = datetime.now()
                scheduled_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)

                if scheduled_time <= now:
                    scheduled_time = now + timedelta(minutes=5)

                task_id = str(uuid.uuid4())[:8]

                task = PublishTask(
                    task_id=task_id,
                    channel_id=post.channel_id,
                    text=post.content,
                    scheduled_time=scheduled_time,
                    status=TaskStatus.SCHEDULED if scheduled_time > now + timedelta(minutes=1) else TaskStatus.PENDING,
                    created_by=admin_id
                )

                await self.telegram_bot.add_task(task)
                scheduled_count += 1

                logger.info(f"⏰ Пост запланирован: {task_id} -> {post.channel_name} в {scheduled_time.strftime('%H:%M')}")

            except Exception as e:
                failed_count += 1
                logger.error(f"Ошибка планирования поста {post.index + 1}: {e}")

        self.stats["total_published"] += scheduled_count
        self.stats["total_failed"] += failed_count

        # Удаляем план из ожидающих
        del self.pending_plans[admin_id]

        return {
            "success": True,
            "scheduled_count": scheduled_count,
            "failed_count": failed_count,
            "plan_id": pending.plan_id
        }

    async def run_daily_cycle(self, specialties: List[str] = None):
        """
        Запускает цикл: подготовка + отправка ленты всем админам.
        Вызывается планировщиком ежедневно.
        """
        if not self.enabled:
            logger.info("⏸️ AutoPublisher отключён, пропуск цикла")
            return

        pending = await self.prepare_daily_plan(specialties)
        if not pending:
            await self._notify_admins("Не удалось подготовить план публикаций.")
            return

        # Отправляем ленту каждому админу для одобрения
        from src.core.config import config
        for admin_id in config.ADMIN_IDS:
            self.pending_plans[admin_id] = pending
            try:
                await self._send_approval_feed(admin_id, pending)
            except Exception as e:
                logger.error(f"Ошибка отправки ленты админу {admin_id}: {e}")

    async def _send_approval_feed(self, admin_id: int, pending: PendingPlan):
        """Отправляет ленту постов админу для одобрения"""
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

        feed_text = self._build_feed_text(pending)

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text=f"✅ Одобрить все ({pending.total_active} постов)",
                callback_data=f"ap_approve_{pending.plan_id}"
            )],
            [InlineKeyboardButton(
                text="✏️ Дать комментарий к посту",
                callback_data=f"ap_edit_{pending.plan_id}"
            )],
            [InlineKeyboardButton(
                text="🗑️ Удалить пост из плана",
                callback_data=f"ap_remove_{pending.plan_id}"
            )],
            [InlineKeyboardButton(
                text="👁️ Посмотреть пост целиком",
                callback_data=f"ap_view_{pending.plan_id}"
            )],
            [InlineKeyboardButton(
                text="❌ Отменить весь план",
                callback_data=f"ap_cancel_{pending.plan_id}"
            )]
        ])

        msg = await self.telegram_bot.bot.send_message(
            admin_id, feed_text, parse_mode="HTML", reply_markup=keyboard
        )
        pending.message_id = msg.message_id

    def _build_feed_text(self, pending: PendingPlan) -> str:
        """Формирует текст ленты постов для одобрения"""
        zone_icons = {"green": "🟢", "yellow": "🟡", "red": "🔴"}

        import html as html_mod

        header = (
            f"📋 <b>План публикаций на сегодня</b>\n"
            f"🆔 <code>{pending.plan_id}</code>\n"
            f"💡 <i>{html_mod.escape(pending.reasoning[:200])}</i>\n\n"
        )

        posts_text = ""
        for post in pending.posts:
            if post.removed:
                posts_text += (
                    f"<s>#{post.index + 1}</s> 🗑️ <i>удалён</i>\n\n"
                )
                continue

            zone_icon = zone_icons.get(post.safety_zone, "⚪")

            # Превью контента (первые 80 символов, экранированные)
            preview = post.content[:80].replace('\n', ' ')
            preview = html_mod.escape(preview)
            if len(post.content) > 80:
                preview += "..."

            issues_text = ""
            if post.safety_issues:
                # safety_issues может содержать str или dict
                str_issues = []
                for iss in post.safety_issues[:2]:
                    if isinstance(iss, dict):
                        str_issues.append(iss.get("description", iss.get("issue", str(iss))))
                    else:
                        str_issues.append(str(iss))
                issues_list = ", ".join(str_issues)
                if len(issues_list) > 100:
                    issues_list = issues_list[:100] + "..."
                issues_text = f"\n   ⚠️ <i>{html_mod.escape(issues_list)}</i>"

            posts_text += (
                f"<b>#{post.index + 1}</b> {zone_icon} {post.channel_emoji} "
                f"<b>{post.channel_name}</b>\n"
                f"   ⏰ {post.publish_time} | 📝 {html_mod.escape(post.post_type)}\n"
                f"   📌 {html_mod.escape(post.topic)}\n"
                f"   💬 <i>{preview}</i>"
                f"{issues_text}\n\n"
            )

        # Подсчёт зон
        greens = sum(1 for p in pending.active_posts if p.safety_zone == "green")
        yellows = sum(1 for p in pending.active_posts if p.safety_zone == "yellow")
        reds = sum(1 for p in pending.active_posts if p.safety_zone == "red")

        summary = (
            f"{'─' * 30}\n"
            f"📊 Итого: {pending.total_active} постов | "
            f"🟢 {greens} 🟡 {yellows} 🔴 {reds}\n\n"
            f"Одобрите план или дайте комментарии."
        )

        return header + posts_text + summary

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


__all__ = ["AutoPublisher", "PreparedPost", "PendingPlan"]
