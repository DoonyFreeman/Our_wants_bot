"""Онбординг и мэтчинг пары через deep-link инвайт (Спринт 8).

Бот публичный: доступ не по whitelist, а по членству в паре. Любой может создать
свой список и пригласить партнёра ссылкой. Данные каждой пары изолированы по pair_id.
"""

from __future__ import annotations

from html import escape

from aiogram import Bot, Router
from aiogram.filters import CommandObject, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from db import repo
from db.models import User
from keyboards import inline
from keyboards.reply import main_menu
from services.invite import build_invite_link
from services.notify import notify_paired

router = Router()

WELCOME_NEW = (
    "Привет, {name}! 💛\n\n"
    "Это бот для <b>общего вишлиста на двоих</b>. Создай список и пригласи "
    "партнёра — потом добавляйте хотелки и получайте уведомления друг от друга."
)

WELCOME_BACK = (
    "С возвращением, {name}! 💛\nВыбирай действие на клавиатуре ниже 👇"
)


async def _send_invite(message: Message, bot: Bot, session: AsyncSession,
                       user: User) -> None:
    """Создаёт (или переиспользует) pending-пару и шлёт пригласительную ссылку."""
    pair = await repo.pending_pair_for(session, user.telegram_id)
    if pair is None:
        pair = await repo.create_pending_pair(session, user.telegram_id)
    token = await repo.create_invite(session, user.telegram_id, pair.id)
    await session.commit()
    link = await build_invite_link(bot, token)
    await message.answer(
        "🔗 Перешли эту ссылку партнёру:\n\n"
        f"{link}\n\n"
        "Как только он(а) откроет ссылку — вы окажетесь в паре, и можно "
        "добавлять хотелки. Ссылка действует 48 часов.",
        disable_web_page_preview=True,
    )


# ---------- /start ----------

@router.message(CommandStart(deep_link=True))
async def start_deeplink(message: Message, command: CommandObject, bot: Bot,
                         state: FSMContext, session: AsyncSession,
                         user: User, pair_id: int | None) -> None:
    await state.clear()
    arg = command.args or ""
    if not arg.startswith("join_"):
        await start_plain(message, state, session, bot, user, pair_id)
        return

    token = arg[len("join_"):]
    status, pair = await repo.accept_invite(session, token, user.telegram_id)
    if status == "ok":
        await session.commit()
        partner = await repo.partner_id(session, pair.id, user.telegram_id)
        if partner is not None:
            await notify_paired(bot, partner, user.first_name)
        await message.answer(
            "🎉 Готово, вы в паре! Теперь добавляйте хотелки 💛",
            reply_markup=main_menu(),
        )
    elif status == "own":
        await message.answer("Это твоя же ссылка 🙂 Перешли её партнёру.")
    elif status == "already":
        await message.answer("Ты уже в паре. Открой меню: /start", reply_markup=main_menu())
    elif status == "full":
        await message.answer("В этой паре уже двое 🙈")
    else:
        await message.answer("Ссылка недействительна или устарела. Попроси новую.")


@router.message(CommandStart())
async def start_plain(message: Message, state: FSMContext, session: AsyncSession,
                      bot: Bot, user: User, pair_id: int | None) -> None:
    await state.clear()
    name = escape(user.first_name or "друг")
    if pair_id is not None:
        await message.answer(WELCOME_BACK.format(name=name), reply_markup=main_menu())
        return
    await message.answer(
        WELCOME_NEW.format(name=name), reply_markup=inline.invite_start_kb()
    )


@router.callback_query(inline.CreateInvite.filter())
async def create_invite(cb: CallbackQuery, bot: Bot, session: AsyncSession,
                        user: User, pair_id: int | None) -> None:
    if pair_id is not None:
        await cb.message.answer("Ты уже в паре 💛", reply_markup=main_menu())
        await cb.answer()
        return
    await _send_invite(cb.message, bot, session, user)
    await cb.answer()
