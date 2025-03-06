from datetime import datetime, date
from typing import List, Optional, Tuple
from sqlalchemy import select, update, delete, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import User, Password, Log

class UserRepository:
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def get_by_user_id(self, user_id: int) -> Optional[User]:
        """Получить пользователя по его Telegram ID"""
        result = await self.session.execute(select(User).where(User.user_id == user_id))
        return result.scalars().first()
    
    async def create_user(self, user_id: int, username: str = None, first_name: str = None, last_name: str = None, is_admin: bool = False) -> User:
        """Создать нового пользователя"""
        user = User(
            user_id=user_id,
            username=username,
            first_name=first_name,
            last_name=last_name,
            is_admin=is_admin
        )
        self.session.add(user)
        await self.session.commit()
        await self.session.refresh(user)
        return user
    
    async def get_or_create_user(self, user_id: int, username: str = None, first_name: str = None, last_name: str = None) -> Tuple[User, bool]:
        """Получить пользователя или создать нового, если он не существует"""
        user = await self.get_by_user_id(user_id)
        created = False
        
        if not user:
            # Проверяем, является ли пользователь администратором
            from config import settings
            is_admin = user_id in settings.ADMIN_IDS
            
            user = await self.create_user(
                user_id=user_id,
                username=username,
                first_name=first_name,
                last_name=last_name,
                is_admin=is_admin
            )
            created = True
        
        return user, created
    
    async def update_user(self, user_id: int, **kwargs) -> Optional[User]:
        """Обновить данные пользователя"""
        await self.session.execute(
            update(User).where(User.user_id == user_id).values(**kwargs)
        )
        await self.session.commit()
        return await self.get_by_user_id(user_id)
    
    async def delete_user(self, user_id: int) -> bool:
        """Удалить пользователя"""
        result = await self.session.execute(
            delete(User).where(User.user_id == user_id)
        )
        await self.session.commit()
        return result.rowcount > 0
    
    async def get_all_users(self) -> List[User]:
        """Получить всех пользователей"""
        result = await self.session.execute(select(User))
        return result.scalars().all()
    
    async def get_all_active_users(self) -> List[User]:
        """Получить всех активных пользователей"""
        result = await self.session.execute(select(User).where(User.is_active == True))
        return result.scalars().all()
    
    async def increment_taken_logs(self, user_id: int, count: int = 1) -> None:
        """Увеличить счетчик взятых логов"""
        await self.session.execute(
            update(User)
            .where(User.user_id == user_id)
            .values(taken_logs_count=User.taken_logs_count + count)
        )
        await self.session.commit()
    
    async def increment_empty_logs(self, user_id: int, count: int = 1) -> None:
        """Увеличить счетчик пустых логов"""
        user = await self.get_by_user_id(user_id)
        
        # Проверяем, нужно ли сбросить счетчик ежедневных пустых логов
        today = date.today()
        if user.last_empty_log_date is None or user.last_empty_log_date.date() < today:
            daily_empty_logs_count = count
        else:
            daily_empty_logs_count = user.daily_empty_logs_count + count
        
        await self.session.execute(
            update(User)
            .where(User.user_id == user_id)
            .values(
                empty_logs_count=User.empty_logs_count + count,
                daily_empty_logs_count=daily_empty_logs_count,
                last_empty_log_date=datetime.utcnow()
            )
        )
        await self.session.commit()

class PasswordRepository:
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def create_password(self, password: str, max_uses: int, created_by: int) -> Password:
        """Создать новый пароль"""
        password_obj = Password(
            password=password,
            max_uses=max_uses,
            created_by=created_by
        )
        self.session.add(password_obj)
        await self.session.commit()
        await self.session.refresh(password_obj)
        return password_obj
    
    async def get_by_password(self, password: str) -> Optional[Password]:
        """Получить пароль по его значению"""
        result = await self.session.execute(
            select(Password).where(Password.password == password, Password.is_active == True)
        )
        return result.scalars().first()
    
    async def use_password(self, password: str) -> bool:
        """Использовать пароль. Возвращает True, если пароль действителен и может быть использован"""
        password_obj = await self.get_by_password(password)
        
        if not password_obj or not password_obj.is_active:
            return False
        
        if password_obj.used_count >= password_obj.max_uses:
            return False
        
        # Увеличиваем счетчик использований
        await self.session.execute(
            update(Password)
            .where(Password.id == password_obj.id)
            .values(used_count=Password.used_count + 1)
        )
        
        # Если достигнуто максимальное количество использований, деактивируем пароль
        if password_obj.used_count + 1 >= password_obj.max_uses:
            await self.session.execute(
                update(Password)
                .where(Password.id == password_obj.id)
                .values(is_active=False)
            )
        
        await self.session.commit()
        return True
    
    async def delete_password(self, password_id: int) -> bool:
        """Удалить пароль"""
        result = await self.session.execute(
            delete(Password).where(Password.id == password_id)
        )
        await self.session.commit()
        return result.rowcount > 0
    
    async def get_all_active_passwords(self) -> List[Password]:
        """Получить все активные пароли"""
        result = await self.session.execute(
            select(Password).where(Password.is_active == True)
        )
        return result.scalars().all()

class LogRepository:
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def create_log(self, file_id: str, file_name: str, file_size: int = None) -> Log:
        """Создать новую запись лога"""
        log = Log(
            file_id=file_id,
            file_name=file_name,
            file_size=file_size
        )
        self.session.add(log)
        await self.session.commit()
        await self.session.refresh(log)
        return log
    
    async def get_log(self, log_id: int) -> Optional[Log]:
        """Получить лог по ID"""
        result = await self.session.execute(select(Log).where(Log.id == log_id))
        return result.scalars().first()
    
    async def get_logs_count(self) -> int:
        """Получить общее количество логов в базе данных"""
        result = await self.session.execute(select(func.count()).select_from(Log))
        return result.scalar() or 0
    
    async def get_available_logs_count(self) -> int:
        """Получить количество доступных логов"""
        result = await self.session.execute(
            select(func.count()).where(Log.is_taken == False)
        )
        return result.scalar()
    
    async def get_available_logs(self, limit: int) -> List[Log]:
        """Получить доступные логи с ограничением по количеству"""
        result = await self.session.execute(
            select(Log)
            .where(Log.is_taken == False)
            .order_by(Log.uploaded_at)
            .limit(limit)
        )
        return result.scalars().all()
    
    async def assign_logs_to_user(self, user_id: int, count: int) -> List[Log]:
        """Назначить логи пользователю"""
        # Получаем ID пользователя из базы данных
        user_result = await self.session.execute(
            select(User.id).where(User.user_id == user_id)
        )
        db_user_id = user_result.scalar()
        
        if not db_user_id:
            return []
        
        # Получаем доступные логи
        logs = await self.get_available_logs(count)
        
        if not logs:
            return []
        
        # Обновляем статус логов
        for log in logs:
            await self.session.execute(
                update(Log)
                .where(Log.id == log.id)
                .values(
                    is_taken=True,
                    user_id=db_user_id,
                    taken_at=datetime.utcnow()
                )
            )
        
        await self.session.commit()
        return logs
    
    async def get_user_logs(self, user_id: int) -> List[Log]:
        """Получить логи пользователя"""
        # Получаем ID пользователя из базы данных
        user_result = await self.session.execute(
            select(User.id).where(User.user_id == user_id)
        )
        db_user_id = user_result.scalar()
        
        if not db_user_id:
            return []
        
        result = await self.session.execute(
            select(Log).where(Log.user_id == db_user_id)
        )
        return result.scalars().all()
    
    async def clear_all_logs(self) -> int:
        """Удалить все логи из базы данных"""
        result = await self.session.execute(delete(Log))
        await self.session.commit()
        return result.rowcount 