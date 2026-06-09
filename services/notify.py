"""Уведомления партнёру при событиях в паре."""

from __future__ import annotations

from html import escape

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError

from db.models import Item


def _render_item(author_name: str, category_label: str, item: Item) -> str:
    lines = [
        f"💛 <b>{escape(author_name)}</b> добавил(а) в {escape(category_label)}:",
        f"📌 {escape(item.title)}",
    ]
    if item.description:
        lines.append(f"📝 {escape(item.description)}")
    if item.url:
        lines.append(f"🔗 {escape(item.url)}")
    return "\n".join(lines)


async def notify_new_item(
    bot: Bot,
    partner_id: int,
    author_name: str,
    category_label: str,
    item: Item,
) -> None:
    """Шлёт партнёру превью новой записи. Молча игнорирует, если партнёр
    ещё не нажимал /start (бот не может ему написать)."""
    text = _render_item(author_name, category_label, item)
    try:
        if item.photo_file_id:
            await bot.send_photo(partner_id, item.photo_file_id, caption=text)
        else:
            await bot.send_message(partner_id, text)
    except TelegramAPIError:
        pass


async def notify_paired(bot: Bot, partner_id: int, joined_name: str) -> None:
    """Уведомляет о том, что партнёр присоединился и пара активна."""
    text = (
        f"🎉 <b>{escape(joined_name)}</b> присоединился(ась)!\n"
        "Теперь у вас общий вишлист — добавляйте хотелки 💛"
    )
    try:
        await bot.send_message(partner_id, text)
    except TelegramAPIError:
        pass


async def notify_status_change(
    bot: Bot, partner_id: int, author_name: str, item: Item
) -> None:
    """Уведомляет партнёра об отметке записи как выполненной."""
    text = (
        f"✅ <b>{escape(author_name)}</b> отметил(а) как выполнено:\n"
        f"📌 {escape(item.title)}"
    )
    try:
        await bot.send_message(partner_id, text)
    except TelegramAPIError:
        pass
