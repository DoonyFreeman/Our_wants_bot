"""Главное reply-меню."""

from aiogram.types import ReplyKeyboardMarkup
from aiogram.utils.keyboard import ReplyKeyboardBuilder

BTN_ADD = "➕ Добавить"
BTN_MY = "📋 Мой список"
BTN_PARTNER = "💙 Список партнёра"
BTN_CATEGORIES = "⚙️ Категории"


def main_menu() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.button(text=BTN_ADD)
    builder.button(text=BTN_MY)
    builder.button(text=BTN_PARTNER)
    builder.button(text=BTN_CATEGORIES)
    builder.adjust(1, 2, 1)
    return builder.as_markup(resize_keyboard=True)
