import asyncio
import logging
from aiogram import Dispatcher, Bot, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from database.base import async_session
from database.repositories import UserRepository, PasswordRepository
from keyboards import get_admin_keyboard, get_worker_keyboard
from states import AuthState

logger = logging.getLogger(__name__)

# Обработчик команды /start
async def cmd_start(message: Message, bot: Bot, state: FSMContext) -> None:
    """Обработчик команды /start"""
    # Отправляем приветственное сообщение с эмодзи машущей руки
    greeting_message = await message.answer("👋")
    
    # Ждем 1 секунду и удаляем сообщение
    await asyncio.sleep(1)
    await bot.delete_message(chat_id=message.chat.id, message_id=greeting_message.message_id)
    
    # Получаем сессию базы данных
    async with async_session() as session:
        user_repo = UserRepository(session)
        
        # Получаем или создаем пользователя
        user, created = await user_repo.get_or_create_user(
            user_id=message.from_user.id,
            username=message.from_user.username,
            first_name=message.from_user.first_name,
            last_name=message.from_user.last_name
        )
        
        # Если пользователь администратор, показываем админскую клавиатуру
        if user.is_admin:
            await message.answer(
                "Добро пожаловать, администратор! Выберите действие:",
                reply_markup=get_admin_keyboard()
            )
            await state.clear()
        else:
            # Если пользователь не администратор, запрашиваем пароль
            await message.answer(
                "Добро пожаловать! Для доступа к боту введите пароль:"
            )
            await state.set_state(AuthState.waiting_for_password)

# Обработчик ввода пароля
async def process_password(message: Message, state: FSMContext, bot: Bot) -> None:
    """Обработчик ввода пароля"""
    # Получаем сессию базы данных
    async with async_session() as session:
        password_repo = PasswordRepository(session)
        user_repo = UserRepository(session)
        
        # Проверяем пароль
        password_valid = await password_repo.use_password(message.text)
        
        if password_valid:
            # Если пароль верный, активируем пользователя
            user = await user_repo.get_by_user_id(message.from_user.id)
            if not user.is_active:
                await user_repo.update_user(message.from_user.id, is_active=True)
            
            # Показываем клавиатуру работника
            await message.answer(
                "Пароль принят! Выберите действие:",
                reply_markup=get_worker_keyboard()
            )
            await state.clear()
        else:
            # Если пароль неверный, сообщаем об этом
            await message.answer(
                "Неверный пароль. Попробуйте еще раз:"
            )

def register_common_handlers(dp: Dispatcher, bot: Bot) -> None:
    """Регистрация обработчиков общих команд"""
    # Регистрация обработчика команды /start
    dp.message.register(cmd_start, Command("start"))
    
    # Регистрация обработчика ввода пароля
    dp.message.register(process_password, AuthState.waiting_for_password) 