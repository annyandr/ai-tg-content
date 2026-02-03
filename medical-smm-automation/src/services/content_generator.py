generator = ContentGeneratorService(
    openrouter=openrouter_service,
    validator=validator,
    auto_validate=True
)

# Генерация поста из новости
post = await generator.generate_post(
    news=news,
    channel_key="gynecology",
    specialty="гинекология",
    max_retries=3  # Повторяет до валидного результата
)

# Перегенерация с учётом обратной связи
improved_post = await generator.regenerate_post(
    post=post,
    feedback="Добавь больше фактов про исследования"
)

# Статистика
stats = generator.get_stats()
