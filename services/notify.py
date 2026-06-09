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
