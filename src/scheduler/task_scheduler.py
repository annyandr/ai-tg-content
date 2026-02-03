"""
Планировщик задач для автоматической публикации
"""

import asyncio
from datetime import datetime, time
from typing import Optional, Callable, List
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from src.core.logger import logger
from src.core.config import config


class TaskScheduler:
    """
    Планировщик для автоматической публикации контента
    """
    
    def __init__(self):
        """Инициализация планировщика"""
        self.scheduler = AsyncIOScheduler(timezone=config.TIMEZONE)
        self.is_running = False
        logger.info("📅 Планировщик инициализирован")
    
    def start(self):
        """Запуск планировщика"""
        if not self.is_running:
            self.scheduler.start()
            self.is_running = True
            logger.info("✅ Планировщик запущен")
    
    def stop(self):
        """Остановка планировщика"""
        if self.is_running:
            self.scheduler.shutdown()
            self.is_running = False
            logger.info("🛑 Планировщик остановлен")
    
    def add_daily_job(
        self,
        func: Callable,
        hour: int,
        minute: int = 0,
        job_id: Optional[str] = None
    ):
        """
        Добавить ежедневную задачу
        
        Args:
            func: Функция для выполнения
            hour: Час выполнения (0-23)
            minute: Минута выполнения (0-59)
            job_id: ID задачи (опционально)
        """
        trigger = CronTrigger(
            hour=hour,
            minute=minute,
            timezone=config.TIMEZONE
        )
        
        self.scheduler.add_job(
            func,
            trigger=trigger,
            id=job_id,
            replace_existing=True
        )
        
        logger.info(f"⏰ Добавлена ежедневная задача: {hour:02d}:{minute:02d}")
    
    def add_interval_job(
        self,
        func: Callable,
        minutes: int,
        job_id: Optional[str] = None
    ):
        """
        Добавить задачу с интервалом
        
        Args:
            func: Функция для выполнения
            minutes: Интервал в минутах
            job_id: ID задачи (опционально)
        """
        self.scheduler.add_job(
            func,
            'interval',
            minutes=minutes,
            id=job_id,
            replace_existing=True
        )
        
        logger.info(f"⏰ Добавлена задача с интервалом: каждые {minutes} мин")
    
    def remove_job(self, job_id: str) -> bool:
        """
        Удалить задачу
        
        Args:
            job_id: ID задачи
        
        Returns:
            True если задача удалена
        """
        try:
            self.scheduler.remove_job(job_id)
            logger.info(f"🗑️ Задача {job_id} удалена")
            return True
        except Exception as e:
            logger.warning(f"⚠️ Не удалось удалить задачу {job_id}: {e}")
            return False
    
    def get_jobs(self) -> List[dict]:
        """
        Получить список всех задач
        
        Returns:
            Список задач
        """
        jobs = []
        
        for job in self.scheduler.get_jobs():
            jobs.append({
                'id': job.id,
                'name': job.name,
                'next_run': job.next_run_time,
                'trigger': str(job.trigger)
            })
        
        return jobs
    
    def pause_job(self, job_id: str) -> bool:
        """Приостановить задачу"""
        try:
            self.scheduler.pause_job(job_id)
            logger.info(f"⏸️ Задача {job_id} приостановлена")
            return True
        except Exception as e:
            logger.warning(f"⚠️ Не удалось приостановить задачу {job_id}: {e}")
            return False
    
    def resume_job(self, job_id: str) -> bool:
        """Возобновить задачу"""
        try:
            self.scheduler.resume_job(job_id)
            logger.info(f"▶️ Задача {job_id} возобновлена")
            return True
        except Exception as e:
            logger.warning(f"⚠️ Не удалось возобновить задачу {job_id}: {e}")
            return False


__all__ = ["TaskScheduler"]
