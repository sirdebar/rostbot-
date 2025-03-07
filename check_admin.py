import asyncio
import logging
from database.base import async_session
from database.repositories import UserRepository
from config import settings

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def check_admin():
    # Выводим список администраторов из настроек
    logger.info(f"Администраторы в настройках: {settings.ADMIN_IDS}")
    
    # Проверяем администраторов в базе данных
    async with async_session() as session:
        user_repo = UserRepository(session)
        
        # Проверяем каждый ID администратора
        for admin_id in settings.ADMIN_IDS:
            user = await user_repo.get_by_user_id(admin_id)
            if user:
                logger.info(f"Пользователь {admin_id} найден в базе данных. is_admin: {user.is_admin}")
                
                # Если пользователь не отмечен как администратор, исправляем это
                if not user.is_admin:
                    logger.info(f"Обновляем статус администратора для пользователя {admin_id}")
                    await user_repo.update_user(admin_id, is_admin=True)
                    
                    # Проверяем, что статус обновился
                    updated_user = await user_repo.get_by_user_id(admin_id)
                    logger.info(f"Статус администратора после обновления: {updated_user.is_admin}")
            else:
                logger.info(f"Пользователь {admin_id} не найден в базе данных")

if __name__ == "__main__":
    asyncio.run(check_admin()) 