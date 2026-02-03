"""
Загрузчик специализированных промптов
Маппинг всех медицинских специализаций
"""

from typing import Dict, List, Optional

# Импортируем все промпты
from src.agents.gynecology_prompts import GYNECOLOGY_SPECIALTY_PROMPT
from src.agents.pediatrics_prompts import PEDIATRICS_SPECIALTY_PROMPT
from src.agents.endocrinology_prompts import ENDOCRINOLOGY_SPECIALTY_PROMPT
from src.agents.therapy_prompts import THERAPY_SPECIALTY_PROMPT
from src.agents.dermatology_prompts import DERMATOLOGY_SPECIALTY_PROMPT


# Маппинг специализаций
SPECIALTY_MAP: Dict[str, Dict] = {
    "гинекология": {
        "prompt": GYNECOLOGY_SPECIALTY_PROMPT,
        "emoji": "🍑",
        "channel": "-1003748097480",
        "link": "https://t.me/profgynecologist",
        "name": "Гинекология",
        "channel_key": "gynecology"
    },
    "педиатрия": {
        "prompt": PEDIATRICS_SPECIALTY_PROMPT,
        "emoji": "👶",
        "channel": "-1003711554131",
        "link": "https://t.me/profpediatrician",
        "name": "Педиатрия",
        "channel_key": "pediatrics"
    },
    "эндокринология": {
        "prompt": ENDOCRINOLOGY_SPECIALTY_PROMPT,
        "emoji": "🩺",
        "channel": "profendocrinologist",
        "link": "https://t.me/profendocrinologist",
        "name": "Эндокринология",
        "channel_key": "endocrinology"
    },
    "терапия": {
        "prompt": THERAPY_SPECIALTY_PROMPT,
        "emoji": "🫀",
        "channel": "profphysician",
        "link": "https://t.me/profphysician",
        "name": "Терапия",
        "channel_key": "therapy"
    },
    "дерматология": {
        "prompt": DERMATOLOGY_SPECIALTY_PROMPT,
        "emoji": "🧴",
        "channel": "profdermatologists",
        "link": "https://t.me/profdermatologists",
        "name": "Дерматология",
        "channel_key": "dermatology"
    }
}


def get_specialty_config(specialty: str) -> Optional[Dict]:
    """
    Получить конфигурацию специализации

    Args:
        specialty: Название специализации (гинекология, педиатрия и т.д.)

    Returns:
        Dict с конфигурацией или None
    """
    specialty_lower = specialty.lower()
    return SPECIALTY_MAP.get(specialty_lower)


def get_specialty_prompt(specialty: str) -> str:
    """
    Получить промпт для специализации

    Args:
        specialty: Название специализации

    Returns:
        Промпт или пустая строка
    """
    config = get_specialty_config(specialty)
    if config:
        return config["prompt"]
    return ""


def get_all_specialties() -> List[str]:
    """Получить список всех доступных специализаций"""
    return list(SPECIALTY_MAP.keys())


def get_specialty_by_channel(channel: str) -> Optional[str]:
    """
    Найти специализацию по имени канала

    Args:
        channel: Username канала (profgynecologist и т.д.)

    Returns:
        Название специализации или None
    """
    for specialty, config in SPECIALTY_MAP.items():
        if config["channel"] == channel:
            return specialty
    return None


def get_channel_by_specialty(specialty: str) -> Optional[str]:
    """
    Получить канал по специализации

    Args:
        specialty: Название специализации

    Returns:
        Username канала или None
    """
    config = get_specialty_config(specialty)
    if config:
        return config["channel"]
    return None


__all__ = [
    "SPECIALTY_MAP",
    "get_specialty_config",
    "get_specialty_prompt",
    "get_all_specialties",
    "get_specialty_by_channel",
    "get_channel_by_specialty"
]
