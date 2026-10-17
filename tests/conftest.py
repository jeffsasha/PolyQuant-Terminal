from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from polyquant.clock import FakeClock
from polyquant.interfaces import MemorySink

FIXTURES = Path(__file__).parent / "fixtures" / "gateway"


def load(name: str) -> dict:
    """Load a recorded gateway response exactly as the client decodes it (numbers as Decimal)."""
    return json.loads((FIXTURES / name).read_bytes(), parse_float=Decimal)


def utc(*args: int) -> datetime:
    return datetime(*args, tzinfo=UTC)


@pytest.fixture
def sink() -> MemorySink:
    return MemorySink(keep=10_000)


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock(utc(2026, 10, 17, 5, 40, 0))


# ---- database ------------------------------------------------------------------------------------

TEST_DB = os.environ.get("POLYQUANT_TEST_DATABASE_URL")


@pytest.fixture
async def pool():
    if not TEST_DB:
        pytest.skip("POLYQUANT_TEST_DATABASE_URL not set")
    import asyncpg

    from polyquant.recorder.db import create_pool, migrate

    conn = await asyncpg.connect(TEST_DB)
    try:
        await conn.execute("DROP SCHEMA public CASCADE; CREATE SCHEMA public;")
        await migrate(conn)
    finally:
        await conn.close()
    p = await create_pool(TEST_DB)
    yield p
    await p.close()
