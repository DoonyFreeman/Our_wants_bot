"""Пользовательские категории: просмотр списка и создание новых.

Базовый набор — встроенные категории (общие). Каждый из пары может создать
свою категорию; она видна обоим (в добавлении и просмотре).
"""

from __future__ import annotations

from html import escape

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from db import repo
from db.models import User
from keyboards import inline
from keyboards.reply import BTN_CATEGORIES, main_menu
from states import NewCategory

router = Router()


async def _categories_text(session: AsyncSession, pair_id: int) -> str:
    cats = await repo.list_categories(session, pair_id)
    lines = ["📂 <b>Категории</b>:"]
    for cat in cats:
        mark = " (своя)" if cat.pair_id is not None else ""
        lines.append(f"{cat.emoji} {escape(cat.name)}{mark}".strip())
    return "\n".join(lines)


@router.message(F.text == BTN_CATEGORIES)
async def categories_menu(
    message: Message, session: AsyncSession, pair_id: int | None
) -> None:
    if pair_id is None:
        await message.answer("Пара ещё не настроена 🙈")
        return
    text = await _categories_text(session, pair_id)
    await message.answer(text, reply_markup=inline.new_category_kb())


@router.callback_query(inline.NewCatStart.filter())
async def new_category_start(cb: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(NewCategory.name)
    await cb.message.answer("Название новой категории:")
    await cb.answer()


@router.message(NewCategory.name, F.text)
async def new_category_name(message: Message, state: FSMContext) -> None:
    name = (message.text or "").strip()
    if not name:
        await message.answer("Название не может быть пустым. Введи ещё раз:")
        return
    await state.update_data(name=name[:64])
    await state.set_state(NewCategory.emoji)
    await message.answer(
        "Пришли эмодзи для категории или пропусти:",
        reply_markup=inline.category_emoji_kb(),
    )


async def _create_category(
    message: Message, state: FSMContext, session: AsyncSession,
    pair_id: int, user: User, emoji: str,
) -> None:
    data = await state.get_data()
    await repo.add_category(
        session, pair_id=pair_id, name=data["name"], emoji=emoji,
        created_by=user.telegram_id,
    )
    await session.commit()
    await state.clear()
    text = await _categories_text(session, pair_id)
    await message.answer(
        f"Категория «{escape(data['name'])}» создана ✅", reply_markup=main_menu()
    )
    await message.answer(text, reply_markup=inline.new_category_kb())


@router.message(NewCategory.emoji, F.text)
async def new_category_emoji(
    message: Message, state: FSMContext, session: AsyncSession,
    pair_id: int, user: User,
) -> None:
    emoji = (message.text or "").strip()[:8]
    await _create_category(message, state, session, pair_id, user, emoji)


@router.callback_query(NewCategory.emoji, inline.CatEmojiSkip.filter())
async def new_category_emoji_skip(
    cb: CallbackQuery, state: FSMContext, session: AsyncSession,
    pair_id: int, user: User,
) -> None:
    await _create_category(cb.message, state, session, pair_id, user, "📁")
    await cb.answer()
