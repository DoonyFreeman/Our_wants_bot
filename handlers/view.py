"""Просмотр: «Мой список» / «Список партнёра» → категории → записи → карточка.

scope:
  'my' — записи текущего пользователя,
  'pt' — записи партнёра по паре.
"""

from __future__ import annotations

from html import escape

from aiogram import F, Router
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from db import repo
from db.models import User
from keyboards import inline
from keyboards.reply import BTN_MY, BTN_PARTNER

router = Router()


async def _scope_author(
    session: AsyncSession, scope: str, pair_id: int, me: int
) -> int | None:
    """ID автора, чьи записи смотрим (свои или партнёра)."""
    if scope == "my":
        return me
    return await repo.partner_id(session, pair_id, me)


async def _categories_payload(
    session: AsyncSession, scope: str, pair_id: int, author_id: int
) -> tuple[str, object | None]:
    counts = await repo.count_items_per_category(session, pair_id, author_id=author_id)
    if not counts:
        title = "твоём" if scope == "my" else "партнёра"
        return f"В списке {title} пока пусто 🤍", None

    cats = await repo.list_categories(session, pair_id)
    with_counts = [(c, counts[c.id]) for c in cats if counts.get(c.id)]
    header = "📋 Твой список" if scope == "my" else "💙 Список партнёра"
    return f"{header}. Выбери категорию:", inline.categories_view_kb(scope, with_counts)


async def _items_payload(
    session: AsyncSession, scope: str, pair_id: int, cat_id: int, author_id: int
) -> tuple[str, object]:
    items = await repo.get_items_by_category(
        session, pair_id, cat_id, author_id=author_id
    )
    cat = await repo.get_category(session, cat_id, pair_id)
    label = f"{cat.emoji} {cat.name}".strip() if cat else "Категория"
    if not items:
        return f"{label}: пусто", inline.items_view_kb(scope, cat_id, [])
    return f"{label} — {len(items)} шт.:", inline.items_view_kb(scope, cat_id, items)


async def _card_payload(
    session: AsyncSession, item, author_name: str
) -> str:
    lines = [f"📌 <b>{escape(item.title)}</b>"]
    if item.description:
        lines.append(f"\n📝 {escape(item.description)}")
    if item.url:
        lines.append(f"🔗 {escape(item.url)}")
    lines.append(f"\n👤 {escape(author_name)}")
    lines.append(f"🕒 {item.created_at:%d.%m.%Y}")
    return "\n".join(lines)


async def send_card(
    message: Message,
    session: AsyncSession,
    item,
    viewer_id: int,
    scope: str,
) -> None:
    """Отправляет карточку записи новым сообщением (фото или текст).

    Кнопки действий показываются только владельцу (own-only).
    """
    author = await session.get(User, item.author_id)
    author_name = (author.first_name if author else "") or "—"
    text = await _card_payload(session, item, author_name)
    is_owner = item.author_id == viewer_id
    kb = inline.card_kb(scope, item.category_id, item.id, is_owner)
    if item.photo_file_id:
        await message.answer_photo(item.photo_file_id, caption=text, reply_markup=kb)
    else:
        await message.answer(text, reply_markup=kb)


# ---------- Точки входа из reply-меню ----------

async def _open_list(
    message: Message, session: AsyncSession, pair_id: int | None, me: int, scope: str
) -> None:
    if pair_id is None:
        await message.answer("Пара ещё не настроена 🙈")
        return
    author_id = await _scope_author(session, scope, pair_id, me)
    if author_id is None:
        await message.answer("Партнёр ещё не присоединился 🤍")
        return
    text, kb = await _categories_payload(session, scope, pair_id, author_id)
    await message.answer(text, reply_markup=kb)


@router.message(F.text == BTN_MY)
async def open_my(
    message: Message, session: AsyncSession, pair_id: int | None, user: User
) -> None:
    await _open_list(message, session, pair_id, user.telegram_id, "my")


@router.message(F.text == BTN_PARTNER)
async def open_partner(
    message: Message, session: AsyncSession, pair_id: int | None, user: User
) -> None:
    await _open_list(message, session, pair_id, user.telegram_id, "pt")


# ---------- Навигация по callback ----------

@router.callback_query(inline.ViewCat.filter())
async def open_category(
    cb: CallbackQuery,
    callback_data: inline.ViewCat,
    session: AsyncSession,
    pair_id: int,
    user: User,
) -> None:
    author_id = await _scope_author(session, callback_data.scope, pair_id, user.telegram_id)
    if author_id is None:
        await cb.answer("Партнёр ещё не присоединился", show_alert=True)
        return
    text, kb = await _items_payload(
        session, callback_data.scope, pair_id, callback_data.cat_id, author_id
    )
    await cb.message.edit_text(text, reply_markup=kb)
    await cb.answer()


@router.callback_query(inline.ViewItem.filter())
async def open_card(
    cb: CallbackQuery,
    callback_data: inline.ViewItem,
    session: AsyncSession,
    pair_id: int,
    user: User,
) -> None:
    item = await repo.get_item(session, callback_data.item_id, pair_id)
    if item is None:
        await cb.answer("Запись не найдена", show_alert=True)
        return
    # Карточка с фото не редактируется из текстового сообщения — пересоздаём.
    await cb.message.delete()
    await send_card(cb.message, session, item, user.telegram_id, callback_data.scope)
    await cb.answer()


@router.callback_query(inline.ViewNav.filter())
async def navigate_back(
    cb: CallbackQuery,
    callback_data: inline.ViewNav,
    session: AsyncSession,
    pair_id: int,
    user: User,
) -> None:
    scope = callback_data.scope
    author_id = await _scope_author(session, scope, pair_id, user.telegram_id)
    if author_id is None:
        await cb.answer()
        return

    if callback_data.to == "cats":
        text, kb = await _categories_payload(session, scope, pair_id, author_id)
        await cb.message.edit_text(text, reply_markup=kb)
    else:  # to == "items"
        text, kb = await _items_payload(
            session, scope, pair_id, callback_data.cat_id, author_id
        )
        # Назад из карточки: предыдущее сообщение могло быть фото — пересоздаём.
        await cb.message.delete()
        await cb.message.answer(text, reply_markup=kb)
    await cb.answer()
