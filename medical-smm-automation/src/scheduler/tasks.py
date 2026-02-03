"""
Фоновые задачи для планировщика
"""

import asyncio
from datetime import datetime
from typing import Optional

from src.core.logger import logger
from src.telegram_bot.task_queue import TaskQueue
from src.telegram_bot.models import TaskStatus


class SchedulerTasks:
    """
    Класс с задачами для планировщика
    """
    
    def __init__(self, telegram_bot, task_queue: Optional[TaskQueue] = None):
        """
        Args:
            telegram_bot: Экземпляр MedicalTelegramBot
            task_queue: Очередь задач (опционально)
        """
        self.telegram_bot = telegram_bot
        self.task_queue = task_queue or TaskQueue()
    
    async def publish_scheduled_posts(self):
        """
        Публикация всех постов, у которых пришло время
        Эта функция вызывается по расписанию (09:00, 20:00)
        """
        logger.info("🚀 Запуск публикации запланированных постов...")
        
        try:
            now = datetime.now()
            
            # Получаем все задачи, готовые к публикации
            ready_tasks = await self.task_queue.get_ready_tasks(now)
            
            if not ready_tasks:
                logger.info("📭 Нет постов готовых к публикации")
                return
            
            logger.info(f"📬 Найдено {len(ready_tasks)} постов для публикации")
            
            # Публикуем каждый пост
            published_count = 0
            failed_count = 0
            
            for task in ready_tasks:
                try:
                    logger.info(f"📤 Публикую пост {task.task_id} в {task.channel_id}")
                    
                    # Публикуем через telegram_bot
                    message = await self.telegram_bot.bot.send_message(
                        chat_id=task.channel_id,
                        text=task.text,
                        parse_mode="HTML"
                    )
                    
                    # Обновляем статус задачи
                    await self.task_queue.complete_task(task.task_id, message.message_id)
                    
                    published_count += 1
                    logger.info(f"✅ Пост {task.task_id} опубликован (message_id: {message.message_id})")
                    
                    # Небольшая задержка между постами
                    await asyncio.sleep(2)
                
                except Exception as e:
                    logger.error(f"❌ Ошибка публикации поста {task.task_id}: {e}")
                    
                    # Отмечаем как провалившуюся
                    await self.task_queue.fail_task(task.task_id, str(e))
                    failed_count += 1
            
            logger.info(
                f"📊 Публикация завершена: "
                f"✅ {published_count} успешно, "
                f"❌ {failed_count} ошибок"
            )
        
        except Exception as e:
            logger.error(f"❌ Критическая ошибка в publish_scheduled_posts: {e}")
    
    async def retry_failed_tasks(self):
        """
        Повторная попытка публикации провалившихся задач
        """
        logger.info("🔄 Проверка провалившихся задач...")
        
        try:
            # Получаем все провалившиеся задачи
            failed_tasks = await self.task_queue.get_failed_tasks()
            
            if not failed_tasks:
                logger.info("✅ Нет провалившихся задач")
                return
            
            logger.info(f"⚠️ Найдено {len(failed_tasks)} провалившихся задач")
            
            for task in failed_tasks:
                # Проверяем количество попыток
                if task.retry_count >= task.max_retries:
                    logger.warning(
                        f"⛔ Задача {task.task_id} превысила максимум попыток ({task.max_retries})"
                    )
                    continue
                
                try:
                    logger.info(f"🔄 Повторная попытка {task.retry_count + 1}/{task.max_retries} для {task.task_id}")
                    
                    # Публикуем
                    message = await self.telegram_bot.bot.send_message(
                        chat_id=task.channel_id,
                        text=task.text,
                        parse_mode="HTML"
                    )
                    
                    # Обновляем статус
                    await self.task_queue.complete_task(task.task_id, message.message_id)
                    
                    logger.info(f"✅ Задача {task.task_id} успешно опубликована после повтора")
                    
                    await asyncio.sleep(2)
                
                except Exception as e:
                    logger.error(f"❌ Повторная попытка провалилась для {task.task_id}: {e}")
                    
                    # Увеличиваем счётчик попыток
                    task.retry_count += 1
                    await self.task_queue.update_task(task)
        
        except Exception as e:
            logger.error(f"❌ Ошибка в retry_failed_tasks: {e}")
    
    async def cleanup_old_tasks(self, days: int = 30):
        """
        Очистка старых выполненных задач
        
        Args:
            days: Удалить задачи старше N дней
        """
        logger.info(f"🧹 Очистка задач старше {days} дней...")
        
        try:
            deleted_count = await self.task_queue.cleanup_old_tasks(days)
            logger.info(f"🗑️ Удалено {deleted_count} старых задач")
        
        except Exception as e:
            logger.error(f"❌ Ошибка очистки: {e}")
    
    async def health_check(self):
        """
        Проверка работоспособности системы
        """
        logger.info("🏥 Health check...")
        
        try:
            # Проверяем бота
            bot_info = await self.telegram_bot.bot.get_me()
            logger.info(f"✅ Бот работает: @{bot_info.username}")
            
            # Проверяем очередь
            stats = self.task_queue.get_stats()
            logger.info(
                f"📊 Статистика очереди: "
                f"активных={stats.get('active', 0)}, "
                f"выполнено={stats.get('completed', 0)}, "
                f"ошибок={stats.get('failed', 0)}"
            )
            
            return True
        
        except Exception as e:
            logger.error(f"❌ Health check failed: {e}")
            return False


__all__ = ["SchedulerTasks"]
