"""Pytest-фикстуры для тестового стенда."""

from __future__ import annotations

import pytest_asyncio

from tests.harness import BotHarness


@pytest_asyncio.fixture
async def harness() -> BotHarness:
    h = await BotHarness().start()
    try:
        yield h
    finally:
        await h.stop()
