"""Спринт 5 (правка/удаление own-only + статус) и Спринт 6 (категории)."""

from __future__ import annotations

from db import repo
from db.models import ItemStatus
from keyboards import inline
from tests.harness import USER_A, USER_B, BotHarness


async def _any_item(h: BotHarness, uid: int):
    """Первая запись пары (включая выполненные)."""
    async with h.sf() as s:
        pid = await repo.active_pair_id(s, uid)
        for cat in await repo.list_categories(s, pid):
            items = await repo.get_items_by_category(
                s, pid, cat.id, author_id=None, status=None
            )
            if items:
                return items[0].id, pid
    return None, None


async def _item_by_id(h: BotHarness, item_id: int, pid: int):
    async with h.sf() as s:
        return await repo.get_item(s, item_id, pid)


# ---------- own-only ----------

async def test_partner_card_has_no_action_buttons(harness: BotHarness):
    await harness.add_item(USER_A, "Место", "Парк")
    harness.clear_inbox()
    await harness.send_text(USER_B, "💙 Список партнёра")
    await harness.click_button(USER_B, "Место")
    await harness.click_button(USER_B, "Парк")
    btns = harness.button_texts(USER_B)
    assert not any("Редактировать" in b for b in btns), btns
    assert not any("Удалить" in b for b in btns), btns
    assert any("Назад" in b for b in btns), btns


async def test_partner_cannot_edit_or_delete_forged_callback(harness: BotHarness):
    await harness.add_item(USER_A, "Место", "Секрет A")
    item_id, pid = await _any_item(harness, USER_A)

    # B шлёт подделанные callback'и на чужую запись
    await harness.click(USER_B, inline.CardEdit(item_id=item_id).pack())
    await harness.click(USER_B, inline.DelConfirm(item_id=item_id, ok=True).pack())

    item = await _item_by_id(harness, item_id, pid)
    assert item is not None, "запись A удалена партнёром!"
    assert item.title == "Секрет A"


# ---------- правка ----------

async def test_edit_title(harness: BotHarness):
    await harness.add_item(USER_A, "Кукла", "Старое имя")
    item_id, pid = await _any_item(harness, USER_A)

    await harness.open_my_card(USER_A, "Кукла", "Старое имя")
    await harness.click_button(USER_A, "Редактировать")
    await harness.click_button(USER_A, "Название")
    await harness.send_text(USER_A, "Новое имя")

    item = await _item_by_id(harness, item_id, pid)
    assert item.title == "Новое имя"


async def test_edit_clear_description(harness: BotHarness):
    await harness.add_item(USER_A, "План", "Поездка", description="черновик")
    item_id, pid = await _any_item(harness, USER_A)

    await harness.open_my_card(USER_A, "План", "Поездка")
    await harness.click_button(USER_A, "Редактировать")
    await harness.click_button(USER_A, "Описание")
    await harness.click_button(USER_A, "Очистить")

    item = await _item_by_id(harness, item_id, pid)
    assert item.description is None


# ---------- удаление ----------

async def test_delete_item(harness: BotHarness):
    await harness.add_item(USER_A, "Подарок", "Удалить меня")
    item_id, pid = await _any_item(harness, USER_A)

    await harness.open_my_card(USER_A, "Подарок", "Удалить меня")
    await harness.click_button(USER_A, "Удалить")
    await harness.click_button(USER_A, "Да")

    item = await _item_by_id(harness, item_id, pid)
    assert item is None


# ---------- статус ----------

async def test_mark_done_removes_from_active_and_notifies(harness: BotHarness):
    await harness.add_item(USER_A, "Место", "Кафе")
    item_id, pid = await _any_item(harness, USER_A)

    await harness.open_my_card(USER_A, "Место", "Кафе")
    harness.clear_inbox(USER_B)  # чистим только партнёра, карточка A нужна для клика
    await harness.click_button(USER_A, "Выполнено")

    # статус done в БД
    item = await _item_by_id(harness, item_id, pid)
    assert item.status == ItemStatus.done

    # ушло из активного списка
    async with harness.sf() as s:
        active = await repo.get_items_by_category(
            s, pid, item.category_id, author_id=USER_A
        )
    assert active == []

    # партнёр уведомлён
    assert any("Кафе" in (m.text or "") for m in harness.messages(USER_B))


# ---------- категории ----------

async def test_create_custom_category_visible_to_both(harness: BotHarness):
    await harness.send_text(USER_A, "⚙️ Категории")
    await harness.click_button(USER_A, "Новая категория")
    await harness.send_text(USER_A, "Книга")
    await harness.click_button(USER_A, "Пропустить")  # эмодзи

    async with harness.sf() as s:
        pid = await repo.active_pair_id(s, USER_A)
        names = [c.name for c in await repo.list_categories(s, pid)]
    assert "Книга" in names

    # Новая категория доступна обоим при добавлении
    await harness.add_item(USER_B, "Книга", "Дюна")
    async with harness.sf() as s:
        cats = await repo.list_categories(s, pid)
        book = next(c for c in cats if c.name == "Книга")
        items = await repo.get_items_by_category(s, pid, book.id, author_id=USER_B)
    assert any(i.title == "Дюна" for i in items)
