"""
Загрузчик специализированных промптов
Маппинг всех медицинских специализаций
"""

import json
import os
from typing import Dict, List, Optional

# Импортируем все промпты
from src.agents.gynecology_prompts import GYNECOLOGY_SPECIALTY_PROMPT
from src.agents.pediatrics_prompts import PEDIATRICS_SPECIALTY_PROMPT
from src.agents.endocrinology_prompts import ENDOCRINOLOGY_SPECIALTY_PROMPT
from src.agents.therapy_prompts import THERAPY_SPECIALTY_PROMPT
from src.agents.dermatology_prompts import DERMATOLOGY_SPECIALTY_PROMPT
from src.core.logger import logger


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

# Файл для сохранения привязок каналов
CHANNEL_OVERRIDES_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "data", "channel_overrides.json"
)


def _load_channel_overrides():
    """Загружает сохранённые привязки каналов и применяет к SPECIALTY_MAP"""
    if not os.path.exists(CHANNEL_OVERRIDES_PATH):
        return

    try:
        with open(CHANNEL_OVERRIDES_PATH, "r", encoding="utf-8") as f:
            overrides = json.load(f)

        for specialty, override in overrides.items():
            if specialty in SPECIALTY_MAP:
                if "channel" in override:
                    SPECIALTY_MAP[specialty]["channel"] = override["channel"]
                if "link" in override:
                    SPECIALTY_MAP[specialty]["link"] = override["link"]
                logger.info(
                    f"📡 Канал для {SPECIALTY_MAP[specialty]['name']}: "
                    f"{override.get('channel', '?')}"
                )

    except Exception as e:
        logger.error(f"Ошибка загрузки channel_overrides.json: {e}")


def update_channel_for_specialty(specialty: str, channel_id: str, link: str = None) -> bool:
    """
    Обновляет ID канала для специализации в памяти и сохраняет на диск.

    Args:
        specialty: Ключ специализации (гинекология, педиатрия и т.д.)
        channel_id: Новый ID канала (числовой, например '-100...')
        link: Ссылка на канал (опционально)

    Returns:
        True если обновлено успешно
    """
    if specialty not in SPECIALTY_MAP:
        return False

    # Обновляем в памяти
    SPECIALTY_MAP[specialty]["channel"] = str(channel_id)
    if link:
        SPECIALTY_MAP[specialty]["link"] = link

    # Сохраняем на диск
    try:
        overrides = {}
        if os.path.exists(CHANNEL_OVERRIDES_PATH):
            with open(CHANNEL_OVERRIDES_PATH, "r", encoding="utf-8") as f:
                overrides = json.load(f)

        overrides[specialty] = {
            "channel": str(channel_id),
            "link": link or SPECIALTY_MAP[specialty]["link"],
            "name": SPECIALTY_MAP[specialty]["name"]
        }

        os.makedirs(os.path.dirname(CHANNEL_OVERRIDES_PATH), exist_ok=True)
        with open(CHANNEL_OVERRIDES_PATH, "w", encoding="utf-8") as f:
            json.dump(overrides, f, ensure_ascii=False, indent=2)

        logger.info(f"✅ Канал для {SPECIALTY_MAP[specialty]['name']} обновлён: {channel_id}")
        return True

    except Exception as e:
        logger.error(f"Ошибка сохранения channel_overrides: {e}")
        return True  # В памяти обновлено, просто не сохранилось


# Загружаем привязки при импорте модуля
_load_channel_overrides()


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
    "get_channel_by_specialty",
    "update_channel_for_specialty"
]
