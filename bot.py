import asyncio
import logging
import os
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.storage.redis import RedisStorage

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
    bot_settings = {}
    
    # Если используется локальный API сервер
    if settings.USE_LOCAL_API:
        bot_settings["base_url"] = f"{settings.LOCAL_API_URL}/bot{settings.BOT_TOKEN}"
        logger.info(f"Используется локальный Telegram Bot API сервер: {settings.LOCAL_API_URL}")
    
    # Создаем экземпляр бота
    bot = Bot(token=settings.BOT_TOKEN, parse_mode=ParseMode.HTML, **bot_settings)
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