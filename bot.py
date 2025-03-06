import asyncio
import logging
import sys
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.enums import ParseMode

from config import settings
from handlers import register_all_handlers
from database.base import init_db

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("bot.log"),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

# Инициализация бота и диспетчера
async def main():
    # Проверка наличия токена бота
    if not settings.BOT_TOKEN:
        logger.error("Токен бота не найден. Убедитесь, что BOT_TOKEN указан в файле .env")
        return
    
    try:
        # Инициализация базы данных
        db_initialized = await init_db()
        if not db_initialized:
            logger.error("Не удалось инициализировать базу данных. Проверьте настройки подключения.")
            return
        
        # Используем MemoryStorage для хранения состояний
        storage = MemoryStorage()
        logger.info("Используется MemoryStorage для хранения состояний")
        
        # Инициализация бота и диспетчера
        bot = Bot(
            token=settings.BOT_TOKEN,
            parse_mode=ParseMode.HTML
        )
        dp = Dispatcher(storage=storage)
        
        # Регистрация всех обработчиков
        register_all_handlers(dp, bot)
        
        # Запуск бота
        logger.info("Бот запущен")
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    except Exception as e:
        logger.error(f"Произошла ошибка при запуске бота: {e}", exc_info=True)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Бот остановлен")
    except Exception as e:
        logger.error(f"Произошла критическая ошибка: {e}", exc_info=True)
        sys.exit(1) 