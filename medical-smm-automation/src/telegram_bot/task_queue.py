queue = TaskQueue()

# Добавить задачу
await queue.add_task(task)

# Получить следующую готовую задачу
task = await queue.get_next_task()

# Отметить выполненной
await queue.complete_task(task_id, message_id)

# Или провалившейся (с автоповтором)
await queue.fail_task(task_id, "Ошибка API")
