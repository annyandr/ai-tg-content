"""Posts routes"""
from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from app.api_client import MedicalSMMAPIClient
import asyncio
from datetime import datetime
from functools import wraps

bp = Blueprint('posts', __name__, url_prefix='/posts')


def async_route(f):
    """Decorator to run async functions in Flask"""
    @wraps(f)
    def wrapper(*args, **kwargs):
        return asyncio.run(f(*args, **kwargs))
    return wrapper


@bp.route('/')
@async_route
async def list_posts():
    """List all posts"""
    status = request.args.get('status', 'all')

    try:
        async with MedicalSMMAPIClient() as client:
            if status == 'all':
                tasks = await client.list_tasks(limit=100)
            else:
                tasks = await client.list_tasks(status=status, limit=100)

            stats = await client.get_stats()

        return render_template(
            'posts/list.html',
            tasks=tasks,
            stats=stats,
            current_status=status
        )
    except Exception as e:
        flash(f'Ошибка загрузки постов: {str(e)}', 'error')
        return render_template('posts/list.html', tasks=[], stats={}, current_status=status)


@bp.route('/create', methods=['GET', 'POST'])
@async_route
async def create_post():
    """Create new post"""

    if request.method == 'GET':
        # Get channels and specialties
        try:
            async with MedicalSMMAPIClient() as client:
                channels = await client.list_channels()
                specialties = await client.list_specialties()

            return render_template(
                'posts/create.html',
                channels=channels,
                specialties=specialties
            )
        except Exception as e:
            flash(f'Ошибка загрузки данных: {str(e)}', 'error')
            return render_template('posts/create.html', channels=[], specialties=[])

    # POST - create post
    form_data = request.form

    # Get ISO datetime from hidden field (Flatpickr provides this)
    scheduled_time_str = form_data.get('scheduled_time_iso') or form_data.get('scheduled_time')

    task_data = {
        "channel_id": form_data.get('channel_id'),
        "text": form_data.get('text'),
        "scheduled_time": scheduled_time_str,
        "photo_url": form_data.get('photo_url') if form_data.get('photo_url') else None
    }

    try:
        async with MedicalSMMAPIClient() as client:
            result = await client.create_task(task_data)

        flash(f'Пост создан успешно! ID: {result["task_id"]}', 'success')
        return redirect(url_for('posts.list_posts'))

    except Exception as e:
        flash(f'Ошибка создания поста: {str(e)}', 'error')
        return redirect(url_for('posts.create_post'))


@bp.route('/<task_id>/cancel', methods=['POST'])
@async_route
async def cancel_post(task_id):
    """Cancel post"""
    try:
        async with MedicalSMMAPIClient() as client:
            await client.cancel_task(task_id)

        flash('Пост отменён успешно', 'success')
    except Exception as e:
        flash(f'Ошибка отмены: {str(e)}', 'error')

    return redirect(url_for('posts.list_posts'))


@bp.route('/generate', methods=['POST'])
@async_route
async def generate_content():
    """AI generate content (AJAX endpoint)"""
    data = request.get_json()

    try:
        async with MedicalSMMAPIClient() as client:
            result = await client.generate_content(
                topic=data['topic'],
                specialty=data['specialty'],
                post_type=data.get('post_type', 'клинрекомендации'),
                max_length=data.get('max_length', 2000)
            )

        return jsonify(result)

    except Exception as e:
        return jsonify({"error": str(e)}), 400
