"""Тестовый стенд: две мок-сущности в одной паре + имитация Telegram.

Позволяет прогонять любые взаимодействия между двумя пользователями без реального
Telegram: каждый «отправляет» текст или «жмёт» кнопку, а исходящие сообщения бота
перехватываются и складываются в «входящие» по chat_id. Так можно проверить,
например, что при добавлении записи партнёр получил уведомление.

Имена: 111 — «Артём», 222 — «Аня». Оба в bootstrap-паре (active).
"""

from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import (
    CallbackQuery,
    Chat,
    InlineKeyboardMarkup,
    Message,
    Update,
)
from aiogram.types import User as TgUser

from config import Config
from db.database import create_engine, create_session_factory, init_db

USER_A = 111
USER_B = 222
NAMES = {USER_A: "Артём", USER_B: "Аня"}

BOT_ID = 123
BOT_TOKEN = f"{BOT_ID}:dummy"


@dataclass
class Sent:
    method: str
    chat_id: int | None
    text: str | None
    markup: InlineKeyboardMarkup | None


class _FakeSession:
    """Подменяет сетевой слой aiogram: ничего не шлёт, всё пишет в inbox."""

    def __init__(self, inbox: dict[int, list[Sent]]) -> None:
        self.inbox = inbox

    def _record(self, method: Any) -> None:
        name = type(method).__name__
        chat_id = getattr(method, "chat_id", None)
        text = getattr(method, "text", None) or getattr(method, "caption", None)
        markup = getattr(method, "reply_markup", None)
        if isinstance(chat_id, int):
            self.inbox.setdefault(chat_id, []).append(Sent(name, chat_id, text, markup))

    async def make_request(self, bot: Bot, method: Any, timeout: Any = None) -> Any:
        self._record(method)
        name = type(method).__name__
        if name in ("SendMessage", "SendPhoto", "EditMessageText"):
            return Message(message_id=1, date=datetime.now(),
                           chat=Chat(id=getattr(method, "chat_id", 0) or 0, type="private"))
        return True

    async def __call__(self, bot: Bot, method: Any, timeout: Any = None) -> Any:
        return await self.make_request(bot, method, timeout)

    async def close(self) -> None: ...


@dataclass
class BotHarness:
    db_path: str = field(default_factory=lambda: tempfile.mktemp(suffix=".db"))
    inbox: dict[int, list[Sent]] = field(default_factory=dict)
    _n: int = 0

    async def start(self) -> "BotHarness":
        from handlers import add_item, categories, edit_item, start, view
        from middlewares.auth import AuthMiddleware
        from middlewares.db import DbSessionMiddleware

        self.config = Config(
            bot_token=BOT_TOKEN, allowed_user_ids=[USER_A, USER_B], db_path=self.db_path
        )
        self.engine = create_engine(self.config)
        self.sf = create_session_factory(self.engine)
        await init_db(self.engine, self.sf, self.config.allowed_user_ids)

        self.bot = Bot(BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
        self.bot.session = _FakeSession(self.inbox)

        self.dp = Dispatcher()
        self.dp.update.outer_middleware(DbSessionMiddleware(self.sf))
        self.dp.update.outer_middleware(AuthMiddleware(self.config.allowed_user_ids))
        routers = (
            start.router, add_item.router, view.router,
            edit_item.router, categories.router,
        )
        for r in routers:
            # Роутеры — модульные синглтоны; между тестами снимаем привязку
            # к предыдущему Dispatcher, чтобы можно было включить заново.
            r._parent_router = None
            self.dp.include_router(r)
        return self

    async def stop(self) -> None:
        await self.engine.dispose()
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    # ---------- Имитация пользователя ----------

    def _user(self, uid: int) -> TgUser:
        return TgUser(id=uid, is_bot=False, first_name=NAMES.get(uid, f"U{uid}"))

    async def send_text(self, uid: int, text: str) -> None:
        self._n += 1
        upd = Update(update_id=self._n, message=Message(
            message_id=self._n, date=datetime.now(),
            chat=Chat(id=uid, type="private"), from_user=self._user(uid), text=text))
        await self.dp.feed_update(self.bot, upd)

    async def send_photo(self, uid: int, file_id: str = "PHOTOID") -> None:
        from aiogram.types import PhotoSize
        self._n += 1
        photo = PhotoSize(file_id=file_id, file_unique_id="u", width=1, height=1)
        upd = Update(update_id=self._n, message=Message(
            message_id=self._n, date=datetime.now(),
            chat=Chat(id=uid, type="private"), from_user=self._user(uid),
            photo=[photo]))
        await self.dp.feed_update(self.bot, upd)

    async def click(self, uid: int, callback_data: str) -> None:
        self._n += 1
        upd = Update(update_id=self._n, callback_query=CallbackQuery(
            id=str(self._n), chat_instance="ci", from_user=self._user(uid),
            data=callback_data,
            message=Message(message_id=10_000 + self._n, date=datetime.now(),
                            chat=Chat(id=uid, type="private"),
                            from_user=TgUser(id=BOT_ID, is_bot=True, first_name="bot"),
                            text="...")))
        await self.dp.feed_update(self.bot, upd)

    async def click_button(self, uid: int, text_substr: str) -> str:
        """Жмёт кнопку последнего сообщения пользователя по подстроке текста."""
        markup = self.last_markup(uid)
        assert markup is not None, f"у последнего сообщения {uid} нет кнопок"
        for row in markup.inline_keyboard:
            for btn in row:
                if text_substr.lower() in (btn.text or "").lower():
                    await self.click(uid, btn.callback_data)
                    return btn.text
        raise AssertionError(
            f"кнопка с «{text_substr}» не найдена среди: "
            f"{[b.text for r in markup.inline_keyboard for b in r]}"
        )

    # ---------- Высокоуровневые сценарии ----------

    async def add_item(
        self, uid: int, category_substr: str, title: str,
        description: str | None = None, url: str | None = None, photo: bool = False,
    ) -> None:
        """Полный поток добавления записи через кнопки и текст."""
        await self.send_text(uid, "➕ Добавить")
        await self.click_button(uid, category_substr)
        await self.send_text(uid, title)
        if description is None:
            await self.click_button(uid, "Пропустить")
        else:
            await self.send_text(uid, description)
        if url is None:
            await self.click_button(uid, "Пропустить")
        else:
            await self.send_text(uid, url)
        if photo:
            await self.send_photo(uid)
        else:
            await self.click_button(uid, "Пропустить")
        await self.click_button(uid, "Сохранить")

    async def open_my_card(self, uid: int, category_substr: str, title_substr: str) -> None:
        """Открывает карточку своей записи: Мой список → категория → запись."""
        await self.send_text(uid, "📋 Мой список")
        await self.click_button(uid, category_substr)
        await self.click_button(uid, title_substr)

    # ---------- Инспекция «входящих» ----------

    def messages(self, uid: int) -> list[Sent]:
        return self.inbox.get(uid, [])

    def last(self, uid: int) -> Sent:
        msgs = self.messages(uid)
        assert msgs, f"у {uid} нет входящих"
        return msgs[-1]

    def last_text(self, uid: int) -> str:
        return self.last(uid).text or ""

    def last_markup(self, uid: int) -> InlineKeyboardMarkup | None:
        return self.last(uid).markup

    def button_texts(self, uid: int) -> list[str]:
        markup = self.last_markup(uid)
        if markup is None:
            return []
        return [b.text for row in markup.inline_keyboard for b in row]

    def clear_inbox(self, uid: int | None = None) -> None:
        if uid is None:
            self.inbox.clear()
        else:
            self.inbox.pop(uid, None)
