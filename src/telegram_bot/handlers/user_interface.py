"""
Пользовательский интерфейс для создания и планирования постов
ОБНОВЛЕНО ДЛЯ MVP - красивый UX для демонстрации
"""
from datetime import datetime, timedelta
import uuid
import html

from aiogram import Router, F, types, Dispatcher
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message, CallbackQuery

from src.agents.specialty_loader import SPECIALTY_MAP, get_specialty_config
# Импорты ваших сервисов
from src.services.content_generator import ContentGeneratorService
from src.services.validator import PostValidator, logger
from src.telegram_bot.handlers.admin import cmd_stats
from src.telegram_bot.models import PublishTask, TaskStatus
from src.utils.formatters import format_for_channel
from src.utils.channel_utils import normalize_channel_id, get_channel_display_name

router = Router()

# FSM States
class PostCreation(StatesGroup):
    waiting_for_specialty = State()
    waiting_for_topic = State()
    reviewing_post = State()
    waiting_for_time = State()


class AutoPubReview(StatesGroup):
    """FSM для review автопубликации"""
    waiting_for_post_number = State()    # Ожидание номера поста (для edit/remove/view)
    waiting_for_comment = State()        # Ожидание комментария к посту


# Глобальные переменные (в production используйте dependency injection)
generator_agent = None  # Инициализируется в main.py
safety_agent = None
telegram_bot = None
auto_publisher = None


def set_agents(gen_agent, safe_agent, tg_bot, auto_pub=None):
    """Инициализация агентов из main.py"""
    global generator_agent, safety_agent, telegram_bot, auto_publisher
    generator_agent = gen_agent
    safety_agent = safe_agent
    telegram_bot = tg_bot
    auto_publisher = auto_pub


# ====================================================================================
# ГЛАВНОЕ МЕНЮ
# ====================================================================================

@router.message(Command("start"))
async def cmd_start(message: Message):
    """Стартовое меню с красивым дизайном"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✨ Создать новый пост", callback_data="new_post")],
        [InlineKeyboardButton(text="🤖 Автопубликация", callback_data="autopub_menu")],
        [InlineKeyboardButton(text="📋 Мои запланированные посты", callback_data="my_posts")],
        [InlineKeyboardButton(text="📊 Статистика", callback_data="stats")],
    ])

    await message.answer(
        "🤖 <b>AI Medical Content Bot</b>\n\n"
        "Автоматическая генерация медицинского контента\n"
        "с проверкой безопасности и умным планированием.\n\n"
        "Выберите действие:",
        parse_mode="HTML",
        reply_markup=keyboard
    )


# ====================================================================================
# СОЗДАНИЕ ПОСТА - ШАГ 1: ВЫБОР СПЕЦИАЛИЗАЦИИ
# ====================================================================================

@router.callback_query(F.data == "new_post")
async def start_post_creation(callback: CallbackQuery, state: FSMContext):
    """Начинаем создание поста - выбор специализации"""
    # Отвечаем на callback сразу
    await callback.answer()

    # Формируем клавиатуру с доступными специализациями
    keyboard_buttons = []

    for specialty, config in SPECIALTY_MAP.items():
        emoji = config['emoji']
        name = config['name']
        keyboard_buttons.append([
            InlineKeyboardButton(
                text=f"{emoji} {name}",
                callback_data=f"specialty_{specialty}"
            )
        ])

    keyboard_buttons.append([InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")])
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)

    await callback.message.edit_text(
        "🎯 <b>Шаг 1/3: Выбор специализации</b>\n\n"
        "Для какого канала создаём контент?",
        parse_mode="HTML",
        reply_markup=keyboard
    )

    await state.set_state(PostCreation.waiting_for_specialty)


@router.callback_query(F.data.startswith("specialty_"))
async def process_specialty_choice(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора специализации"""
    # Отвечаем на callback сразу
    await callback.answer()

    specialty = callback.data.replace("specialty_", "")
    config = get_specialty_config(specialty)
    
    if not config:
        await callback.answer("❌ Ошибка: специализация не найдена", show_alert=True)
        return
    
    # Сохраняем в состояние
    await state.update_data(
        specialty=specialty,
        channel=config['channel'],
        emoji=config['emoji'],
        name=config['name'],
        link=config['link']
    )
    
    await callback.message.edit_text(
        f"{config['emoji']} <b>Выбрано: {config['name']}</b>\n\n"
        f"📝 <b>Шаг 2/3: Тема для поста</b>\n\n"
        f"Введите тему или новость, на основе которой нужно создать пост.\n\n"
        f"<i>Примеры:</i>\n"
        f"• Новые рекомендации по лечению гипертонии\n"
        f"• Исследование эффективности метформина при диабете\n"
        f"• Обновление протокола ведения беременных с ГСД",
        parse_mode="HTML"
    )

    await state.set_state(PostCreation.waiting_for_topic)


# ====================================================================================
# СОЗДАНИЕ ПОСТА - ШАГ 2: ГЕНЕРАЦИЯ КОНТЕНТА
# ====================================================================================

@router.message(PostCreation.waiting_for_topic)
async def process_topic_and_generate(message: Message, state: FSMContext):
    """Получаем тему и генерируем пост с AI"""
    from aiogram.exceptions import TelegramNetworkError, TelegramAPIError

    topic = message.text
    data = await state.get_data()

    # Показываем прогресс
    progress_msg = await message.answer(
        "🤖 <b>Генерирую контент...</b>\n\n"
        "⏳ Использую AI для создания поста\n"
        "⏳ Проверяю медицинскую безопасность\n"
        "⏳ Форматирую согласно стилю канала",
        parse_mode="HTML"
    )

    async def safe_edit_progress(text: str):
        """Безопасное обновление прогресса с обработкой timeout"""
        try:
            await progress_msg.edit_text(text, parse_mode="HTML")
        except (TelegramNetworkError, TelegramAPIError) as e:
            logger.warning(f"⚠️ Не удалось обновить прогресс: {e}")
            # Продолжаем работу даже если не удалось обновить UI

    try:
        # Формируем данные для генератора
        news = {
            "title": topic,
            "content": f"Тема для поста: {topic}",
            "source_name": "Пользовательский запрос",
            "source_url": ""
        }

        channel = {
            "name": data['name'],
            "specialty": data['specialty'],
            "emoji": data['emoji'],
            "link": data['link']
        }

        # 1. Генерируем контент
        await safe_edit_progress(
            "🤖 <b>Генерирую контент...</b>\n\n"
            "✅ Анализирую тему\n"
            "⏳ Создаю структуру поста\n"
            "⏳ Проверяю медицинскую безопасность"
        )

        gen_result = await generator_agent.execute(
            news=news,
            channel=channel
        )

        if not gen_result["success"]:
            raise Exception(f"Ошибка генерации: {gen_result.get('error')}")

        post_content = gen_result["content"]

        # 2. Проверяем безопасность
        await safe_edit_progress(
            "🤖 <b>Генерирую контент...</b>\n\n"
            "✅ Анализирую тему\n"
            "✅ Создал структуру поста\n"
            "⏳ Проверяю медицинскую безопасность"
        )

        safety_result = await safety_agent.execute(
            content=post_content,
            specialty=data['specialty'],
            channel_name=data['name']
        )

        if not safety_result["success"]:
            raise Exception("Ошибка проверки безопасности")

        is_safe = safety_result.get("is_safe", False)
        severity = safety_result.get("severity", "unknown")
        issues = safety_result.get("issues", [])

        # Определяем эмодзи статуса
        if is_safe and severity == "safe":
            status_emoji = "✅"
            status_text = "БЕЗОПАСНО"
            status_color = "🟢"
        elif severity in ["low", "medium"]:
            status_emoji = "⚠️"
            status_text = "ТРЕБУЕТ ВНИМАНИЯ"
            status_color = "🟡"
        else:
            status_emoji = "❌"
            status_text = "ТРЕБУЕТ ПРАВКИ"
            status_color = "🔴"

        # Сохраняем в состояние
        await state.update_data(
            topic=topic,
            post_content=post_content,
            is_safe=is_safe,
            severity=severity,
            issues=issues
        )

        # 3. Показываем результат
        try:
            await progress_msg.delete()
        except (TelegramNetworkError, TelegramAPIError):
            pass  # Игнорируем ошибки при удалении

        preview_text = (
            f"✨ <b>Пост готов!</b>\n\n"
            f"<b>Специализация:</b> {data['emoji']} {data['name']}\n"
            f"<b>Тема:</b> {topic[:100]}{'...' if len(topic) > 100 else ''}\n\n"
            f"<b>Проверка безопасности:</b> {status_color} {status_emoji} {status_text}\n"
        )

        if issues:
            preview_text += f"<b>Замечания:</b> {len(issues)}\n"

        preview_text += f"\n{'─' * 40}\n\n{post_content}\n\n{'─' * 40}\n"

        # Кнопки действий
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🚀 Опубликовать мгновенно", callback_data="publish_now")],
            [InlineKeyboardButton(text="⏰ Запланировать публикацию", callback_data="publish_scheduled")],
            [InlineKeyboardButton(text="🔄 Сгенерировать заново", callback_data="regenerate")],
            [InlineKeyboardButton(text="❌ Отменить", callback_data="cancel")]
        ])

        await message.answer(
            preview_text,
            parse_mode="HTML",
            reply_markup=keyboard
        )

        await state.set_state(PostCreation.reviewing_post)

    except Exception as e:
        logger.error(f"Ошибка генерации: {e}")
        try:
            await progress_msg.edit_text(
                f"❌ <b>Ошибка генерации контента</b>\n\n"
                f"<code>{str(e)}</code>\n\n"
                f"Попробуйте ещё раз или измените тему.",
                parse_mode="HTML"
            )
        except (TelegramNetworkError, TelegramAPIError):
            # Если не удалось обновить, отправим новое сообщение
            await message.answer(
                f"❌ <b>Ошибка генерации контента</b>\n\n"
                f"<code>{str(e)}</code>\n\n"
                f"Попробуйте ещё раз или измените тему.",
                parse_mode="HTML"
            )
        await state.clear()


# ====================================================================================
# ПУБЛИКАЦИЯ - МГНОВЕННАЯ
# ====================================================================================

@router.callback_query(F.data == "publish_now", PostCreation.reviewing_post)
async def publish_immediately(callback: CallbackQuery, state: FSMContext):
    """Публикация поста немедленно"""
    data = await state.get_data()
    
    await callback.message.edit_text(
        "🚀 <b>Публикую пост...</b>",
        parse_mode="HTML"
    )
    
    try:
        # Создаём задачу на публикацию
        task_id = str(uuid.uuid4())[:8]
        
        task = PublishTask(
            task_id=task_id,
            channel_id=normalize_channel_id(data['channel']),
            text=data['post_content'],
            scheduled_time=datetime.now(),
            status=TaskStatus.PENDING
        )
        
        # Отправляем в очередь
        await telegram_bot.add_task(task)
        
        await callback.message.edit_text(
            f"✅ <b>Пост опубликован!</b>\n\n"
            f"📢 <b>Канал:</b> {get_channel_display_name(data['channel'], data.get('name'))}\n"
            f"🆔 <b>ID задачи:</b> <code>{task_id}</code>\n"
            f"⏰ <b>Время:</b> {datetime.now().strftime('%d.%m.%Y %H:%M')}\n\n"
            f"Пост отправлен в канал. Проверьте результат!",
            parse_mode="HTML"
        )
        
        logger.info(f"✅ Пост опубликован мгновенно в @{data['channel']}: {task_id}")
        
    except Exception as e:
        logger.error(f"Ошибка публикации: {e}")
        await callback.message.edit_text(
            f"❌ <b>Ошибка публикации</b>\n\n"
            f"<code>{str(e)}</code>",
            parse_mode="HTML"
        )
    
    await state.clear()
    await callback.answer()


# ====================================================================================
# ПУБЛИКАЦИЯ - ОТЛОЖЕННАЯ
# ====================================================================================

@router.callback_query(F.data == "publish_scheduled", PostCreation.reviewing_post)
async def schedule_publication(callback: CallbackQuery, state: FSMContext):
    """Планирование публикации"""
    
    # Предлагаем варианты времени
    now = datetime.now()
    
    options = [
        ("Через 1 час", now + timedelta(hours=1)),
        ("Через 3 часа", now + timedelta(hours=3)),
        ("Завтра в 9:00", (now + timedelta(days=1)).replace(hour=9, minute=0, second=0)),
        ("Завтра в 20:00", (now + timedelta(days=1)).replace(hour=20, minute=0, second=0)),
        ("Своё время", "custom")
    ]
    
    keyboard = []
    for text, time_option in options:
        if time_option == "custom":
            callback_data = "time_custom"
        else:
            callback_data = f"time_{time_option.isoformat()}"
        
        keyboard.append([InlineKeyboardButton(text=text, callback_data=callback_data)])
    
    keyboard.append([InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")])
    
    await callback.message.edit_text(
        "⏰ <b>Шаг 3/3: Выберите время публикации</b>\n\n"
        "Когда опубликовать пост?",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
    )
    
    await state.set_state(PostCreation.waiting_for_time)
    await callback.answer()


@router.callback_query(F.data.startswith("time_"), PostCreation.waiting_for_time)
async def process_scheduled_time(callback: CallbackQuery, state: FSMContext):
    """Обработка выбранного времени"""
    data = await state.get_data()
    
    if callback.data == "time_custom":
        # Запрашиваем ручной ввод
        await callback.message.edit_text(
            "⏰ <b>Введите время публикации</b>\n\n"
            "Формат: <code>ДД.ММ.ГГГГ ЧЧ:ММ</code>\n"
            "Пример: <code>05.02.2026 14:30</code>",
            parse_mode="HTML"
        )
        await callback.answer()
        return
    
    # Извлекаем время из callback_data
    time_str = callback.data.replace("time_", "")
    scheduled_time = datetime.fromisoformat(time_str)
    
    await callback.message.edit_text(
        "⏰ <b>Планирую публикацию...</b>",
        parse_mode="HTML"
    )
    
    try:
        # Создаём задачу
        task_id = str(uuid.uuid4())[:8]

        task = PublishTask(
            task_id=task_id,
            channel_id=normalize_channel_id(data['channel']),
            text=data['post_content'],
            scheduled_time=scheduled_time,
            status=TaskStatus.SCHEDULED
        )

        # Добавляем в очередь
        await telegram_bot.add_task(task)

        await callback.message.edit_text(
            f"⏰ <b>Пост запланирован!</b>\n\n"
            f"📢 <b>Канал:</b> {get_channel_display_name(data['channel'], data.get('name'))}\n"
            f"🆔 <b>ID задачи:</b> <code>{task_id}</code>\n"
            f"📅 <b>Время публикации:</b> {scheduled_time.strftime('%d.%m.%Y %H:%M')}\n\n"
            f"Пост будет автоматически опубликован в указанное время.",
            parse_mode="HTML"
        )
        
        logger.info(f"⏰ Пост запланирован в @{data['channel']} на {scheduled_time}: {task_id}")
        
    except Exception as e:
        logger.error(f"Ошибка планирования: {e}")
        await callback.message.edit_text(
            f"❌ <b>Ошибка планирования</b>\n\n"
            f"<code>{str(e)}</code>",
            parse_mode="HTML"
        )
    
    await state.clear()
    await callback.answer()


@router.message(PostCreation.waiting_for_time)
async def process_custom_time(message: Message, state: FSMContext):
    """Обработка ручного ввода времени"""
    data = await state.get_data()
    
    try:
        # Парсим время
        scheduled_time = datetime.strptime(message.text, "%d.%m.%Y %H:%M")
        
        # Проверяем, что время в будущем
        if scheduled_time <= datetime.now():
            await message.answer(
                "❌ Время должно быть в будущем!",
                parse_mode="HTML"
            )
            return
        
        # Создаём задачу
        task_id = str(uuid.uuid4())[:8]

        task = PublishTask(
            task_id=task_id,
            channel_id=normalize_channel_id(data['channel']),
            text=data['post_content'],
            scheduled_time=scheduled_time,
            status=TaskStatus.SCHEDULED
        )

        await telegram_bot.add_task(task)

        await message.answer(
            f"⏰ <b>Пост запланирован!</b>\n\n"
            f"📢 <b>Канал:</b> {get_channel_display_name(data['channel'], data.get('name'))}\n"
            f"🆔 <b>ID задачи:</b> <code>{task_id}</code>\n"
            f"📅 <b>Время публикации:</b> {scheduled_time.strftime('%d.%m.%Y %H:%M')}\n\n"
            f"Пост будет автоматически опубликован в указанное время.",
            parse_mode="HTML"
        )
        
        await state.clear()
        
    except ValueError:
        await message.answer(
            "❌ <b>Неверный формат!</b>\n\n"
            "Используйте: <code>ДД.ММ.ГГГГ ЧЧ:ММ</code>\n"
            "Пример: <code>05.02.2026 14:30</code>",
            parse_mode="HTML"
        )


# ====================================================================================
# РЕГЕНЕРАЦИЯ
# ====================================================================================

@router.callback_query(F.data == "regenerate", PostCreation.reviewing_post)
async def regenerate_post(callback: CallbackQuery, state: FSMContext):
    """Регенерация поста"""
    # Отвечаем на callback сразу, чтобы не истек таймаут
    await callback.answer()

    await callback.message.edit_text(
        "🔄 <b>Генерирую новый вариант...</b>",
        parse_mode="HTML"
    )

    data = await state.get_data()

    # Повторяем генерацию
    await process_topic_and_generate(callback.message, state)


# ====================================================================================
# МОИ ПОСТЫ
# ====================================================================================

@router.callback_query(F.data == "my_posts")
async def show_my_posts(callback: CallbackQuery):
    """Список запланированных постов"""
    
    stats = telegram_bot.get_stats()
    active_tasks = stats.get("active_tasks", 0)
    
    await callback.message.edit_text(
        f"📋 <b>Запланированные посты</b>\n\n"
        f"Активных задач: {active_tasks}\n\n"
        f"<i>Здесь будет отображаться список ваших запланированных постов</i>",
        parse_mode="HTML"
    )
    await callback.answer()


# ====================================================================================
# ОТМЕНА
# ====================================================================================

@router.callback_query(F.data == "cancel")
async def cancel_action(callback: CallbackQuery, state: FSMContext):
    """Отмена действия"""
    await state.clear()
    await callback.message.edit_text(
        "❌ Действие отменено.\n\n"
        "Используйте /start для возврата в главное меню.",
        parse_mode="HTML"
    )
    await callback.answer()


# ====================================================================================
# ОСТАЛЬНЫЕ КОМАНДЫ И HANDLERS (ДЛЯ setup_handlers)
# ====================================================================================

@router.message(Command("new_post"))
async def cmd_new_post(message: Message):
    """Команда /new_post"""
    await cmd_start(message)


@router.message(Command("queue"))
async def cmd_queue(message: Message):
    """Команда /queue - детальный просмотр очереди публикаций"""
    if not telegram_bot:
        await message.answer("❌ Бот не инициализирован", parse_mode="HTML")
        return

    try:
        # Получаем статистику
        stats = telegram_bot.get_stats()

        # Получаем запланированные посты
        upcoming = await telegram_bot.get_upcoming_posts(limit=10)

        queue_text = f"""📋 <b>Очередь публикаций</b>

📊 <b>Статистика:</b>
• Ожидают: {stats['pending']}
• Запланировано: {stats['scheduled']}
• Выполнено: {stats['completed']}
• Ошибок: {stats['failed']}

"""

        if upcoming:
            queue_text += "⏰ <b>Запланированные посты:</b>\n\n"
            for i, task in enumerate(upcoming, 1):
                time_str = task.scheduled_time.strftime('%d.%m.%Y %H:%M')

                # task.status уже строка из-за use_enum_values = True
                status_value = task.status if isinstance(task.status, str) else task.status.value
                status_emoji = {
                    "pending": "🟡",
                    "scheduled": "⏰",
                    "processing": "🔄",
                    "completed": "✅",
                    "failed": "❌",
                    "cancelled": "🚫"
                }.get(status_value, "❓")

                channel_display = task.channel_id
                if task.channel_id.startswith('-'):
                    channel_display = "Приватный канал"
                elif not task.channel_id.startswith('@'):
                    channel_display = f"@{task.channel_id}"

                # Экранируем HTML теги в тексте поста для безопасного отображения
                text_preview = task.text[:50] + "..." if len(task.text) > 50 else task.text
                text_preview = text_preview.replace('\n', ' ')
                text_preview = html.escape(text_preview)

                queue_text += f"{i}. {status_emoji} <b>{time_str}</b>\n"
                queue_text += f"   📢 {channel_display}\n"
                queue_text += f"   📝 {text_preview}\n"
                queue_text += f"   🆔 <code>{task.task_id}</code>\n\n"
        else:
            queue_text += "<i>Нет запланированных публикаций</i>"

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✨ Создать новый пост", callback_data="new_post")],
            [InlineKeyboardButton(text="🔄 Обновить", callback_data="refresh_queue")],
            [InlineKeyboardButton(text="◀️ Главное меню", callback_data="back_to_menu")]
        ])

        await message.answer(
            queue_text,
            parse_mode="HTML",
            reply_markup=keyboard
        )

    except Exception as e:
        logger.error(f"Ошибка в /queue: {e}")
        await message.answer(
            f"❌ <b>Ошибка получения очереди</b>\n\n<code>{str(e)}</code>",
            parse_mode="HTML"
        )


@router.message(Command("stats"))
async def cmd_stats(message: Message):
    """Команда /stats - статистика"""
    if not telegram_bot:
        await message.answer("❌ Бот не инициализирован", parse_mode="HTML")
        return

    try:
        stats = telegram_bot.get_stats()

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Обновить", callback_data="stats")],
            [InlineKeyboardButton(text="◀️ Главное меню", callback_data="back_to_menu")]
        ])

        stats_text = f"""📊 <b>Статистика бота</b>

📬 <b>Очередь:</b>
• Ожидают: {stats['pending']}
• Запланировано: {stats['scheduled']}

✅ <b>Выполнено:</b> {stats['completed']}
❌ <b>Ошибок:</b> {stats['failed']}

📈 <b>Success Rate:</b> {stats['success_rate']}%
📊 <b>Всего опубликовано:</b> {stats['total_published']}
"""

        await message.answer(
            stats_text,
            parse_mode="HTML",
            reply_markup=keyboard
        )

    except Exception as e:
        logger.error(f"Ошибка в /stats: {e}")
        await message.answer(
            f"❌ <b>Ошибка получения статистики</b>\n\n<code>{str(e)}</code>",
            parse_mode="HTML"
        )


@router.message(Command("scheduler"))
async def cmd_scheduler(message: Message):
    """Команда /scheduler - управление планировщиком"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⏰ Планировщик", callback_data="scheduler")],
        [InlineKeyboardButton(text="◀️ Главное меню", callback_data="back_to_menu")]
    ])

    await message.answer(
        "⏰ <b>Планировщик задач</b>\n\n"
        "Автоматическая публикация: ⏸️ <b>ПАУЗА</b>\n\n"
        "Функция в разработке.",
        parse_mode="HTML",
        reply_markup=keyboard
    )


# ====================================================================================
# CALLBACK HANDLERS
# ====================================================================================

@router.callback_query(F.data == "my_posts")
async def handle_view_queue(callback: CallbackQuery):
    """Обработка кнопки 'Мои посты'"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✨ Создать новый пост", callback_data="new_post")],
        [InlineKeyboardButton(text="◀️ Главное меню", callback_data="back_to_menu")]
    ])

    await callback.message.edit_text(
        "📋 <b>Запланированные посты</b>\n\n"
        "Пока нет запланированных публикаций.\n\n"
        "Создайте первый пост!",
        parse_mode="HTML",
        reply_markup=keyboard
    )
    await callback.answer()


@router.callback_query(F.data == "stats")
async def handle_view_stats(callback: CallbackQuery):
    """Обработка кнопки 'Статистика'"""
    if not telegram_bot:
        await callback.answer("❌ Бот не инициализирован", show_alert=True)
        return

    try:
        stats = telegram_bot.get_stats()

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📋 Мои посты", callback_data="my_posts")],
            [InlineKeyboardButton(text="🔄 Обновить", callback_data="stats")],
            [InlineKeyboardButton(text="◀️ Главное меню", callback_data="back_to_menu")]
        ])

        stats_text = f"""📊 <b>Статистика бота</b>

📬 <b>Очередь:</b>
• Ожидают: {stats['pending']}
• Запланировано: {stats['scheduled']}

✅ <b>Выполнено:</b> {stats['completed']}
❌ <b>Ошибок:</b> {stats['failed']}

📈 <b>Success Rate:</b> {stats['success_rate']}%
📊 <b>Всего опубликовано:</b> {stats['total_published']}
"""

        await callback.message.edit_text(
            stats_text,
            parse_mode="HTML",
            reply_markup=keyboard
        )
        await callback.answer()

    except Exception as e:
        logger.error(f"Ошибка в handle_view_stats: {e}")
        await callback.answer(f"❌ Ошибка получения статистики", show_alert=True)


@router.callback_query(F.data == "scheduler")
async def handle_scheduler(callback: CallbackQuery):
    """Обработка кнопки 'Планировщик'"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✨ Создать новый пост", callback_data="new_post")],
        [InlineKeyboardButton(text="◀️ Главное меню", callback_data="back_to_menu")]
    ])

    await callback.message.edit_text(
        "⏰ <b>Планировщик</b>\n\n"
        "Автопубликация: ⏸️ <b>ПАУЗА</b>\n\n"
        "Функция в разработке.",
        parse_mode="HTML",
        reply_markup=keyboard
    )
    await callback.answer()


@router.callback_query(F.data == "back_to_menu")
async def handle_back_to_menu(callback: CallbackQuery):
    """Возврат в главное меню"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✨ Создать новый пост", callback_data="new_post")],
        [InlineKeyboardButton(text="🤖 Автопубликация", callback_data="autopub_menu")],
        [InlineKeyboardButton(text="📋 Мои запланированные посты", callback_data="my_posts")],
        [InlineKeyboardButton(text="📊 Статистика", callback_data="stats")],
    ])

    await callback.message.edit_text(
        "🤖 <b>AI Medical Content Bot</b>\n\n"
        "Выберите действие:",
        parse_mode="HTML",
        reply_markup=keyboard
    )
    await callback.answer()


@router.callback_query(F.data == "autopub_menu")
async def handle_autopub_menu(callback: CallbackQuery):
    """Обработка кнопки автопубликации из меню"""
    if not auto_publisher:
        await callback.answer("❌ AutoPublisher не инициализирован", show_alert=True)
        return

    ap_stats = auto_publisher.get_stats()
    status_emoji = "▶️" if ap_stats["enabled"] else "⏸️"
    status_text = "ВКЛЮЧЕНА" if ap_stats["enabled"] else "ВЫКЛЮЧЕНА"

    # Проверяем, есть ли ожидающий план
    admin_id = callback.from_user.id
    has_pending = admin_id in auto_publisher.pending_plans

    buttons = [
        [InlineKeyboardButton(
            text="⏸️ Выключить" if ap_stats["enabled"] else "▶️ Включить",
            callback_data="autopub_toggle"
        )],
        [InlineKeyboardButton(text="🚀 Сгенерировать план", callback_data="autopub_run_now")],
    ]

    if has_pending:
        pending = auto_publisher.pending_plans[admin_id]
        buttons.insert(1, [InlineKeyboardButton(
            text=f"📋 Открыть ожидающий план ({pending.total_active} постов)",
            callback_data=f"ap_back_{pending.plan_id}"
        )])

    buttons.append([InlineKeyboardButton(text="◀️ Главное меню", callback_data="back_to_menu")])
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

    text = (
        f"🤖 <b>Автопубликация</b> {status_emoji} {status_text}\n\n"
        f"<b>Как это работает:</b>\n"
        f"1. AI составляет план публикаций\n"
        f"2. Генерирует контент и проверяет безопасность\n"
        f"3. Вам приходит лента с зонами 🟢🟡🔴\n"
        f"4. Вы одобряете / правите / удаляете\n"
        f"5. Одобренные посты публикуются автоматически\n\n"
        f"📊 <b>Статистика:</b>\n"
        f"• Запусков: {ap_stats['total_runs']}\n"
        f"• Опубликовано: {ap_stats['total_published']}\n"
        f"• Ошибки: {ap_stats['total_failed']}\n\n"
        f"⏰ Последний запуск: {ap_stats['last_run']}"
    )

    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)
    except Exception:
        pass
    await callback.answer()


@router.callback_query(F.data == "refresh_queue")
async def handle_refresh_queue(callback: CallbackQuery):
    """Обновление очереди публикаций"""
    from aiogram.exceptions import TelegramBadRequest

    if not telegram_bot:
        await callback.answer("❌ Бот не инициализирован", show_alert=True)
        return

    try:
        # Получаем статистику
        stats = telegram_bot.get_stats()

        # Получаем запланированные посты
        upcoming = await telegram_bot.get_upcoming_posts(limit=10)

        queue_text = f"""📋 <b>Очередь публикаций</b>

📊 <b>Статистика:</b>
• Ожидают: {stats['pending']}
• Запланировано: {stats['scheduled']}
• Выполнено: {stats['completed']}
• Ошибок: {stats['failed']}

"""

        if upcoming:
            queue_text += "⏰ <b>Запланированные посты:</b>\n\n"
            for i, task in enumerate(upcoming, 1):
                time_str = task.scheduled_time.strftime('%d.%m.%Y %H:%M')

                # task.status уже строка из-за use_enum_values = True
                status_value = task.status if isinstance(task.status, str) else task.status.value
                status_emoji = {
                    "pending": "🟡",
                    "scheduled": "⏰",
                    "processing": "🔄",
                    "completed": "✅",
                    "failed": "❌",
                    "cancelled": "🚫"
                }.get(status_value, "❓")

                channel_display = task.channel_id
                if task.channel_id.startswith('-'):
                    channel_display = "Приватный канал"
                elif not task.channel_id.startswith('@'):
                    channel_display = f"@{task.channel_id}"

                # Экранируем HTML теги в тексте поста для безопасного отображения
                text_preview = task.text[:50] + "..." if len(task.text) > 50 else task.text
                text_preview = text_preview.replace('\n', ' ')
                text_preview = html.escape(text_preview)

                queue_text += f"{i}. {status_emoji} <b>{time_str}</b>\n"
                queue_text += f"   📢 {channel_display}\n"
                queue_text += f"   📝 {text_preview}\n"
                queue_text += f"   🆔 <code>{task.task_id}</code>\n\n"
        else:
            queue_text += "<i>Нет запланированных публикаций</i>"

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✨ Создать новый пост", callback_data="new_post")],
            [InlineKeyboardButton(text="🔄 Обновить", callback_data="refresh_queue")],
            [InlineKeyboardButton(text="◀️ Главное меню", callback_data="back_to_menu")]
        ])

        await callback.message.edit_text(
            queue_text,
            parse_mode="HTML",
            reply_markup=keyboard
        )

        await callback.answer("✅ Обновлено")

    except TelegramBadRequest as e:
        # Обрабатываем случай когда сообщение не изменилось
        if "message is not modified" in str(e).lower():
            await callback.answer("✅ Очередь актуальна", show_alert=False)
        else:
            logger.error(f"Telegram error в refresh_queue: {e}")
            await callback.answer(f"❌ Ошибка: {str(e)}", show_alert=True)

    except Exception as e:
        logger.error(f"Ошибка в refresh_queue: {e}")
        await callback.answer(f"❌ Ошибка обновления", show_alert=True)


@router.callback_query(F.data == "cancel")
async def handle_cancel(callback: CallbackQuery, state: FSMContext):
    """Отмена операции"""
    await state.clear()
    await handle_back_to_menu(callback)


@router.callback_query(F.data == "regenerate")
async def handle_regenerate(callback: CallbackQuery, state: FSMContext):
    """Перегенерация поста"""
    data = await state.get_data()
    await callback.message.edit_text(
        f"🔄 <b>Перегенерирую пост для темы:</b>\n\n"
        f"{data.get('topic', 'Неизвестная тема')}\n\n"
        f"⏳ Генерирую новый вариант...",
        parse_mode="HTML"
    )
    # Повторяем генерацию (логика из process_topic_and_generate)
    await callback.answer()


# ====================================================================================
# ОПРЕДЕЛЕНИЕ ID КАНАЛА
# ====================================================================================

@router.message(Command("chatid"))
async def cmd_chatid(message: Message):
    """
    Команда /chatid — помощь в определении ID канала.
    Два режима:
    1. /chatid @username — резолвит username через Bot API
    2. Пересланное сообщение из канала — извлекает chat.id
    """
    args = message.text.strip().split(maxsplit=1)

    if len(args) > 1:
        # Пользователь передал username: /chatid @profendocrinologist
        username = args[1].strip()
        if not username.startswith("@"):
            username = f"@{username}"

        try:
            chat = await telegram_bot.bot.get_chat(username)
            await message.answer(
                f"✅ <b>Канал найден</b>\n\n"
                f"📢 <b>Название:</b> {html.escape(chat.title or 'N/A')}\n"
                f"🆔 <b>ID:</b> <code>{chat.id}</code>\n"
                f"👤 <b>Username:</b> @{chat.username or 'нет'}\n\n"
                f"Используйте ID <code>{chat.id}</code> в channels.json",
                parse_mode="HTML"
            )
        except Exception as e:
            await message.answer(
                f"❌ <b>Не удалось найти канал</b> {html.escape(username)}\n\n"
                f"<code>{html.escape(str(e))}</code>\n\n"
                f"Убедитесь, что бот добавлен в канал как администратор.",
                parse_mode="HTML"
            )
        return

    # Без аргументов — инструкция
    await message.answer(
        "🔍 <b>Определение ID канала</b>\n\n"
        "<b>Способ 1:</b> Укажите username канала:\n"
        "<code>/chatid @profendocrinologist</code>\n\n"
        "<b>Способ 2:</b> Перешлите любое сообщение из канала в этот чат — "
        "бот автоматически определит ID.\n\n"
        "<b>Способ 3:</b> /resolve_channels — проверить все настроенные каналы",
        parse_mode="HTML"
    )


@router.message(Command("resolve_channels"))
async def cmd_resolve_channels(message: Message):
    """Резолвит все каналы из SPECIALTY_MAP и показывает их реальные ID"""
    results = []

    for specialty, config in SPECIALTY_MAP.items():
        channel = config["channel"]
        emoji = config["emoji"]
        name = config["name"]

        try:
            chat_id = channel if channel.startswith("-") else f"@{channel}"
            chat = await telegram_bot.bot.get_chat(chat_id)
            results.append(
                f"{emoji} <b>{name}</b>\n"
                f"   Настроено: <code>{channel}</code>\n"
                f"   Реальный ID: <code>{chat.id}</code>\n"
                f"   Название: {html.escape(chat.title or 'N/A')}\n"
                f"   ✅ Бот имеет доступ"
            )
        except Exception as e:
            results.append(
                f"{emoji} <b>{name}</b>\n"
                f"   Настроено: <code>{channel}</code>\n"
                f"   ❌ Нет доступа: {html.escape(str(e)[:80])}"
            )

    text = "🔍 <b>Проверка каналов</b>\n\n" + "\n\n".join(results)
    text += (
        "\n\n<i>Для каналов без доступа: добавьте бота как администратора "
        "и используйте /chatid @username или перешлите сообщение из канала</i>"
    )

    await message.answer(text, parse_mode="HTML")


@router.message(F.forward_from_chat)
async def handle_forwarded_from_channel(message: Message):
    """Обработка пересланного сообщения из канала — показывает ID"""
    chat = message.forward_from_chat
    if chat.type in ("channel", "supergroup"):
        await message.answer(
            f"📢 <b>Информация о канале</b>\n\n"
            f"<b>Название:</b> {html.escape(chat.title or 'N/A')}\n"
            f"🆔 <b>ID:</b> <code>{chat.id}</code>\n"
            f"👤 <b>Username:</b> @{chat.username or 'нет'}\n\n"
            f"Используйте этот ID в channels.json и specialty_loader.py:\n"
            f"<code>\"channel\": \"{chat.id}\"</code>",
            parse_mode="HTML"
        )


# ====================================================================================
# АВТОПУБЛИКАЦИЯ - УПРАВЛЕНИЕ И ОДОБРЕНИЕ
# ====================================================================================

@router.message(Command("autopublish"))
async def cmd_autopublish(message: Message):
    """Команда /autopublish - управление автоматической публикацией"""
    if not auto_publisher:
        await message.answer("❌ <b>AutoPublisher не инициализирован</b>", parse_mode="HTML")
        return

    ap_stats = auto_publisher.get_stats()
    status_emoji = "▶️" if ap_stats["enabled"] else "⏸️"
    status_text = "ВКЛЮЧЕНА" if ap_stats["enabled"] else "ВЫКЛЮЧЕНА"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="⏸️ Выключить" if ap_stats["enabled"] else "▶️ Включить",
            callback_data="autopub_toggle"
        )],
        [InlineKeyboardButton(text="🚀 Запустить сейчас", callback_data="autopub_run_now")],
        [InlineKeyboardButton(text="◀️ Главное меню", callback_data="back_to_menu")]
    ])

    text = (
        f"🤖 <b>Автопубликация</b> {status_emoji} {status_text}\n\n"
        f"📊 <b>Статистика:</b>\n"
        f"• Запусков: {ap_stats['total_runs']}\n"
        f"• Запланировано: {ap_stats['total_planned']}\n"
        f"• Сгенерировано: {ap_stats['total_generated']}\n"
        f"• Опубликовано: {ap_stats['total_published']}\n"
        f"• Отклонено (безопасность): {ap_stats['total_safety_rejected']}\n"
        f"• Ошибки: {ap_stats['total_failed']}\n\n"
        f"⏰ Последний запуск: {ap_stats['last_run']}\n"
        f"📋 Постов в последнем плане: {ap_stats['last_plan_posts']}"
    )

    await message.answer(text, parse_mode="HTML", reply_markup=keyboard)


@router.callback_query(F.data == "autopub_toggle")
async def handle_autopub_toggle(callback: CallbackQuery):
    """Вкл/выкл автопубликации"""
    if not auto_publisher:
        await callback.answer("❌ AutoPublisher не инициализирован", show_alert=True)
        return

    if auto_publisher.enabled:
        auto_publisher.disable()
        await callback.answer("⏸️ Автопубликация выключена")
    else:
        auto_publisher.enable()
        await callback.answer("▶️ Автопубликация включена")

    # Обновляем сообщение — вызываем тот же autopub_menu
    await handle_autopub_menu(callback)


@router.callback_query(F.data == "autopub_run_now")
async def handle_autopub_run_now(callback: CallbackQuery):
    """Запуск подготовки плана: генерация -> проверка -> лента для одобрения"""
    if not auto_publisher:
        await callback.answer("❌ AutoPublisher не инициализирован", show_alert=True)
        return

    await callback.answer("🚀 Запускаю подготовку плана...")

    await callback.message.edit_text(
        "🤖 <b>Подготовка плана публикаций...</b>\n\n"
        "⏳ AI-планировщик составляет план\n"
        "⏳ Генерация контента для каждого поста\n"
        "⏳ Проверка безопасности\n\n"
        "Это займёт 1-3 минуты. Вы получите ленту постов для одобрения.",
        parse_mode="HTML"
    )

    # Запускаем в фоне
    import asyncio
    asyncio.create_task(auto_publisher.run_daily_cycle())


# --- Одобрение плана ---

@router.callback_query(F.data.startswith("ap_approve_"))
async def handle_ap_approve(callback: CallbackQuery):
    """Одобрить все посты и запланировать публикацию"""
    plan_id = callback.data.replace("ap_approve_", "")
    admin_id = callback.from_user.id

    pending = auto_publisher.pending_plans.get(admin_id)
    if not pending or pending.plan_id != plan_id:
        await callback.answer("❌ План не найден или устарел", show_alert=True)
        return

    await callback.answer("✅ Одобряю и планирую...")

    result = await auto_publisher.approve_and_schedule(admin_id)

    if result["success"]:
        await callback.message.edit_text(
            f"✅ <b>План одобрен и запланирован!</b>\n\n"
            f"📋 Запланировано: {result['scheduled_count']} постов\n"
            f"❌ Ошибки: {result['failed_count']}\n\n"
            f"Посты будут автоматически опубликованы в указанное время.",
            parse_mode="HTML"
        )
    else:
        await callback.message.edit_text(
            f"❌ <b>Ошибка:</b> {result.get('error')}",
            parse_mode="HTML"
        )


# --- Редактирование поста (комментарий) ---

@router.callback_query(F.data.startswith("ap_edit_"))
async def handle_ap_edit_start(callback: CallbackQuery, state: FSMContext):
    """Начало редактирования — запрос номера поста"""
    plan_id = callback.data.replace("ap_edit_", "")
    admin_id = callback.from_user.id

    pending = auto_publisher.pending_plans.get(admin_id)
    if not pending or pending.plan_id != plan_id:
        await callback.answer("❌ План не найден", show_alert=True)
        return

    active = pending.active_posts
    if not active:
        await callback.answer("Нет активных постов", show_alert=True)
        return

    # Формируем кнопки с номерами постов
    buttons = []
    for post in active:
        zone_icons = {"green": "🟢", "yellow": "🟡", "red": "🔴"}
        zone = zone_icons.get(post.safety_zone, "⚪")
        btn_text = f"#{post.index + 1} {zone} {post.channel_emoji} {post.topic[:30]}"
        buttons.append([InlineKeyboardButton(
            text=btn_text,
            callback_data=f"ap_editpost_{plan_id}_{post.index}"
        )])
    buttons.append([InlineKeyboardButton(text="◀️ Назад к плану", callback_data=f"ap_back_{plan_id}")])

    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

    await callback.message.edit_text(
        "✏️ <b>Какой пост отредактировать?</b>\n\n"
        "Выберите пост, к которому хотите дать комментарий:",
        parse_mode="HTML",
        reply_markup=keyboard
    )
    await callback.answer()


@router.callback_query(F.data.regexp(r"^ap_editpost_[a-f0-9]+_\d+$"))
async def handle_ap_edit_post_selected(callback: CallbackQuery, state: FSMContext):
    """Пост выбран для редактирования — запрос комментария"""
    parts = callback.data.split("_")
    plan_id = parts[2]
    post_index = int(parts[3])
    admin_id = callback.from_user.id

    pending = auto_publisher.pending_plans.get(admin_id)
    if not pending or pending.plan_id != plan_id:
        await callback.answer("❌ План не найден", show_alert=True)
        return

    if post_index >= len(pending.posts) or pending.posts[post_index].removed:
        await callback.answer("❌ Пост не найден", show_alert=True)
        return

    post = pending.posts[post_index]

    await state.update_data(ap_plan_id=plan_id, ap_post_index=post_index)
    await state.set_state(AutoPubReview.waiting_for_comment)

    await callback.message.edit_text(
        f"✏️ <b>Редактирование поста #{post.index + 1}</b>\n\n"
        f"{post.channel_emoji} <b>{post.channel_name}</b>\n"
        f"📌 {post.topic}\n\n"
        f"Напишите комментарий: что исправить в этом посте?\n\n"
        f"<i>Например: «Добавь ссылку на исследование», "
        f"«Убери упоминание конкретных препаратов», "
        f"«Сделай более практичным для врачей»</i>",
        parse_mode="HTML"
    )
    await callback.answer()


@router.message(AutoPubReview.waiting_for_comment)
async def handle_ap_edit_comment(message: Message, state: FSMContext):
    """Получен комментарий — перегенерация поста"""
    data = await state.get_data()
    plan_id = data.get("ap_plan_id")
    post_index = data.get("ap_post_index")
    admin_id = message.from_user.id
    comment = message.text

    await state.clear()

    progress = await message.answer(
        "🔄 <b>Перегенерирую пост с учётом комментария...</b>\n\n"
        f"💬 <i>{comment[:200]}</i>",
        parse_mode="HTML"
    )

    success = await auto_publisher.regenerate_post(plan_id, post_index, comment, admin_id)

    pending = auto_publisher.pending_plans.get(admin_id)

    if success and pending:
        # Отправляем обновлённую ленту
        try:
            await progress.delete()
        except Exception:
            pass

        feed_text = auto_publisher._build_feed_text(pending)

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

        try:
            await message.answer(
                f"✅ <b>Пост #{post_index + 1} обновлён!</b>\n\n" + feed_text,
                parse_mode="HTML",
                reply_markup=keyboard
            )
        except Exception as e:
            logger.warning(f"Ошибка HTML после перегенерации: {e}")
            await message.answer(
                f"Пост #{post_index + 1} обновлён!\n\n" + html.escape(feed_text),
                reply_markup=keyboard
            )
    else:
        await progress.edit_text(
            "❌ <b>Не удалось перегенерировать пост.</b>\n"
            "Попробуйте ещё раз через /autopublish",
            parse_mode="HTML"
        )


# --- Удаление поста из плана ---

@router.callback_query(F.data.startswith("ap_remove_"))
async def handle_ap_remove_start(callback: CallbackQuery):
    """Начало удаления — выбор поста"""
    plan_id = callback.data.replace("ap_remove_", "")
    admin_id = callback.from_user.id

    pending = auto_publisher.pending_plans.get(admin_id)
    if not pending or pending.plan_id != plan_id:
        await callback.answer("❌ План не найден", show_alert=True)
        return

    active = pending.active_posts
    if not active:
        await callback.answer("Нет активных постов", show_alert=True)
        return

    buttons = []
    for post in active:
        zone_icons = {"green": "🟢", "yellow": "🟡", "red": "🔴"}
        zone = zone_icons.get(post.safety_zone, "⚪")
        btn_text = f"🗑️ #{post.index + 1} {zone} {post.channel_emoji} {post.topic[:25]}"
        buttons.append([InlineKeyboardButton(
            text=btn_text,
            callback_data=f"ap_rmpost_{plan_id}_{post.index}"
        )])
    buttons.append([InlineKeyboardButton(text="◀️ Назад к плану", callback_data=f"ap_back_{plan_id}")])

    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

    await callback.message.edit_text(
        "🗑️ <b>Какой пост удалить из плана?</b>",
        parse_mode="HTML",
        reply_markup=keyboard
    )
    await callback.answer()


@router.callback_query(F.data.regexp(r"^ap_rmpost_[a-f0-9]+_\d+$"))
async def handle_ap_remove_post(callback: CallbackQuery):
    """Удаление конкретного поста"""
    parts = callback.data.split("_")
    plan_id = parts[2]
    post_index = int(parts[3])
    admin_id = callback.from_user.id

    pending = auto_publisher.pending_plans.get(admin_id)
    if not pending or pending.plan_id != plan_id:
        await callback.answer("❌ План не найден", show_alert=True)
        return

    if post_index < len(pending.posts):
        pending.posts[post_index].removed = True
        await callback.answer(f"🗑️ Пост #{post_index + 1} удалён")

    # Обновляем ленту
    await _refresh_feed(callback, pending)


# --- Просмотр поста целиком ---

@router.callback_query(F.data.startswith("ap_view_"))
async def handle_ap_view_start(callback: CallbackQuery):
    """Выбор поста для полного просмотра"""
    plan_id = callback.data.replace("ap_view_", "")
    admin_id = callback.from_user.id

    pending = auto_publisher.pending_plans.get(admin_id)
    if not pending or pending.plan_id != plan_id:
        await callback.answer("❌ План не найден", show_alert=True)
        return

    active = pending.active_posts
    if not active:
        await callback.answer("Нет активных постов", show_alert=True)
        return

    buttons = []
    for post in active:
        zone_icons = {"green": "🟢", "yellow": "🟡", "red": "🔴"}
        zone = zone_icons.get(post.safety_zone, "⚪")
        btn_text = f"👁️ #{post.index + 1} {zone} {post.channel_emoji} {post.topic[:25]}"
        buttons.append([InlineKeyboardButton(
            text=btn_text,
            callback_data=f"ap_viewpost_{plan_id}_{post.index}"
        )])
    buttons.append([InlineKeyboardButton(text="◀️ Назад к плану", callback_data=f"ap_back_{plan_id}")])

    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

    await callback.message.edit_text(
        "👁️ <b>Какой пост посмотреть целиком?</b>",
        parse_mode="HTML",
        reply_markup=keyboard
    )
    await callback.answer()


@router.callback_query(F.data.regexp(r"^ap_viewpost_[a-f0-9]+_\d+$"))
async def handle_ap_view_post(callback: CallbackQuery):
    """Показ полного текста поста"""
    parts = callback.data.split("_")
    plan_id = parts[2]
    post_index = int(parts[3])
    admin_id = callback.from_user.id

    pending = auto_publisher.pending_plans.get(admin_id)
    if not pending or pending.plan_id != plan_id:
        await callback.answer("❌ План не найден", show_alert=True)
        return

    if post_index >= len(pending.posts) or pending.posts[post_index].removed:
        await callback.answer("❌ Пост не найден", show_alert=True)
        return

    post = pending.posts[post_index]
    zone_icons = {"green": "🟢", "yellow": "🟡", "red": "🔴"}
    zone = zone_icons.get(post.safety_zone, "⚪")

    issues_text = ""
    if post.safety_issues:
        issues_text = "\n⚠️ <b>Замечания:</b>\n"
        for issue in post.safety_issues:
            if isinstance(issue, dict):
                issue = issue.get("description", issue.get("issue", str(issue)))
            issues_text += f"  • {html.escape(str(issue))}\n"

    recs_text = ""
    if post.safety_recommendations:
        recs_text = "\n💡 <b>Рекомендации:</b>\n"
        for rec in post.safety_recommendations[:3]:
            if isinstance(rec, dict):
                rec = rec.get("description", rec.get("recommendation", str(rec)))
            recs_text += f"  • {html.escape(str(rec))}\n"

    header = (
        f"👁️ <b>Пост #{post.index + 1}</b> {zone}\n"
        f"{post.channel_emoji} <b>{post.channel_name}</b>\n"
        f"⏰ {post.publish_time} | 📝 {html.escape(post.post_type)}\n"
        f"📌 {html.escape(post.topic)}\n"
        f"{issues_text}{recs_text}\n"
        f"{'─' * 30}\n\n"
    )

    # Текст поста может быть длинным, обрезаем до лимита Telegram
    max_content_len = 3500 - len(header)
    content_display = post.content
    if len(content_display) > max_content_len:
        content_display = content_display[:max_content_len] + "\n\n<i>... (обрезано)</i>"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад к плану", callback_data=f"ap_back_{plan_id}")]
    ])

    # Пытаемся отправить как HTML; если контент содержит невалидные теги — экранируем
    try:
        await callback.message.edit_text(
            header + content_display,
            parse_mode="HTML",
            reply_markup=keyboard
        )
    except Exception:
        # Контент содержит невалидный HTML — экранируем весь текст поста
        content_escaped = html.escape(post.content)
        if len(content_escaped) > max_content_len:
            content_escaped = content_escaped[:max_content_len] + "\n\n... (обрезано)"
        await callback.message.edit_text(
            header + content_escaped,
            parse_mode="HTML",
            reply_markup=keyboard
        )
    await callback.answer()


# --- Отмена плана ---

@router.callback_query(F.data.startswith("ap_cancel_"))
async def handle_ap_cancel(callback: CallbackQuery):
    """Отмена всего плана"""
    plan_id = callback.data.replace("ap_cancel_", "")
    admin_id = callback.from_user.id

    if admin_id in auto_publisher.pending_plans:
        del auto_publisher.pending_plans[admin_id]

    await callback.message.edit_text(
        "❌ <b>План отменён.</b>\n\n"
        "Используйте /autopublish для нового запуска.",
        parse_mode="HTML"
    )
    await callback.answer("План отменён")


# --- Назад к ленте ---

@router.callback_query(F.data.startswith("ap_back_"))
async def handle_ap_back(callback: CallbackQuery):
    """Возврат к ленте плана"""
    plan_id = callback.data.replace("ap_back_", "")
    admin_id = callback.from_user.id

    pending = auto_publisher.pending_plans.get(admin_id)
    if not pending or pending.plan_id != plan_id:
        await callback.answer("❌ План не найден", show_alert=True)
        return

    await _refresh_feed(callback, pending)


async def _refresh_feed(callback: CallbackQuery, pending):
    """Обновляет сообщение с лентой плана"""
    feed_text = auto_publisher._build_feed_text(pending)

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

    try:
        await callback.message.edit_text(feed_text, parse_mode="HTML", reply_markup=keyboard)
    except Exception as e:
        logger.warning(f"Ошибка HTML в _refresh_feed: {e}")
        try:
            await callback.message.edit_text(
                html.escape(feed_text), reply_markup=keyboard
            )
        except Exception:
            pass
    await callback.answer()


# ====================================================================================
# SETUP FUNCTION
# ====================================================================================

def setup_handlers(dp: Dispatcher):
    """
    Регистрация всех handlers в Dispatcher
    """
    # Регистрируем user interface handlers
    dp.include_router(router)
    logger.info("✅ UserInterface handlers зарегистрированы")

    # Регистрируем admin handlers
    from src.telegram_bot.handlers.admin import router as admin_router
    dp.include_router(admin_router)
    logger.info("✅ Admin handlers зарегистрированы")

# def setup_handlers(dp: Dispatcher):
#     """
#     Регистрация всех handlers
#
#     Args:
#         dp: Dispatcher aiogram
#     """
#     # Регистрируем команды
#     dp.message.register(cmd_start, Command("start"))
#     dp.message.register(cmd_new_post, Command("new_post"))
#     dp.message.register(cmd_queue, Command("queue"))
#     dp.message.register(cmd_stats, Command("stats"))
#     dp.message.register(cmd_scheduler, Command("scheduler"))
#
#     # Регистрируем callback handlers
#     dp.callback_query.register(handle_new_post, lambda c: c.data == "new_post")
#     dp.callback_query.register(handle_view_queue, lambda c: c.data == "view_queue")
#     dp.callback_query.register(handle_view_stats, lambda c: c.data == "view_stats")
#     dp.callback_query.register(handle_scheduler, lambda c: c.data == "scheduler")
#
#     # Регистрируем обработчик для кнопки "Назад"
#     dp.callback_query.register(handle_back_to_menu, lambda c: c.data == "back_to_menu")
#
#     logger.info("✅ Handlers зарегистрированы")


__all__ = ["setup_handlers"]

