bot = MedicalTelegramBot(bot_token="YOUR_TOKEN")

# Запуск (с автоматическим worker'ом очереди)
await bot.start()

# Планирование поста
task_id = await bot.schedule_post(
    channel_id="@profgynecologist",
    text="🍑 **Новый пост**\n\n✅ Контент",
    scheduled_time=datetime(2026, 2, 3, 9, 0, 0),
    photo_url="https://...",  # опционально
    buttons=[{"text": "Читать", "url": "..."}]  # опционально
)

# Отмена поста
await bot.cancel_post(task_id)

# Проверка статуса
task = await bot.get_task_status(task_id)
print(task.status)  # COMPLETED / FAILED / SCHEDULED

# Статистика
stats = bot.get_stats()
# {'completed': 42, 'failed': 3, 'active_tasks': 15}
