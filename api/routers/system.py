"""System health and monitoring endpoints"""
from fastapi import APIRouter, Depends
from typing import Dict
import platform
import sys
from datetime import datetime

from api.dependencies import get_task_queue, get_telegram_bot
from src.telegram_bot.task_queue import TaskQueue
from src.telegram_bot.bot import MedicalTelegramBot

router = APIRouter(prefix="/api/v1/system", tags=["system"])


@router.get("/health")
async def health_check() -> Dict:
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0"
    }


@router.get("/stats")
async def system_stats(
    queue: TaskQueue = Depends(get_task_queue),
    bot: MedicalTelegramBot = Depends(get_telegram_bot)
) -> Dict:
    """Get system statistics"""
    task_stats = queue.get_stats()

    return {
        "system": {
            "python_version": sys.version,
            "platform": platform.platform(),
            "uptime": "N/A"  # TODO: Track startup time
        },
        "tasks": task_stats,
        "bot": {
            "running": True,
            "worker_active": True
        }
    }
