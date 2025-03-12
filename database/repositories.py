from datetime import datetime, date
from typing import List, Optional, Tuple
from sqlalchemy import select, update, delete, func, and_, text
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import User, Password, Log, Session, UsedPhoneNumber

class UserRepository:
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def get_by_user_id(self, user_id: int) -> Optional[User]:
        """Получить пользователя по его Telegram ID"""
        import logging
        logger = logging.getLogger(__name__)
        
        logger.info(f"Запрос пользователя с ID {user_id}")
        
        result = await self.session.execute(select(User).where(User.user_id == user_id))
        user = result.scalars().first()
        
        if user:
            logger.info(f"Найден пользователь: ID={user.id}, user_id={user.user_id}, taken_logs_count={user.taken_logs_count}, empty_logs_count={user.empty_logs_count}")
        else:
            logger.info(f"Пользователь с ID {user_id} не найден")
        
        return user
    
    async def create_user(self, user_id: int, username: str = None, first_name: str = None, last_name: str = None, is_admin: bool = False) -> User:
        """Создать нового пользователя"""
        # Проверяем, является ли пользователь администратором
        from config import settings
        is_admin = is_admin or (user_id in settings.ADMIN_IDS)
        
        # Устанавливаем is_active в True только для админов, для остальных - False
        is_active = is_admin
        
        user = User(
            user_id=user_id,
            username=username,
            first_name=first_name,
            last_name=last_name,
            is_admin=is_admin,
            is_active=is_active,
            taken_logs_count=0,
            empty_logs_count=0,
            daily_empty_logs_count=0
        )
        self.session.add(user)
        await self.session.commit()
        await self.session.refresh(user)
        return user
    
    async def get_or_create_user(self, user_id: int, username: str = None, first_name: str = None, last_name: str = None) -> Tuple[User, bool]:
        """Получить пользователя или создать нового, если он не существует"""
        user = await self.get_by_user_id(user_id)
        
        if user:
            # Обновляем информацию о пользователе
            update_data = {}
            if username is not None and username != user.username:
                update_data["username"] = username
            if first_name is not None and first_name != user.first_name:
                update_data["first_name"] = first_name
            if last_name is not None and last_name != user.last_name:
                update_data["last_name"] = last_name
            
            if update_data:
                await self.update_user(user_id, **update_data)
                user = await self.get_by_user_id(user_id)
            
            return user, False
        else:
            # Создаем нового пользователя
            user = await self.create_user(
                user_id=user_id,
                username=username,
                first_name=first_name,
                last_name=last_name
            )
            return user, True
    
    async def update_user(self, user_id: int, **kwargs) -> Optional[User]:
        """Обновить пользователя"""
        # Выводим отладочную информацию
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"Обновление пользователя {user_id} с параметрами: {kwargs}")
        
        # Проверяем, что счетчики не None
        if 'taken_logs_count' in kwargs and kwargs['taken_logs_count'] is None:
            kwargs['taken_logs_count'] = 0
            logger.info(f"Установлен taken_logs_count=0 для пользователя {user_id}")
        if 'empty_logs_count' in kwargs and kwargs['empty_logs_count'] is None:
            kwargs['empty_logs_count'] = 0
            logger.info(f"Установлен empty_logs_count=0 для пользователя {user_id}")
        
        # Получаем пользователя до обновления
        user_before = await self.get_by_user_id(user_id)
        if user_before:
            logger.info(f"Пользователь до обновления: {user_before.taken_logs_count}, {user_before.empty_logs_count}")
        
        # Обновляем пользователя
        await self.session.execute(
            update(User)
            .where(User.user_id == user_id)
            .values(**kwargs)
        )
        await self.session.commit()
        
        # Получаем обновленного пользователя
        updated_user = await self.get_by_user_id(user_id)
        logger.info(f"Пользователь после обновления: {updated_user.taken_logs_count}, {updated_user.empty_logs_count}")
        
        # Возвращаем обновленного пользователя
        return updated_user
    
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
    
    async def increment_taken_logs(self, user_id: int, count: int = 1) -> User:
        """Увеличить счетчик взятых логов"""
        # Получаем текущее значение счетчика
        user = await self.get_by_user_id(user_id)
        if user is None:
            # Если пользователь не найден, создаем его
            user = await self.create_user(user_id=user_id, taken_logs_count=count)
            return user
        
        # Проверяем, что счетчик не None
        current_count = user.taken_logs_count or 0
        new_count = current_count + count
        
        # Выводим отладочную информацию
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"increment_taken_logs: user_id={user_id}, current_count={current_count}, new_count={new_count}")
        
        # Обновляем счетчик
        await self.session.execute(
            update(User)
            .where(User.user_id == user_id)
            .values(taken_logs_count=new_count)
        )
        await self.session.commit()
        
        # Возвращаем обновленного пользователя
        return await self.get_by_user_id(user_id)
    
    async def increment_empty_logs(self, user_id: int, count: int = 1) -> User:
        """Увеличить счетчик пустых логов"""
        # Получаем пользователя
        user = await self.get_by_user_id(user_id)
        if user is None:
            # Если пользователь не найден, создаем его
            user = await self.create_user(user_id=user_id, empty_logs_count=count)
            return user
        
        # Проверяем, что счетчик не None
        current_count = user.empty_logs_count or 0
        new_empty_count = current_count + count
        
        # Выводим отладочную информацию
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"increment_empty_logs: user_id={user_id}, current_count={current_count}, new_count={new_empty_count}")
        
        # Проверяем, нужно ли сбросить счетчик ежедневных пустых логов
        today = date.today()
        if user.last_empty_log_date is None or user.last_empty_log_date.date() < today:
            daily_empty_logs_count = count
        else:
            daily_empty_logs_count = user.daily_empty_logs_count + count
        
        # Обновляем счетчики
        await self.session.execute(
            update(User)
            .where(User.user_id == user_id)
            .values(
                empty_logs_count=new_empty_count,
                daily_empty_logs_count=daily_empty_logs_count,
                last_empty_log_date=datetime.utcnow()
            )
        )
        await self.session.commit()
        
        # Возвращаем обновленного пользователя
        return await self.get_by_user_id(user_id)
    
    async def update_statistics(self, user_id: int, taken_logs_to_add: int = 0, empty_logs_to_add: int = 0) -> User:
        """Обновить статистику пользователя"""
        import logging
        logger = logging.getLogger(__name__)
        
        # Получаем пользователя
        user = await self.get_by_user_id(user_id)
        if not user:
            # Если пользователь не найден, создаем его
            logger.info(f"Пользователь {user_id} не найден, создаем нового")
            user = await self.create_user(
                user_id=user_id,
                taken_logs_count=taken_logs_to_add,
                empty_logs_count=empty_logs_to_add
            )
            return user
        
        # Текущие значения счетчиков (с проверкой на None)
        current_taken = user.taken_logs_count if user.taken_logs_count is not None else 0
        current_empty = user.empty_logs_count if user.empty_logs_count is not None else 0
        
        # Новые значения счетчиков
        new_taken = current_taken + taken_logs_to_add
        new_empty = current_empty + empty_logs_to_add
        
        logger.info(f"Обновление статистики для пользователя {user_id}:")
        logger.info(f"  Текущие значения: taken={current_taken}, empty={current_empty}")
        logger.info(f"  Добавляем: taken={taken_logs_to_add}, empty={empty_logs_to_add}")
        logger.info(f"  Новые значения: taken={new_taken}, empty={new_empty}")
        
        # Обновляем счетчики
        await self.session.execute(
            update(User)
            .where(User.user_id == user_id)
            .values(
                taken_logs_count=new_taken,
                empty_logs_count=new_empty,
                updated_at=datetime.utcnow()
            )
        )
        await self.session.commit()
        
        # Получаем обновленного пользователя
        updated_user = await self.get_by_user_id(user_id)
        logger.info(f"Пользователь после обновления: taken={updated_user.taken_logs_count}, empty={updated_user.empty_logs_count}")
        
        return updated_user
    
    async def get_user_statistics(self, user_id: int) -> dict:
        """Получить статистику пользователя"""
        import logging
        logger = logging.getLogger(__name__)
        
        # Получаем пользователя
        user = await self.get_by_user_id(user_id)
        if not user:
            # Если пользователь не найден, создаем его
            logger.info(f"Пользователь {user_id} не найден, создаем нового")
            user = await self.create_user(user_id=user_id)
        
        # Значения счетчиков (с проверкой на None)
        taken_logs = user.taken_logs_count if user.taken_logs_count is not None else 0
        empty_logs = user.empty_logs_count if user.empty_logs_count is not None else 0
        
        logger.info(f"Статистика пользователя {user_id}: taken={taken_logs}, empty={empty_logs}")
        
        return {
            "taken_logs_count": taken_logs,
            "empty_logs_count": empty_logs
        }

    async def force_update_statistics(self, user_id: int) -> User:
        """Принудительно обновить статистику пользователя из базы данных"""
        import logging
        logger = logging.getLogger(__name__)
        
        # Получаем пользователя
        user = await self.get_by_user_id(user_id)
        if not user:
            # Если пользователь не найден, создаем его
            logger.info(f"Пользователь {user_id} не найден, создаем нового")
            user = await self.create_user(user_id=user_id)
            return user
        
        # Выполняем запрос к базе данных для получения актуальных данных
        result = await self.session.execute(
            select(User).where(User.user_id == user_id)
        )
        updated_user = result.scalars().first()
        
        if updated_user:
            logger.info(f"Принудительное обновление статистики для пользователя {user_id}:")
            logger.info(f"  Текущие значения: taken={updated_user.taken_logs_count}, empty={updated_user.empty_logs_count}")
        else:
            logger.error(f"Не удалось получить пользователя {user_id} после принудительного обновления")
        
        return updated_user

    async def get_actual_statistics(self, user_id: int) -> dict:
        """Получить актуальную статистику пользователя из базы данных"""
        import logging
        logger = logging.getLogger(__name__)
        
        # Выполняем прямой запрос к базе данных для получения актуальных данных
        query = select(User).where(User.user_id == user_id)
        result = await self.session.execute(query)
        user = result.scalars().first()
        
        if not user:
            logger.warning(f"Пользователь {user_id} не найден в базе данных при запросе статистики")
            return {"taken_logs_count": 0, "empty_logs_count": 0}
        
        # Получаем актуальные значения счетчиков
        taken_logs = user.taken_logs_count if user.taken_logs_count is not None else 0
        empty_logs = user.empty_logs_count if user.empty_logs_count is not None else 0
        
        logger.info(f"Актуальная статистика пользователя {user_id} из базы данных: taken={taken_logs}, empty={empty_logs}")
        
        return {
            "taken_logs_count": taken_logs,
            "empty_logs_count": empty_logs
        }

    async def get_fresh_statistics(self, user_id: int) -> dict:
        """Получить свежую статистику пользователя из базы данных с принудительным запросом"""
        import logging
        logger = logging.getLogger(__name__)
        
        # Очищаем кэш сессии
        await self.session.flush()
        
        # Выполняем прямой запрос к базе данных для получения актуальных данных
        query = """
        SELECT taken_logs_count, empty_logs_count 
        FROM users 
        WHERE user_id = :user_id
        """
        result = await self.session.execute(text(query), {"user_id": user_id})
        row = result.fetchone()
        
        if not row:
            logger.warning(f"Пользователь {user_id} не найден в базе данных при запросе свежей статистики")
            return {"taken_logs_count": 0, "empty_logs_count": 0}
        
        # Получаем актуальные значения счетчиков
        taken_logs = row[0] if row[0] is not None else 0
        empty_logs = row[1] if row[1] is not None else 0
        
        logger.info(f"Свежая статистика пользователя {user_id} из базы данных: taken={taken_logs}, empty={empty_logs}")
        
        return {
            "taken_logs_count": taken_logs,
            "empty_logs_count": empty_logs
        }

class PasswordRepository:
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def create_password(self, password: str, max_uses: int, created_by: int = None) -> Password:
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
        """Использовать пароль (увеличить счетчик использований)"""
        # Получаем пароль из базы данных
        password_obj = await self.get_by_password(password)
        
        # Если пароль не найден или не активен, возвращаем False
        if not password_obj or not password_obj.is_active:
            return False
        
        # Если пароль уже использован максимальное количество раз, возвращаем False
        if password_obj.used_count >= password_obj.max_uses:
            return False
        
        # Увеличиваем счетчик использований
        await self.session.execute(
            update(Password)
            .where(Password.id == password_obj.id)
            .values(used_count=Password.used_count + 1)
        )
        
        # Если после увеличения счетчик достиг максимума, деактивируем пароль
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
    
    async def get_password(self, password_id: int) -> Optional[Password]:
        """Получить пароль по ID"""
        result = await self.session.execute(select(Password).where(Password.id == password_id))
        return result.scalars().first()

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

class SessionRepository:
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def create_session(self, phone_number: str) -> Session:
        """Создать новую запись сессии"""
        session = Session(
            phone_number=phone_number
        )
        self.session.add(session)
        await self.session.commit()
        await self.session.refresh(session)
        return session
    
    async def get_session(self, session_id: int) -> Optional[Session]:
        """Получить сессию по ID"""
        result = await self.session.execute(select(Session).where(Session.id == session_id))
        return result.scalars().first()
    
    async def get_session_by_phone(self, phone_number: str) -> Optional[Session]:
        """Получить сессию по номеру телефона"""
        result = await self.session.execute(select(Session).where(Session.phone_number == phone_number))
        return result.scalars().first()
    
    async def get_available_sessions_count(self) -> int:
        """Получить количество доступных сессий"""
        result = await self.session.execute(
            select(func.count()).where(Session.is_taken == False)
        )
        return result.scalar() or 0
    
    async def get_available_sessions(self, limit: int) -> List[Session]:
        """Получить доступные сессии с ограничением по количеству"""
        result = await self.session.execute(
            select(Session)
            .where(Session.is_taken == False)
            .order_by(Session.created_at)
            .limit(limit)
        )
        return result.scalars().all()
    
    async def assign_sessions_to_user(self, user_id: int, count: int) -> List[Session]:
        """Назначить сессии пользователю"""
        # Получаем ID пользователя из базы данных
        user_result = await self.session.execute(
            select(User.id).where(User.user_id == user_id)
        )
        db_user_id = user_result.scalar()
        
        if not db_user_id:
            return []
        
        # Получаем доступные сессии
        sessions = await self.get_available_sessions(count)
        
        if not sessions:
            return []
        
        # Обновляем статус сессий
        for session in sessions:
            await self.session.execute(
                update(Session)
                .where(Session.id == session.id)
                .values(
                    is_taken=True,
                    user_id=db_user_id,
                    taken_at=datetime.utcnow()
                )
            )
        
        await self.session.commit()
        return sessions
    
    async def get_user_sessions(self, user_id: int) -> List[Session]:
        """Получить сессии пользователя"""
        # Получаем ID пользователя из базы данных
        user_result = await self.session.execute(
            select(User.id).where(User.user_id == user_id)
        )
        db_user_id = user_result.scalar()
        
        if not db_user_id:
            return []
        
        result = await self.session.execute(
            select(Session).where(Session.user_id == db_user_id)
        )
        return result.scalars().all()
    
    async def delete_session(self, session_id: int) -> bool:
        """Удалить сессию по ID"""
        result = await self.session.execute(
            delete(Session).where(Session.id == session_id)
        )
        await self.session.commit()
        return result.rowcount > 0
    
    async def clear_all_sessions(self) -> int:
        """Удалить все сессии из базы данных"""
        result = await self.session.execute(delete(Session))
        await self.session.commit()
        return result.rowcount

class UsedPhoneNumberRepository:
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def add_used_phone_number(self, phone_number: str) -> UsedPhoneNumber:
        """Добавить использованный номер телефона"""
        # Проверяем, существует ли уже такой номер
        existing = await self.get_by_phone_number(phone_number)
        if existing:
            return existing
        
        # Создаем новую запись
        used_phone = UsedPhoneNumber(
            phone_number=phone_number
        )
        self.session.add(used_phone)
        await self.session.commit()
        await self.session.refresh(used_phone)
        return used_phone
    
    async def get_by_phone_number(self, phone_number: str) -> Optional[UsedPhoneNumber]:
        """Получить запись по номеру телефона"""
        result = await self.session.execute(
            select(UsedPhoneNumber).where(UsedPhoneNumber.phone_number == phone_number)
        )
        return result.scalars().first()
    
    async def is_phone_number_used(self, phone_number: str) -> bool:
        """Проверить, использовался ли номер телефона ранее"""
        result = await self.get_by_phone_number(phone_number)
        return result is not None
    
    async def get_all_used_phone_numbers(self) -> List[str]:
        """Получить все использованные номера телефонов"""
        result = await self.session.execute(
            select(UsedPhoneNumber.phone_number)
        )
        return result.scalars().all() 