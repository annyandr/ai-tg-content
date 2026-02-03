"""Dashboard routes"""
from flask import Blueprint, render_template, flash
from app.api_client import MedicalSMMAPIClient
import asyncio
from functools import wraps

bp = Blueprint('dashboard', __name__)


def async_route(f):
    """Decorator to run async functions in Flask"""
    @wraps(f)
    def wrapper(*args, **kwargs):
        return asyncio.run(f(*args, **kwargs))
    return wrapper


@bp.route('/')
@async_route
async def index():
    """Dashboard main page"""
    try:
        async with MedicalSMMAPIClient() as client:
            stats = await client.get_stats()
            recent_tasks = await client.list_tasks(limit=10)
            channels = await client.list_channels()

        return render_template(
            'dashboard.html',
            stats=stats,
            recent_tasks=recent_tasks,
            channels=channels
        )
    except Exception as e:
        flash(f'Ошибка загрузки данных: {str(e)}', 'error')
        return render_template('dashboard.html', stats={}, recent_tasks=[], channels=[])
