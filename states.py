"""FSM-состояния для пошаговых сценариев."""

from aiogram.fsm.state import State, StatesGroup


class AddItem(StatesGroup):
    category = State()
    title = State()
    description = State()
    url = State()
    photo = State()
    confirm = State()


class EditItem(StatesGroup):
    """Заполняется в Спринте 5."""
    field = State()
    value = State()


class NewCategory(StatesGroup):
    """Заполняется в Спринте 6."""
    name = State()
    emoji = State()
