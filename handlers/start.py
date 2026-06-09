"""/start, /cancel и главное меню."""

from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from db.models import User
from keyboards.reply import main_menu

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message, user: User, state: FSMContext) -> None:
    await state.clear()
    name = user.first_name or "друг"
    await message.answer(
        f"Привет, {name}! 💛\nЭто наш общий вишлист. Выбирай действие:",
        reply_markup=main_menu(),
    )


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext) -> None:
    if await state.get_state() is None:
        await message.answer("Нечего отменять.", reply_markup=main_menu())
        return
    await state.clear()
    await message.answer("Отменено.", reply_markup=main_menu())
