import re


def clean_text(text: str) -> str:
    """Очищает текст от лишних пробелов и символов."""
    if not text:
        return ""
    # Удаляем лишние пробелы и переносы строк
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = text.strip()
    return text


def extract_title(text: str) -> str:
    """Извлекает первую строку в качестве заголовка."""
    if not text:
        return "Без заголовка"
    return text.split('\n')[0].strip()[:50]


def count_words(text: str) -> int:
    """Считает количество слов в тексте."""
    if not text:
        return 0
    return len(text.split())


def format_for_channel(text: str, specialty: str) -> str:
    """Форматирует текст для канала (добавляет хештеги и подпись)."""
    hashtags = {
        "gynecology": "#гинекология #здоровье #медицина",
        "pediatrics": "#педиатрия #дети #здоровье",
        "therapy": "#терапия #врач #здоровье"
    }

    tag_line = hashtags.get(specialty, "#медицина")
    return f"{text}\n\n{tag_line}"
