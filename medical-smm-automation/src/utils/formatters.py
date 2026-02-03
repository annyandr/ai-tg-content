# Очистка текста от лишних символов
clean_text(text)

# Извлечение заголовка
extract_title(text)

# Подсчёт слов и предложений
count_words(text)
count_sentences(text)

# Работа с эмодзи
extract_emojis(text)

# Обрезка текста
truncate_text(text, max_length=100)

# Markdown → Plain text
markdown_to_plain(text)

# Форматирование для любого канала
format_for_channel(text, channel_emoji="🍑", channel_link="...", specialty_name="...")

# Валидация Markdown
validate_markdown(text)  # Проверяет закрытые теги

# Время чтения
estimate_reading_time(text)  # В секундах
