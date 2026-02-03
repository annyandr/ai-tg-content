"""
Утилиты для работы с Telegram каналами
"""


def normalize_channel_id(channel: str) -> str:
    """
    Нормализует channel в формат для Telegram API

    Args:
        channel: Username (profgynecologist) или ID (-1003748097480)

    Returns:
        Нормализованный channel_id для Telegram API
        - Для username: @username
        - Для numeric ID: без изменений
    """
    if not channel:
        return None

    # Если начинается с "-" или содержит только цифры → это channel ID
    if channel.startswith('-') or channel.lstrip('-').isdigit():
        return channel

    # Если содержит только буквы/цифры/подчеркивания → это username
    # Добавляем @ если его нет
    if not channel.startswith('@'):
        return f"@{channel}"

    return channel


def get_channel_display_name(channel: str, name: str = None) -> str:
    """
    Возвращает отформатированное имя канала для отображения в UI

    Args:
        channel: Username или ID канала
        name: Человекочитаемое имя (например, "Гинекология")

    Returns:
        Отформатированная строка для UI
    """
    # Если это numeric ID - показываем имя или "Частный канал"
    if channel.startswith('-') or channel.lstrip('-').isdigit():
        return name if name else "Частный канал"

    # Для username показываем с @
    if not channel.startswith('@'):
        return f"@{channel}"

    return channel


def is_channel_id(channel: str) -> bool:
    """
    Проверяет, является ли значение numeric channel ID

    Args:
        channel: Строка для проверки

    Returns:
        True если это numeric ID, False если username
    """
    if not channel:
        return False

    # Numeric ID начинается с "-" и содержит только цифры
    return channel.startswith('-') or channel.lstrip('-').isdigit()


__all__ = ["normalize_channel_id", "get_channel_display_name", "is_channel_id"]
