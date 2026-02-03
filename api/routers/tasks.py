"""Tasks API endpoints"""
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional
from datetime import datetime

from api.schemas.task import TaskCreate, TaskResponse, TaskStats
from api.schemas.response import SuccessResponse
from api.dependencies import get_telegram_bot, get_task_queue
from src.telegram_bot.bot import MedicalTelegramBot
from src.telegram_bot.task_queue import TaskQueue
from src.telegram_bot.models import TaskStatus

router = APIRouter(prefix="/api/v1/tasks", tags=["tasks"])


@router.post("", response_model=TaskResponse, status_code=201)
async def create_task(
    task_data: TaskCreate,
    bot: MedicalTelegramBot = Depends(get_telegram_bot)
):
    """Create a new publish task"""
    try:
        task_id = await bot.schedule_post(
            channel_id=task_data.channel_id,
            text=task_data.text,
            scheduled_time=task_data.scheduled_time,
            photo_url=task_data.photo_url
        )

        # Get the created task
        queue = get_task_queue()
        task = queue.get_task(task_id)

        if not task:
            raise HTTPException(status_code=500, detail="Failed to retrieve created task")

        return TaskResponse.from_publish_task(task)

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("", response_model=List[TaskResponse])
async def list_tasks(
    status: Optional[str] = Query(None, description="Filter by status"),
    limit: int = Query(50, ge=1, le=500, description="Maximum number of tasks to return"),
    queue: TaskQueue = Depends(get_task_queue)
):
    """Get list of tasks with optional filtering"""
    try:
        if status == "failed":
            tasks = await queue.get_failed_tasks()
        elif status == "upcoming":
            tasks = queue.get_upcoming_tasks(limit=limit)
        elif status:
            # Filter by specific status
            tasks = [
                task for task in queue.tasks.values()
                if task.status.value == status
            ]
        else:
            # All tasks
            tasks = list(queue.tasks.values())

        # Sort by scheduled_time (most recent first)
        tasks.sort(key=lambda x: x.scheduled_time, reverse=True)

        return [TaskResponse.from_publish_task(t) for t in tasks[:limit]]

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats", response_model=TaskStats)
async def get_stats(queue: TaskQueue = Depends(get_task_queue)):
    """Get task statistics"""
    try:
        stats = queue.get_stats()
        return TaskStats(**stats)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(
    task_id: str,
    queue: TaskQueue = Depends(get_task_queue)
):
    """Get task details by ID"""
    task = queue.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    return TaskResponse.from_publish_task(task)


@router.delete("/{task_id}", response_model=SuccessResponse)
async def cancel_task(
    task_id: str,
    bot: MedicalTelegramBot = Depends(get_telegram_bot)
):
    """Cancel a task"""
    try:
        success = await bot.cancel_post(task_id)
        if not success:
            raise HTTPException(status_code=404, detail="Task not found or already completed")

        return SuccessResponse(message="Task cancelled successfully")

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
