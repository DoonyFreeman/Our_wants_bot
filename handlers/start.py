"""/start, /help, /cancel и главное меню."""

from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from db.models import User
from keyboards.reply import (
    BTN_ADD,
    BTN_CATEGORIES,
    BTN_MY,
    BTN_PARTNER,
    main_menu,
)

router = Router()

HELP_TEXT = (
    "💛 <b>Наш общий вишлист</b>\n\n"
    f"• <b>{BTN_ADD}</b> — добавить хотелку: выбираешь категорию и пошагово "
    "заполняешь название (обязательно), описание, ссылку и фото (по желанию).\n"
    f"• <b>{BTN_MY}</b> — посмотреть свои записи по категориям.\n"
    f"• <b>{BTN_PARTNER}</b> — посмотреть, что добавил партнёр.\n"
    f"• <b>{BTN_CATEGORIES}</b> — категории и создание своих.\n\n"
    "Когда ты добавляешь запись, партнёру приходит уведомление. "
    "Свои записи можно изменить, удалить или отметить как выполненные.\n\n"
    "Команды: /start — меню, /help — помощь, /cancel — отменить действие."
)


@router.message(CommandStart())
async def cmd_start(message: Message, user: User, state: FSMContext) -> None:
    await state.clear()
    name = user.first_name or "друг"
    await message.answer(
        f"Привет, {name}! 💛\n"
        "Это наш общий вишлист — добавляй хотелки и смотри, что хочет партнёр.\n\n"
        "Выбирай действие на клавиатуре ниже 👇",
        reply_markup=main_menu(),
    )


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(HELP_TEXT, reply_markup=main_menu())


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext) -> None:
    if await state.get_state() is None:
        await message.answer("Нечего отменять 🙂", reply_markup=main_menu())
        return
    await state.clear()
    await message.answer("Отменено 👌", reply_markup=main_menu())
