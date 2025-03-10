# Telegram Bot для выдачи логов WhatsApp

Бот для выдачи логов WhatsApp пользователям по паролю.

## Функциональность

- Авторизация пользователей по паролю
- Выдача логов WhatsApp пользователям
- Статистика по выданным логам
- Управление паролями и пользователями
- Загрузка логов администратором

## Установка и запуск

1. Клонируйте репозиторий:
```bash
git clone https://github.com/yourusername/telegram-bot.git
cd telegram-bot
```

2. Создайте виртуальное окружение и установите зависимости:
```bash
python -m venv venv
source venv/bin/activate  # На Windows: venv\Scripts\activate
pip install -r requirements.txt
```

3. Создайте файл `.env` на основе `.env.example` и заполните его:
```bash
cp .env.example .env
# Отредактируйте файл .env, указав токен бота и другие настройки
```

4. Запустите бота:
```bash
python bot.py
```

## Настройка локального Telegram Bot API сервера (для загрузки файлов >50 МБ)

Стандартный Telegram Bot API имеет ограничение на размер файлов в 50 МБ. Для загрузки больших файлов (до 2000 МБ) можно использовать локальный Telegram Bot API сервер.

### Установка на Ubuntu

1. Получите API ID и API Hash на сайте Telegram:
   - Перейдите на https://my.telegram.org/auth
   - Войдите в свой аккаунт Telegram
   - Выберите "API development tools"
   - Создайте новое приложение
   - Запишите полученные API ID и API Hash

2. Установите зависимости:
```bash
sudo apt-get update
sudo apt-get install -y build-essential cmake g++ git zlib1g-dev libssl-dev gperf libreadline-dev
```

3. Клонируйте и соберите Telegram Bot API:
```bash
mkdir -p ~/telegram-bot-api
cd ~/telegram-bot-api
git clone --recursive https://github.com/tdlib/telegram-bot-api.git
cd telegram-bot-api
mkdir build
cd build
cmake -DCMAKE_BUILD_TYPE=Release ..
cmake --build . --target install
```

4. Запустите локальный API сервер:
```bash
cd ~/telegram-bot-api/telegram-bot-api/bin
./telegram-bot-api --api-id=ВАШЕ_API_ID --api-hash=ВАШ_API_HASH --local
```

5. Для запуска в фоновом режиме:
```bash
nohup ./telegram-bot-api --api-id=ВАШЕ_API_ID --api-hash=ВАШ_API_HASH --local > telegram-bot-api.log 2>&1 &
```

6. Настройте бота для использования локального API сервера:
   - В файле `.env` установите:
   ```
   USE_LOCAL_API=True
   LOCAL_API_URL=http://localhost:8081
   ```

7. Перезапустите бота:
```bash
python bot.py
```

## Структура проекта

- `bot.py` - основной файл бота
- `config.py` - конфигурация бота
- `database/` - модули для работы с базой данных
- `handlers/` - обработчики команд и сообщений
- `keyboards/` - клавиатуры для бота
- `states/` - состояния для FSM
- `utils/` - вспомогательные функции

## Лицензия

MIT 