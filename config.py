"""Конфигурация из окружения (.env).

Загружает токен бота, список разрешённых ID (для bootstrap-пары на soft-launch)
и путь к БД. Имена пользователей берутся из Telegram, поэтому здесь не хранятся.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent


def _parse_ids(raw: str | None) -> list[int]:
    if not raw:
        return []
    ids: list[int] = []
    for part in raw.split(","):
        part = part.strip()
        if part:
            ids.append(int(part))
    return ids


@dataclass(frozen=True)
class Config:
    bot_token: str
    allowed_user_ids: list[int] = field(default_factory=list)
    db_path: str = "wants.db"

    @property
    def db_url(self) -> str:
        """URL для async-движка SQLAlchemy поверх aiosqlite."""
        path = self.db_path
        if not os.path.isabs(path):
            path = str(BASE_DIR / path)
        return f"sqlite+aiosqlite:///{path}"


def load_config() -> Config:
    token = os.getenv("BOT_TOKEN", "").strip()
    if not token:
        raise RuntimeError("BOT_TOKEN не задан в окружении (.env)")
    return Config(
        bot_token=token,
        allowed_user_ids=_parse_ids(os.getenv("ALLOWED_USER_IDS")),
        db_path=os.getenv("DB_PATH", "wants.db").strip() or "wants.db",
    )
