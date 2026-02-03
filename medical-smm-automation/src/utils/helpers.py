# Генерация ID
generate_id(prefix="post", length=8)  # "post_a3f9c2d1"

# Хеширование контента
hash_content(content)  # MD5 для проверки дубликатов

# Декоратор повторных попыток
@retry_async(max_attempts=3, delay=1.0)
async def my_function():
    pass

# Парсинг времени
parse_time_string("09:00")  # → datetime
parse_time_string("2026-02-03 09:00:00")

# Вычисление следующего времени публикации
calculate_next_posting_time(base_time, slot="morning")  # 09:00
calculate_next_posting_time(base_time, slot="evening")  # 20:00

# Безопасное получение из словаря
safe_get(data, "user", "profile", "name", default="Unknown")

# Работа с JSON
load_json_file("config.json", default={})
save_json_file("data.json", data)

# Разбиение на чанки
list(chunks([1,2,3,4,5], size=2))  # [[1,2], [3,4], [5]]

# Замер времени
with Timer("Generation"):
    await generate_post()  # Автоматически выведет время
