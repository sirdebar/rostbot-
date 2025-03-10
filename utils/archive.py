import os
import re
import shutil
import logging
import zipfile
import rarfile
import tempfile
from typing import List, Tuple, Optional
from pathlib import Path
import math

logger = logging.getLogger(__name__)

# Настраиваем rarfile для использования unrar
rarfile.UNRAR_TOOL = "unrar"

# Регулярное выражение для извлечения номера телефона из имени архива
SESSION_PATTERN = re.compile(r'session_(\d+)\.(zip|rar)')

# Создаем директории для хранения сессий и архивов
SESSIONS_DIR = Path("data/sessions")
ARCHIVES_DIR = Path("data/archives")
TEMP_DIR = Path("data/temp")
CHUNKS_DIR = Path("data/chunks")

# Создаем директории, если они не существуют
SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
ARCHIVES_DIR.mkdir(parents=True, exist_ok=True)
TEMP_DIR.mkdir(parents=True, exist_ok=True)
CHUNKS_DIR.mkdir(parents=True, exist_ok=True)

# Максимальный размер части архива (45 МБ)
MAX_CHUNK_SIZE = 45 * 1024 * 1024  # 45 МБ в байтах

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

async def split_large_archive(archive_path: str, base_name: str) -> List[str]:
    """
    Разделяет большой архив на части по MAX_CHUNK_SIZE байт
    Возвращает список путей к частям архива
    """
    try:
        # Получаем размер архива
        file_size = os.path.getsize(archive_path)
        
        # Если размер меньше максимального, возвращаем исходный архив
        if file_size <= MAX_CHUNK_SIZE:
            return [archive_path]
        
        # Вычисляем количество частей
        num_chunks = math.ceil(file_size / MAX_CHUNK_SIZE)
        logger.info(f"Разделение архива {archive_path} на {num_chunks} частей")
        
        # Создаем директорию для частей, если она не существует
        chunks_dir = CHUNKS_DIR / base_name
        chunks_dir.mkdir(parents=True, exist_ok=True)
        
        chunk_paths = []
        
        # Разделяем файл на части
        with open(archive_path, 'rb') as f:
            for i in range(num_chunks):
                chunk_path = chunks_dir / f"{base_name}_part{i+1}of{num_chunks}.zip"
                chunk_paths.append(str(chunk_path))
                
                # Читаем часть файла
                chunk_data = f.read(MAX_CHUNK_SIZE)
                
                # Записываем часть в отдельный файл
                with open(chunk_path, 'wb') as chunk_file:
                    chunk_file.write(chunk_data)
                
                logger.info(f"Создана часть {i+1}/{num_chunks}: {chunk_path}")
        
        return chunk_paths
    
    except Exception as e:
        logger.error(f"Ошибка при разделении архива {archive_path}: {e}")
        return [archive_path]  # В случае ошибки возвращаем исходный архив

async def create_archive_with_sessions(archive_files: List[str], output_path: str) -> List[str]:
    """
    Создает архив с указанными архивами сессий
    Возвращает список путей к частям архива (если архив был разделен)
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
            archive_full_path = f"{output_path}.zip"
            shutil.make_archive(
                str(output_path),  # Путь без расширения
                'zip',        # Формат архива
                temp_dir      # Директория для архивации
            )
            
            # Проверяем размер созданного архива
            file_size = os.path.getsize(archive_full_path)
            logger.info(f"Создан архив {archive_full_path} размером {file_size / (1024 * 1024):.2f} МБ")
            
            # Если размер архива превышает максимальный, разделяем его на части
            if file_size > MAX_CHUNK_SIZE:
                base_name = os.path.basename(output_path)
                chunk_paths = await split_large_archive(archive_full_path, base_name)
                
                # Удаляем исходный большой архив
                if len(chunk_paths) > 1 and os.path.exists(archive_full_path):
                    os.remove(archive_full_path)
                
                return chunk_paths
            
            return [archive_full_path]
    
    except Exception as e:
        logger.error(f"Ошибка при создании архива: {e}")
        return []

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
        
        # Выводим информацию о размере скачанного файла
        file_size = os.path.getsize(destination)
        logger.info(f"Файл {file_id} успешно скачан. Размер: {get_file_size_str(file_size)}")
        
        return destination
    
    except Exception as e:
        logger.error(f"Ошибка при скачивании файла {file_id}: {e}")
        return ""

async def cleanup_chunks_directory() -> None:
    """
    Очищает директорию с частями архивов
    """
    try:
        # Удаляем все поддиректории в директории chunks
        for item in CHUNKS_DIR.iterdir():
            if item.is_dir():
                shutil.rmtree(item)
                logger.info(f"Удалена директория с частями архива: {item}")
    except Exception as e:
        logger.error(f"Ошибка при очистке директории с частями архивов: {e}")

def get_file_size_str(size_bytes: int) -> str:
    """
    Возвращает размер файла в человекочитаемом формате
    """
    if size_bytes < 1024:
        return f"{size_bytes} Б"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.2f} КБ"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.2f} МБ"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.2f} ГБ"

def split_file_instructions() -> str:
    """
    Возвращает инструкции по разделению больших файлов
    """
    instructions = (
        "📋 Инструкция по разделению больших архивов:\n\n"
        "1. Используя 7-Zip (Windows):\n"
        "   - Правый клик на архиве -> 7-Zip -> Разделить файл...\n"
        "   - Укажите размер части (например, 45M для 45 МБ)\n\n"
        "2. Используя WinRAR (Windows):\n"
        "   - Правый клик на архиве -> Открыть с помощью WinRAR\n"
        "   - Нажмите 'Инструменты' -> 'Мастер архивов'\n"
        "   - Выберите 'Разделить на части' и укажите размер (например, 45000 КБ)\n\n"
        "3. Используя командную строку (Linux/Mac):\n"
        "   - Выполните команду: split -b 45m архив.zip 'архив.zip.part'\n\n"
        "После разделения загрузите все части по очереди."
    )
    return instructions 