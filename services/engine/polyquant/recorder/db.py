"""Connection pool and ordered, transactional SQL migrations."""

from __future__ import annotations

import logging
from importlib import resources

import asyncpg

log = logging.getLogger(__name__)

MIGRATIONS_PACKAGE = "polyquant.recorder.migrations"
LOCK_KEY = 0x504F4C59  # pg_advisory_lock key so two processes never migrate concurrently


def migration_files() -> list[tuple[str, str]]:
    root = resources.files(MIGRATIONS_PACKAGE)
    files = sorted(p for p in root.iterdir() if p.name.endswith(".sql"))
    return [(p.name, p.read_text(encoding="utf-8")) for p in files]


async def migrate(conn: asyncpg.Connection) -> list[str]:
    applied: list[str] = []
    await conn.execute("SELECT pg_advisory_lock($1)", LOCK_KEY)
    try:
        await conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations (name text PRIMARY KEY, applied_at timestamptz NOT NULL"
            " DEFAULT now())"
        )
        done = {r["name"] for r in await conn.fetch("SELECT name FROM schema_migrations")}
        for name, sql in migration_files():
            if name in done:
                continue
            async with conn.transaction():
                await conn.execute(sql)
                await conn.execute("INSERT INTO schema_migrations (name) VALUES ($1)", name)
            applied.append(name)
            log.info("applied migration %s", name)
    finally:
        await conn.execute("SELECT pg_advisory_unlock($1)", LOCK_KEY)
    return applied


async def create_pool(dsn: str) -> asyncpg.Pool:
    return await asyncpg.create_pool(dsn, min_size=1, max_size=4, command_timeout=30)
