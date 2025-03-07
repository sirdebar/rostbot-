import asyncio
import logging
from aiogram import Dispatcher, Bot, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from database.base import async_session
from database.repositories import UserRepository, PasswordRepository, LogRepository, SessionRepository
from keyboards import get_admin_inline_keyboard, get_worker_inline_keyboard
from states import AuthState

logger = logging.getLogger(__name__)

# Функция для создания приветственного сообщения
async def get_welcome_message(user_id: int) -> str:
    """Создает приветственное сообщение с ID пользователя и информацией о боте"""
    welcome_text = f"Твой 🆔 {user_id}\n\n"
    welcome_text += "Бот для удобной выдачи логов WhatsApp запущен! Теперь получать аккаунты стало проще и быстрее.\n\n"
    welcome_text += "По техническим вопросам обращайтесь: @wrldxrd. (https://t.me/wrldxrd)"
    
    return welcome_text

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
            welcome_text = await get_welcome_message(message.from_user.id)
            
            await message.answer(
                welcome_text,
                reply_markup=get_admin_inline_keyboard(),
                disable_web_page_preview=True
            )
            await state.clear()
        # Если пользователь активен (уже ввел пароль ранее), показываем клавиатуру работника
        elif user.is_active:
            welcome_text = await get_welcome_message(message.from_user.id)
            
            await message.answer(
                welcome_text,
                reply_markup=get_worker_inline_keyboard(),
                disable_web_page_preview=True
            )
            await state.clear()
        else:
            # Если пользователь не активен, запрашиваем пароль
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
            
            # Показываем приветственное сообщение и клавиатуру работника
            welcome_text = await get_welcome_message(message.from_user.id)
            
            await message.answer(
                welcome_text,
                reply_markup=get_worker_inline_keyboard(),
                disable_web_page_preview=True
            )
            await state.clear()
        else:
            # Если пароль неверный, сообщаем об этом
            await message.answer(
                "Неверный пароль. Попробуйте еще раз:"
            )

# Обработчик инлайн-кнопок для админа
async def admin_button_handler(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    """Обработчик инлайн-кнопок для админа"""
    action = callback.data
    
    # Отвечаем на callback, чтобы убрать часы загрузки
    await callback.answer()
    
    if action == "admin_passwords":
        # Перенаправляем на обработчик паролей
        from handlers.admin import show_passwords
        await show_passwords(callback.message)
    elif action == "admin_users":
        # Перенаправляем на обработчик пользователей
        from handlers.admin import show_users
        await show_users(callback.message)
    elif action == "admin_upload_logs":
        # Перенаправляем на обработчик загрузки логов
        from handlers.admin import upload_logs
        await upload_logs(callback.message, state)
    elif action == "admin_stop_logs":
        # Перенаправляем на обработчик остановки логов
        from handlers.admin import stop_logs
        await stop_logs(callback.message)
    elif action == "admin_allow_logs":
        # Перенаправляем на обработчик разрешения логов
        from handlers.admin import allow_logs
        await allow_logs(callback.message)
    elif action == "admin_clear_logs":
        # Перенаправляем на обработчик очистки логов
        from handlers.admin import clear_logs
        await clear_logs(callback.message)
    elif action == "admin_broadcast":
        # Перенаправляем на обработчик рассылки сообщений
        from handlers.admin import broadcast_message
        await broadcast_message(callback, state)

# Обработчик инлайн-кнопок для работника
async def worker_button_handler(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    """Обработчик инлайн-кнопок для работника"""
    action = callback.data
    
    # Отвечаем на callback, чтобы убрать часы загрузки
    await callback.answer()
    
    if action == "worker_statistics":
        # Перенаправляем на обработчик статистики
        from handlers.worker import show_statistics_inline
        await show_statistics_inline(callback)
    elif action == "worker_empty_log":
        # Перенаправляем на обработчик пустых логов
        from handlers.worker import empty_log
        await empty_log(callback.message, state)
    elif action == "worker_take_logs":
        # Перенаправляем на обработчик взятия логов
        from handlers.worker import take_logs
        await take_logs(callback.message, state)
    elif action == "worker_your_logs":
        # Перенаправляем на обработчик просмотра логов
        from handlers.worker import show_user_logs
        await show_user_logs(callback.message, bot)

def register_common_handlers(dp: Dispatcher, bot: Bot) -> None:
    """Регистрация обработчиков общих команд"""
    # Регистрация обработчика команды /start
    dp.message.register(cmd_start, Command("start"))
    
    # Регистрация обработчика ввода пароля
    dp.message.register(process_password, AuthState.waiting_for_password)
    
    # Регистрация обработчиков инлайн-кнопок
    dp.callback_query.register(admin_button_handler, F.data.startswith("admin_"))
    dp.callback_query.register(worker_button_handler, F.data.startswith("worker_")) 