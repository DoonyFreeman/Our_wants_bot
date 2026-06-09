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


def card_kb(
    scope: str, cat_id: int, item_id: int, is_owner: bool
) -> InlineKeyboardMarkup:
    """Карточка записи. Для владельца — действия, для чужой — только «Назад»."""
    builder = InlineKeyboardBuilder()
    if is_owner:
        builder.button(text="✏️ Редактировать", callback_data=CardEdit(item_id=item_id))
        builder.button(text="✅ Выполнено", callback_data=CardDone(item_id=item_id))
        builder.button(text="🗑 Удалить", callback_data=CardDelete(item_id=item_id))
    builder.button(
        text="⬅️ Назад",
        callback_data=ViewNav(to="items", scope=scope, cat_id=cat_id),
    )
    builder.adjust(2, 1, 1)
    return builder.as_markup()


# ---------- Правка / удаление / статус (Спринт 5) ----------

class CardEdit(CallbackData, prefix="cedit"):
    item_id: int


class CardDelete(CallbackData, prefix="cdel"):
    item_id: int


class CardDone(CallbackData, prefix="cdone"):
    item_id: int


class EditField(CallbackData, prefix="efield"):
    item_id: int
    field: str


class EditClear(CallbackData, prefix="eclear"):
    item_id: int
    field: str


class EditCancel(CallbackData, prefix="ecancel"):
    item_id: int


class EditCatPick(CallbackData, prefix="ecatpick"):
    item_id: int
    cat_id: int


class DelConfirm(CallbackData, prefix="delc"):
    item_id: int
    ok: bool


_EDIT_FIELDS = [
    ("Название", "title"),
    ("Описание", "description"),
    ("Ссылка", "url"),
    ("Фото", "photo"),
    ("Категория", "category"),
]


def edit_fields_kb(item_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for label, field in _EDIT_FIELDS:
        builder.button(text=label, callback_data=EditField(item_id=item_id, field=field))
    builder.button(text="⬅️ Назад", callback_data=EditCancel(item_id=item_id))
    builder.adjust(2, 2, 1, 1)
    return builder.as_markup()


def edit_value_kb(item_id: int, field: str, optional: bool) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if optional:
        builder.button(
            text="🚫 Очистить", callback_data=EditClear(item_id=item_id, field=field)
        )
    builder.button(text="❌ Отмена", callback_data=EditCancel(item_id=item_id))
    builder.adjust(1)
    return builder.as_markup()


def edit_categories_kb(item_id: int, categories: Iterable[Category]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for cat in categories:
        builder.button(
            text=f"{cat.emoji} {cat.name}".strip(),
            callback_data=EditCatPick(item_id=item_id, cat_id=cat.id),
        )
    builder.button(text="❌ Отмена", callback_data=EditCancel(item_id=item_id))
    builder.adjust(1)
    return builder.as_markup()


def delete_confirm_kb(item_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🗑 Да, удалить", callback_data=DelConfirm(item_id=item_id, ok=True))
    builder.button(text="↩️ Нет", callback_data=DelConfirm(item_id=item_id, ok=False))
    builder.adjust(2)
    return builder.as_markup()


# ---------- Пользовательские категории (Спринт 6) ----------

class NewCatStart(CallbackData, prefix="newcat"):
    pass


class CatEmojiSkip(CallbackData, prefix="cemojiskip"):
    pass


def new_category_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="➕ Новая категория", callback_data=NewCatStart())
    return builder.as_markup()


def category_emoji_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Пропустить ⏭", callback_data=CatEmojiSkip())
    return builder.as_markup()
