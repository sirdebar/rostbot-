import logging
import os
from datetime import datetime
from aiogram import Dispatcher, Bot, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, FSInputFile
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from database.base import async_session
from database.repositories import UserRepository, LogRepository, SessionRepository
from keyboards import get_worker_inline_keyboard
from states import WorkerState
from handlers.common import get_welcome_message
from utils.archive import create_archive_with_sessions, delete_session_folders, TEMP_DIR, SESSIONS_DIR

logger = logging.getLogger(__name__)

# Обработчик кнопки "Статистика"
async def show_statistics(message: Message) -> None:
    """Обработчик кнопки 'Статистика'"""
    # Получаем ID пользователя
    user_id = message.from_user.id
    
    # Выводим отладочную информацию
    logger.info(f"Запрос статистики от пользователя {user_id} через текстовую кнопку")
    
    # Получаем сессию базы данных
    async with async_session() as session:
        user_repo = UserRepository(session)
        
        # Получаем свежую статистику пользователя
        stats = await user_repo.get_fresh_statistics(user_id)
        
        # Формируем сообщение со статистикой
        stats_message = "📊 **Статистика**\n\n"
        stats_message += f"Всего вы взяли: {stats['taken_logs_count']} сессий.\n"
        stats_message += f"Всего пустых логов: {stats['empty_logs_count']}\n"
        
        # Отправляем сообщение со статистикой
        await message.answer(stats_message, parse_mode="Markdown")
        
        # Выводим отладочную информацию
        logger.info(f"Статистика отправлена пользователю {user_id}: taken={stats['taken_logs_count']}, empty={stats['empty_logs_count']}")

# Обработчик кнопки "Пустой лог"
async def empty_log(message: Message, state: FSMContext) -> None:
    """Обработчик кнопки 'Пустой лог'"""
    # Отправляем сообщение с запросом количества пустых логов
    await message.answer("Введите количество пустых логов:")
    
    # Устанавливаем состояние ожидания количества пустых логов
    await state.set_state(WorkerState.waiting_for_empty_logs_count)

# Обработчик ввода количества пустых логов
async def process_empty_logs_count(message: Message, state: FSMContext) -> None:
    """Обработчик ввода количества пустых логов"""
    # Получаем ID пользователя
    user_id = message.from_user.id
    
    # Проверяем, что введено число
    try:
        empty_logs_count = int(message.text)
        if empty_logs_count <= 0:
            await message.answer("Количество пустых логов должно быть положительным числом. Попробуйте еще раз:")
            return
    except ValueError:
        await message.answer("Введите число. Попробуйте еще раз:")
        return
    
    # Выводим отладочную информацию
    logger.info(f"Пользователь {user_id} добавляет {empty_logs_count} пустых логов")
    
    # Получаем сессию базы данных
    async with async_session() as session:
        user_repo = UserRepository(session)
        
        # Обновляем статистику пользователя
        updated_user = await user_repo.update_statistics(
            user_id=user_id,
            empty_logs_to_add=empty_logs_count
        )
    
    # Отправляем сообщение с результатом
    await message.answer(
        f"Вы взяли {empty_logs_count} пустых логов.\n"
        f"Всего пустых логов: {updated_user.empty_logs_count}"
    )
    
    # Выводим отладочную информацию
    logger.info(f"Статистика пользователя {user_id} обновлена: empty_logs_count={updated_user.empty_logs_count}")
    
    # Очищаем состояние
    await state.clear()

# Обработчик кнопки "Взять логи"
async def take_logs(message: Message, state: FSMContext) -> None:
    """Обработчик кнопки 'Взять логи'"""
    # Получаем сессию базы данных
    async with async_session() as session:
        session_repo = SessionRepository(session)
        
        # Получаем количество доступных сессий
        available_sessions_count = await session_repo.get_available_sessions_count()
        
        if available_sessions_count == 0:
            await message.answer("К сожалению, сейчас нет доступных сессий. Попробуйте позже.")
            return
        
        # Запрашиваем количество сессий для выдачи
        await message.answer(
            f"Доступно сессий: {available_sessions_count}\n"
            f"Введите количество сессий, которое хотите получить (от 1 до {min(available_sessions_count, settings.MAX_LOGS_PER_USER)}):"
        )
        
        # Устанавливаем состояние ожидания ввода количества сессий
        await state.set_state(WorkerState.waiting_for_logs_count)

# Обработчик ввода количества сессий для выдачи
async def process_logs_count(message: Message, state: FSMContext, bot: Bot) -> None:
    """Обработчик ввода количества сессий для выдачи"""
    # Получаем ID пользователя
    user_id = message.from_user.id
    
    try:
        count = int(message.text)
        
        # Получаем сессию базы данных
        async with async_session() as session:
            session_repo = SessionRepository(session)
            user_repo = UserRepository(session)
            
            # Получаем количество доступных сессий
            available_sessions_count = await session_repo.get_available_sessions_count()
            
            # Проверяем, что запрошенное количество корректно
            if count <= 0:
                await message.answer("Количество должно быть положительным числом. Попробуйте еще раз:")
                return
            
            if count > min(available_sessions_count, settings.MAX_LOGS_PER_USER):
                await message.answer(
                    f"Вы не можете взять больше {min(available_sessions_count, settings.MAX_LOGS_PER_USER)} сессий. Попробуйте еще раз:"
                )
                return
            
            # Отправляем сообщение о начале обработки
            status_message = await message.answer("Подготавливаю сессии...")
            
            # Назначаем сессии пользователю
            sessions = await session_repo.assign_sessions_to_user(user_id, count)
            
            if not sessions:
                await bot.edit_message_text(
                    chat_id=message.chat.id,
                    message_id=status_message.message_id,
                    text="Произошла ошибка при получении сессий. Попробуйте позже."
                )
                await state.clear()
                return
            
            # Выводим отладочную информацию
            logger.info(f"Пользователь {user_id} берет {count} сессий")
            
            # Обновляем статистику пользователя
            updated_user = await user_repo.update_statistics(
                user_id=user_id,
                taken_logs_to_add=count
            )
            
            # Создаем архив с сессиями
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            archive_name = f"logs_{timestamp}"
            archive_path = TEMP_DIR / archive_name
            
            # Получаем номера телефонов сессий
            phone_numbers = [session.phone_number for session in sessions]
            
            # Создаем папки сессий для архивации
            folder_names = []
            for phone in phone_numbers:
                folder_name = f"session_{phone}"
                folder_path = SESSIONS_DIR / folder_name
                os.makedirs(folder_path, exist_ok=True)
                folder_names.append(folder_name)
            
            # Создаем архив
            success = await create_archive_with_sessions(folder_names, archive_path)
            
            if not success:
                await bot.edit_message_text(
                    chat_id=message.chat.id,
                    message_id=status_message.message_id,
                    text="Произошла ошибка при создании архива. Попробуйте позже."
                )
                await state.clear()
                return
            
            # Отправляем архив пользователю
            await bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=status_message.message_id,
                text=f"Архив с {count} сессиями готов! Отправляю..."
            )
            
            # Отправляем файл
            zip_path = f"{archive_path}.zip"
            await message.answer_document(
                FSInputFile(zip_path),
                caption=f"Ваши логи WhatsApp ({count} шт.)"
            )
            
            # Удаляем временный архив
            try:
                if os.path.exists(zip_path):
                    os.remove(zip_path)
            except Exception as e:
                logger.error(f"Ошибка при удалении архива {zip_path}: {e}")
            
            # Удаляем папки сессий
            await delete_session_folders(folder_names)
            
            # Отправляем сообщение об успешной выдаче
            await message.answer(
                f"Сессии успешно выданы! Всего вы взяли: {updated_user.taken_logs_count} сессий."
            )
            
            # Выводим отладочную информацию
            logger.info(f"Сессии успешно выданы пользователю {user_id}. Всего взято: {updated_user.taken_logs_count}")
    
    except ValueError:
        await message.answer("Пожалуйста, введите число. Попробуйте еще раз:")
        return
    
    # Очищаем состояние
    await state.clear()

# Обработчик кнопки "Ваши логи"
async def show_user_logs(message: Message, bot: Bot) -> None:
    """Обработчик кнопки 'Ваши логи'"""
    # Получаем сессию базы данных
    async with async_session() as session:
        log_repo = LogRepository(session)
        session_repo = SessionRepository(session)
        
        # Получаем логи пользователя
        logs = await log_repo.get_user_logs(message.from_user.id)
        
        # Получаем сессии пользователя
        sessions = await session_repo.get_user_sessions(message.from_user.id)
        
        if not logs and not sessions:
            await message.answer("У вас пока нет логов или сессий.")
            return
        
        # Отправляем сообщение с информацией о логах
        if logs:
            await message.answer(f"📦 У вас есть {len(logs)} логов:")
            
            # Отправляем каждый лог пользователю
            for log in logs:
                try:
                    await bot.send_document(
                        chat_id=message.chat.id,
                        document=log.file_id,
                        caption=f"Лог: {log.file_name}"
                    )
                except Exception as e:
                    logger.error(f"Ошибка при отправке лога {log.id}: {e}")
        
        # Отправляем сообщение с информацией о сессиях
        if sessions:
            await message.answer(f"📱 У вас есть {len(sessions)} сессий:")
            
            # Группируем сессии по 10 для удобства отображения
            sessions_chunks = [sessions[i:i+10] for i in range(0, len(sessions), 10)]
            
            for chunk in sessions_chunks:
                sessions_info = "\n".join([f"- {session.phone_number}" for session in chunk])
                await message.answer(sessions_info)

# Обработчик инлайн-кнопки "Статистика"
async def show_statistics_inline(callback: CallbackQuery) -> None:
    """Обработчик инлайн-кнопки 'Статистика'"""
    # Получаем ID пользователя
    user_id = callback.from_user.id
    
    # Выводим отладочную информацию
    logger.info(f"Запрос статистики от пользователя {user_id} через инлайн-кнопку")
    
    # Получаем сессию базы данных
    async with async_session() as session:
        user_repo = UserRepository(session)
        
        # Получаем свежую статистику пользователя
        stats = await user_repo.get_fresh_statistics(user_id)
        
        # Формируем сообщение со статистикой
        stats_message = "📊 **Статистика**\n\n"
        stats_message += f"Всего вы взяли: {stats['taken_logs_count']} сессий.\n"
        stats_message += f"Всего пустых логов: {stats['empty_logs_count']}\n"
        
        # Отправляем сообщение со статистикой
        await callback.message.answer(stats_message, parse_mode="Markdown")
        
        # Отвечаем на callback, чтобы убрать часы загрузки
        await callback.answer()
        
        # Выводим отладочную информацию
        logger.info(f"Статистика отправлена пользователю {user_id}: taken={stats['taken_logs_count']}, empty={stats['empty_logs_count']}")

def register_worker_handlers(dp: Dispatcher, bot: Bot) -> None:
    """Регистрация обработчиков команд работника"""
    # Регистрация обработчиков инлайн-кнопок
    dp.callback_query.register(show_statistics_inline, F.data == "worker_statistics")
    dp.message.register(show_statistics, F.text == "📊 Статистика")
    
    dp.callback_query.register(lambda callback, state: empty_log(callback.message, state), F.data == "worker_empty_log")
    dp.message.register(lambda message, state: empty_log(message, state), F.text == "🗑️ Пустой лог")
    
    dp.callback_query.register(lambda callback, state: take_logs(callback.message, state), F.data == "worker_take_logs")
    dp.message.register(lambda message, state: take_logs(message, state), F.text == "📥 Взять логи")
    
    dp.callback_query.register(lambda callback: show_user_logs(callback.message, bot), F.data == "worker_your_logs")
    dp.message.register(lambda message: show_user_logs(message, bot), F.text == "📋 Ваши логи")
    
    # Регистрация обработчиков состояний
    dp.message.register(process_empty_logs_count, WorkerState.waiting_for_empty_logs_count)
    dp.message.register(process_logs_count, WorkerState.waiting_for_logs_count) 