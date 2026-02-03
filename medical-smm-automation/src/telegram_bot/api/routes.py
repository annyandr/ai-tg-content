"""
API эндпоинты для управления публикациями
"""
from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, Field

from fastapi import APIRouter, HTTPException, status

from src.telegram_bot.bot import MedicalTelegramBot
from src.telegram_bot.models import PublishTask
from src.core.logger import logger


# Схемы запросов
class SchedulePostRequest(BaseModel):
    """Запрос на планирование поста"""
    channel_id: str = Field(..., description="ID или username канала")
    text: str = Field(..., description="Текст поста")
    scheduled_time: datetime = Field(..., description="Время публикации")
    parse_mode: str = Field(default="Markdown", description="Режим парсинга")
    photo_url: Optional[str] = Field(default=None)
    video_url: Optional[str] = Field(default=None)
    document_url: Optional[str] = Field(default=None)
    buttons: Optional[List[dict]] = Field(default=None)
    task_id: Optional[str] = Field(default=None)


class SchedulePostResponse(BaseModel):
    """Ответ на планирование поста"""
    success: bool
    task_id: str
    scheduled_time: datetime
    message: str


class CancelTaskResponse(BaseModel):
    """Ответ на отмену задачи"""
    success: bool
    message: str


class TaskStatusResponse(BaseModel):
    """Ответ со статусом задачи"""
    task: Optional[PublishTask]
    found: bool


class StatsResponse(BaseModel):
    """Статистика бота"""
    stats: dict


# Создаём router
def create_api_router(bot: MedicalTelegramBot) -> APIRouter:
    """
    Создаёт API router с эндпоинтами
    
    Args:
        bot: Экземпляр MedicalTelegramBot
        
    Returns:
        APIRouter
    """
    router = APIRouter(prefix="/api", tags=["bot"])
    
    @router.post("/schedule_post", response_model=SchedulePostResponse)
    async def schedule_post(request: SchedulePostRequest):
        """
        Планирует публикацию поста
        
        Принимает задачу и добавляет её в очередь.
        Пост будет опубликован в указанное время.
        """
        try:
            task_id = await bot.schedule_post(
                channel_id=request.channel_id,
                text=request.text,
                scheduled_time=request.scheduled_time,
                task_id=request.task_id,
                parse_mode=request.parse_mode,
                photo_url=request.photo_url,
                video_url=request.video_url,
                document_url=request.document_url,
                buttons=request.buttons
            )
            
            logger.info(
                f"API: Запланирован пост {task_id} "
                f"для {request.channel_id} на {request.scheduled_time}"
            )
            
            return SchedulePostResponse(
                success=True,
                task_id=task_id,
                scheduled_time=request.scheduled_time,
                message=f"Пост запланирован на {request.scheduled_time}"
            )
            
        except Exception as e:
            logger.error(f"API: Ошибка планирования поста: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=str(e)
            )
    
    @router.delete("/cancel_task/{task_id}", response_model=CancelTaskResponse)
    async def cancel_task(task_id: str):
        """Отменяет запланированную публикацию"""
        try:
            success = await bot.cancel_post(task_id)
            
            if success:
                logger.info(f"API: Задача {task_id} отменена")
                return CancelTaskResponse(
                    success=True,
                    message=f"Задача {task_id} отменена"
                )
            else:
                return CancelTaskResponse(
                    success=False,
                    message=f"Задачу {task_id} нельзя отменить"
                )
                
        except Exception as e:
            logger.error(f"API: Ошибка отмены задачи: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=str(e)
            )
    
    @router.get("/task_status/{task_id}", response_model=TaskStatusResponse)
    async def get_task_status(task_id: str):
        """Получает статус задачи"""
        task = await bot.get_task_status(task_id)
        return TaskStatusResponse(task=task, found=task is not None)
    
    @router.get("/stats", response_model=StatsResponse)
    async def get_stats():
        """Получает статистику бота"""
        stats = bot.get_stats()
        return StatsResponse(stats=stats)
    
    @router.get("/health")
    async def health_check():
        """Health check эндпоинт"""
        return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}
    
    return router


__all__ = ["create_api_router", "SchedulePostRequest", "SchedulePostResponse"]
