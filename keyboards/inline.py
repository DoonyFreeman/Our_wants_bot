"""Inline-клавиатуры и CallbackData-фабрики."""

from __future__ import annotations

from collections.abc import Iterable

from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from db.models import Category


class CatPick(CallbackData, prefix="catpick"):
    """Выбор категории при добавлении записи."""
    id: int


class Skip(CallbackData, prefix="skip"):
    """Пропуск опционального шага FSM (description/url/photo)."""
    step: str


class Confirm(CallbackData, prefix="confirm"):
    """Подтверждение/отмена сохранения записи."""
    ok: bool


def categories_kb(categories: Iterable[Category]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for cat in categories:
        builder.button(
            text=f"{cat.emoji} {cat.name}".strip(),
            callback_data=CatPick(id=cat.id),
        )
    builder.adjust(1)
    return builder.as_markup()


def skip_kb(step: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Пропустить ⏭", callback_data=Skip(step=step))
    return builder.as_markup()


def confirm_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Сохранить", callback_data=Confirm(ok=True))
    builder.button(text="❌ Отмена", callback_data=Confirm(ok=False))
    builder.adjust(2)
    return builder.as_markup()
