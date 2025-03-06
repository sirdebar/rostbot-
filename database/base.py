import logging
import os
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import declarative_base
from sqlalchemy import MetaData, text

from config import settings

# Настройка логирования
logger = logging.getLogger(__name__)

# Создание базового класса для моделей
Base = declarative_base()

# Используем SQLite для упрощения тестирования
# Создаем директорию для базы данных, если она не существует
os.makedirs('data', exist_ok=True)
db_url = "sqlite+aiosqlite:///data/telegram_bot.db"

logger.info(f"Используется URL базы данных: {db_url}")

# Создание движка базы данных
engine = create_async_engine(
    db_url,
    echo=True,  # Включаем вывод SQL-запросов для отладки
)

# Создание фабрики сессий
async_session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

# Функция для получения сессии базы данных
async def get_session() -> AsyncSession:
    async with async_session() as session:
        yield session

# Функция для инициализации базы данных
async def init_db():
    """Инициализация базы данных и создание всех таблиц"""
    try:
        # Импортируем модели, чтобы они были зарегистрированы в Base.metadata
        from database.models import User, Password, Log
        
        # Создаем все таблицы
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            
        logger.info("База данных успешно инициализирована")
        return True
    except Exception as e:
        logger.error(f"Ошибка при инициализации базы данных: {e}", exc_info=True)
        return False 