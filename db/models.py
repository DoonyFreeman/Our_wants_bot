"""SQLAlchemy 2.0 модели (pair-aware с самого начала).

Все данные изолированы по паре (`pair_id`). Схема заложена под будущий
публичный мэтчинг и несколько связей на пользователя (см. context/multitenant).
"""

from __future__ import annotations

import enum
from datetime import UTC, datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    Enum,
    ForeignKey,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class PairStatus(enum.StrEnum):
    pending = "pending"      # создана, ждёт второго участника
    active = "active"        # оба участника на месте
    archived = "archived"    # пара расторгнута, данные сохранены


class ItemStatus(enum.StrEnum):
    active = "active"
    done = "done"


class User(Base):
    __tablename__ = "users"

    telegram_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    first_name: Mapped[str] = mapped_column(String(128), default="")
    username: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # Активная связь (для будущего переключателя нескольких связей).
    current_pair_id: Mapped[int | None] = mapped_column(
        ForeignKey("pairs.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, server_default=func.now()
    )

    memberships: Mapped[list[PairMember]] = relationship(
        back_populates="user",
        foreign_keys="PairMember.user_id",
        cascade="all, delete-orphan",
    )


class Pair(Base):
    __tablename__ = "pairs"

    id: Mapped[int] = mapped_column(primary_key=True)
    status: Mapped[PairStatus] = mapped_column(
        Enum(PairStatus, native_enum=False, length=16),
        default=PairStatus.pending,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, server_default=func.now()
    )
    archived_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    members: Mapped[list[PairMember]] = relationship(
        back_populates="pair", cascade="all, delete-orphan"
    )


class PairMember(Base):
    __tablename__ = "pair_members"
    __table_args__ = (
        UniqueConstraint("pair_id", "user_id", name="uq_pair_member"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    pair_id: Mapped[int] = mapped_column(
        ForeignKey("pairs.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.telegram_id", ondelete="CASCADE"), index=True
    )
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, server_default=func.now()
    )

    pair: Mapped[Pair] = relationship(back_populates="members")
    user: Mapped[User] = relationship(
        back_populates="memberships", foreign_keys=[user_id]
    )


class Invite(Base):
    __tablename__ = "invites"

    token: Mapped[str] = mapped_column(String(64), primary_key=True)
    inviter_id: Mapped[int] = mapped_column(
        ForeignKey("users.telegram_id", ondelete="CASCADE")
    )
    pair_id: Mapped[int] = mapped_column(
        ForeignKey("pairs.id", ondelete="CASCADE")
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, server_default=func.now()
    )


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(64))
    emoji: Mapped[str] = mapped_column(String(16), default="")
    # NULL = встроенная категория (общая для всех пар), иначе — пользовательская.
    pair_id: Mapped[int | None] = mapped_column(
        ForeignKey("pairs.id", ondelete="CASCADE"), nullable=True, index=True
    )
    created_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, server_default=func.now()
    )

    items: Mapped[list[Item]] = relationship(back_populates="category")


class Item(Base):
    __tablename__ = "items"

    id: Mapped[int] = mapped_column(primary_key=True)
    pair_id: Mapped[int] = mapped_column(
        ForeignKey("pairs.id", ondelete="CASCADE"), index=True
    )
    category_id: Mapped[int] = mapped_column(
        ForeignKey("categories.id", ondelete="RESTRICT"), index=True
    )
    author_id: Mapped[int] = mapped_column(
        ForeignKey("users.telegram_id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(256))
    description: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    photo_file_id: Mapped[str | None] = mapped_column(String(256), nullable=True)
    status: Mapped[ItemStatus] = mapped_column(
        Enum(ItemStatus, native_enum=False, length=16),
        default=ItemStatus.active,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        server_default=func.now(),
        onupdate=utcnow,
    )

    category: Mapped[Category] = relationship(back_populates="items")
