"""FSM добавления записи: категория → название → описание → ссылка → фото → превью."""

from __future__ import annotations

from html import escape

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from db import repo
from db.models import User
from keyboards import inline
from keyboards.reply import BTN_ADD, main_menu
from services.notify import notify_new_item
from states import AddItem

router = Router()


def _build_preview(data: dict) -> str:
    lines = [
        f"<b>{escape(data['category_label'])}</b>",
        f"📌 {escape(data['title'])}",
    ]
    if data.get("description"):
        lines.append(f"📝 {escape(data['description'])}")
    if data.get("url"):
        lines.append(f"🔗 {escape(data['url'])}")
    return "\n".join(lines)


async def _send_preview(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    await state.set_state(AddItem.confirm)
    text = "👀 <b>Проверь запись</b>\n\n" + _build_preview(data) + "\n\nСохранить?"
    if data.get("photo_file_id"):
        await message.answer_photo(
            data["photo_file_id"], caption=text, reply_markup=inline.confirm_kb()
        )
    else:
        await message.answer(text, reply_markup=inline.confirm_kb())


# ---------- Шаг 1: старт и выбор категории ----------

@router.message(F.text == BTN_ADD)
async def add_start(
    message: Message, state: FSMContext, session: AsyncSession, pair_id: int | None
) -> None:
    if pair_id is None:
        await message.answer("Сначала создай список и пригласи партнёра — нажми /start 💛")
        return
    cats = await repo.list_categories(session, pair_id)
    await state.clear()
    await state.set_state(AddItem.category)
    await message.answer(
        "➕ <b>Новая хотелка</b>\n\nШаг 1/5 — выбери категорию:",
        reply_markup=inline.categories_kb(cats),
    )


@router.callback_query(AddItem.category, inline.CatPick.filter())
async def add_category(
    cb: CallbackQuery,
    callback_data: inline.CatPick,
    state: FSMContext,
    session: AsyncSession,
    pair_id: int,
) -> None:
    cat = await repo.get_category(session, callback_data.id, pair_id)
    if cat is None:
        await cb.answer("Категория не найдена", show_alert=True)
        return
    await state.update_data(
        category_id=cat.id, category_label=f"{cat.emoji} {cat.name}".strip()
    )
    await state.set_state(AddItem.title)
    await cb.message.edit_text(
        f"✅ Категория: {cat.emoji} {cat.name}\n\n"
        f"Шаг 2/5 — напиши <b>название</b>:"
    )
    await cb.answer()


# ---------- Шаг 2: название (обязательно) ----------

@router.message(AddItem.title, F.text)
async def add_title(message: Message, state: FSMContext) -> None:
    title = (message.text or "").strip()
    if not title:
        await message.answer("Название не может быть пустым. Попробуй ещё раз:")
        return
    await state.update_data(title=title)
    await state.set_state(AddItem.description)
    await message.answer(
        "Шаг 3/5 — добавь <b>описание</b> или пропусти:",
        reply_markup=inline.skip_kb("description"),
    )


@router.message(AddItem.title)
async def add_title_invalid(message: Message) -> None:
    await message.answer("Нужен текст. Введи название записи:")


# ---------- Шаг 3: описание (опционально) ----------

@router.message(AddItem.description, F.text)
async def add_description(message: Message, state: FSMContext) -> None:
    await state.update_data(description=(message.text or "").strip())
    await state.set_state(AddItem.url)
    await message.answer(
        "Шаг 4/5 — пришли <b>ссылку</b> или пропусти:",
        reply_markup=inline.skip_kb("url"),
    )


# ---------- Шаг 4: ссылка (опционально) ----------

@router.message(AddItem.url, F.text)
async def add_url(message: Message, state: FSMContext) -> None:
    await state.update_data(url=(message.text or "").strip())
    await state.set_state(AddItem.photo)
    await message.answer(
        "Шаг 5/5 — пришли <b>фото</b> или пропусти:",
        reply_markup=inline.skip_kb("photo"),
    )


# ---------- Шаг 5: фото (опционально) ----------

@router.message(AddItem.photo, F.photo)
async def add_photo(message: Message, state: FSMContext) -> None:
    await state.update_data(photo_file_id=message.photo[-1].file_id)
    await _send_preview(message, state)


# ---------- Пропуск опциональных шагов ----------

@router.callback_query(inline.Skip.filter())
async def add_skip(
    cb: CallbackQuery, callback_data: inline.Skip, state: FSMContext
) -> None:
    step = callback_data.step
    if step == "description":
        await state.update_data(description=None)
        await state.set_state(AddItem.url)
        await cb.message.edit_text(
            "Шаг 4/5 — пришли <b>ссылку</b> или пропусти:",
            reply_markup=inline.skip_kb("url"),
        )
    elif step == "url":
        await state.update_data(url=None)
        await state.set_state(AddItem.photo)
        await cb.message.edit_text(
            "Шаг 5/5 — пришли <b>фото</b> или пропусти:",
            reply_markup=inline.skip_kb("photo"),
        )
    elif step == "photo":
        await state.update_data(photo_file_id=None)
        await cb.message.delete()
        await _send_preview(cb.message, state)
    await cb.answer()


# ---------- Отмена потока ----------

@router.callback_query(inline.FlowCancel.filter())
async def add_flow_cancel(cb: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await cb.message.delete()
    await cb.message.answer("Отменено 👌", reply_markup=main_menu())
    await cb.answer()


# ---------- Шаг 6: подтверждение и сохранение ----------

@router.callback_query(AddItem.confirm, inline.Confirm.filter())
async def add_confirm(
    cb: CallbackQuery,
    callback_data: inline.Confirm,
    state: FSMContext,
    session: AsyncSession,
    pair_id: int,
    user: User,
    bot: Bot,
) -> None:
    if not callback_data.ok:
        await state.clear()
        await cb.message.answer("Отменено.", reply_markup=main_menu())
        await cb.answer()
        return

    data = await state.get_data()
    item = await repo.add_item(
        session,
        pair_id=pair_id,
        category_id=data["category_id"],
        author_id=user.telegram_id,
        title=data["title"],
        description=data.get("description"),
        url=data.get("url"),
        photo_file_id=data.get("photo_file_id"),
    )
    # Коммитим до уведомления, чтобы не уведомить о несохранённой записи.
    await session.commit()

    partner = await repo.partner_id(session, pair_id, user.telegram_id)
    if partner is not None:
        await notify_new_item(
            bot, partner, user.first_name, data["category_label"], item
        )

    await state.clear()
    await cb.message.answer("Добавлено ✅", reply_markup=main_menu())
    await cb.answer()
