import logging
from typing import List
import aiofiles
from aiogram import Dispatcher, Bot, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, FSInputFile, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from config import settings
from database.base import async_session
from database.repositories import UserRepository, PasswordRepository, LogRepository
from database.models import User, Password, Log
from keyboards import (
    get_admin_inline_keyboard, get_passwords_keyboard, get_password_management_keyboard,
    get_users_keyboard, get_user_management_keyboard, get_confirmation_keyboard
)
from states import AdminState
from handlers.common import get_welcome_message

# Состояния для рассылки сообщений
class BroadcastState(StatesGroup):
    waiting_for_message = State()

logger = logging.getLogger(__name__)

# Обработчик кнопки "Пароли"
async def show_passwords(message: Message) -> None:
    """Обработчик кнопки 'Пароли'"""
    # Получаем сессию базы данных
    async with async_session() as session:
        password_repo = PasswordRepository(session)
        
        # Получаем все активные пароли
        passwords = await password_repo.get_all_active_passwords()
        
        # Отправляем сообщение с клавиатурой паролей
        await message.answer(
            "Управление паролями. Выберите действие:",
            reply_markup=get_passwords_keyboard(passwords)
        )

# Обработчик кнопки "Создать новый пароль"
async def create_password(callback: CallbackQuery, state: FSMContext) -> None:
    """Обработчик кнопки 'Создать новый пароль'"""
    # Отправляем сообщение с запросом пароля
    await callback.message.answer("Введите новый пароль:")
    
    # Устанавливаем состояние ожидания пароля
    await state.set_state(AdminState.waiting_for_password)
    
    # Отвечаем на callback, чтобы убрать часы загрузки
    await callback.answer()

# Обработчик ввода нового пароля
async def process_new_password(message: Message, state: FSMContext) -> None:
    """Обработчик ввода нового пароля"""
    # Сохраняем пароль в состоянии
    await state.update_data(password=message.text)
    
    # Запрашиваем количество использований
    await message.answer("Введите максимальное количество использований пароля:")
    
    # Устанавливаем состояние ожидания количества использований
    await state.set_state(AdminState.waiting_for_max_uses)

# Обработчик ввода количества использований пароля
async def process_max_uses(message: Message, state: FSMContext) -> None:
    """Обработчик ввода количества использований пароля"""
    # Проверяем, что введено число
    try:
        max_uses = int(message.text)
        if max_uses <= 0:
            await message.answer("Количество использований должно быть положительным числом. Попробуйте еще раз:")
            return
    except ValueError:
        await message.answer("Введите число. Попробуйте еще раз:")
        return
    
    # Получаем данные из состояния
    data = await state.get_data()
    password = data.get("password")
    
    # Получаем сессию базы данных
    async with async_session() as session:
        password_repo = PasswordRepository(session)
        
        # Создаем новый пароль
        await password_repo.create_password(
            password=password,
            max_uses=max_uses,
            created_by=message.from_user.id
        )
        
        # Получаем все активные пароли
        passwords = await password_repo.get_all_active_passwords()
        
        # Отправляем сообщение об успешном создании пароля
        await message.answer(
            f"Пароль '{password}' успешно создан с максимальным количеством использований: {max_uses}."
        )
        
        # Отправляем обновленную клавиатуру паролей
        await message.answer(
            "Управление паролями. Выберите действие:",
            reply_markup=get_passwords_keyboard(passwords)
        )
    
    # Очищаем состояние
    await state.clear()

# Обработчик выбора пароля
async def password_selected(callback: CallbackQuery) -> None:
    """Обработчик выбора пароля"""
    # Получаем ID пароля из callback_data
    password_id = int(callback.data.split("_")[1])
    
    # Получаем сессию базы данных
    async with async_session() as session:
        # Получаем пароль по ID с помощью SQL-запроса
        result = await session.execute(text(f"SELECT * FROM passwords WHERE id = {password_id}"))
        password = result.fetchone()
        
        if password:
            # Отправляем сообщение с информацией о пароле и клавиатурой управления
            await callback.message.answer(
                f"Пароль: {password.password}\n"
                f"Максимальное количество использований: {password.max_uses}\n"
                f"Использовано: {password.used_count}\n"
                f"Активен: {'Да' if password.is_active else 'Нет'}\n"
                f"Создан: {password.created_at.strftime('%d.%m.%Y %H:%M:%S')}",
                reply_markup=get_password_management_keyboard(password_id)
            )
        else:
            await callback.message.answer("Пароль не найден.")
    
    # Отвечаем на callback, чтобы убрать часы загрузки
    await callback.answer()

# Обработчик кнопки "Удалить пароль"
async def delete_password(callback: CallbackQuery) -> None:
    """Обработчик кнопки 'Удалить пароль'"""
    # Получаем ID пароля из callback_data
    password_id = int(callback.data.split("_")[2])
    
    # Отправляем сообщение с подтверждением удаления
    await callback.message.answer(
        "Вы уверены, что хотите удалить этот пароль?",
        reply_markup=get_confirmation_keyboard("delete_password", password_id)
    )
    
    # Отвечаем на callback, чтобы убрать часы загрузки
    await callback.answer()

# Обработчик подтверждения удаления пароля
async def confirm_delete_password(callback: CallbackQuery) -> None:
    """Обработчик подтверждения удаления пароля"""
    # Получаем ID пароля из callback_data
    password_id = int(callback.data.split("_")[2])
    
    # Получаем сессию базы данных
    async with async_session() as session:
        password_repo = PasswordRepository(session)
        
        # Удаляем пароль
        deleted = await password_repo.delete_password(password_id)
        
        if deleted:
            await callback.message.answer("Пароль успешно удален.")
        else:
            await callback.message.answer("Не удалось удалить пароль.")
        
        # Получаем все активные пароли
        passwords = await password_repo.get_all_active_passwords()
        
        # Отправляем обновленную клавиатуру паролей
        await callback.message.answer(
            "Управление паролями. Выберите действие:",
            reply_markup=get_passwords_keyboard(passwords)
        )
    
    # Отвечаем на callback, чтобы убрать часы загрузки
    await callback.answer()

# Обработчик отмены удаления пароля
async def cancel_delete_password(callback: CallbackQuery) -> None:
    """Обработчик отмены удаления пароля"""
    # Получаем ID пароля из callback_data
    password_id = int(callback.data.split("_")[2])
    
    # Отправляем сообщение об отмене удаления
    await callback.message.answer("Удаление пароля отменено.")
    
    # Получаем сессию базы данных
    async with async_session() as session:
        password_repo = PasswordRepository(session)
        
        # Получаем все активные пароли
        passwords = await password_repo.get_all_active_passwords()
        
        # Отправляем обновленную клавиатуру паролей
        await callback.message.answer(
            "Управление паролями. Выберите действие:",
            reply_markup=get_passwords_keyboard(passwords)
        )
    
    # Отвечаем на callback, чтобы убрать часы загрузки
    await callback.answer()

# Обработчик кнопки "Назад к паролям"
async def back_to_passwords(callback: CallbackQuery) -> None:
    """Обработчик кнопки 'Назад к паролям'"""
    # Получаем сессию базы данных
    async with async_session() as session:
        password_repo = PasswordRepository(session)
        
        # Получаем все активные пароли
        passwords = await password_repo.get_all_active_passwords()
        
        # Отправляем обновленную клавиатуру паролей
        await callback.message.answer(
            "Управление паролями. Выберите действие:",
            reply_markup=get_passwords_keyboard(passwords)
        )
    
    # Отвечаем на callback, чтобы убрать часы загрузки
    await callback.answer()

# Обработчик кнопки "Пользователи"
async def show_users(message: Message) -> None:
    """Обработчик кнопки 'Пользователи'"""
    # Получаем сессию базы данных
    async with async_session() as session:
        user_repo = UserRepository(session)
        
        # Получаем всех активных пользователей
        users = await user_repo.get_all_active_users()
        
        # Отправляем сообщение с клавиатурой пользователей
        await message.answer(
            "Управление пользователями. Выберите пользователя:",
            reply_markup=get_users_keyboard(users)
        )

# Обработчик выбора пользователя
async def user_selected(callback: CallbackQuery) -> None:
    """Обработчик выбора пользователя"""
    # Получаем ID пользователя из callback_data
    user_id = int(callback.data.split("_")[1])
    
    # Получаем сессию базы данных
    async with async_session() as session:
        user_repo = UserRepository(session)
        
        # Получаем пользователя по ID
        user = await user_repo.get_by_user_id(user_id)
        
        if user:
            # Отправляем сообщение с информацией о пользователе и клавиатурой управления
            await callback.message.answer(
                f"Пользователь: {user.username or 'Без имени'}\n"
                f"ID: {user.user_id}\n"
                f"Имя: {user.first_name or 'Не указано'}\n"
                f"Фамилия: {user.last_name or 'Не указана'}\n"
                f"Администратор: {'Да' if user.is_admin else 'Нет'}\n"
                f"Активен: {'Да' if user.is_active else 'Нет'}\n"
                f"Взято логов: {user.taken_logs_count}\n"
                f"Пустых логов: {user.empty_logs_count}\n"
                f"Пустых логов сегодня: {user.daily_empty_logs_count}",
                reply_markup=get_user_management_keyboard(user.user_id)
            )
        else:
            await callback.message.answer("Пользователь не найден.")
    
    # Отвечаем на callback, чтобы убрать часы загрузки
    await callback.answer()

# Обработчик кнопки "Удалить пользователя"
async def delete_user(callback: CallbackQuery) -> None:
    """Обработчик кнопки 'Удалить пользователя'"""
    # Логируем callback_data для отладки
    logger.info(f"delete_user callback_data: {callback.data}")
    
    # Получаем ID пользователя из callback_data
    parts = callback.data.split("_")
    if len(parts) >= 3:
        user_id = int(parts[2])
        
        # Создаем простой формат callback_data для подтверждения
        confirm_data = f"confirm_user_{user_id}"
        cancel_data = f"cancel_user_{user_id}"
        
        # Создаем клавиатуру подтверждения вручную
        keyboard = [
            [
                InlineKeyboardButton(text="✅ Да", callback_data=confirm_data),
                InlineKeyboardButton(text="❌ Нет", callback_data=cancel_data)
            ]
        ]
        markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
        
        # Отправляем сообщение с подтверждением удаления
        await callback.message.answer(
            "Вы уверены, что хотите удалить этого пользователя? Это действие нельзя отменить.",
            reply_markup=markup
        )
    else:
        await callback.message.answer("Ошибка: неверный формат данных callback.")
    
    # Отвечаем на callback, чтобы убрать часы загрузки
    await callback.answer()

# Обработчик подтверждения удаления пользователя
async def confirm_delete_user(callback: CallbackQuery) -> None:
    """Обработчик подтверждения удаления пользователя"""
    # Логируем callback_data для отладки
    logger.info(f"confirm_delete_user callback_data: {callback.data}")
    
    try:
        # Получаем ID пользователя из callback_data
        parts = callback.data.split("_")
        
        # Проверяем формат callback_data
        if len(parts) < 3:
            await callback.message.answer("Ошибка: неверный формат данных callback (недостаточно частей).")
            await callback.answer()
            return
        
        # Проверяем, что третья часть - это число
        try:
            user_id = int(parts[2])
        except ValueError:
            await callback.message.answer(f"Ошибка: ID пользователя должен быть числом, получено: {parts[2]}")
            await callback.answer()
            return
        
        # Получаем сессию базы данных
        async with async_session() as session:
            user_repo = UserRepository(session)
            
            # Удаляем пользователя (на самом деле просто деактивируем)
            await user_repo.update_user(user_id, is_active=False)
            
            await callback.message.answer("Пользователь успешно удален (деактивирован).")
            
            # Получаем всех активных пользователей
            users = await user_repo.get_all_active_users()
            
            # Отправляем обновленную клавиатуру пользователей
            await callback.message.answer(
                "Управление пользователями. Выберите пользователя:",
                reply_markup=get_users_keyboard(users)
            )
    except Exception as e:
        logger.error(f"Ошибка при удалении пользователя: {e}", exc_info=True)
        await callback.message.answer(f"Произошла ошибка: {e}")
    
    # Отвечаем на callback, чтобы убрать часы загрузки
    await callback.answer()

# Обработчик отмены удаления пользователя
async def cancel_delete_user(callback: CallbackQuery) -> None:
    """Обработчик отмены удаления пользователя"""
    # Отправляем сообщение об отмене удаления
    await callback.message.answer("Удаление пользователя отменено.")
    
    # Получаем сессию базы данных
    async with async_session() as session:
        user_repo = UserRepository(session)
        
        # Получаем всех активных пользователей
        users = await user_repo.get_all_active_users()
        
        # Отправляем обновленную клавиатуру пользователей
        await callback.message.answer(
            "Управление пользователями. Выберите пользователя:",
            reply_markup=get_users_keyboard(users)
        )
    
    # Отвечаем на callback, чтобы убрать часы загрузки
    await callback.answer()

# Обработчик кнопки "Назад к пользователям"
async def back_to_users(callback: CallbackQuery) -> None:
    """Обработчик кнопки 'Назад к пользователям'"""
    # Получаем сессию базы данных
    async with async_session() as session:
        user_repo = UserRepository(session)
        
        # Получаем всех активных пользователей
        users = await user_repo.get_all_active_users()
        
        # Отправляем обновленную клавиатуру пользователей
        await callback.message.answer(
            "Управление пользователями. Выберите пользователя:",
            reply_markup=get_users_keyboard(users)
        )
    
    # Отвечаем на callback, чтобы убрать часы загрузки
    await callback.answer()

# Обработчик кнопки "Загрузить логи"
async def upload_logs(message: Message, state: FSMContext) -> None:
    """Обработчик кнопки 'Загрузить логи'"""
    # Отправляем сообщение с запросом файла
    await message.answer(
        "Отправьте файл с логами в формате RAR или ZIP. "
        "Файл будет сохранен как есть, без распаковки."
    )
    
    # Устанавливаем состояние ожидания файла
    await state.set_state(AdminState.waiting_for_log_file)

# Обработчик загрузки файла с логами
async def process_log_file(message: Message, state: FSMContext, bot: Bot) -> None:
    """Обработчик загрузки файла с логами"""
    # Проверяем, что сообщение содержит документ
    if not message.document:
        await message.answer("Пожалуйста, отправьте файл. Попробуйте еще раз.")
        return
    
    # Проверяем формат файла
    file_name = message.document.file_name
    if not (file_name.endswith(".rar") or file_name.endswith(".zip")):
        await message.answer("Файл должен быть в формате RAR или ZIP. Попробуйте еще раз.")
        return
    
    # Получаем информацию о файле
    file_id = message.document.file_id
    file_size = message.document.file_size
    
    # Получаем сессию базы данных
    async with async_session() as session:
        log_repo = LogRepository(session)
        # user_repo = UserRepository(session)  # Закомментировано
        
        # Сохраняем информацию о файле в базе данных
        log = await log_repo.create_log(
            file_id=file_id,
            file_name=file_name,
            file_size=file_size
        )
        
        # Отправляем сообщение об успешной загрузке
        await message.answer(
            f"Файл '{file_name}' успешно загружен и добавлен в базу данных."
        )
        
        # Закомментированная логика оповещения пользователей
        # # Получаем всех активных пользователей
        # users = await user_repo.get_all_active_users()
        # 
        # # Отправляем уведомление всем активным пользователям
        # for user in users:
        #     if not user.is_admin:  # Не отправляем уведомление администраторам
        #         try:
        #             await bot.send_message(
        #                 chat_id=user.user_id,
        #                 text=f"Администратор загрузил новый лог: {file_name}"
        #             )
        #         except Exception as e:
        #             logger.error(f"Ошибка при отправке уведомления пользователю {user.user_id}: {e}")
    
    # Очищаем состояние
    await state.clear()

# Обработчик кнопки "Стоп логи"
async def stop_logs(message: Message) -> None:
    """Обработчик кнопки 'Стоп логи'"""
    # Устанавливаем флаг блокировки выдачи логов
    settings.LOGS_BLOCKED = True
    
    # Отправляем сообщение об успешной блокировке
    await message.answer("Выдача логов заблокирована.")

# Обработчик кнопки "Разрешить логи"
async def allow_logs(message: Message) -> None:
    """Обработчик кнопки 'Разрешить логи'"""
    # Снимаем флаг блокировки выдачи логов
    settings.LOGS_BLOCKED = False
    
    # Отправляем сообщение о разблокировке
    await message.answer("Выдача логов разблокирована.")

# Обработчик кнопки "Очистить базу логов"
async def clear_logs(message: Message) -> None:
    """Обработчик кнопки 'Очистить базу логов'"""
    # Отправляем сообщение с подтверждением очистки
    await message.answer(
        "Вы уверены, что хотите очистить базу логов? Это действие нельзя отменить.",
        reply_markup=get_confirmation_keyboard("clear_logs")
    )

# Обработчик подтверждения очистки базы логов
async def confirm_clear_logs(callback: CallbackQuery) -> None:
    """Обработчик подтверждения очистки базы логов"""
    # Получаем сессию базы данных
    async with async_session() as session:
        log_repo = LogRepository(session)
        
        # Очищаем базу логов
        deleted_count = await log_repo.clear_all_logs()
        
        # Отправляем сообщение об успешной очистке
        await callback.message.answer(f"База логов успешно очищена. Удалено {deleted_count} записей.")
    
    # Отвечаем на callback, чтобы убрать часы загрузки
    await callback.answer()

# Обработчик отмены очистки базы логов
async def cancel_clear_logs(callback: CallbackQuery) -> None:
    """Обработчик отмены очистки базы логов"""
    # Отправляем сообщение об отмене очистки
    await callback.message.answer("Очистка базы логов отменена.")
    
    # Отвечаем на callback, чтобы убрать часы загрузки
    await callback.answer()

# Обработчик кнопки "Назад" (к главному меню)
async def back_to_main(callback: CallbackQuery) -> None:
    """Обработчик кнопки 'Назад' (к главному меню)"""
    # Формируем приветственное сообщение
    welcome_text = await get_welcome_message(callback.from_user.id)
    
    # Отправляем сообщение с главным меню
    await callback.message.answer(
        welcome_text,
        reply_markup=get_admin_inline_keyboard(),
        disable_web_page_preview=True
    )
    
    # Отвечаем на callback, чтобы убрать часы загрузки
    await callback.answer()

# Обработчик кнопки "Сообщение"
async def broadcast_message(callback: CallbackQuery, state: FSMContext) -> None:
    """Обработчик кнопки 'Сообщение'"""
    await callback.message.answer(
        "Введите сообщение, которое хотите разослать всем пользователям бота:"
    )
    await state.set_state(BroadcastState.waiting_for_message)
    
    # Отвечаем на callback, чтобы убрать часы загрузки
    await callback.answer()

# Обработчик ввода сообщения для рассылки
async def process_broadcast_message(message: Message, state: FSMContext, bot: Bot) -> None:
    """Обработчик ввода сообщения для рассылки"""
    broadcast_text = message.text
    
    if not broadcast_text:
        await message.answer("Сообщение не может быть пустым. Попробуйте еще раз:")
        return
    
    # Получаем сессию базы данных
    async with async_session() as session:
        user_repo = UserRepository(session)
        
        # Получаем всех активных пользователей
        users = await user_repo.get_all_active_users()
        
        # Отправляем сообщение о начале рассылки
        status_message = await message.answer(
            f"Начинаю рассылку сообщения {len(users)} пользователям..."
        )
        
        # Счетчики для статистики
        success_count = 0
        error_count = 0
        
        # Отправляем сообщение всем пользователям
        for user in users:
            try:
                await bot.send_message(
                    chat_id=user.user_id,
                    text=broadcast_text
                )
                success_count += 1
            except Exception as e:
                logger.error(f"Ошибка при отправке сообщения пользователю {user.user_id}: {e}")
                error_count += 1
        
        # Обновляем сообщение о статусе рассылки
        await bot.edit_message_text(
            chat_id=message.chat.id,
            message_id=status_message.message_id,
            text=f"Рассылка завершена!\n\n"
                 f"✅ Успешно отправлено: {success_count}\n"
                 f"❌ Ошибок: {error_count}"
        )
    
    # Очищаем состояние
    await state.clear()
    
    # Отправляем приветственное сообщение с клавиатурой
    welcome_text = await get_welcome_message(message.from_user.id)
    await message.answer(
        welcome_text,
        reply_markup=get_admin_inline_keyboard(),
        disable_web_page_preview=True
    )

def register_admin_handlers(dp: Dispatcher, bot: Bot) -> None:
    """Регистрация обработчиков команд администратора"""
    # Регистрация обработчиков для паролей
    dp.callback_query.register(create_password, F.data == "create_password")
    dp.callback_query.register(password_selected, F.data.startswith("password_"))
    dp.callback_query.register(delete_password, F.data.startswith("delete_password_"))
    dp.callback_query.register(confirm_delete_password, F.data.startswith("confirm_delete_password_"))
    dp.callback_query.register(cancel_delete_password, F.data.startswith("cancel_delete_password_"))
    dp.callback_query.register(back_to_passwords, F.data == "back_to_passwords")
    
    # Регистрация обработчиков для пользователей
    dp.callback_query.register(user_selected, F.data.startswith("user_"))
    dp.callback_query.register(delete_user, F.data.startswith("delete_user_"))
    dp.callback_query.register(confirm_delete_user, F.data.startswith("confirm_delete_user_"))
    dp.callback_query.register(cancel_delete_user, F.data.startswith("cancel_delete_user_"))
    dp.callback_query.register(back_to_users, F.data == "back_to_users")
    
    # Регистрация обработчиков для логов
    dp.callback_query.register(confirm_clear_logs, F.data == "confirm_clear_logs")
    dp.callback_query.register(cancel_clear_logs, F.data == "cancel_clear_logs")
    
    # Регистрация обработчика кнопки "Назад"
    dp.callback_query.register(back_to_main, F.data == "back_to_main")
    
    # Регистрация обработчиков состояний
    dp.message.register(process_new_password, AdminState.waiting_for_password)
    dp.message.register(process_max_uses, AdminState.waiting_for_max_uses)
    dp.message.register(process_log_file, AdminState.waiting_for_log_file)
    dp.message.register(process_broadcast_message, BroadcastState.waiting_for_message) 