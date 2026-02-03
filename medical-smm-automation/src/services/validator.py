import logging

logger = logging.getLogger(__name__)

class PostValidator:
    """Класс для валидации сгенерированных постов."""

    def __init__(self):
        self.min_length = 50
        self.max_length = 4000
        # Список стоп-слов (пример)
        self.forbidden_words = ["срочно купите", "инфоцыгане", "100% гарантия"]

    def validate_post(self, content: str) -> dict:
        """
        Проверяет пост на корректность.
        Возвращает словарь: {"valid": bool, "error": str/None}
        """
        if not content:
            return {"valid": False, "error": "Пустой контент"}

        if len(content) < self.min_length:
            return {"valid": False, "error": "Текст слишком короткий"}

        if len(content) > self.max_length:
            return {"valid": False, "error": "Текст слишком длинный для Telegram"}

        for word in self.forbidden_words:
            if word.lower() in content.lower():
                return {"valid": False, "error": f"Найдено запрещенное слово: {word}"}

        return {"valid": True, "error": None}
