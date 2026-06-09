"""Async engine, sessionmaker и инициализация БД.

`init_db()` создаёт схему, сидит встроенные категории и (для soft-launch)
bootstrap-пару из ALLOWED_USER_IDS, чтобы бот работал на двоих до включения
публичного мэтчинга.
"""

from __future__ import annotations

from sqlalchemy import event, select
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from config import Config
from db.models import (
    Base,
    Category,
    Pair,
    PairMember,
    PairStatus,
    User,
)

# Встроенные категории (pair_id = NULL, видны всем парам).
BUILTIN_CATEGORIES: list[tuple[str, str]] = [
    ("Место для прогулки", "🚶"),
    ("Подарок на праздник", "🎁"),
    ("3D-модель", "🧩"),
    ("Кукла", "🪆"),
    ("Хотелка", "✨"),
    ("План", "🗺"),
]


def _enable_sqlite_fk(dbapi_connection, _connection_record) -> None:
    """SQLite по умолчанию не форсит внешние ключи — включаем."""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def create_engine(config: Config) -> AsyncEngine:
    engine = create_async_engine(config.db_url, echo=False)
    event.listen(engine.sync_engine, "connect", _enable_sqlite_fk)
    return engine


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)


async def _seed_builtin_categories(session: AsyncSession) -> None:
    existing = await session.scalar(
        select(Category).where(Category.pair_id.is_(None)).limit(1)
    )
    if existing is not None:
        return
    for name, emoji in BUILTIN_CATEGORIES:
        session.add(Category(name=name, emoji=emoji, pair_id=None, created_by=None))


async def _seed_bootstrap_pair(session: AsyncSession, allowed_ids: list[int]) -> None:
    """Создаёт одну пару из разрешённых ID, если её ещё нет (soft-launch)."""
    if len(allowed_ids) < 2:
        return
    has_pair = await session.scalar(select(Pair).limit(1))
    if has_pair is not None:
        return

    a, b = allowed_ids[0], allowed_ids[1]
    pair = Pair(status=PairStatus.active)
    session.add(pair)
    await session.flush()  # получить pair.id

    for uid in (a, b):
        user = await session.get(User, uid)
        if user is None:
            user = User(telegram_id=uid)
            session.add(user)
        user.current_pair_id = pair.id
        session.add(PairMember(pair_id=pair.id, user_id=uid))


async def init_db(
    engine: AsyncEngine,
    session_factory: async_sessionmaker[AsyncSession],
    allowed_ids: list[int] | None = None,
) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with session_factory() as session:
        await _seed_builtin_categories(session)
        await _seed_bootstrap_pair(session, allowed_ids or [])
        await session.commit()
