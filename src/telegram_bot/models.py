"""
Модели данных для Telegram Bot
"""

from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class TaskStatus(str, Enum):
    """Статусы задачи публикации"""
    PENDING = "pending"           # Ожидает публикации
    SCHEDULED = "scheduled"       # Запланирована
    PROCESSING = "processing"     # В процессе публикации
    COMPLETED = "completed"       # Успешно опубликована
    FAILED = "failed"            # Провалена
    CANCELLED = "cancelled"       # Отменена


class ButtonModel(BaseModel):
    """Модель кнопки для поста"""
    text: str
    url: str


class PublishTask(BaseModel):
    """Задача на публикацию поста"""
    
    # Основные данные
    task_id: str = Field(..., description="Уникальный ID задачи")
    channel_id: str = Field(..., description="ID канала (@profgynecologist)")
    text: str = Field(..., description="Текст поста (HTML/Markdown)")
    scheduled_time: datetime = Field(..., description="Время публикации")
    status: TaskStatus = Field(default=TaskStatus.PENDING, description="Статус задачи")
    
    # Результат публикации
    message_id: Optional[int] = Field(default=None, description="ID опубликованного сообщения")
    published_at: Optional[datetime] = Field(default=None, description="Фактическое время публикации")
    
    # Медиа
    photo_url: Optional[str] = Field(default=None, description="URL фото")
    video_url: Optional[str] = Field(default=None, description="URL видео")
    document_url: Optional[str] = Field(default=None, description="URL документа")
    
    # Кнопки
    buttons: Optional[List[ButtonModel]] = Field(default=None, description="Кнопки под постом")
    
    # Повторные попытки
    retry_count: int = Field(default=0, description="Количество попыток")
    max_retries: int = Field(default=3, description="Максимум попыток")
    last_error: Optional[str] = Field(default=None, description="Последняя ошибка")
    
    # Метаданные
    created_at: datetime = Field(default_factory=datetime.now, description="Время создания")
    created_by: Optional[int] = Field(default=None, description="ID создателя (Telegram user_id)")
    
    # Настройки форматирования
    parse_mode: str = Field(default="HTML", description="Режим парсинга (HTML/Markdown)")
    disable_web_page_preview: bool = Field(default=False, description="Отключить превью ссылок")
    disable_notification: bool = Field(default=False, description="Отключить уведомления")
    
    class Config:
        use_enum_values = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """Конвертация в словарь"""
        return self.model_dump()
    
    def is_ready_to_publish(self, current_time: datetime = None) -> bool:
        """
        Проверка готовности к публикации
        
        Args:
            current_time: Текущее время (по умолчанию datetime.now())
        
        Returns:
            True если задача готова к публикации
        """
        if current_time is None:
            current_time = datetime.now()
        
        return (
            self.status in [TaskStatus.PENDING, TaskStatus.SCHEDULED] and
            self.scheduled_time <= current_time and
            self.retry_count < self.max_retries
        )
    
    def can_retry(self) -> bool:
        """Можно ли повторить попытку публикации"""
        return (
            self.status == TaskStatus.FAILED and
            self.retry_count < self.max_retries
        )


class BotStats(BaseModel):
    """Статистика бота"""
    active_tasks: int = 0
    pending: int = 0
    scheduled: int = 0
    processing: int = 0
    completed: int = 0
    failed: int = 0
    cancelled: int = 0
    total_published: int = 0
    success_rate: float = 0.0


__all__ = [
    "TaskStatus",
    "ButtonModel",
    "PublishTask",
    "BotStats"
]
