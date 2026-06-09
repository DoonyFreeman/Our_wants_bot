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


# ---------- Просмотр (Спринт 4) ----------

class ViewCat(CallbackData, prefix="vcat"):
    """Открыть список записей категории. scope: 'my' | 'pt'."""
    scope: str
    cat_id: int


class ViewItem(CallbackData, prefix="vitem"):
    """Открыть карточку записи."""
    scope: str
    item_id: int


class ViewNav(CallbackData, prefix="vnav"):
    """Навигация «Назад». to: 'cats' | 'items'."""
    to: str
    scope: str
    cat_id: int


def _truncate(text: str, limit: int = 40) -> str:
    return text if len(text) <= limit else text[: limit - 1] + "…"


def categories_view_kb(
    scope: str, cats_with_counts: list[tuple[Category, int]]
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for cat, count in cats_with_counts:
        builder.button(
            text=f"{cat.emoji} {cat.name} ({count})".strip(),
            callback_data=ViewCat(scope=scope, cat_id=cat.id),
        )
    builder.adjust(1)
    return builder.as_markup()


def items_view_kb(scope: str, cat_id: int, items) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for item in items:
        builder.button(
            text=_truncate(item.title),
            callback_data=ViewItem(scope=scope, item_id=item.id),
        )
    builder.button(
        text="⬅️ К категориям",
        callback_data=ViewNav(to="cats", scope=scope, cat_id=0),
    )
    builder.adjust(1)
    return builder.as_markup()


def card_kb(scope: str, cat_id: int) -> InlineKeyboardMarkup:
    """Карточка записи. Кнопки правки/удаления добавятся в Спринте 5."""
    builder = InlineKeyboardBuilder()
    builder.button(
        text="⬅️ Назад",
        callback_data=ViewNav(to="items", scope=scope, cat_id=cat_id),
    )
    return builder.as_markup()
