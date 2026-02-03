"""
Telegram Bot для публикации постов в каналы
"""

import asyncio
import ssl
from datetime import datetime
from typing import Optional, List, Dict, Any
from aiogram import Bot
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.exceptions import TelegramAPIError
import aiohttp

from src.telegram_bot.models import PublishTask, TaskStatus, ButtonModel
from src.telegram_bot.task_queue import TaskQueue
from src.core.logger import logger
from src.core.exceptions import PublishError


class MedicalTelegramBot:
    """
    Telegram Bot для автоматической публикации контента в медицинские каналы
    """
    
    def __init__(self, bot_token: str, task_queue: Optional[TaskQueue] = None):
        """
        Инициализация бота
        
        Args:
            bot_token: Токен Telegram бота
            task_queue: Очередь задач (опционально, создастся автоматически)
        """
        # Инициализируем бота (SSL уже отключен глобально в main.py)
        self.bot = Bot(token=bot_token)
        self.task_queue = task_queue or TaskQueue()
        self.is_running = False
        self._worker_task: Optional[asyncio.Task] = None
        
        logger.info("🤖 MedicalTelegramBot инициализирован")


    
    async def start(self):
        """Запуск бота и фонового worker'а"""
        if self.is_running:
            logger.warning("⚠️ Бот уже запущен")
            return
        
        # Проверяем бота
        try:
            bot_info = await self.bot.get_me()
            logger.info(f"✅ Бот подключён: @{bot_info.username} (ID: {bot_info.id})")
        except Exception as e:
            logger.error(f"❌ Ошибка подключения бота: {e}")
            raise
        
        # Запускаем фоновый worker
        self.is_running = True
        self._worker_task = asyncio.create_task(self._background_worker())
        logger.info("✅ Фоновый worker запущен")
    
    async def stop(self):
        """Остановка бота"""
        if not self.is_running:
            return
        
        self.is_running = False
        
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
        
        await self.bot.session.close()
        logger.info("🛑 MedicalTelegramBot остановлен")
    
    async def _background_worker(self):
        """
        Фоновый worker для автоматической публикации постов
        Проверяет очередь каждые 30 секунд
        """
        logger.info("🔄 Background worker запущен")
        
        while self.is_running:
            try:
                # Получаем готовые к публикации задачи
                ready_tasks = await self.task_queue.get_ready_tasks()
                
                if ready_tasks:
                    logger.info(f"📬 Найдено {len(ready_tasks)} задач для публикации")
                    
                    for task in ready_tasks:
                        try:
                            await self._publish_task(task)
                            await asyncio.sleep(2)  # Задержка между постами
                        except Exception as e:
                            logger.error(f"❌ Ошибка публикации задачи {task.task_id}: {e}")
                
                # Ждём перед следующей проверкой
                await asyncio.sleep(30)
            
            except asyncio.CancelledError:
                logger.info("🛑 Background worker остановлен")
                break
            except Exception as e:
                logger.error(f"❌ Ошибка в background worker: {e}")
                await asyncio.sleep(60)  # Ждём дольше после ошибки
    
    async def _publish_task(self, task: PublishTask):
        """
        Публикация одной задачи
        
        Args:
            task: Задача публикации
        """
        logger.info(f"📤 Публикую задачу {task.task_id} в {task.channel_id}")
        
        # Обновляем статус
        task.status = TaskStatus.PROCESSING
        await self.task_queue.update_task(task)
        
        try:
            # Формируем клавиатуру (если есть кнопки)
            reply_markup = None
            if task.buttons:
                buttons = []
                for btn in task.buttons:
                    if isinstance(btn, dict):
                        buttons.append([InlineKeyboardButton(text=btn["text"], url=btn["url"])])
                    elif isinstance(btn, ButtonModel):
                        buttons.append([InlineKeyboardButton(text=btn.text, url=btn.url)])
                
                reply_markup = InlineKeyboardMarkup(inline_keyboard=buttons)
            
            # Публикуем в зависимости от типа контента
            message = None
            
            if task.photo_url:
                # Пост с фото
                message = await self.bot.send_photo(
                    chat_id=task.channel_id,
                    photo=task.photo_url,
                    caption=task.text,
                    parse_mode=task.parse_mode,
                    reply_markup=reply_markup,
                    disable_notification=task.disable_notification
                )
            
            elif task.video_url:
                # Пост с видео
                message = await self.bot.send_video(
                    chat_id=task.channel_id,
                    video=task.video_url,
                    caption=task.text,
                    parse_mode=task.parse_mode,
                    reply_markup=reply_markup,
                    disable_notification=task.disable_notification
                )
            
            elif task.document_url:
                # Пост с документом
                message = await self.bot.send_document(
                    chat_id=task.channel_id,
                    document=task.document_url,
                    caption=task.text,
                    parse_mode=task.parse_mode,
                    reply_markup=reply_markup,
                    disable_notification=task.disable_notification
                )
            
            else:
                # Текстовый пост
                message = await self.bot.send_message(
                    chat_id=task.channel_id,
                    text=task.text,
                    parse_mode=task.parse_mode,
                    reply_markup=reply_markup,
                    disable_web_page_preview=task.disable_web_page_preview,
                    disable_notification=task.disable_notification
                )
            
            # Успешная публикация
            await self.task_queue.complete_task(task.task_id, message.message_id)
            
            logger.info(
                f"✅ Задача {task.task_id} опубликована успешно "
                f"(message_id: {message.message_id})"
            )
        
        except TelegramAPIError as e:
            # Ошибка Telegram API
            error_msg = f"Telegram API error: {e}"
            logger.error(f"❌ {error_msg}")
            
            task.last_error = error_msg
            await self.task_queue.fail_task(task.task_id, error_msg)
            
            raise PublishError(error_msg)
        
        except Exception as e:
            # Другие ошибки
            error_msg = f"Unexpected error: {e}"
            logger.error(f"❌ {error_msg}")
            
            task.last_error = error_msg
            await self.task_queue.fail_task(task.task_id, error_msg)
            
            raise PublishError(error_msg)
    
    async def schedule_post(
        self,
        channel_id: str,
        text: str,
        scheduled_time: datetime,
        photo_url: Optional[str] = None,
        video_url: Optional[str] = None,
        document_url: Optional[str] = None,
        buttons: Optional[List[Dict[str, str]]] = None,
        parse_mode: str = "HTML",
        disable_web_page_preview: bool = False,
        disable_notification: bool = False,
        created_by: Optional[int] = None
    ) -> str:
        """
        Запланировать публикацию поста
        
        Args:
            channel_id: ID канала (@profgynecologist)
            text: Текст поста
            scheduled_time: Время публикации
            photo_url: URL фото (опционально)
            video_url: URL видео (опционально)
            document_url: URL документа (опционально)
            buttons: Кнопки [{"text": "...", "url": "..."}] (опционально)
            parse_mode: Режим парсинга (HTML/Markdown)
            disable_web_page_preview: Отключить превью ссылок
            disable_notification: Отключить уведомления
            created_by: ID создателя (Telegram user_id)
        
        Returns:
            ID задачи
        """
        import uuid
        
        # Генерируем ID задачи
        task_id = str(uuid.uuid4())[:8]
        
        # Конвертируем кнопки
        button_models = None
        if buttons:
            button_models = [ButtonModel(**btn) for btn in buttons]
        
        # Создаём задачу
        task = PublishTask(
            task_id=task_id,
            channel_id=channel_id,
            text=text,
            scheduled_time=scheduled_time,
            status=TaskStatus.SCHEDULED if scheduled_time > datetime.now() else TaskStatus.PENDING,
            photo_url=photo_url,
            video_url=video_url,
            document_url=document_url,
            buttons=button_models,
            parse_mode=parse_mode,
            disable_web_page_preview=disable_web_page_preview,
            disable_notification=disable_notification,
            created_by=created_by
        )
        
        # Добавляем в очередь
        await self.task_queue.add_task(task)
        
        logger.info(
            f"⏰ Задача {task_id} запланирована: "
            f"{channel_id} на {scheduled_time.strftime('%d.%m.%Y %H:%M')}"
        )
        
        return task_id
    
    async def publish_now(
        self,
        channel_id: str,
        text: str,
        photo_url: Optional[str] = None,
        video_url: Optional[str] = None,
        buttons: Optional[List[Dict[str, str]]] = None,
        **kwargs
    ) -> str:
        """
        Опубликовать пост немедленно
        
        Args:
            channel_id: ID канала
            text: Текст поста
            photo_url: URL фото (опционально)
            video_url: URL видео (опционально)
            buttons: Кнопки (опционально)
            **kwargs: Дополнительные параметры
        
        Returns:
            ID задачи
        """
        return await self.schedule_post(
            channel_id=channel_id,
            text=text,
            scheduled_time=datetime.now(),
            photo_url=photo_url,
            video_url=video_url,
            buttons=buttons,
            **kwargs
        )
    
    async def cancel_post(self, task_id: str) -> bool:
        """Отменить запланированную публикацию"""
        result = await self.task_queue.cancel_task(task_id)
        
        if result:
            logger.info(f"🚫 Задача {task_id} отменена")
        else:
            logger.warning(f"⚠️ Задача {task_id} не найдена для отмены")
        
        return result
    
    async def get_task_status(self, task_id: str) -> Optional[PublishTask]:
        """Получить статус задачи"""
        return await self.task_queue.get_task(task_id)
    
    def get_stats(self) -> Dict[str, Any]:
        """Получить статистику бота"""
        stats = self.task_queue.get_stats()
        
        # Вычисляем success rate
        total = stats['completed'] + stats['failed']
        success_rate = (stats['completed'] / total * 100) if total > 0 else 0.0
        
        return {
            'active_tasks': stats['active_tasks'],
            'pending': stats['pending'],
            'scheduled': stats['scheduled'],
            'completed': stats['completed'],
            'failed': stats['failed'],
            'success_rate': round(success_rate, 2),
            'total_published': stats['completed']
        }
    
    async def get_upcoming_posts(self, limit: int = 10) -> List[PublishTask]:
        """Получить список запланированных постов"""
        return self.task_queue.get_upcoming_tasks(limit=limit)

    async def add_task(self, task: PublishTask) -> str:
        """
        Добавить задачу в очередь публикации

        Args:
            task: Задача публикации

        Returns:
            ID задачи
        """
        return await self.task_queue.add_task(task)

    async def retry_failed_tasks(self) -> int:
        """Повторить все провалившиеся задачи"""
        failed_tasks = await self.task_queue.get_failed_tasks()
        
        if not failed_tasks:
            logger.info("✅ Нет провалившихся задач")
            return 0
        
        logger.info(f"🔄 Повторяю {len(failed_tasks)} провалившихся задач")
        
        success_count = 0
        
        for task in failed_tasks:
            if not task.can_retry():
                continue
            
            try:
                await self._publish_task(task)
                success_count += 1
                await asyncio.sleep(2)
            except Exception as e:
                logger.error(f"❌ Повтор провалился для {task.task_id}: {e}")
        
        logger.info(f"✅ Успешно повторено: {success_count}/{len(failed_tasks)}")
        return success_count


__all__ = ["MedicalTelegramBot"]
