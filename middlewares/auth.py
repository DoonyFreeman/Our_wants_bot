"""Whitelist-middleware: пускает только разрешённые Telegram ID.

НЕ отключать этот whitelist (главное правило приватности на soft-launch).
В Спринте 8 доступ расширится до членства в паре + флоу приглашения.

Помимо проверки доступа, подгружает текущего пользователя и его активную пару
и кладёт их в `data["user"]` / `data["pair_id"]`.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

from db import repo


class AuthMiddleware(BaseMiddleware):
    def __init__(self, allowed_ids: list[int]) -> None:
        self.allowed_ids = set(allowed_ids)

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        tg_user = data.get("event_from_user")
        if tg_user is None or tg_user.id not in self.allowed_ids:
            return  # молча игнорируем посторонних

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
