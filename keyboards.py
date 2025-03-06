import logging
from typing import List
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from database.models import User

logger = logging.getLogger(__name__)

# Клавиатура для администратора
def get_admin_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура для администратора"""
    keyboard = [
        [KeyboardButton(text="Пароли")],
        [KeyboardButton(text="Пользователи")],
        [KeyboardButton(text="Загрузить логи")],
        [KeyboardButton(text="Стоп логи"), KeyboardButton(text="Разрешить логи")],
        [KeyboardButton(text="Очистить базу логов")]
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

# Клавиатура для работника
def get_worker_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура для работника"""
    keyboard = [
        [KeyboardButton(text="Статистика")],
        [KeyboardButton(text="Пустой лог")],
        [KeyboardButton(text="Взять логи")],
        [KeyboardButton(text="Ваши логи")]
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

# Клавиатура для управления паролями
def get_passwords_keyboard(passwords: List) -> InlineKeyboardMarkup:
    """Клавиатура для управления паролями"""
    keyboard = []
    
    # Добавляем кнопку для создания нового пароля
    keyboard.append([InlineKeyboardButton(text="➕ Создать новый пароль", callback_data="create_password")])
    
    # Добавляем кнопки для существующих паролей
    for password in passwords:
        remaining_uses = password.max_uses - password.used_count
        keyboard.append([
            InlineKeyboardButton(
                text=f"{password.password} ({remaining_uses}/{password.max_uses})",
                callback_data=f"password_{password.id}"
            )
        ])
    
    # Добавляем кнопку для возврата назад
    keyboard.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_main")])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

# Клавиатура для управления паролем
def get_password_management_keyboard(password_id: int) -> InlineKeyboardMarkup:
    """Клавиатура для управления конкретным паролем"""
    keyboard = [
        [InlineKeyboardButton(text="❌ Удалить пароль", callback_data=f"delete_password_{password_id}")],
        [InlineKeyboardButton(text="⬅️ Назад к паролям", callback_data="back_to_passwords")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

# Клавиатура для управления пользователями
def get_users_keyboard(users: List[User]) -> InlineKeyboardMarkup:
    """Клавиатура для управления пользователями"""
    keyboard = []
    
    # Добавляем кнопки для пользователей
    for user in users:
        display_name = user.username or f"{user.first_name or ''} {user.last_name or ''}".strip() or f"User {user.user_id}"
        callback_data = f"user_{user.user_id}"
        logger.info(f"Создаем кнопку для пользователя {user.user_id} с callback_data: {callback_data}")
        keyboard.append([
            InlineKeyboardButton(
                text=f"{'👑 ' if user.is_admin else ''}{display_name}",
                callback_data=callback_data
            )
        ])
    
    # Добавляем кнопку для возврата назад
    keyboard.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_main")])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

# Клавиатура для управления пользователем
def get_user_management_keyboard(user_id: int) -> InlineKeyboardMarkup:
    """Клавиатура для управления конкретным пользователем"""
    callback_data = f"delete_user_{user_id}"
    logger.info(f"Создаем кнопку удаления для пользователя {user_id} с callback_data: {callback_data}")
    keyboard = [
        [InlineKeyboardButton(text="❌ Удалить пользователя", callback_data=callback_data)],
        [InlineKeyboardButton(text="⬅️ Назад к пользователям", callback_data="back_to_users")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

# Клавиатура для подтверждения действия
def get_confirmation_keyboard(action: str, entity_id: int = None) -> InlineKeyboardMarkup:
    """Клавиатура для подтверждения действия"""
    callback_data_confirm = f"confirm_{action}"
    callback_data_cancel = f"cancel_{action}"
    
    if entity_id is not None:
        callback_data_confirm += f"_{entity_id}"
        callback_data_cancel += f"_{entity_id}"
    
    logger.info(f"Создаем клавиатуру подтверждения с callback_data: {callback_data_confirm} и {callback_data_cancel}")
    
    keyboard = [
        [
            InlineKeyboardButton(text="✅ Да", callback_data=callback_data_confirm),
            InlineKeyboardButton(text="❌ Нет", callback_data=callback_data_cancel)
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard) 