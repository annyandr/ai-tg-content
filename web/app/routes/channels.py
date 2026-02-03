"""Channels routes"""
from flask import Blueprint, render_template, flash
from app.api_client import MedicalSMMAPIClient
import asyncio
from functools import wraps

bp = Blueprint('channels', __name__, url_prefix='/channels')


def async_route(f):
    """Decorator to run async functions in Flask"""
    @wraps(f)
    def wrapper(*args, **kwargs):
        return asyncio.run(f(*args, **kwargs))
    return wrapper


@bp.route('/')
@async_route
async def list_channels():
    """List all channels"""
    try:
        async with MedicalSMMAPIClient() as client:
            channels = await client.list_channels()

        return render_template('channels/list.html', channels=channels)
    except Exception as e:
        flash(f'Ошибка загрузки каналов: {str(e)}', 'error')
        return render_template('channels/list.html', channels=[])
