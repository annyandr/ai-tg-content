"""
🎨 UI для создания и публикации постов
Интерактивный интерфейс с FSM для MVP
"""

import asyncio
from datetime import datetime, timedelta
from typing import Optional

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from src.agents.specialty_loader import SPECIALTY_MAP, get_specialty_config, get_all_specialties
from src.services.content_generator import ContentGeneratorService
from src.telegram_bot.bot import MedicalTelegramBot
from src.core.logger import logger

# Создаём роутер
router = Router()

# Глобальные сервисы (инициализируются в main.py)
content_generator: Optional[ContentGeneratorService] = None
telegram_bot: Optional[MedicalTelegramBot] = None


def init_services(generator: ContentGeneratorService, bot: MedicalTelegramBot):
    """Инициализация сервисов"""
    global content_generator, telegram_bot
    content_generator = generator
    telegram_bot = bot


# ============================================================================
# FSM STATES
# ============================================================================

class PostCreation(StatesGroup):
    """Состояния создания поста"""
    choosing_channel = State()
    entering_topic = State()
    choosing_action = State()
    entering_schedule = State()


# ============================================================================
# МЕНЮ
# ============================================================================

def get_main_menu() -> InlineKeyboardMarkup:
    """Главное меню"""
    keyboard = [
        [InlineKeyboardButton(text="✨ Создать пост", callback_data="create_post")],
        [InlineKeyboardButton(text="📋 Мои посты", callback_data="my_posts")],
        [InlineKeyboardButton(text="📊 Статистика", callback_data="stats")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_channels_menu() -> InlineKeyboardMarkup:
    """Меню выбора канала"""
    keyboard = []

    for specialty in get_all_specialties():
        config = get_specialty_config(specialty)
        emoji = config.get("emoji", "📌")
        name = config.get("name", specialty.capitalize())

        keyboard.append([
            InlineKeyboardButton(
                text=f"{emoji} {name}",
                callback_data=f"channel_{specialty}"
            )
        ])

    keyboard.append([InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_main")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_action_menu() -> InlineKeyboardMarkup:
    """Меню действий с постом"""
    keyboard = [
        [InlineKeyboardButton(text="🚀 Опубликовать сейчас", callback_data="publish_now")],
        [InlineKeyboardButton(text="⏰ Запланировать публикацию", callback_data="schedule_post")],
        [InlineKeyboardButton(text="◀️ Отмена", callback_data="cancel")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_schedule_menu() -> InlineKeyboardMarkup:
    """Меню выбора времени"""
    keyboard = [
        [
            InlineKeyboardButton(text="🌅 Через 1 час", callback_data="schedule_1h"),
            InlineKeyboardButton(text="🌞 Через 3 часа", callback_data="schedule_3h")
        ],
        [
            InlineKeyboardButton(text="🌆 Через 6 часов", callback_data="schedule_6h"),
            InlineKeyboardButton(text="🌃 Завтра в 9:00", callback_data="schedule_tomorrow")
        ],
        [InlineKeyboardButton(text="📅 Указать время", callback_data="schedule_custom")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_action")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


# ============================================================================
# КОМАНДЫ
# ============================================================================

@router.message(Command("start"))
async def cmd_start(message: Message):
    """Команда /start"""
    welcome_text = """
👋 <b>Добро пожаловать в Medical Content Bot!</b>

🎯 <b>Что я умею:</b>
• Генерировать качественные медицинские посты
• Публиковать в Telegram-каналы
• Планировать публикации по расписанию

🚀 <b>Специализации:</b>
🍑 Гинекология
👶 Педиатрия
🩺 Эндокринология
🫀 Терапия
🧴 Дерматология

📌 <i>Нажмите кнопку ниже, чтобы начать</i>
    """

    await message.answer(
        welcome_text,
        reply_markup=get_main_menu(),
        parse_mode="HTML"
    )


@router.message(Command("help"))
async def cmd_help(message: Message):
    """Команда /help"""
    help_text = """
📖 <b>Инструкция:</b>

1️⃣ Нажмите "✨ Создать пост"
2️⃣ Выберите специализацию
3️⃣ Введите тему поста
4️⃣ Дождитесь генерации (~20 сек)
5️⃣ Выберите:
   • 🚀 Опубликовать сейчас
   • ⏰ Запланировать

<b>Примеры тем:</b>
• Новые клинрекомендации по ГСД
• Вакцинация против ротавируса
• Скрининг меланомы 2026

💡 <i>Бот использует специализированные промпты для каждой области</i>
    """
    await message.answer(help_text, parse_mode="HTML")


# ============================================================================
# СОЗДАНИЕ ПОСТА
# ============================================================================

@router.callback_query(F.data == "create_post")
async def start_post_creation(callback: CallbackQuery, state: FSMContext):
    """Начало создания поста"""
    await callback.message.edit_text(
        "🎯 <b>Выберите специализацию:</b>\n\n"
        "Для какого канала создать пост?",
        reply_markup=get_channels_menu(),
        parse_mode="HTML"
    )
    await state.set_state(PostCreation.choosing_channel)
    await callback.answer()


@router.callback_query(F.data.startswith("channel_"))
async def channel_selected(callback: CallbackQuery, state: FSMContext):
    """Канал выбран"""
    specialty = callback.data.replace("channel_", "")
    config = get_specialty_config(specialty)

    await state.update_data(
        specialty=specialty,
        channel=config["channel"],
        emoji=config["emoji"],
        link=config["link"],
        name=config["name"]
    )

    await callback.message.edit_text(
        f"{config['emoji']} <b>{config['name']}</b>\n\n"
        "✍️ <b>Введите тему для поста:</b>\n\n"
        "<i>Примеры:</i>\n"
        "• Новые клинрекомендации по артериальной гипертензии\n"
        "• Вакцинация против ротавируса: обновление 2026\n"
        "• Скрининг меланомы: кого проверять\n\n"
        "💡 Постарайтесь быть конкретными",
        parse_mode="HTML"
    )

    await state.set_state(PostCreation.entering_topic)
    await callback.answer()


@router.message(PostCreation.entering_topic)
async def topic_entered(message: Message, state: FSMContext):
    """Тема введена, генерируем пост"""
    topic = message.text
    data = await state.get_data()

    specialty = data["specialty"]
    channel = data["channel"]
    emoji = data["emoji"]
    name = data["name"]

    # Показываем прогресс
    progress_msg = await message.answer(
        f"⚙️ <b>Генерирую пост...</b>\n\n"
        f"📌 Специализация: {name}\n"
        f"📝 Тема: {topic}\n\n"
        f"<i>⏱ Обычно занимает 15-30 секунд</i>",
        parse_mode="HTML"
    )

    try:
        # ГЕНЕРАЦИЯ ПОСТА
        post_content = await content_generator.generate_from_topic(
            topic=topic,
            specialty=specialty,
            post_type="клинрекомендации"
        )

        await progress_msg.delete()

        # Сохраняем в state
        await state.update_data(
            topic=topic,
            post_content=post_content,
            generated_at=datetime.now()
        )

        # Показываем результат
        preview = (
            f"✅ <b>Пост сгенерирован!</b>\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"{post_content[:500]}{'...' if len(post_content) > 500 else ''}\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"📊 Символов: {len(post_content)}\n"
            f"🎯 Канал: @{channel}\n\n"
            f"Что делаем дальше?"
        )

        await message.answer(
            preview,
            reply_markup=get_action_menu(),
            parse_mode="HTML"
        )

        await state.set_state(PostCreation.choosing_action)

    except Exception as e:
        logger.error(f"Ошибка генерации: {e}")
        await progress_msg.edit_text(
            f"❌ <b>Ошибка генерации</b>\n\n"
            f"Попробуйте ещё раз или измените тему.\n\n"
            f"<i>Ошибка: {str(e)[:100]}</i>",
            parse_mode="HTML"
        )
        await state.clear()


# ============================================================================
# ПУБЛИКАЦИЯ
# ============================================================================

@router.callback_query(F.data == "publish_now")
async def publish_immediately(callback: CallbackQuery, state: FSMContext):
    """Публикация немедленно"""
    data = await state.get_data()
    post_content = data["post_content"]
    channel = data["channel"]
    name = data["name"]

    await callback.message.edit_text(
        "🚀 <b>Публикую пост...</b>",
        parse_mode="HTML"
    )

    try:
        # Публикация через бота
        task_id = await telegram_bot.schedule_post(
            channel_id=f"@{channel}",
            text=post_content,
            scheduled_time=datetime.now(),  # Сейчас
            parse_mode="HTML"
        )

        await callback.message.edit_text(
            f"✅ <b>Пост опубликован!</b>\n\n"
            f"📢 Канал: @{channel}\n"
            f"🕐 Время: {datetime.now().strftime('%d.%m.%Y %H:%M')}\n"
            f"🆔 ID задачи: <code>{task_id}</code>",
            parse_mode="HTML"
        )

        logger.info(f"✅ Пост опубликован в @{channel}: {task_id}")

    except Exception as e:
        logger.error(f"Ошибка публикации: {e}")
        await callback.message.edit_text(
            f"❌ <b>Ошибка публикации</b>\n\n{str(e)}",
            parse_mode="HTML"
        )

    await state.clear()
    await callback.answer()


@router.callback_query(F.data == "schedule_post")
async def choose_schedule(callback: CallbackQuery, state: FSMContext):
    """Выбор времени планирования"""
    await callback.message.edit_text(
        "⏰ <b>Когда опубликовать пост?</b>\n\n"
        "Выберите удобное время:",
        reply_markup=get_schedule_menu(),
        parse_mode="HTML"
    )
    await state.set_state(PostCreation.entering_schedule)
    await callback.answer()


@router.callback_query(F.data.startswith("schedule_"), PostCreation.entering_schedule)
async def schedule_selected(callback: CallbackQuery, state: FSMContext):
    """Время выбрано"""
    schedule_type = callback.data.replace("schedule_", "")
    data = await state.get_data()

    # Рассчитываем время
    now = datetime.now()
    if schedule_type == "1h":
        scheduled_time = now + timedelta(hours=1)
    elif schedule_type == "3h":
        scheduled_time = now + timedelta(hours=3)
    elif schedule_type == "6h":
        scheduled_time = now + timedelta(hours=6)
    elif schedule_type == "tomorrow":
        scheduled_time = (now + timedelta(days=1)).replace(hour=9, minute=0, second=0)
    elif schedule_type == "custom":
        await callback.message.edit_text(
            "📅 <b>Введите время:</b>\n\n"
            "Формат: <code>ДД.ММ.ГГГГ ЧЧ:ММ</code>\n"
            "Пример: <code>05.02.2026 14:30</code>",
            parse_mode="HTML"
        )
        await callback.answer()
        return
    else:
        await callback.answer("Неизвестный вариант")
        return

    post_content = data["post_content"]
    channel = data["channel"]
    name = data["name"]

    await callback.message.edit_text(
        "⏰ <b>Планирую публикацию...</b>",
        parse_mode="HTML"
    )

    try:
        # Планирование через бота
        task_id = await telegram_bot.schedule_post(
            channel_id=f"@{channel}",
            text=post_content,
            scheduled_time=scheduled_time,
            parse_mode="HTML"
        )

        await callback.message.edit_text(
            f"✅ <b>Пост запланирован!</b>\n\n"
            f"📢 Канал: @{channel}\n"
            f"⏰ Публикация: {scheduled_time.strftime('%d.%m.%Y %H:%M')}\n"
            f"🆔 ID: <code>{task_id}</code>",
            parse_mode="HTML"
        )

        logger.info(f"⏰ Пост запланирован в @{channel} на {scheduled_time}: {task_id}")

    except Exception as e:
        logger.error(f"Ошибка планирования: {e}")
        await callback.message.edit_text(
            f"❌ <b>Ошибка планирования</b>\n\n{str(e)}",
            parse_mode="HTML"
        )

    await state.clear()
    await callback.answer()


@router.message(PostCreation.entering_schedule)
async def custom_time_entered(message: Message, state: FSMContext):
    """Введено пользовательское время"""
    try:
        scheduled_time = datetime.strptime(message.text, "%d.%m.%Y %H:%M")

        if scheduled_time < datetime.now():
            await message.answer("❌ Время не может быть в прошлом!")
            return

        data = await state.get_data()
        post_content = data["post_content"]
        channel = data["channel"]

        progress = await message.answer("⏰ Планирую...")

        task_id = await telegram_bot.schedule_post(
            channel_id=f"@{channel}",
            text=post_content,
            scheduled_time=scheduled_time,
            parse_mode="HTML"
        )

        await progress.delete()
        await message.answer(
            f"✅ <b>Пост запланирован!</b>\n\n"
            f"📢 @{channel}\n"
            f"⏰ {scheduled_time.strftime('%d.%m.%Y %H:%M')}\n"
            f"🆔 <code>{task_id}</code>",
            parse_mode="HTML"
        )

        await state.clear()

    except ValueError:
        await message.answer(
            "❌ Неверный формат!\n\n"
            "Используйте: <code>ДД.ММ.ГГГГ ЧЧ:ММ</code>",
            parse_mode="HTML"
        )


# ============================================================================
# МОИ ПОСТЫ
# ============================================================================

@router.callback_query(F.data == "my_posts")
async def show_my_posts(callback: CallbackQuery):
    """Список запланированных постов"""
    # Получаем запланированные задачи из бота
    stats = telegram_bot.get_stats()
    active_tasks = stats.get("active_tasks", 0)

    await callback.message.edit_text(
        f"📋 <b>Запланированные посты</b>\n\n"
        f"Активных задач: {active_tasks}\n\n"
        f"<i>Подробный список в разработке</i>",
        reply_markup=get_main_menu(),
        parse_mode="HTML"
    )
    await callback.answer()


# ============================================================================
# СТАТИСТИКА
# ============================================================================

@router.callback_query(F.data == "stats")
async def show_stats(callback: CallbackQuery):
    """Показать статистику"""
    bot_stats = telegram_bot.get_stats()
    gen_stats = content_generator.get_stats()

    stats_text = (
        f"📊 <b>Статистика бота</b>\n\n"
        f"<b>Публикации:</b>\n"
        f"✅ Выполнено: {bot_stats.get('completed', 0)}\n"
        f"❌ Ошибки: {bot_stats.get('failed', 0)}\n"
        f"⏳ В очереди: {bot_stats.get('active_tasks', 0)}\n\n"
        f"<b>Генерация:</b>\n"
        f"📝 Всего: {gen_stats.get('total_generated', 0)}\n"
        f"✅ Успешно: {gen_stats.get('successful', 0)}\n"
        f"❌ Ошибки: {gen_stats.get('failed', 0)}"
    )

    await callback.message.edit_text(
        stats_text,
        reply_markup=get_main_menu(),
        parse_mode="HTML"
    )
    await callback.answer()


# ============================================================================
# НАВИГАЦИЯ
# ============================================================================

@router.callback_query(F.data == "back_to_main")
async def back_to_main(callback: CallbackQuery, state: FSMContext):
    """Возврат в главное меню"""
    await state.clear()
    await callback.message.edit_text(
        "🏠 <b>Главное меню</b>\n\nВыберите действие:",
        reply_markup=get_main_menu(),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "back_to_action")
async def back_to_action(callback: CallbackQuery, state: FSMContext):
    """Возврат к выбору действия"""
    data = await state.get_data()
    post_content = data.get("post_content", "")
    channel = data.get("channel", "")

    preview = (
        f"✅ <b>Пост готов!</b>\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{post_content[:500]}{'...' if len(post_content) > 500 else ''}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📊 Символов: {len(post_content)}\n"
        f"🎯 Канал: @{channel}\n\n"
        f"Что делаем?"
    )

    await callback.message.edit_text(
        preview,
        reply_markup=get_action_menu(),
        parse_mode="HTML"
    )
    await state.set_state(PostCreation.choosing_action)
    await callback.answer()


@router.callback_query(F.data == "cancel")
async def cancel_action(callback: CallbackQuery, state: FSMContext):
    """Отмена действия"""
    await state.clear()
    await callback.message.edit_text(
        "❌ Действие отменено",
        reply_markup=get_main_menu(),
        parse_mode="HTML"
    )
    await callback.answer()


__all__ = ["router", "init_services"]
