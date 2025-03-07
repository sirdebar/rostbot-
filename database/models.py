from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text, BigInteger
from sqlalchemy.orm import relationship

from database.base import Base

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(BigInteger, unique=True, nullable=False)
    username = Column(String(255), nullable=True)
    first_name = Column(String(255), nullable=True)
    last_name = Column(String(255), nullable=True)
    is_admin = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Статистика пользователя
    taken_logs_count = Column(Integer, default=0)
    empty_logs_count = Column(Integer, default=0)
    daily_empty_logs_count = Column(Integer, default=0)
    last_empty_log_date = Column(DateTime, nullable=True)
    
    # Отношения
    logs = relationship("Log", back_populates="user")
    
    def __repr__(self):
        return f"<User(id={self.id}, user_id={self.user_id}, username={self.username})>"

class Password(Base):
    __tablename__ = "passwords"
    
    id = Column(Integer, primary_key=True)
    password = Column(String(255), nullable=False)
    max_uses = Column(Integer, default=1)
    used_count = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    created_by = Column(BigInteger, nullable=True)  # ID администратора, создавшего пароль
    
    def __repr__(self):
        return f"<Password(id={self.id}, password={self.password}, used_count={self.used_count}/{self.max_uses})>"

class Log(Base):
    __tablename__ = "logs"
    
    id = Column(Integer, primary_key=True)
    file_id = Column(String(255), nullable=False)  # ID файла в Telegram
    file_name = Column(String(255), nullable=False)
    file_size = Column(Integer, nullable=True)
    is_taken = Column(Boolean, default=False)
    uploaded_at = Column(DateTime, default=datetime.utcnow)
    taken_at = Column(DateTime, nullable=True)
    
    # Отношения
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    user = relationship("User", back_populates="logs")
    
    def __repr__(self):
        return f"<Log(id={self.id}, file_name={self.file_name}, is_taken={self.is_taken})>"

class Session(Base):
    __tablename__ = "sessions"
    
    id = Column(Integer, primary_key=True)
    phone_number = Column(String(255), nullable=False, unique=True)  # Номер телефона из названия папки
    is_taken = Column(Boolean, default=False)  # Взята ли сессия
    created_at = Column(DateTime, default=datetime.utcnow)
    taken_at = Column(DateTime, nullable=True)
    
    # Отношения
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    user = relationship("User")
    
    def __repr__(self):
        return f"<Session(id={self.id}, phone_number={self.phone_number}, is_taken={self.is_taken})>"

class UsedPhoneNumber(Base):
    __tablename__ = "used_phone_numbers"
    
    id = Column(Integer, primary_key=True)
    phone_number = Column(String(255), nullable=False, unique=True)  # Номер телефона из названия папки
    created_at = Column(DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f"<UsedPhoneNumber(id={self.id}, phone_number={self.phone_number})>" 