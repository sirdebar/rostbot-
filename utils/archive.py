import os
import re
import shutil
import logging
import zipfile
import rarfile
import tempfile
from typing import List, Tuple, Optional
from pathlib import Path

logger = logging.getLogger(__name__)

# Настраиваем rarfile для использования unrar
rarfile.UNRAR_TOOL = "unrar"

# Регулярное выражение для извлечения номера телефона из имени папки
SESSION_PATTERN = re.compile(r'session_(\d+)')

# Создаем директории для хранения сессий
SESSIONS_DIR = Path("data/sessions")
TEMP_DIR = Path("data/temp")

# Создаем директории, если они не существуют
SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
TEMP_DIR.mkdir(parents=True, exist_ok=True)

def extract_phone_number(folder_name: str) -> Optional[str]:
    """Извлекает номер телефона из имени папки"""
    match = SESSION_PATTERN.match(folder_name)
    if match:
        return match.group(1)
    return None

async def extract_archive(file_path: str) -> List[Tuple[str, str]]:
    """
    Распаковывает архив и возвращает список кортежей (номер_телефона, имя_папки)
    """
    extracted_sessions = []
    temp_extract_dir = TEMP_DIR / f"extract_{os.path.basename(file_path)}"
    
    try:
        # Создаем временную директорию для распаковки
        os.makedirs(temp_extract_dir, exist_ok=True)
        
        # Определяем тип архива и распаковываем
        if file_path.endswith('.zip'):
            with zipfile.ZipFile(file_path, 'r') as zip_ref:
                zip_ref.extractall(temp_extract_dir)
        elif file_path.endswith('.rar'):
            with rarfile.RarFile(file_path, 'r') as rar_ref:
                rar_ref.extractall(temp_extract_dir)
        else:
            logger.error(f"Неподдерживаемый формат архива: {file_path}")
            return []
        
        # Ищем папки сессий в распакованном архиве
        for root, dirs, files in os.walk(temp_extract_dir):
            for dir_name in dirs:
                phone_number = extract_phone_number(dir_name)
                if phone_number:
                    extracted_sessions.append((phone_number, dir_name))
        
        return extracted_sessions
    
    except Exception as e:
        logger.error(f"Ошибка при распаковке архива {file_path}: {e}")
        return []
    finally:
        # Удаляем временную директорию
        shutil.rmtree(temp_extract_dir, ignore_errors=True)

async def create_archive_with_sessions(session_folders: List[str], output_path: str) -> bool:
    """
    Создает архив с указанными папками сессий
    """
    try:
        # Создаем временную директорию для сбора файлов
        with tempfile.TemporaryDirectory() as temp_dir:
            # Создаем пустые папки сессий во временной директории
            for folder_name in session_folders:
                dst_path = Path(temp_dir) / folder_name
                os.makedirs(dst_path, exist_ok=True)
            
            # Создаем архив
            shutil.make_archive(
                str(output_path),  # Путь без расширения
                'zip',        # Формат архива
                temp_dir      # Директория для архивации
            )
            
            return True
    
    except Exception as e:
        logger.error(f"Ошибка при создании архива: {e}")
        return False

async def delete_session_folders(session_folders: List[str]) -> None:
    """
    Удаляет папки сессий после их выдачи
    """
    for folder_name in session_folders:
        folder_path = SESSIONS_DIR / folder_name
        if os.path.exists(folder_path):
            try:
                shutil.rmtree(folder_path)
                logger.info(f"Удалена папка сессии: {folder_name}")
            except Exception as e:
                logger.error(f"Ошибка при удалении папки {folder_name}: {e}")

async def download_telegram_file(bot, file_id: str, destination: str) -> str:
    """
    Скачивает файл из Telegram и сохраняет его по указанному пути
    """
    try:
        file = await bot.get_file(file_id)
        file_path = file.file_path
        
        # Создаем директорию, если она не существует
        os.makedirs(os.path.dirname(destination), exist_ok=True)
        
        # Скачиваем файл
        await bot.download_file(file_path, destination)
        return destination
    
    except Exception as e:
        logger.error(f"Ошибка при скачивании файла {file_id}: {e}")
        return "" 