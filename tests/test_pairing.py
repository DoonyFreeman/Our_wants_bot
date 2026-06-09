"""Онбординг и мэтчинг пары через инвайт-ссылку (Спринт 8)."""

from __future__ import annotations

import re

from db import repo
from tests.harness import USER_A, USER_B, BotHarness

INVITE_RE = re.compile(r"join_([A-Za-z0-9_-]+)")


async def _make_invite(h: BotHarness, uid: int) -> str:
    await h.send_text(uid, "/start")
    await h.click_button(uid, "Создать список")
    m = INVITE_RE.search(h.last_text(uid))
    assert m, f"в сообщении нет инвайт-ссылки: {h.last_text(uid)}"
    return m.group(1)


async def test_onboarding_creates_invite_and_matches():
    h = await BotHarness(seed_ids=[]).start()
    try:
        # A не в паре → онбординг с кнопкой
        await h.send_text(USER_A, "/start")
        assert any("Создать список" in b for b in h.button_texts(USER_A))

        token = await _make_invite(h, USER_A)
        await h.send_text(USER_B, f"/start join_{token}")

        # оба в одной активной паре
        async with h.sf() as s:
            pa = await repo.active_pair_id(s, USER_A)
            pb = await repo.active_pair_id(s, USER_B)
        assert pa is not None and pa == pb

        # B — подтверждение, A — уведомление о присоединении
        assert any("паре" in (m.text or "").lower() for m in h.messages(USER_B))
        assert any("присоединил" in (m.text or "").lower() for m in h.messages(USER_A))
    finally:
        await h.stop()


async def test_cannot_join_own_link():
    h = await BotHarness(seed_ids=[]).start()
    try:
        token = await _make_invite(h, USER_A)
        await h.send_text(USER_A, f"/start join_{token}")
        assert "твоя же ссылка" in h.last_text(USER_A).lower()
    finally:
        await h.stop()


async def test_used_invite_rejects_third_user():
    h = await BotHarness(seed_ids=[]).start()
    try:
        token = await _make_invite(h, USER_A)
        await h.send_text(USER_B, f"/start join_{token}")
        # третий по той же (уже использованной) ссылке
        await h.send_text(333, f"/start join_{token}")
        last = h.last_text(333).lower()
        assert "недействительна" in last or "устарела" in last
    finally:
        await h.stop()


async def test_paired_after_match_can_add_and_notify():
    """После мэтчинга работает основной сценарий: добавление + уведомление."""
    h = await BotHarness(seed_ids=[]).start()
    try:
        token = await _make_invite(h, USER_A)
        await h.send_text(USER_B, f"/start join_{token}")
        h.clear_inbox()

        await h.add_item(USER_A, "Место", "Парк у реки")
        # B (партнёр) получил уведомление
        assert any("Парк у реки" in (m.text or "") for m in h.messages(USER_B))
    finally:
        await h.stop()
