import logging
from typing import List
from aiogram import Dispatcher, Bot, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from database.base import async_session
from database.repositories import UserRepository, LogRepository
from keyboards import get_worker_keyboard
from states import WorkerState
from handlers.common import get_welcome_message

logger = logging.getLogger(__name__)

# Обработчик кнопки "Статистика"
async def show_statistics(message: Message) -> None:
    """Обработчик кнопки 'Статистика'"""
    # Получаем сессию базы данных
    async with async_session() as session:
        user_repo = UserRepository(session)
        
        # Получаем пользователя
        user = await user_repo.get_by_user_id(message.from_user.id)
        
        if user:
            # Отправляем сообщение со статистикой
            await message.answer(
                f"📊 <b>Ваша статистика:</b>\n\n"
                f"📦 Взято логов: {user.taken_logs_count}\n"
                f"🗑 Пустых логов: {user.empty_logs_count}\n"
                f"🗓 Пустых логов сегодня: {user.daily_empty_logs_count}"
            )
        else:
            await message.answer("Не удалось получить статистику. Попробуйте позже.")

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
    # Проверяем, что введено число
    try:
        empty_logs_count = int(message.text)
        if empty_logs_count <= 0:
            await message.answer("Количество пустых логов должно быть положительным числом. Попробуйте еще раз:")
            return
    except ValueError:
        await message.answer("Введите число. Попробуйте еще раз:")
        return
    
    # Получаем сессию базы данных
    async with async_session() as session:
        user_repo = UserRepository(session)
        
        # Получаем пользователя
        user = await user_repo.get_by_user_id(message.from_user.id)
        
        if user:
            # Увеличиваем счетчик пустых логов
            await user_repo.increment_empty_logs(message.from_user.id, empty_logs_count)
            
            # Получаем обновленные данные пользователя
            user = await user_repo.get_by_user_id(message.from_user.id)
            
            # Отправляем сообщение с результатом
            await message.answer(
                f"{empty_logs_count} пустых лога\n"
                f"Итог за сегодня: {user.daily_empty_logs_count} пустых"
            )
        else:
            await message.answer("Не удалось обновить статистику. Попробуйте позже.")
    
    # Очищаем состояние
    await state.clear()

# Обработчик кнопки "Взять логи"
async def take_logs(message: Message, state: FSMContext) -> None:
    """Обработчик кнопки 'Взять логи'"""
    # Проверяем, не заблокирована ли выдача логов
    if settings.LOGS_BLOCKED:
        await message.answer("Выдача логов временно заблокирована администратором.")
        return
    
    # Получаем сессию базы данных
    async with async_session() as session:
        log_repo = LogRepository(session)
        
        # Получаем количество доступных логов
        available_logs_count = await log_repo.get_available_logs_count()
        
        if available_logs_count == 0:
            await message.answer("В данный момент нет доступных логов.")
            return
        
        # Отправляем сообщение с запросом количества логов
        await message.answer(
            f"Введите количество логов для получения.\n"
            f"Доступно: {available_logs_count}\n"
            f"Максимум: {settings.MAX_LOGS_PER_USER}"
        )
    
    # Устанавливаем состояние ожидания количества логов
    await state.set_state(WorkerState.waiting_for_logs_count)

# Обработчик ввода количества логов для получения
async def process_logs_count(message: Message, state: FSMContext, bot: Bot) -> None:
    """Обработчик ввода количества логов для получения"""
    # Проверяем, что введено число
    try:
        logs_count = int(message.text)
        if logs_count <= 0:
            await message.answer("Количество логов должно быть положительным числом. Попробуйте еще раз:")
            return
    except ValueError:
        await message.answer("Введите число. Попробуйте еще раз:")
        return
    
    # Проверяем, не превышает ли запрошенное количество максимально допустимое
    if logs_count > settings.MAX_LOGS_PER_USER:
        await message.answer(
            f"Вы не можете взять больше {settings.MAX_LOGS_PER_USER} логов за один раз. "
            f"Попробуйте еще раз:"
        )
        return
    
    # Получаем сессию базы данных
    async with async_session() as session:
        log_repo = LogRepository(session)
        user_repo = UserRepository(session)
        
        # Получаем количество доступных логов
        available_logs_count = await log_repo.get_available_logs_count()
        
        if available_logs_count == 0:
            await message.answer("В данный момент нет доступных логов.")
            await state.clear()
            return
        
        # Если запрошено больше логов, чем доступно, ограничиваем количество
        if logs_count > available_logs_count:
            logs_count = available_logs_count
            await message.answer(
                f"Доступно только {available_logs_count} логов. "
                f"Выдаем все доступные логи."
            )
        
        # Назначаем логи пользователю
        logs = await log_repo.assign_logs_to_user(message.from_user.id, logs_count)
        
        if logs:
            # Увеличиваем счетчик взятых логов
            await user_repo.increment_taken_logs(message.from_user.id, len(logs))
            
            # Отправляем сообщение об успешном получении логов
            await message.answer(f"Вы получили {len(logs)} логов.")
            
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
        else:
            await message.answer("Не удалось получить логи. Попробуйте позже.")
    
    # Очищаем состояние
    await state.clear()

# Обработчик кнопки "Ваши логи"
async def show_user_logs(message: Message, bot: Bot) -> None:
    """Обработчик кнопки 'Ваши логи'"""
    # Получаем сессию базы данных
    async with async_session() as session:
        log_repo = LogRepository(session)
        
        # Получаем логи пользователя
        logs = await log_repo.get_user_logs(message.from_user.id)
        
        if logs:
            # Отправляем сообщение с количеством логов
            await message.answer(f"У вас есть {len(logs)} логов:")
            
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
        else:
            await message.answer("У вас нет логов.")

def register_worker_handlers(dp: Dispatcher, bot: Bot) -> None:
    """Регистрация обработчиков команд работника"""
    # Регистрация обработчиков кнопок главного меню
    dp.message.register(show_statistics, F.text == "📊 Статистика")
    dp.message.register(empty_log, F.text == "🗑️ Пустой лог")
    dp.message.register(take_logs, F.text == "📥 Взять логи")
    dp.message.register(show_user_logs, F.text == "📋 Ваши логи")
    
    # Регистрация обработчиков состояний
    dp.message.register(process_empty_logs_count, WorkerState.waiting_for_empty_logs_count)
    dp.message.register(process_logs_count, WorkerState.waiting_for_logs_count) 