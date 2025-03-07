import asyncio
import logging
from database.base import async_session
from database.repositories import UserRepository

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def reset_stats():
    """Сбросить счетчики статистики для всех пользователей"""
    async with async_session() as session:
        user_repo = UserRepository(session)
        
        # Получаем всех пользователей
        users = await user_repo.get_all_users()
        
        for user in users:
            logger.info(f"Сброс статистики для пользователя {user.user_id}")
            logger.info(f"До сброса: taken_logs_count={user.taken_logs_count}, empty_logs_count={user.empty_logs_count}")
            
            # Сбрасываем счетчики
            await user_repo.update_user(
                user_id=user.user_id,
                taken_logs_count=0,
                empty_logs_count=0,
                daily_empty_logs_count=0
            )
            
            # Проверяем, что счетчики сброшены
            updated_user = await user_repo.get_by_user_id(user.user_id)
            logger.info(f"После сброса: taken_logs_count={updated_user.taken_logs_count}, empty_logs_count={updated_user.empty_logs_count}")
        
        logger.info("Счетчики статистики успешно сброшены для всех пользователей")

if __name__ == "__main__":
    asyncio.run(reset_stats()) 