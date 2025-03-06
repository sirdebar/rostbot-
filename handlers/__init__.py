from aiogram import Dispatcher, Bot
from handlers.common import register_common_handlers
from handlers.admin import register_admin_handlers
from handlers.worker import register_worker_handlers

def register_all_handlers(dp: Dispatcher, bot: Bot) -> None:
    """Регистрация всех обработчиков"""
    # Порядок регистрации важен - сначала общие, потом админские, потом для работников
    register_common_handlers(dp, bot)
    register_admin_handlers(dp, bot)
    register_worker_handlers(dp, bot) 