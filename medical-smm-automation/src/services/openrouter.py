service = OpenRouterService(api_key="...", model="anthropic/claude-3.5-sonnet")

# Генерация текста
result = await service.generate(
    system_prompt="Ты медицинский редактор",
    user_prompt="Создай пост про эндометриоз",
    temperature=0.75
)

# Генерация с повторами при ошибках
result = await service.generate_with_retry(
    system_prompt="...",
    user_prompt="...",
    max_retries=3
)

# Генерация JSON
result = await service.generate_json(
    system_prompt="...",
    user_prompt="Верни результат в JSON"
)

# Статистика
stats = service.get_stats()
# {'total_requests': 42, 'total_cost': 1.23, 'average_cost': 0.029}
