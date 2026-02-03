# Быстрый старт: Веб-интерфейс Medical SMM Bot

## Установка

```bash
# 1. Установите зависимости
pip install -r requirements-api.txt
pip install -r requirements-web.txt

# 2. Убедитесь, что .env настроен
# Должны быть: BOT_TOKEN, OPENROUTER_API_KEY, ADMIN_IDS
```

## Запуск

### Вариант 1: Автоматический запуск (рекомендуется)

```bash
./start-web.sh
```

Это запустит:
- API Server на порту 8000
- Web Frontend на порту 3000

### Вариант 2: Ручной запуск

```bash
# Терминал 1: API + Telegram Bot
python main.py all

# Терминал 2: Web Frontend
cd web && python main.py
```

### Вариант 3: Только API (без Telegram бота)

```bash
# Терминал 1: Только API
python main.py api

# Терминал 2: Web Frontend
cd web && python main.py
```

## Доступ

После запуска откройте в браузере:

- **Веб-интерфейс:** http://localhost:3000
- **API Docs (Swagger):** http://localhost:8000/api/docs
- **API ReDoc:** http://localhost:8000/api/redoc

## Основные функции

### 1. Dashboard (Главная)
- Статистика по всем задачам
- Последние посты
- Список каналов
- Быстрые действия

### 2. Создание поста

1. Перейдите в "Создать пост"
2. Выберите канал и время публикации
3. Два способа создания контента:
   - **AI генерация:** Выберите специализацию, введите тему, нажмите "Генерировать"
   - **Ручной ввод:** Просто введите текст в редакторе
4. Отредактируйте текст при необходимости
5. Нажмите "Создать пост"

### 3. Просмотр постов

- Фильтруйте по статусу: Все, Запланированные, Выполнено, Ошибки
- Отменяйте запланированные посты
- Просматривайте ошибки неудачных публикаций

### 4. Каналы

- Просмотр всех настроенных Telegram каналов
- Информация о специализациях
- Быстрое создание поста для канала

## Тестирование

```bash
# Проверка API
python test_api.py

# Или вручную
curl http://localhost:8000/api/v1/system/health
```

## Режимы работы

### Mode: bot
Запускает только Telegram бота (без API)
```bash
python main.py bot
```

### Mode: api
Запускает только API сервер (без Telegram бота)
```bash
python main.py api
```

### Mode: all (по умолчанию)
Запускает и Telegram бота, и API сервер
```bash
python main.py all
# или просто
python main.py
```

## Примеры использования

### Создать пост через Web UI

1. Откройте http://localhost:3000
2. Нажмите "Создать пост"
3. Выберите канал: "Гинекология"
4. Выберите специализацию: "gynecology"
5. Введите тему: "Новые протоколы ведения беременных"
6. Нажмите "Генерировать с AI"
7. Отредактируйте при необходимости
8. Выберите время публикации
9. Нажмите "Создать пост"

### Создать пост через API

```bash
curl -X POST http://localhost:8000/api/v1/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "channel_id": "-1003748097480",
    "text": "Тестовый пост о новых рекомендациях",
    "scheduled_time": "2026-02-05T10:00:00"
  }'
```

### Сгенерировать контент через API

```bash
curl -X POST http://localhost:8000/api/v1/content/generate \
  -H "Content-Type: application/json" \
  -d '{
    "topic": "Лечение диабета 2 типа",
    "specialty": "endocrinology",
    "post_type": "клинрекомендации"
  }'
```

## Troubleshooting

### API не запускается

Проверьте .env файл:
```bash
cat .env | grep -E "BOT_TOKEN|OPENROUTER_API_KEY"
```

### Web UI показывает ошибки

Убедитесь, что API запущен:
```bash
curl http://localhost:8000/api/v1/system/health
```

### AI генерация не работает

Проверьте OPENROUTER_API_KEY и логи:
```bash
tail -f api.log
```

## Следующие шаги

1. Настройте каналы в `data/channels.json`
2. Попробуйте создать тестовый пост
3. Используйте AI генерацию для создания контента
4. Просмотрите статистику на Dashboard
5. Изучите API через Swagger UI

## Дополнительно

- Полная документация: `WEB_README.md`
- Документация проекта: `CLAUDE.md`
- API Reference: http://localhost:8000/api/docs

---

**Полезные команды:**

```bash
# Просмотр логов API
tail -f api.log

# Просмотр логов Web
tail -f web.log

# Остановка всех сервисов
pkill -f "python main.py"
pkill -f "python web/main.py"

# Быстрый перезапуск
./start-web.sh
```
