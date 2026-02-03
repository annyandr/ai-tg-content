"""
Кастомные исключения для приложения
"""


class MedicalSMMError(Exception):
    """Базовое исключение для всех ошибок приложения"""
    pass


class BotError(MedicalSMMError):
    """Ошибка работы бота"""
    pass


class PublishError(MedicalSMMError):
    """Ошибка публикации в канал"""
    pass


class GenerationError(MedicalSMMError):
    """Ошибка генерации контента"""
    pass


class ConfigError(MedicalSMMError):
    """Ошибка конфигурации"""
    pass


class ValidationError(MedicalSMMError):
    """Ошибка валидации данных"""
    pass


class APIError(MedicalSMMError):
    """Ошибка внешнего API"""
    pass


class SchedulerError(MedicalSMMError):
    """Ошибка планировщика"""
    pass


__all__ = [
    "MedicalSMMError",
    "BotError",
    "PublishError",
    "GenerationError",
    "ConfigError",
    "ValidationError",
    "APIError",
    "SchedulerError"
]
