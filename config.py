import os
from typing import List, Optional
from dotenv import load_dotenv

# Загрузка переменных окружения из .env файла
load_dotenv()

class Settings:
    """Класс настроек приложения"""
    
    def __init__(self):
        # Настройки бота
        self.BOT_TOKEN = os.getenv("BOT_TOKEN")
        
        # Преобразование строки с ID администраторов в список целых чисел
        admin_ids_str = os.getenv("ADMIN_IDS", "")
        self.ADMIN_IDS = []
        if admin_ids_str:
            try:
                # Если в строке несколько ID, разделенных запятыми
                if "," in admin_ids_str:
                    self.ADMIN_IDS = [int(admin_id.strip()) for admin_id in admin_ids_str.split(",") if admin_id.strip()]
                # Если в строке только один ID
                else:
                    self.ADMIN_IDS = [int(admin_ids_str.strip())]
            except ValueError:
                print(f"Ошибка при преобразовании ADMIN_IDS: {admin_ids_str}")
        
        # Настройки базы данных
        self.DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost/telegram_bot")
        
        # Настройки Redis
        self.REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        
        # Максимальное количество логов на одного пользователя
        max_logs_str = os.getenv("MAX_LOGS_PER_USER", "10")
        try:
            self.MAX_LOGS_PER_USER = int(max_logs_str)
        except ValueError:
            self.MAX_LOGS_PER_USER = 10
            print(f"Ошибка при преобразовании MAX_LOGS_PER_USER: {max_logs_str}, используется значение по умолчанию: 10")
        
        # Максимальное количество пустых логов в день
        self.MAX_EMPTY_LOGS_PER_DAY = 5
        
        # Флаг для блокировки выдачи логов
        self.LOGS_BLOCKED = False

        # Настройки для локального Telegram Bot API сервера
        self.USE_LOCAL_API = os.getenv("USE_LOCAL_API", "False").lower() in ("true", "1", "t")
        self.LOCAL_API_URL = os.getenv("LOCAL_API_URL", "http://localhost:8081")

settings = Settings()

# Вывод настроек для отладки
print(f"BOT_TOKEN: {'*' * 10 if settings.BOT_TOKEN else 'Not set'}")
print(f"ADMIN_IDS: {settings.ADMIN_IDS}")
print(f"DATABASE_URL: {settings.DATABASE_URL}")
print(f"REDIS_URL: {settings.REDIS_URL}")
print(f"MAX_LOGS_PER_USER: {settings.MAX_LOGS_PER_USER}")
print(f"MAX_EMPTY_LOGS_PER_DAY: {settings.MAX_EMPTY_LOGS_PER_DAY}")
print(f"LOGS_BLOCKED: {settings.LOGS_BLOCKED}")
print(f"USE_LOCAL_API: {settings.USE_LOCAL_API}")
print(f"LOCAL_API_URL: {settings.LOCAL_API_URL}") 