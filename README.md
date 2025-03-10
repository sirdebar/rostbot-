# Telegram Bot для работы с логами

Телеграм бот для управления логами с системой авторизации по паролю, разделением прав администраторов и работников.

## Функциональность

### Для администраторов:
- Управление паролями (создание, удаление)
- Управление пользователями (просмотр, удаление)
- Загрузка логов в формате RAR или ZIP
- Блокировка/разблокировка выдачи логов
- Очистка базы логов

### Для работников:
- Просмотр статистики (взятые логи, пустые логи)
- Отметка пустых логов
- Получение логов из базы
- Просмотр своих логов

## Требования

- Python 3.8+
- PostgreSQL
- Redis

## Установка

1. Клонируйте репозиторий:
```bash
git clone https://github.com/yourusername/telegram-log-bot.git
cd telegram-log-bot
```

2. Создайте виртуальное окружение и активируйте его:
```bash
python -m venv venv
# Для Windows
venv\Scripts\activate
# Для Linux/Mac
source venv/bin/activate
```

3. Установите зависимости:
```bash
pip install -r requirements.txt
```

4. Создайте базу данных PostgreSQL:
```bash
createdb telegram_bot
```

5. Настройте файл `.env` с вашими параметрами:
```
BOT_TOKEN=your_bot_token
ADMIN_IDS=123456789,987654321
DATABASE_URL=postgresql+asyncpg://username:password@localhost/telegram_bot
REDIS_URL=redis://localhost:6379/0
MAX_LOGS_PER_USER=10
```

## Запуск

```bash
python bot.py
```

## Использование

1. Запустите бота и отправьте команду `/start`
2. Если вы администратор (ваш ID указан в `ADMIN_IDS`), вы получите доступ к админской панели
3. Если вы работник, вам потребуется ввести пароль, созданный администратором

## Структура проекта

- `bot.py` - Основной файл бота
- `config.py` - Конфигурация и настройки
- `states.py` - Состояния для FSM (Finite State Machine)
- `keyboards.py` - Клавиатуры для бота
- `database/` - Модуль для работы с базой данных
  - `base.py` - Базовые функции для работы с БД
  - `models.py` - Модели данных
  - `repositories.py` - Репозитории для работы с данными
- `handlers/` - Обработчики команд
  - `common.py` - Общие обработчики
  - `admin.py` - Обработчики для администраторов
  - `worker.py` - Обработчики для работников

## Лицензия

MIT 