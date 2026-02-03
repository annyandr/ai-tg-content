# bot_service = TelegramBotService(bot=telegram_bot)
#
# # Публикация поста в канал
# task_id = await bot_service.publish_post(
#     post=post,
#     channel=channel,
#     scheduled_time=datetime(2026, 2, 3, 9, 0, 0)
# )
#
# # Публикация немедленно
# task_id = await bot_service.publish_immediately(post, channel)
#
# # Отмена публикации
# success = await bot_service.cancel_post(post)
#
# # Проверка статуса
# task = await bot_service.check_post_status(post)
# print(task.status)  # SCHEDULED / COMPLETED / FAILED
#
# # Статистика бота
# stats = bot_service.get_bot_stats()
