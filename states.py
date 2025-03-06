from aiogram.fsm.state import State, StatesGroup

class AuthState(StatesGroup):
    """Состояния для авторизации"""
    waiting_for_password = State()

class AdminState(StatesGroup):
    """Состояния для админа"""
    waiting_for_password = State()
    waiting_for_max_uses = State()
    waiting_for_log_file = State()

class WorkerState(StatesGroup):
    """Состояния для работника"""
    waiting_for_empty_logs_count = State()
    waiting_for_logs_count = State() 