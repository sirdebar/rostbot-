import asyncio
import logging
import os
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.storage.redis import RedisStorage
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.client.telegram import TelegramAPIServer

from config import settings
from database.base import init_db
from handlers.admin import register_admin_handlers
from handlers.common import register_common_handlers
from handlers.worker import register_worker_handlers

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

async def main():
    # Инициализация базы данных
    await init_db()
    
    # Настройка хранилища состояний
    if settings.REDIS_URL:
        storage = RedisStorage.from_url(settings.REDIS_URL)
        logger.info("Используется RedisStorage для хранения состояний")
    else:
        storage = MemoryStorage()
        logger.info("Используется MemoryStorage для хранения состояний")
    
    # Инициализация бота и диспетчера
    token = settings.BOT_TOKEN
    
    # Если используется локальный API сервер
    if settings.USE_LOCAL_API:
        # Создаем объект TelegramAPIServer для локального API
        local_server = TelegramAPIServer.from_base(settings.LOCAL_API_URL)
        # Создаем сессию с локальным сервером
        session = AiohttpSession(api=local_server)
        # Создаем бота с настроенной сессией
        bot = Bot(token=token, parse_mode=ParseMode.HTML, session=session)
        logger.info(f"Используется локальный Telegram Bot API сервер: {settings.LOCAL_API_URL}")
    else:
        # Стандартная инициализация
        bot = Bot(token=token, parse_mode=ParseMode.HTML)
    
    dp = Dispatcher(storage=storage)
    
    # Регистрация обработчиков
    register_common_handlers(dp, bot)
    register_admin_handlers(dp, bot)
    register_worker_handlers(dp, bot)
    
    # Запуск бота
    logger.info("Бот запущен")
    await dp.start_polling(bot)
    logger.info("Бот остановлен")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Бот остановлен") 