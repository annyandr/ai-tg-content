"""
Пользовательский интерфейс для создания и планирования постов
ОБНОВЛЕНО ДЛЯ MVP - красивый UX для демонстрации
"""

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from datetime import datetime, timedelta
import uuid

from src.core.logger import logger
from src.agents.specialty_loader import SPECIALTY_MAP, get_specialty_config
from src.agents.generator_agent import ContentGeneratorAgent
from src.agents.safety_agent import SafetyAgent
from src.telegram_bot.models import PublishTask, TaskStatus

router = Router()

# FSM States
class PostCreation(StatesGroup):
    waiting_for_specialty = State()
    waiting_for_topic = State()
    reviewing_post = State()
    waiting_for_time = State()


# Глобальные переменные (в production используйте dependency injection)
generator_agent = None  # Инициализируется в main.py
safety_agent = None
telegram_bot = None


def set_agents(gen_agent, safe_agent, tg_bot):
    """Инициализация агентов из main.py"""
    global generator_agent, safety_agent, telegram_bot
    generator_agent = gen_agent
    safety_agent = safe_agent
    telegram_bot = tg_bot


# ====================================================================================
# ГЛАВНОЕ МЕНЮ
# ====================================================================================

@router.message(Command("start"))
async def cmd_start(message: Message):
    """Стартовое меню с красивым дизайном"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✨ Создать новый пост", callback_data="new_post")],
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
    await callback.answer()


@router.callback_query(F.data.startswith("specialty_"))
async def process_specialty_choice(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора специализации"""
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
    await callback.answer()


# ====================================================================================
# СОЗДАНИЕ ПОСТА - ШАГ 2: ГЕНЕРАЦИЯ КОНТЕНТА
# ====================================================================================

@router.message(PostCreation.waiting_for_topic)
async def process_topic_and_generate(message: Message, state: FSMContext):
    """Получаем тему и генерируем пост с AI"""
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
        await progress_msg.edit_text(
            "🤖 <b>Генерирую контент...</b>\n\n"
            "✅ Анализирую тему\n"
            "⏳ Создаю структуру поста\n"
            "⏳ Проверяю медицинскую безопасность",
            parse_mode="HTML"
        )
        
        gen_result = await generator_agent.execute(
            news=news,
            channel=channel
        )
        
        if not gen_result["success"]:
            raise Exception(f"Ошибка генерации: {gen_result.get('error')}")
        
        post_content = gen_result["content"]
        
        # 2. Проверяем безопасность
        await progress_msg.edit_text(
            "🤖 <b>Генерирую контент...</b>\n\n"
            "✅ Анализирую тему\n"
            "✅ Создал структуру поста\n"
            "⏳ Проверяю медицинскую безопасность",
            parse_mode="HTML"
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
        await progress_msg.delete()
        
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
        await progress_msg.edit_text(
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
            channel_id=f"@{data['channel']}",
            text=data['post_content'],
            scheduled_time=datetime.now(),
            status=TaskStatus.PENDING
        )
        
        # Отправляем в очередь
        await telegram_bot.add_task(task)
        
        await callback.message.edit_text(
            f"✅ <b>Пост опубликован!</b>\n\n"
            f"📢 <b>Канал:</b> @{data['channel']}\n"
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
            channel_id=f"@{data['channel']}",
            text=data['post_content'],
            scheduled_time=scheduled_time,
            status=TaskStatus.SCHEDULED
        )
        
        # Добавляем в очередь
        await telegram_bot.add_task(task)
        
        await callback.message.edit_text(
            f"⏰ <b>Пост запланирован!</b>\n\n"
            f"📢 <b>Канал:</b> @{data['channel']}\n"
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
            channel_id=f"@{data['channel']}",
            text=data['post_content'],
            scheduled_time=scheduled_time,
            status=TaskStatus.SCHEDULED
        )
        
        await telegram_bot.add_task(task)
        
        await message.answer(
            f"⏰ <b>Пост запланирован!</b>\n\n"
            f"📢 <b>Канал:</b> @{data['channel']}\n"
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
    await callback.message.edit_text(
        "🔄 <b>Генерирую новый вариант...</b>",
        parse_mode="HTML"
    )
    
    data = await state.get_data()
    
    # Повторяем генерацию
    await process_topic_and_generate(callback.message, state)
    await callback.answer()


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
# СТАТИСТИКА
# ====================================================================================

@router.callback_query(F.data == "stats")
async def show_stats(callback: CallbackQuery):
    """Статистика"""
    
    stats = telegram_bot.get_stats()
    
    await callback.message.edit_text(
        f"📊 <b>Статистика</b>\n\n"
        f"✅ Опубликовано: {stats.get('completed', 0)}\n"
        f"⏰ В очереди: {stats.get('active_tasks', 0)}\n"
        f"❌ Ошибок: {stats.get('failed', 0)}",
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


__all__ = ["router", "set_agents"]
