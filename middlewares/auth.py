"""Контекст пользователя и пары на каждый апдейт.

Доступ к боту открыт всем (публичный мульти-тенант), но данные изолированы по
паре: middleware подгружает текущего пользователя и его активную пару и кладёт
их в `data["user"]` / `data["pair_id"]`. Хендлеры, требующие пары, проверяют
`pair_id is None` и направляют в онбординг (/start).
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

from db import repo


class AuthMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        tg_user = data.get("event_from_user")
        if tg_user is None or tg_user.is_bot:
            return  # системные апдейты без пользователя пропускаем

        session = data["session"]
        user = await repo.get_or_create_user(
            session,
            telegram_id=tg_user.id,
            first_name=tg_user.first_name or "",
            username=tg_user.username,
        )
        data["user"] = user
        data["pair_id"] = await repo.active_pair_id(session, tg_user.id)
        return await handler(event, data)
