"""Правка, удаление и смена статуса записей (own-only).

Все действия доступны только автору записи — проверяется и в хендлере
(`item.author_id == user.telegram_id`), и в repo (own-only в update/delete).
"""

from __future__ import annotations

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from db import repo
from db.models import ItemStatus, User
from handlers import view
from keyboards import inline
from keyboards.reply import main_menu
from services.notify import notify_status_change
from states import EditItem

router = Router()

OPTIONAL_FIELDS = {"description", "url", "photo"}
PROMPTS = {
    "title": "новое название",
    "description": "новое описание",
    "url": "новую ссылку",
    "photo": "новое фото",
}


async def _owned_item(session: AsyncSession, item_id: int, pair_id: int, user: User):
    """Запись пары, если она принадлежит пользователю; иначе None."""
    item = await repo.get_item(session, item_id, pair_id)
    if item is None or item.author_id != user.telegram_id:
        return None
    return item


async def _back_to_items(message: Message, session: AsyncSession, pair_id: int,
                         user: User, cat_id: int) -> None:
    text, kb = await view._items_payload(session, "my", pair_id, cat_id, user.telegram_id)
    await message.answer(text, reply_markup=kb)


# ---------- Меню правки ----------

@router.callback_query(inline.CardEdit.filter())
async def edit_menu(cb: CallbackQuery, callback_data: inline.CardEdit,
                    session: AsyncSession, pair_id: int, user: User) -> None:
    item = await _owned_item(session, callback_data.item_id, pair_id, user)
    if item is None:
        await cb.answer("Можно редактировать только свои записи", show_alert=True)
        return
    await cb.message.delete()
    await cb.message.answer("Что изменить?", reply_markup=inline.edit_fields_kb(item.id))
    await cb.answer()


@router.callback_query(inline.EditCancel.filter())
async def edit_cancel(cb: CallbackQuery, callback_data: inline.EditCancel,
                      state: FSMContext, session: AsyncSession, pair_id: int,
                      user: User) -> None:
    await state.clear()
    item = await repo.get_item(session, callback_data.item_id, pair_id)
    await cb.message.delete()
    if item is not None:
        await view.send_card(cb.message, session, item, user.telegram_id, "my")
    await cb.answer()


@router.callback_query(inline.EditField.filter())
async def edit_field(cb: CallbackQuery, callback_data: inline.EditField,
                     state: FSMContext, session: AsyncSession, pair_id: int,
                     user: User) -> None:
    item = await _owned_item(session, callback_data.item_id, pair_id, user)
    if item is None:
        await cb.answer("Нельзя", show_alert=True)
        return
    field = callback_data.field

    if field == "category":
        cats = await repo.list_categories(session, pair_id)
        await cb.message.edit_text(
            "Выбери новую категорию:",
            reply_markup=inline.edit_categories_kb(item.id, cats),
        )
        await cb.answer()
        return

    await state.set_state(EditItem.value)
    await state.update_data(item_id=item.id, field=field)
    optional = field in OPTIONAL_FIELDS
    await cb.message.edit_text(
        f"Пришли {PROMPTS[field]}:",
        reply_markup=inline.edit_value_kb(item.id, field, optional),
    )
    await cb.answer()


# ---------- Ввод нового значения ----------

@router.message(EditItem.value, F.text)
async def edit_value_text(message: Message, state: FSMContext,
                          session: AsyncSession, pair_id: int, user: User) -> None:
    data = await state.get_data()
    field, item_id = data["field"], data["item_id"]
    if field == "photo":
        await message.answer("Жду фото 📷")
        return
    value = (message.text or "").strip()
    if field == "title" and not value:
        await message.answer("Название не может быть пустым.")
        return
    await repo.update_item(session, item_id, pair_id, user.telegram_id, **{field: value})
    await state.clear()
    item = await repo.get_item(session, item_id, pair_id)
    await message.answer("Изменено ✅")
    await view.send_card(message, session, item, user.telegram_id, "my")


@router.message(EditItem.value, F.photo)
async def edit_value_photo(message: Message, state: FSMContext,
                           session: AsyncSession, pair_id: int, user: User) -> None:
    data = await state.get_data()
    if data.get("field") != "photo":
        await message.answer("Сейчас жду текст.")
        return
    await repo.update_item(session, data["item_id"], pair_id, user.telegram_id,
                           photo_file_id=message.photo[-1].file_id)
    await state.clear()
    item = await repo.get_item(session, data["item_id"], pair_id)
    await message.answer("Фото обновлено ✅")
    await view.send_card(message, session, item, user.telegram_id, "my")


@router.callback_query(inline.EditClear.filter())
async def edit_clear(cb: CallbackQuery, callback_data: inline.EditClear,
                     state: FSMContext, session: AsyncSession, pair_id: int,
                     user: User) -> None:
    await repo.update_item(session, callback_data.item_id, pair_id,
                           user.telegram_id, **{callback_data.field: None})
    await state.clear()
    item = await repo.get_item(session, callback_data.item_id, pair_id)
    await cb.message.delete()
    if item is not None:
        await view.send_card(cb.message, session, item, user.telegram_id, "my")
    await cb.answer("Очищено")


@router.callback_query(inline.EditCatPick.filter())
async def edit_category(cb: CallbackQuery, callback_data: inline.EditCatPick,
                        session: AsyncSession, pair_id: int, user: User) -> None:
    item = await _owned_item(session, callback_data.item_id, pair_id, user)
    if item is None:
        await cb.answer("Нельзя", show_alert=True)
        return
    cat = await repo.get_category(session, callback_data.cat_id, pair_id)
    if cat is None:
        await cb.answer("Категория не найдена", show_alert=True)
        return
    await repo.update_item(session, item.id, pair_id, user.telegram_id,
                           category_id=cat.id)
    refreshed = await repo.get_item(session, item.id, pair_id)
    await cb.message.delete()
    await view.send_card(cb.message, session, refreshed, user.telegram_id, "my")
    await cb.answer("Категория изменена")


# ---------- Удаление ----------

@router.callback_query(inline.CardDelete.filter())
async def delete_ask(cb: CallbackQuery, callback_data: inline.CardDelete,
                     session: AsyncSession, pair_id: int, user: User) -> None:
    item = await _owned_item(session, callback_data.item_id, pair_id, user)
    if item is None:
        await cb.answer("Можно удалять только свои записи", show_alert=True)
        return
    await cb.message.delete()
    await cb.message.answer(
        f"Удалить «{item.title}»?", reply_markup=inline.delete_confirm_kb(item.id)
    )
    await cb.answer()


@router.callback_query(inline.DelConfirm.filter())
async def delete_confirm(cb: CallbackQuery, callback_data: inline.DelConfirm,
                         session: AsyncSession, pair_id: int, user: User) -> None:
    item = await repo.get_item(session, callback_data.item_id, pair_id)
    if item is None:
        await cb.answer()
        return
    cat_id = item.category_id
    if not callback_data.ok:
        await cb.message.delete()
        await view.send_card(cb.message, session, item, user.telegram_id, "my")
        await cb.answer()
        return

    deleted = await repo.delete_item(session, item.id, pair_id, user.telegram_id)
    await cb.message.delete()
    if deleted:
        await _back_to_items(cb.message, session, pair_id, user, cat_id)
        await cb.answer("Удалено 🗑")
    else:
        await cb.answer("Можно удалять только свои записи", show_alert=True)


# ---------- Статус «выполнено» ----------

@router.callback_query(inline.CardDone.filter())
async def mark_done(cb: CallbackQuery, callback_data: inline.CardDone,
                    session: AsyncSession, pair_id: int, user: User, bot: Bot) -> None:
    item = await _owned_item(session, callback_data.item_id, pair_id, user)
    if item is None:
        await cb.answer("Нельзя", show_alert=True)
        return
    cat_id = item.category_id
    await repo.set_status(session, item.id, pair_id, user.telegram_id, ItemStatus.done)
    await session.commit()

    partner = await repo.partner_id(session, pair_id, user.telegram_id)
    if partner is not None:
        await notify_status_change(bot, partner, user.first_name, item)

    await cb.message.delete()
    await _back_to_items(cb.message, session, pair_id, user, cat_id)
    await cb.answer("Отмечено ✅")
