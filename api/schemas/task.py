"""Task-related Pydantic schemas"""
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from src.telegram_bot.models import PublishTask, TaskStatus


class TaskCreate(BaseModel):
    """Schema for creating a new task"""
    channel_id: str = Field(..., description="Telegram channel ID")
    text: str = Field(..., description="Post content", max_length=4096)
    scheduled_time: datetime = Field(..., description="When to publish")
    photo_url: Optional[str] = Field(None, description="Optional photo URL")


class TaskResponse(BaseModel):
    """Schema for task response"""
    task_id: str
    channel_id: str
    text: str
    scheduled_time: datetime
    status: str
    photo_url: Optional[str] = None
    created_at: datetime
    error_message: Optional[str] = None
    retry_count: int = 0

    @classmethod
    def from_publish_task(cls, task: PublishTask) -> "TaskResponse":
        """Convert PublishTask to TaskResponse"""
        # Handle both TaskStatus enum and string values
        status_value = task.status.value if hasattr(task.status, 'value') else task.status

        return cls(
            task_id=task.task_id,
            channel_id=task.channel_id,
            text=task.text,
            scheduled_time=task.scheduled_time,
            status=status_value,
            photo_url=task.photo_url,
            created_at=task.created_at,
            error_message=task.last_error,  # PublishTask uses 'last_error', not 'error_message'
            retry_count=task.retry_count
        )


class TaskStats(BaseModel):
    """Schema for task statistics"""
    total: int = Field(..., description="Total tasks")
    pending: int = Field(..., description="Pending tasks")
    scheduled: int = Field(..., description="Scheduled tasks")
    processing: int = Field(..., description="Processing tasks")
    completed: int = Field(..., description="Completed tasks")
    failed: int = Field(..., description="Failed tasks")
    cancelled: int = Field(..., description="Cancelled tasks")
    success_rate: float = Field(..., description="Success rate percentage")
