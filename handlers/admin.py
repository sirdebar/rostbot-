import logging
import os
from typing import List
import aiofiles
from aiogram import Dispatcher, Bot, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, FSInputFile, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from datetime import datetime

from config import settings
from database.base import async_session
from database.repositories import UserRepository, PasswordRepository, LogRepository, SessionRepository, UsedPhoneNumberRepository
from database.models import User, Password, Log, Session, UsedPhoneNumber
from keyboards import (
    get_admin_inline_keyboard, get_passwords_keyboard, get_password_management_keyboard,
    get_users_keyboard, get_user_management_keyboard, get_confirmation_keyboard
)
from states import AdminState
from handlers.common import get_welcome_message
from utils.archive import (
    extract_archive, download_telegram_file, TEMP_DIR, 
    get_file_size_str, split_file_instructions
)

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
        
        if passwords:
            # Отправляем сообщение с клавиатурой паролей
            await message.answer(
                "Управление паролями. Выберите действие:",
                reply_markup=get_passwords_keyboard(passwords)
            )
        else:
            # Если паролей нет, отправляем сообщение и клавиатуру для создания пароля
            await message.answer(
                "У вас нет активных паролей. Создайте новый пароль:",
                reply_markup=get_passwords_keyboard([])
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
    # Получаем введенный пароль
    password = message.text.strip()
    
    if not password:
        await message.answer("Пароль не может быть пустым. Введите пароль:")
        return
    
    # Сохраняем пароль в состоянии
    await state.update_data(password=password)
    
    # Запрашиваем максимальное количество использований
    await message.answer("Введите максимальное количество использований пароля:")
    
    # Устанавливаем состояние ожидания ввода максимального количества использований
    await state.set_state(AdminState.waiting_for_max_uses)

# Обработчик ввода количества использований пароля
async def process_max_uses(message: Message, state: FSMContext) -> None:
    """Обработчик ввода максимального количества использований пароля"""
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
    
    # Отправляем сообщение об успешном создании пароля
    await message.answer(
        f"Пароль успешно создан!\n"
        f"Пароль: {password}\n"
        f"Максимальное количество использований: {max_uses}"
    )
    
    # Отправляем клавиатуру с паролями
    await show_passwords(message)
    
    # Очищаем состояние
    await state.clear()

# Обработчик выбора пароля
async def password_selected(callback: CallbackQuery) -> None:
    """Обработчик выбора пароля из списка"""
    # Извлекаем ID пароля из callback_data
    password_id = int(callback.data.split("_")[1])
    
    # Получаем сессию базы данных
    async with async_session() as session:
        password_repo = PasswordRepository(session)
        
        # Получаем пароль по ID
        password = await password_repo.get_password(password_id)
        
        if password:
            # Формируем сообщение с информацией о пароле
            message_text = (
                f"🔐 <b>Информация о пароле:</b>\n\n"
                f"Пароль: <code>{password.password}</code>\n"
                f"Использований: {password.used_count}/{password.max_uses}\n"
                f"Создан: {password.created_at.strftime('%d.%m.%Y %H:%M')}"
            )
            
            # Отправляем сообщение с клавиатурой управления паролем
            await callback.message.edit_text(
                message_text,
                reply_markup=get_password_management_keyboard(password.id),
                parse_mode="HTML"
            )
        else:
            # Если пароль не найден, отправляем сообщение об ошибке
            await callback.answer("Пароль не найден.")
            
            # Возвращаемся к списку паролей
            await back_to_passwords(callback)

# Обработчик кнопки "Удалить пароль"
async def delete_password(callback: CallbackQuery) -> None:
    """Обработчик кнопки 'Удалить пароль'"""
    # Извлекаем ID пароля из callback_data
    password_id = int(callback.data.split("_")[2])
    
    # Получаем сессию базы данных
    async with async_session() as session:
        password_repo = PasswordRepository(session)
        
        # Получаем пароль по ID
        password = await password_repo.get_password(password_id)
        
        if password:
            # Отправляем сообщение с запросом подтверждения удаления
            await callback.message.edit_text(
                f"Вы уверены, что хотите удалить пароль <code>{password.password}</code>?",
                reply_markup=get_confirmation_keyboard("delete_password", password_id),
                parse_mode="HTML"
            )
        else:
            # Если пароль не найден, отправляем сообщение об ошибке
            await callback.answer("Пароль не найден.")
            
            # Возвращаемся к списку паролей
            await back_to_passwords(callback)

# Обработчик подтверждения удаления пароля
async def confirm_delete_password(callback: CallbackQuery) -> None:
    """Обработчик подтверждения удаления пароля"""
    # Извлекаем ID пароля из callback_data
    password_id = int(callback.data.split("_")[3])
    
    # Получаем сессию базы данных
    async with async_session() as session:
        password_repo = PasswordRepository(session)
        
        # Получаем пароль по ID
        password = await password_repo.get_password(password_id)
        
        if password:
            # Удаляем пароль
            success = await password_repo.delete_password(password_id)
            
            if success:
                # Отправляем сообщение об успешном удалении
                await callback.answer("Пароль успешно удален.")
            else:
                # Отправляем сообщение об ошибке
                await callback.answer("Не удалось удалить пароль.")
        else:
            # Если пароль не найден, отправляем сообщение об ошибке
            await callback.answer("Пароль не найден.")
    
    # Возвращаемся к списку паролей
    await back_to_passwords(callback)

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
        
        # Отправляем сообщение с клавиатурой паролей
        await callback.message.edit_text(
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
            # Поддерживаем оба формата: confirm_delete_user_ID и confirm_user_ID
            user_id = int(parts[2]) if len(parts) == 3 or parts[0] == "confirm_user" else int(parts[3])
        except ValueError:
            await callback.message.answer(f"Ошибка: ID пользователя должен быть числом, получено: {parts[2] if len(parts) == 3 or parts[0] == 'confirm_user' else parts[3]}")
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
    # Логируем callback_data для отладки
    logger.info(f"cancel_delete_user callback_data: {callback.data}")
    
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
async def process_log_file(message: Message, state: FSMContext) -> None:
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
    
    # Предупреждаем о длительной загрузке для больших файлов
    if file_size > 1024 * 1024 * 1024:  # Если файл больше 1 ГБ
        await message.answer(
            f"Размер файла: {file_size / (1024 * 1024 * 1024):.2f} ГБ. "
            f"Загрузка может занять длительное время (до 15 минут). Пожалуйста, подождите..."
        )
    elif file_size > 100 * 1024 * 1024:  # Если файл больше 100 МБ
        await message.answer(
            f"Размер файла: {file_size / (1024 * 1024):.2f} МБ. "
            f"Загрузка может занять некоторое время (до 5 минут). Пожалуйста, подождите..."
        )
    
    # Отправляем сообщение о начале обработки
    status_message = await message.answer("Начинаю загрузку архива...")
    
    # Создаем директорию для временных файлов, если она не существует
    os.makedirs(TEMP_DIR, exist_ok=True)
    
    # Путь для сохранения файла
    file_path = os.path.join(TEMP_DIR, file_name)
    
    try:
        # Обновляем статус
        await message.bot.edit_message_text(
            chat_id=message.chat.id,
            message_id=status_message.message_id,
            text=f"Загружаю файл ({file_size / (1024 * 1024):.2f} МБ)..."
        )
        
        # Метод 1: Прямое скачивание через subprocess (curl)
        # Этот метод обходит ограничения API и работает с файлами любого размера
        try:
            # Получаем информацию о файле через getFile API
            import aiohttp
            import subprocess
            import time
            
            # Формируем URL для getFile
            api_url = f"{settings.LOCAL_API_URL}/bot{message.bot.token}/getFile"
            logger.info(f"Запрос getFile: {api_url}")
            
            # Отправляем запрос getFile
            async with aiohttp.ClientSession() as session:
                async with session.post(api_url, json={"file_id": file_id}, timeout=60) as resp:
                    if resp.status != 200:
                        error_text = await resp.text()
                        logger.error(f"Ошибка при получении информации о файле: {resp.status}, {error_text}")
                        raise Exception(f"Ошибка при получении информации о файле: {resp.status}, {error_text}")
                    
                    result = await resp.json()
                    logger.info(f"Ответ getFile: {result}")
                    
                    if not result.get("ok"):
                        logger.error(f"Ошибка API: {result}")
                        raise Exception(f"Ошибка API: {result}")
                    
                    # Получаем путь к файлу на сервере
                    file_path_on_server = result["result"]["file_path"]
                    logger.info(f"Путь к файлу на сервере: {file_path_on_server}")
            
            # Метод 1.1: Прямой доступ к файлу в локальной файловой системе
            # Проверяем несколько возможных путей к файлу
            possible_paths = [
                # Путь 1: Стандартный путь в директории storage
                os.path.join("/root/telegram-bot-api/telegram-bot-api/build/storage", file_path_on_server),
                # Путь 2: Путь относительно корня build
                os.path.join("/root/telegram-bot-api/telegram-bot-api/build", file_path_on_server),
                # Путь 3: Путь с токеном бота
                os.path.join("/root/telegram-bot-api/telegram-bot-api/build/storage", message.bot.token, "documents", os.path.basename(file_path_on_server)),
                # Путь 4: Путь без токена бота
                os.path.join("/root/telegram-bot-api/telegram-bot-api/build/storage/documents", os.path.basename(file_path_on_server)),
            ]
            
            file_found = False
            for local_path in possible_paths:
                logger.info(f"Проверяю путь: {local_path}")
                if os.path.exists(local_path):
                    logger.info(f"Файл найден по пути: {local_path}")
                    # Копируем файл
                    import shutil
                    shutil.copy2(local_path, file_path)
                    logger.info(f"Файл успешно скопирован: {file_path}")
                    file_found = True
                    break
            
            # Метод 1.2: Если файл не найден, ищем его по всей директории storage
            if not file_found:
                logger.info("Файл не найден по стандартным путям, выполняю поиск по всей директории storage")
                storage_dir = "/root/telegram-bot-api/telegram-bot-api/build/storage"
                
                # Ищем файл по всей директории storage
                for root, dirs, files in os.walk(storage_dir):
                    for file in files:
                        # Проверяем, содержит ли имя файла file_id или последние 10 символов file_id
                        if file_id[-10:] in file:
                            found_path = os.path.join(root, file)
                            logger.info(f"Найден файл: {found_path}")
                            shutil.copy2(found_path, file_path)
                            logger.info(f"Файл успешно скопирован: {file_path}")
                            file_found = True
                            break
                    if file_found:
                        break
            
            # Метод 2: Если файл не найден, используем curl для скачивания
            if not file_found:
                logger.info("Файл не найден в файловой системе, пробую скачать через curl")
                download_url = f"{settings.LOCAL_API_URL}/file/bot{message.bot.token}/{file_path_on_server}"
                logger.info(f"URL для скачивания: {download_url}")
                
                # Используем curl для скачивания файла
                curl_command = f"curl -o {file_path} {download_url}"
                logger.info(f"Выполняю команду: {curl_command}")
                
                process = subprocess.Popen(curl_command, shell=True)
                process.wait()
                
                if process.returncode == 0 and os.path.exists(file_path) and os.path.getsize(file_path) > 0:
                    logger.info(f"Файл успешно скачан через curl: {file_path}")
                    file_found = True
                else:
                    logger.error(f"Ошибка при скачивании файла через curl: {process.returncode}")
            
            # Метод 3: Если все предыдущие методы не сработали, используем aiohttp
            if not file_found:
                logger.info("Пробую скачать файл через aiohttp")
                download_url = f"{settings.LOCAL_API_URL}/file/bot{message.bot.token}/{file_path_on_server}"
                
                async with aiohttp.ClientSession() as session:
                    async with session.get(download_url, timeout=1800) as resp:  # 30 минут таймаут
                        if resp.status == 200:
                            # Создаем директорию, если она не существует
                            os.makedirs(os.path.dirname(file_path), exist_ok=True)
                            
                            # Скачиваем файл по частям
                            with open(file_path, 'wb') as fd:
                                # Используем большие чанки для ускорения скачивания
                                async for chunk in resp.content.iter_chunked(8 * 1024 * 1024):  # 8 МБ за раз
                                    fd.write(chunk)
                                    # Обновляем статус каждые 100 МБ
                                    if fd.tell() % (100 * 1024 * 1024) < 8 * 1024 * 1024:
                                        await message.bot.edit_message_text(
                                            chat_id=message.chat.id,
                                            message_id=status_message.message_id,
                                            text=f"Загружено {fd.tell() / (1024 * 1024):.2f} МБ из {file_size / (1024 * 1024):.2f} МБ..."
                                        )
                            
                            logger.info(f"Файл успешно скачан через aiohttp: {file_path}")
                            file_found = True
                        else:
                            error_text = await resp.text()
                            logger.error(f"Ошибка при скачивании файла через aiohttp: {resp.status}, {error_text}")
            
            # Метод 4: Если все предыдущие методы не сработали, используем стандартный метод
            if not file_found:
                logger.info("Пробую стандартный метод download_file")
                await message.bot.download_file(file_path_on_server, file_path, timeout=1800)  # 30 минут таймаут
                logger.info(f"Файл успешно скачан стандартным методом: {file_path}")
                file_found = True
            
            # Проверяем, что файл успешно скачан
            if not os.path.exists(file_path) or os.path.getsize(file_path) == 0:
                raise Exception("Не удалось скачать файл ни одним из методов")
            
        except Exception as e:
            logger.error(f"Ошибка при скачивании файла: {str(e)}")
            raise Exception(f"Ошибка при скачивании файла: {str(e)}")
        
        # Обновляем статус
        await message.bot.edit_message_text(
            chat_id=message.chat.id,
            message_id=status_message.message_id,
            text="Файл успешно загружен. Начинаю обработку архива..."
        )
        
        # Получаем сессию базы данных
        async with async_session() as session:
            log_repo = LogRepository(session)
            session_repo = SessionRepository(session)
            used_phone_repo = UsedPhoneNumberRepository(session)
            
            # Сохраняем информацию о файле в базе данных
            log = await log_repo.create_log(
                file_id=file_id,
                file_name=file_name,
                file_size=file_size
            )
            
            # Распаковываем архив и получаем список вложенных архивов
            await message.bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=status_message.message_id,
                text="Распаковываю архив и обрабатываю вложенные архивы..."
            )
            
            extracted_archives = await extract_archive(file_path)
            
            # Счетчики для статистики
            total_archives = len(extracted_archives)
            new_archives = 0
            duplicate_archives = 0
            
            # Обновляем статус с прогрессом
            await message.bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=status_message.message_id,
                text=f"Найдено {total_archives} архивов. Обрабатываю..."
            )
            
            # Обрабатываем каждый архив
            for i, (phone_number, archive_name) in enumerate(extracted_archives):
                # Периодически обновляем статус с прогрессом (каждые 10 архивов)
                if i % 10 == 0 and i > 0:
                    await message.bot.edit_message_text(
                        chat_id=message.chat.id,
                        message_id=status_message.message_id,
                        text=f"Обработано {i}/{total_archives} архивов..."
                    )
                
                # Проверяем, использовался ли номер ранее
                is_used = await used_phone_repo.is_phone_number_used(phone_number)
                
                if is_used:
                    duplicate_archives += 1
                    continue
                
                # Добавляем сессию в базу данных
                await session_repo.create_session(
                    phone_number=phone_number
                )
                
                # Добавляем номер в список использованных
                await used_phone_repo.add_used_phone_number(phone_number)
                new_archives += 1
            
            # Удаляем скачанный файл
            try:
                os.remove(file_path)
            except Exception as e:
                logger.error(f"Ошибка при удалении файла {file_path}: {e}")
            
            # Отправляем сообщение об успешной загрузке
            await message.bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=status_message.message_id,
                text=f"Архив успешно обработан!\n\n"
                     f"📊 Статистика:\n"
                     f"- Всего архивов в загрузке: {total_archives}\n"
                     f"- Новых архивов добавлено: {new_archives}\n"
                     f"- Дубликатов пропущено: {duplicate_archives}"
            )
    
    except Exception as e:
        logger.error(f"Ошибка при обработке файла: {str(e)}")
        await message.answer(f"Произошла ошибка при обработке файла: {str(e)}")
        
        # Удаляем скачанный файл в случае ошибки
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
        except Exception as cleanup_error:
            logger.error(f"Ошибка при удалении файла после ошибки: {cleanup_error}")
    
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
    """Обработчик кнопки 'Очистить базу данных'
    
    Очищает базу данных логов и сессий, чтобы работники не могли получить их.
    """
    # Отправляем сообщение с подтверждением очистки
    await message.answer(
        "Вы уверены, что хотите очистить базу данных логов и сессий? Это действие нельзя отменить.\n"
        "После очистки все логи и сессии будут удалены, и работники не смогут их получить.",
        reply_markup=get_confirmation_keyboard("clear_logs")
    )

# Обработчик подтверждения очистки базы логов
async def confirm_clear_logs(callback: CallbackQuery) -> None:
    """Обработчик подтверждения очистки базы данных
    
    Очищает базу данных логов и сессий, чтобы работники не могли получить их.
    """
    # Получаем сессию базы данных
    async with async_session() as session:
        log_repo = LogRepository(session)
        session_repo = SessionRepository(session)
        
        # Очищаем базу логов
        deleted_logs_count = await log_repo.clear_all_logs()
        
        # Очищаем базу сессий
        deleted_sessions_count = await session_repo.clear_all_sessions()
        
        # Отправляем сообщение об успешной очистке
        await callback.message.answer(
            f"База данных успешно очищена.\n"
            f"Удалено логов: {deleted_logs_count}\n"
            f"Удалено сессий: {deleted_sessions_count}"
        )
    
    # Отвечаем на callback, чтобы убрать часы загрузки
    await callback.answer()

# Обработчик отмены очистки базы логов
async def cancel_clear_logs(callback: CallbackQuery) -> None:
    """Обработчик отмены очистки базы данных"""
    # Отправляем сообщение об отмене очистки
    await callback.message.answer("Очистка базы данных логов и сессий отменена.")
    
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
    
    # Регистрация обработчиков для новых форматов callback_data
    dp.callback_query.register(confirm_delete_user, F.data.startswith("confirm_user_"))
    dp.callback_query.register(cancel_delete_user, F.data.startswith("cancel_user_"))
    
    # Регистрация обработчиков для логов
    dp.callback_query.register(confirm_clear_logs, F.data == "confirm_clear_logs")
    dp.callback_query.register(cancel_clear_logs, F.data == "cancel_clear_logs")
    
    # Регистрация обработчика кнопки "Назад"
    dp.callback_query.register(back_to_main, F.data == "back_to_main")
    
    # Регистрация обработчиков для текстовых кнопок
    dp.message.register(show_passwords, F.text == "🔑 Пароли")
    dp.message.register(show_users, F.text == "👥 Пользователи")
    dp.message.register(upload_logs, F.text == "📤 Загрузить логи")
    dp.message.register(stop_logs, F.text == "🚫 Стоп логи")
    dp.message.register(allow_logs, F.text == "✅ Разрешить логи")
    dp.message.register(clear_logs, F.text == "🗑️ Очистить базу данных")
    
    # Регистрация обработчиков состояний
    dp.message.register(process_new_password, AdminState.waiting_for_password)
    dp.message.register(process_max_uses, AdminState.waiting_for_max_uses)
    dp.message.register(process_log_file, AdminState.waiting_for_log_file)
    dp.message.register(process_broadcast_message, BroadcastState.waiting_for_message) 