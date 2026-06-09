"""CRUD-функции поверх async-сессии.

Главный инвариант изоляции: все выборки/изменения items и пользовательских
категорий фильтруются по `pair_id`. Никакой объект чужой пары не должен утекать.
Правка/удаление записей — own-only (проверяется по author_id в хендлерах/здесь).
"""

from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import (
    Category,
    Invite,
    Item,
    ItemStatus,
    Pair,
    PairMember,
    PairStatus,
    User,
)

# ---------- Пользователи и пары ----------

async def get_or_create_user(
    session: AsyncSession,
    telegram_id: int,
    first_name: str = "",
    username: str | None = None,
) -> User:
    user = await session.get(User, telegram_id)
    if user is None:
        user = User(telegram_id=telegram_id, first_name=first_name, username=username)
        session.add(user)
        await session.flush()
    else:
        # Поддерживаем имя/username в актуальном состоянии.
        if first_name and user.first_name != first_name:
            user.first_name = first_name
        if username is not None and user.username != username:
            user.username = username
    return user


async def active_pair_id(session: AsyncSession, telegram_id: int) -> int | None:
    """Текущая активная пара пользователя.

    Берём `current_pair_id`, если он указывает на активную пару; иначе —
    первую активную пару из членства (на soft-launch она единственная).
    """
    user = await session.get(User, telegram_id)
    if user is not None and user.current_pair_id is not None:
        pair = await session.get(Pair, user.current_pair_id)
        if pair is not None and pair.status.value == "active":
            return pair.id

    pair_id = await session.scalar(
        select(PairMember.pair_id)
        .join(Pair, Pair.id == PairMember.pair_id)
        .where(PairMember.user_id == telegram_id, Pair.status == "active")
        .order_by(PairMember.pair_id)
        .limit(1)
    )
    return pair_id


async def partner_id(session: AsyncSession, pair_id: int, telegram_id: int) -> int | None:
    """ID второго участника пары (для уведомлений)."""
    return await session.scalar(
        select(PairMember.user_id).where(
            PairMember.pair_id == pair_id,
            PairMember.user_id != telegram_id,
        )
    )


# ---------- Пары и инвайты (онбординг) ----------

async def create_pending_pair(session: AsyncSession, owner_id: int) -> Pair:
    """Создаёт пару в статусе pending с одним участником (приглашающим)."""
    pair = Pair(status=PairStatus.pending)
    session.add(pair)
    await session.flush()
    session.add(PairMember(pair_id=pair.id, user_id=owner_id))
    owner = await session.get(User, owner_id)
    if owner is not None:
        owner.current_pair_id = pair.id
    await session.flush()
    return pair


async def pending_pair_for(session: AsyncSession, user_id: int) -> Pair | None:
    return await session.scalar(
        select(Pair)
        .join(PairMember, PairMember.pair_id == Pair.id)
        .where(PairMember.user_id == user_id, Pair.status == PairStatus.pending)
        .order_by(Pair.id.desc())
        .limit(1)
    )


async def create_invite(
    session: AsyncSession, inviter_id: int, pair_id: int, ttl_hours: int = 48
) -> str:
    token = secrets.token_urlsafe(8)
    session.add(
        Invite(
            token=token,
            inviter_id=inviter_id,
            pair_id=pair_id,
            expires_at=datetime.now(UTC) + timedelta(hours=ttl_hours),
        )
    )
    await session.flush()
    return token


async def get_valid_invite(session: AsyncSession, token: str) -> Invite | None:
    inv = await session.get(Invite, token)
    if inv is None or inv.used_at is not None:
        return None
    if inv.expires_at is not None:
        exp = inv.expires_at
        if exp.tzinfo is None:  # SQLite возвращает naive datetime
            exp = exp.replace(tzinfo=UTC)
        if exp < datetime.now(UTC):
            return None
    return inv


async def pair_member_count(session: AsyncSession, pair_id: int) -> int:
    return await session.scalar(
        select(func.count(PairMember.id)).where(PairMember.pair_id == pair_id)
    ) or 0


async def accept_invite(
    session: AsyncSession, token: str, user_id: int
) -> tuple[str, Pair | None]:
    """Принять инвайт. Возвращает (status, pair).

    status: ok | invalid | own | already | full.
    """
    inv = await get_valid_invite(session, token)
    if inv is None:
        return ("invalid", None)
    if inv.inviter_id == user_id:
        return ("own", None)
    if await active_pair_id(session, user_id) is not None:
        return ("already", None)
    pair = await session.get(Pair, inv.pair_id)
    if pair is None or pair.status == PairStatus.archived:
        return ("invalid", None)
    if await pair_member_count(session, inv.pair_id) >= 2:
        return ("full", None)

    session.add(PairMember(pair_id=inv.pair_id, user_id=user_id))
    pair.status = PairStatus.active
    inv.used_at = datetime.now(UTC)
    user = await session.get(User, user_id)
    if user is not None:
        user.current_pair_id = pair.id
    await session.flush()
    return ("ok", pair)


# ---------- Категории ----------

async def list_categories(session: AsyncSession, pair_id: int) -> list[Category]:
    """Встроенные (pair_id IS NULL) + пользовательские категории пары."""
    result = await session.scalars(
        select(Category)
        .where(or_(Category.pair_id.is_(None), Category.pair_id == pair_id))
        .order_by(Category.pair_id.is_(None).desc(), Category.id)
    )
    return list(result)


async def get_category(
    session: AsyncSession, category_id: int, pair_id: int
) -> Category | None:
    cat = await session.get(Category, category_id)
    if cat is None:
        return None
    if cat.pair_id is None or cat.pair_id == pair_id:
        return cat
    return None


async def add_category(
    session: AsyncSession,
    pair_id: int,
    name: str,
    emoji: str,
    created_by: int,
) -> Category:
    cat = Category(name=name, emoji=emoji, pair_id=pair_id, created_by=created_by)
    session.add(cat)
    await session.flush()
    return cat


# ---------- Записи ----------

async def add_item(
    session: AsyncSession,
    pair_id: int,
    category_id: int,
    author_id: int,
    title: str,
    description: str | None = None,
    url: str | None = None,
    photo_file_id: str | None = None,
) -> Item:
    item = Item(
        pair_id=pair_id,
        category_id=category_id,
        author_id=author_id,
        title=title,
        description=description,
        url=url,
        photo_file_id=photo_file_id,
    )
    session.add(item)
    await session.flush()
    return item


async def get_items_by_category(
    session: AsyncSession,
    pair_id: int,
    category_id: int,
    author_id: int | None = None,
    status: ItemStatus | None = ItemStatus.active,
) -> list[Item]:
    stmt = select(Item).where(
        Item.pair_id == pair_id, Item.category_id == category_id
    )
    if author_id is not None:
        stmt = stmt.where(Item.author_id == author_id)
    if status is not None:
        stmt = stmt.where(Item.status == status)
    stmt = stmt.order_by(Item.created_at.desc())
    return list(await session.scalars(stmt))


async def count_items_per_category(
    session: AsyncSession,
    pair_id: int,
    author_id: int | None = None,
    status: ItemStatus | None = ItemStatus.active,
) -> dict[int, int]:
    """Карта category_id -> количество записей (для счётчиков в меню)."""
    stmt = select(Item.category_id, func.count(Item.id)).where(
        Item.pair_id == pair_id
    )
    if author_id is not None:
        stmt = stmt.where(Item.author_id == author_id)
    if status is not None:
        stmt = stmt.where(Item.status == status)
    stmt = stmt.group_by(Item.category_id)
    rows = await session.execute(stmt)
    return {cat_id: cnt for cat_id, cnt in rows.all()}


async def get_item(session: AsyncSession, item_id: int, pair_id: int) -> Item | None:
    item = await session.get(Item, item_id)
    if item is None or item.pair_id != pair_id:
        return None
    return item


async def update_item(
    session: AsyncSession,
    item_id: int,
    pair_id: int,
    author_id: int,
    **fields,
) -> Item | None:
    """Обновляет запись. Только автор (own-only) и только в своей паре."""
    item = await get_item(session, item_id, pair_id)
    if item is None or item.author_id != author_id:
        return None
    allowed = {"title", "description", "url", "photo_file_id", "category_id", "status"}
    for key, value in fields.items():
        if key in allowed:
            setattr(item, key, value)
    await session.flush()
    return item


async def set_status(
    session: AsyncSession,
    item_id: int,
    pair_id: int,
    author_id: int,
    status: ItemStatus,
) -> Item | None:
    return await update_item(
        session, item_id, pair_id, author_id, status=status
    )


async def delete_item(
    session: AsyncSession,
    item_id: int,
    pair_id: int,
    author_id: int,
) -> bool:
    """Удаляет запись. Только автор (own-only) и только в своей паре."""
    item = await get_item(session, item_id, pair_id)
    if item is None or item.author_id != author_id:
        return False
    await session.delete(item)
    await session.flush()
    return True
