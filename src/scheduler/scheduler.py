"""
Планировщик задач для автоматической публикации
"""

import asyncio
from datetime import datetime, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from typing import Optional

from src.core.logger import logger
from src.core.config import config


class PostScheduler:
    """
    Планировщик публикаций постов
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
        else:
            logger.warning("⚠️ Планировщик уже запущен")
    
    def stop(self):
        """Остановка планировщика"""
        if self.is_running:
            self.scheduler.shutdown()
            self.is_running = False
            logger.info("🛑 Планировщик остановлен")
    
    def add_daily_jobs(self, callback, times: list = None):
        """
        Добавляет ежедневные задачи публикации
        
        Args:
            callback: Async функция для выполнения
            times: Список времён в формате "HH:MM" (например ["09:00", "20:00"])
        """
        if times is None:
            times = config.POSTING_TIMES
        
        for time_str in times:
            try:
                hour, minute = map(int, time_str.split(":"))
                
                self.scheduler.add_job(
                    callback,
                    trigger=CronTrigger(hour=hour, minute=minute, timezone=config.TIMEZONE),
                    id=f"daily_post_{time_str}",
                    name=f"Ежедневная публикация в {time_str}",
                    replace_existing=True,
                    misfire_grace_time=300  # 5 минут на выполнение пропущенной задачи
                )
                
                logger.info(f"✅ Добавлена ежедневная задача: {time_str} MSK")
            
            except ValueError as e:
                logger.error(f"❌ Неверный формат времени '{time_str}': {e}")
    
    def add_scheduled_job(self, callback, run_date: datetime, job_id: str = None):
        """
        Добавляет одноразовую задачу на конкретное время
        
        Args:
            callback: Async функция для выполнения
            run_date: Время выполнения (datetime)
            job_id: ID задачи (опционально)
        """
        if run_date <= datetime.now():
            logger.error(f"❌ Время {run_date} уже прошло, задача не добавлена")
            return None
        
        if job_id is None:
            job_id = f"scheduled_{run_date.strftime('%Y%m%d_%H%M%S')}"
        
        job = self.scheduler.add_job(
            callback,
            trigger=DateTrigger(run_date=run_date, timezone=config.TIMEZONE),
            id=job_id,
            name=f"Публикация {run_date.strftime('%d.%m.%Y %H:%M')}",
            replace_existing=True,
            misfire_grace_time=600  # 10 минут на выполнение
        )
        
        logger.info(f"⏰ Задача запланирована: {run_date.strftime('%d.%m.%Y %H:%M')} (ID: {job_id})")
        return job
    
    def add_interval_job(self, callback, minutes: int, job_id: str = None):
        """
        Добавляет задачу с интервальным выполнением
        
        Args:
            callback: Async функция для выполнения
            minutes: Интервал в минутах
            job_id: ID задачи
        """
        if job_id is None:
            job_id = f"interval_{minutes}min"
        
        self.scheduler.add_job(
            callback,
            trigger="interval",
            minutes=minutes,
            id=job_id,
            name=f"Интервальная задача (каждые {minutes} мин)",
            replace_existing=True
        )
        
        logger.info(f"🔄 Добавлена интервальная задача: каждые {minutes} мин (ID: {job_id})")
    
    def remove_job(self, job_id: str):
        """Удаление задачи по ID"""
        try:
            self.scheduler.remove_job(job_id)
            logger.info(f"🗑️ Задача удалена: {job_id}")
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка удаления задачи {job_id}: {e}")
            return False
    
    def get_jobs(self):
        """Получить список всех задач"""
        return self.scheduler.get_jobs()
    
    def get_job(self, job_id: str):
        """Получить задачу по ID"""
        return self.scheduler.get_job(job_id)
    
    def print_jobs(self):
        """Вывести все запланированные задачи"""
        jobs = self.get_jobs()
        
        if not jobs:
            logger.info("📋 Нет запланированных задач")
            return
        
        logger.info(f"📋 Запланировано задач: {len(jobs)}")
        for job in jobs:
            next_run = job.next_run_time.strftime('%d.%m.%Y %H:%M:%S') if job.next_run_time else "N/A"
            logger.info(f"  • {job.id} — {job.name} — {next_run}")


# Глобальный экземпляр планировщика
scheduler = PostScheduler()

__all__ = ["scheduler", "PostScheduler"]
