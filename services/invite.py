"""Построение deep-link инвайт-ссылки для онбординга пары."""

from __future__ import annotations

from aiogram import Bot


async def build_invite_link(bot: Bot, token: str) -> str:
    me = await bot.me()
    return f"https://t.me/{me.username}?start=join_{token}"
