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

# Регулярное выражение для извлечения номера телефона из имени архива
SESSION_PATTERN = re.compile(r'session_(\d+)\.(zip|rar)')

# Создаем директории для хранения сессий и архивов
SESSIONS_DIR = Path("data/sessions")
ARCHIVES_DIR = Path("data/archives")
TEMP_DIR = Path("data/temp")

# Создаем директории, если они не существуют
SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
ARCHIVES_DIR.mkdir(parents=True, exist_ok=True)
TEMP_DIR.mkdir(parents=True, exist_ok=True)

def extract_phone_number(file_name: str) -> Optional[str]:
    """Извлекает номер телефона из имени архива"""
    match = SESSION_PATTERN.match(file_name)
    if match:
        return match.group(1)
    return None

async def extract_archive(file_path: str) -> List[Tuple[str, str]]:
    """
    Распаковывает основной архив и сохраняет вложенные архивы.
    Возвращает список кортежей (номер_телефона, имя_архива)
    """
    extracted_archives = []
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
        
        # Ищем вложенные архивы в распакованном архиве
        for root, dirs, files in os.walk(temp_extract_dir):
            for file_name in files:
                if file_name.endswith('.zip') or file_name.endswith('.rar'):
                    # Извлекаем номер телефона из имени архива
                    phone_number = extract_phone_number(file_name)
                    
                    if phone_number:
                        # Сохраняем архив в директорию архивов
                        source_path = Path(root) / file_name
                        dest_path = ARCHIVES_DIR / file_name
                        shutil.copy2(source_path, dest_path)
                        
                        extracted_archives.append((phone_number, file_name))
                    else:
                        logger.warning(f"Не удалось извлечь номер телефона из имени архива: {file_name}")
        
        return extracted_archives
    
    except Exception as e:
        logger.error(f"Ошибка при распаковке архива {file_path}: {e}")
        return []
    finally:
        # Удаляем временную директорию
        shutil.rmtree(temp_extract_dir, ignore_errors=True)

async def create_archive_with_sessions(archive_files: List[str], output_path: str) -> bool:
    """
    Создает архив с указанными архивами сессий
    """
    try:
        # Создаем временную директорию для сбора файлов
        with tempfile.TemporaryDirectory() as temp_dir:
            # Копируем архивы сессий во временную директорию
            for file_name in archive_files:
                src_path = ARCHIVES_DIR / file_name
                dst_path = Path(temp_dir) / file_name
                if src_path.exists():
                    shutil.copy2(src_path, dst_path)
                else:
                    logger.warning(f"Архив {src_path} не найден")
            
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

async def delete_session_archives(archive_files: List[str]) -> None:
    """
    Удаляет архивы сессий после их выдачи
    """
    for file_name in archive_files:
        file_path = ARCHIVES_DIR / file_name
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception as e:
                logger.error(f"Ошибка при удалении архива {file_path}: {e}")

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