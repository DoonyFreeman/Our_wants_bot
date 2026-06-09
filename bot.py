"""Entrypoint: инициализация БД, Bot/Dispatcher, middleware, роутеры, polling."""

from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from config import load_config
from db.database import create_engine, create_session_factory, init_db
from handlers import add_item, start
from middlewares.auth import AuthMiddleware
from middlewares.db import DbSessionMiddleware


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    config = load_config()

    engine = create_engine(config)
    session_factory = create_session_factory(engine)
    await init_db(engine, session_factory, config.allowed_user_ids)

    bot = Bot(
        config.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()

    # Порядок важен: сессия БД должна быть доступна middleware авторизации.
    dp.update.outer_middleware(DbSessionMiddleware(session_factory))
    dp.update.outer_middleware(AuthMiddleware(config.allowed_user_ids))

    dp.include_router(start.router)
    dp.include_router(add_item.router)

    try:
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)
    finally:
        await bot.session.close()
        await engine.dispose()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Бот остановлен")
