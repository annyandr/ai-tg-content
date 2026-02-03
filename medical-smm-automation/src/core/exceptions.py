"""
Кастомные исключения
"""


class MedicalSMMException(Exception):
    """Базовое исключение системы"""
    pass


class GenerationError(MedicalSMMException):
    """Ошибка генерации контента"""
    pass


class SafetyCheckError(MedicalSMMException):
    """Ошибка проверки безопасности"""
    pass


class PublishError(MedicalSMMException):
    """Ошибка публикации"""
    pass


class DatabaseError(MedicalSMMException):
    """Ошибка работы с БД"""
    pass


__all__ = [
    "MedicalSMMException",
    "GenerationError",
    "SafetyCheckError",
    "PublishError",
    "DatabaseError"
]
