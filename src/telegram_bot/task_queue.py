"""
Очередь задач для публикации постов
"""

from datetime import datetime, timedelta
from typing import List, Optional, Dict
from collections import defaultdict

from src.telegram_bot.models import PublishTask, TaskStatus
from src.core.logger import logger


class TaskQueue:
    """
    In-memory очередь задач публикации
    Для production рекомендуется использовать Redis или БД
    """
    
    def __init__(self):
        self.tasks: Dict[str, PublishTask] = {}
        self.completed_tasks: Dict[str, PublishTask] = {}
        self.failed_tasks: Dict[str, PublishTask] = {}
        logger.info("📋 Очередь задач инициализирована")
    
    async def add_task(self, task: PublishTask) -> str:
        """
        Добавить задачу в очередь
        
        Args:
            task: Задача публикации
        
        Returns:
            ID задачи
        """
        self.tasks[task.task_id] = task
        logger.info(f"➕ Задача добавлена: {task.task_id} → {task.channel_id} в {task.scheduled_time}")
        return task.task_id
    
    def get_task(self, task_id: str) -> Optional[PublishTask]:
        """Получить задачу по ID"""
        return (
            self.tasks.get(task_id) or
            self.completed_tasks.get(task_id) or
            self.failed_tasks.get(task_id)
        )
    
    async def get_ready_tasks(self, current_time: datetime = None) -> List[PublishTask]:
        """
        Получить все задачи, готовые к публикации
        
        Args:
            current_time: Текущее время (по умолчанию datetime.now())
        
        Returns:
            Список готовых задач
        """
        if current_time is None:
            current_time = datetime.now()
        
        ready_tasks = []
        
        for task in self.tasks.values():
            if task.status in [TaskStatus.PENDING, TaskStatus.SCHEDULED]:
                if task.scheduled_time <= current_time:
                    ready_tasks.append(task)
        
        return ready_tasks
    
    def get_failed_tasks(self) -> List[PublishTask]:
        """Получить все провалившиеся задачи"""
        return list(self.failed_tasks.values())
    
    async def complete_task(self, task_id: str, message_id: int):
        """
        Отметить задачу как выполненную
        
        Args:
            task_id: ID задачи
            message_id: ID опубликованного сообщения в Telegram
        """
        task = self.tasks.pop(task_id, None)
        
        if task:
            task.status = TaskStatus.COMPLETED
            task.message_id = message_id
            self.completed_tasks[task_id] = task
            logger.info(f"✅ Задача выполнена: {task_id}")
        else:
            logger.warning(f"⚠️ Задача {task_id} не найдена для завершения")
    
    async def fail_task(self, task_id: str, error: str):
        """
        Отметить задачу как провалившуюся
        
        Args:
            task_id: ID задачи
            error: Описание ошибки
        """
        task = self.tasks.get(task_id)
        
        if task:
            task.retry_count += 1
            
            if task.retry_count >= task.max_retries:
                # Превышен лимит попыток — перемещаем в failed
                self.tasks.pop(task_id)
                task.status = TaskStatus.FAILED
                self.failed_tasks[task_id] = task
                logger.error(f"❌ Задача провалена окончательно: {task_id} ({error})")
            else:
                # Оставляем в очереди для повтора
                task.status = TaskStatus.PENDING
                logger.warning(f"⚠️ Задача провалена, попытка {task.retry_count}/{task.max_retries}: {task_id}")
        else:
            logger.warning(f"⚠️ Задача {task_id} не найдена для отметки провала")
    
    async def update_task(self, task: PublishTask):
        """Обновить задачу в очереди"""
        self.tasks[task.task_id] = task
    
    async def cancel_task(self, task_id: str) -> bool:
        """
        Отменить задачу
        
        Args:
            task_id: ID задачи
        
        Returns:
            True если задача отменена, False если не найдена
        """
        task = self.tasks.pop(task_id, None)
        
        if task:
            logger.info(f"🚫 Задача отменена: {task_id}")
            return True
        
        logger.warning(f"⚠️ Задача {task_id} не найдена для отмены")
        return False
    
    async def cleanup_old_tasks(self, days: int = 30) -> int:
        """
        Удалить старые выполненные задачи
        
        Args:
            days: Удалить задачи старше N дней
        
        Returns:
            Количество удалённых задач
        """
        cutoff_date = datetime.now() - timedelta(days=days)
        deleted_count = 0
        
        # Очистка выполненных задач
        for task_id in list(self.completed_tasks.keys()):
            task = self.completed_tasks[task_id]
            if task.scheduled_time < cutoff_date:
                del self.completed_tasks[task_id]
                deleted_count += 1
        
        # Очистка провалившихся задач
        for task_id in list(self.failed_tasks.keys()):
            task = self.failed_tasks[task_id]
            if task.scheduled_time < cutoff_date:
                del self.failed_tasks[task_id]
                deleted_count += 1
        
        return deleted_count
    
    def get_stats(self) -> Dict:
        """Получить статистику очереди"""
        pending = len([t for t in self.tasks.values() if t.status == TaskStatus.PENDING])
        scheduled = len([t for t in self.tasks.values() if t.status == TaskStatus.SCHEDULED])
        processing = len([t for t in self.tasks.values() if t.status == TaskStatus.PROCESSING])
        cancelled = len([t for t in self.tasks.values() if t.status == TaskStatus.CANCELLED])
        completed = len(self.completed_tasks)
        failed = len(self.failed_tasks)

        # Calculate total and success rate
        total = len(self.tasks) + completed + failed
        success_rate = (completed / (completed + failed) * 100) if (completed + failed) > 0 else 0.0

        return {
            "total": total,
            "pending": pending,
            "scheduled": scheduled,
            "processing": processing,
            "completed": completed,
            "failed": failed,
            "cancelled": cancelled,
            "success_rate": success_rate
        }
    
    def get_upcoming_tasks(self, limit: int = 10) -> List[PublishTask]:
        """
        Получить ближайшие запланированные задачи
        
        Args:
            limit: Максимум задач
        
        Returns:
            Список задач, отсортированных по времени
        """
        scheduled_tasks = [
            task for task in self.tasks.values()
            if task.status == TaskStatus.SCHEDULED
        ]
        
        # Сортируем по времени публикации
        scheduled_tasks.sort(key=lambda t: t.scheduled_time)
        
        return scheduled_tasks[:limit]


__all__ = ["TaskQueue"]
