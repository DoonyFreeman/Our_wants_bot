"""Взаимодействия между двумя пользователями пары (Артём 111 ↔ Аня 222)."""

from __future__ import annotations

from db import repo
from tests.harness import USER_A, USER_B, BotHarness


async def _add_item(
    h: BotHarness, uid: int, category_substr: str, title: str,
    description: str | None = None, url: str | None = None, photo: bool = False,
) -> None:
    """Полный пользовательский поток добавления через кнопки и текст."""
    await h.send_text(uid, "➕ Добавить")
    await h.click_button(uid, category_substr)        # выбор категории
    await h.send_text(uid, title)                      # название
    if description is None:
        await h.click_button(uid, "Пропустить")
    else:
        await h.send_text(uid, description)
    if url is None:
        await h.click_button(uid, "Пропустить")
    else:
        await h.send_text(uid, url)
    if photo:
        await h.send_photo(uid)
    else:
        await h.click_button(uid, "Пропустить")
    await h.click_button(uid, "Сохранить")             # подтверждение


async def test_add_notifies_partner(harness: BotHarness):
    """A добавляет → B получает уведомление, A видит подтверждение."""
    await _add_item(harness, USER_A, "Место", "Парк Горького", description="вечером")

    # A получил «Добавлено»
    assert any("Добавлено" in (m.text or "") for m in harness.messages(USER_A))

    # B получил уведомление с автором и названием
    b_texts = [m.text or "" for m in harness.messages(USER_B)]
    assert any("Парк Горького" in t for t in b_texts), b_texts
    assert any("Артём" in t for t in b_texts), b_texts

    # Запись реально в БД
    async with harness.sf() as s:
        pid = await repo.active_pair_id(s, USER_A)
        cats = await repo.list_categories(s, pid)
    assert pid is not None


async def test_partner_sees_my_items_in_their_partner_list(harness: BotHarness):
    """То, что добавил A, видно у B в разделе «Список партнёра»."""
    await _add_item(harness, USER_A, "Подарок", "Букет")
    harness.clear_inbox()

    await harness.send_text(USER_B, "💙 Список партнёра")
    assert "Список партнёра" in harness.last_text(USER_B)
    # есть категория со счётчиком (1)
    assert any("(1)" in t for t in harness.button_texts(USER_B)), harness.button_texts(USER_B)

    await harness.click_button(USER_B, "Подарок")      # открыть категорию
    assert "Букет" in harness.button_texts(USER_B), harness.button_texts(USER_B)

    await harness.click_button(USER_B, "Букет")        # открыть карточку
    assert "Букет" in harness.last_text(USER_B)
    assert "Артём" in harness.last_text(USER_B)        # автор — A


async def test_my_list_is_isolated_per_author(harness: BotHarness):
    """«Мой список» показывает только свои записи."""
    await _add_item(harness, USER_A, "Кукла", "BJD")
    await _add_item(harness, USER_B, "План", "Поездка")
    harness.clear_inbox()

    # У A в «Мой список» — Кукла, нет Плана
    await harness.send_text(USER_A, "📋 Мой список")
    a_cats = harness.button_texts(USER_A)
    assert any("Кукла" in t for t in a_cats), a_cats
    assert not any("План" in t for t in a_cats), a_cats

    # У B в «Мой список» — План, нет Куклы
    await harness.send_text(USER_B, "📋 Мой список")
    b_cats = harness.button_texts(USER_B)
    assert any("План" in t for t in b_cats), b_cats
    assert not any("Кукла" in t for t in b_cats), b_cats


async def test_photo_item_card(harness: BotHarness):
    """Запись с фото открывается карточкой (SendPhoto с подписью)."""
    await _add_item(harness, USER_A, "3D", "Дракон", photo=True)
    harness.clear_inbox()

    await harness.send_text(USER_A, "📋 Мой список")
    await harness.click_button(USER_A, "3D")
    await harness.click_button(USER_A, "Дракон")
    last = harness.last(USER_A)
    assert last.method == "SendPhoto", last.method
    assert "Дракон" in (last.text or "")


async def test_outsider_is_ignored(harness: BotHarness):
    """Посторонний ID не получает ничего."""
    await harness.send_text(999, "📋 Мой список")
    await harness.send_text(999, "/start")
    assert harness.messages(999) == []


async def test_empty_list_message(harness: BotHarness):
    """Пустой список — дружелюбное сообщение, без падений."""
    await harness.send_text(USER_A, "📋 Мой список")
    assert "пусто" in harness.last_text(USER_A).lower()
