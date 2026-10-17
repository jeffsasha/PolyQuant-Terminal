"""Command line: `polyquant db-migrate | run | status | verify-references`."""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import logging
import signal
import sys
from datetime import UTC, datetime, timedelta

from polyquant.config import LIVE_TRADING_ENABLED, Settings
from polyquant.logsetup import setup_logging

log = logging.getLogger("polyquant")


def _secrets(settings: Settings) -> list[str]:
    return [s.get_secret_value() for s in (settings.polymarket_us_key_id, settings.polymarket_us_secret_key) if s]


async def cmd_migrate(settings: Settings) -> int:
    import asyncpg

    from polyquant.recorder.db import migrate

    conn = await asyncpg.connect(settings.database_url)
    try:
        applied = await migrate(conn)
    finally:
        await conn.close()
    print(f"applied: {applied or 'nothing (up to date)'}")
    return 0


async def cmd_run(settings: Settings, *, api: bool, duration_s: float | None) -> int:
    from polyquant.engine import Engine
    from polyquant.recorder.db import create_pool, migrate
    from polyquant.recorder.store import RecorderSink, latest_index_ts
    from polyquant.venue.gateway import GatewayClient

    assert LIVE_TRADING_ENABLED is False
    log.info("PolyQuant starting in PAPER mode (live trading disabled in code). Credentials present: %s; "
             "markets WebSocket: %s", settings.has_credentials,
             "on" if settings.has_credentials and settings.ws_enabled else "off (REST BBO only)")
    pool = await create_pool(settings.database_url)
    async with pool.acquire() as conn:
        await migrate(conn)
    recorder = RecorderSink(pool, book_levels=settings.book_record_levels)
    recorder.start()
    gateway = GatewayClient(max_rps=settings.gateway_max_rps, timeout_s=settings.http_timeout_s)
    engine = Engine(settings, gateway, recorder)
    engine.reference.resume_from(await latest_index_ts(pool, settings.asset))
    paper = None
    if settings.paper_enabled:
        from polyquant.fees.schedule import FeeSchedule
        from polyquant.paper.engine import PaperExecutionEngine
        from polyquant.paper.ledger import PostgresLedger
        from polyquant.paper.risk import CentralRiskManager, RiskConfig

        paper = PaperExecutionEngine(PostgresLedger(pool, settings.paper_account), engine, engine.sink, engine.clock,
                                     fees=FeeSchedule(maker_tier=settings.maker_fee_tier),
                                     risk=CentralRiskManager(RiskConfig(
                                         starting_capital=settings.paper_starting_capital)),
                                     profile=settings.paper_profile, day_tz=settings.paper_day_tz)
        await paper.start()
        engine.add_loop("paper", settings.paper_step_interval_s, paper.step)
        log.info("paper trading on: account %s, profile %s, equity %s", settings.paper_account, paper.profile.name,
                 paper.equity())

    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        with contextlib.suppress(NotImplementedError):
            loop.add_signal_handler(sig, stop.set)
    if duration_s:
        loop.call_later(duration_s, stop.set)

    server_task = None
    if api:
        import uvicorn

        from polyquant.api.app import create_app

        app = create_app(engine, paper)
        server = uvicorn.Server(uvicorn.Config(app, host=settings.api_host, port=settings.api_port,
                                               log_level="warning", lifespan="off"))
        server.install_signal_handlers = lambda: None  # we own signals
        server_task = asyncio.create_task(server.serve())
        log.info("read-only API on http://%s:%d", settings.api_host, settings.api_port)
    try:
        await engine.run(stop)
    finally:
        if server_task:
            server.should_exit = True
            await server_task
        await recorder.stop()
        await gateway.aclose()
        await pool.close()
        log.info("stopped. recorder wrote %d events, dropped %d, write errors %d",
                 recorder.written, recorder.dropped, recorder.write_errors)
    return 0


async def cmd_status(settings: Settings) -> int:
    from polyquant.recorder.db import create_pool
    from polyquant.recorder.store import counts

    pool = await create_pool(settings.database_url)
    try:
        for k, v in (await counts(pool)).items():
            print(f"{k:22s} {v}")
        async with pool.acquire() as conn:
            rows = await conn.fetch("SELECT kind, count(*) n FROM data_quality_events GROUP BY kind ORDER BY n DESC")
            print("quality events:", {r["kind"]: r["n"] for r in rows})
            row = await conn.fetchrow("SELECT min(ts), max(ts) FROM index_points")
            print("index range:", row[0], "→", row[1])
    finally:
        await pool.close()
    return 0


async def cmd_verify(settings: Settings, *, hours: float) -> int:
    """Re-checks the empirical reference rule (RESEARCH_AUDIT §1.3) against resolved markets."""
    from polyquant.domain.settlement import check_references, outcome_from_settlement_flag, reference_ts
    from polyquant.domain.timeutil import to_unix
    from polyquant.venue.gateway import GatewayClient
    from polyquant.venue.parsing import (
        is_target_market,
        iter_event_markets,
        parse_index_points,
        parse_instrument,
    )

    now = datetime.now(UTC)
    ok = bad = 0
    async with GatewayClient(max_rps=settings.gateway_max_rps) as gw:
        seen: dict[str, object] = {}
        for closed in (True, False):
            resp = await gw.events(closed=closed, end_min=(now - timedelta(hours=hours)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                                   end_max=now.strftime("%Y-%m-%dT%H:%M:%SZ"))
            for ev, m in iter_event_markets(resp.data):
                if is_target_market(m, settings.asset, settings.horizons):
                    inst = parse_instrument(m, event_slug=ev)
                    if inst.settlement_price is not None:
                        seen[inst.slug] = inst
        for inst in sorted(seen.values(), key=lambda i: i.window_start):
            series = {}
            for t in (inst.window_start, inst.window_end):
                rt = to_unix(reference_ts(t))
                r = await gw.index_history(settings.asset, rt - 1, rt)
                for p in parse_index_points(r.data, asset=settings.asset, recv_at=r.recv_at):
                    series[p.ts] = p.value
            flag_resp = await gw.settlement(inst.slug)
            flag = flag_resp.data.get("settlement") if flag_resp.ok else None
            checks = check_references(inst, series)
            good = all(c.matches for c in checks) and (
                flag is None or outcome_from_settlement_flag(int(flag)) == inst.settled_outcome())
            ok += good
            bad += not good
            if not good:
                print("MISMATCH", inst.slug, [(c.kind, c.official, c.derived) for c in checks], "flag", flag)
    print(f"verified {ok} / {ok + bad} resolved markets in the last {hours}h")
    return 0 if bad == 0 else 1


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="polyquant", description="PolyQuant Terminal engine (PAPER mode only)")
    p.add_argument("--log-level", default="INFO")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("db-migrate", help="apply database migrations")
    r = sub.add_parser("run", help="run discovery, pollers and recorder (+ read-only API)")
    r.add_argument("--no-api", action="store_true")
    r.add_argument("--duration", type=float, default=None, help="stop after N seconds")
    sub.add_parser("status", help="show recorded data counts")
    v = sub.add_parser("verify-references", help="re-verify the reference-price rule on resolved markets")
    v.add_argument("--hours", type=float, default=3.0)
    args = p.parse_args(argv)

    settings = Settings()
    setup_logging(args.log_level, _secrets(settings))
    if args.cmd == "db-migrate":
        coro = cmd_migrate(settings)
    elif args.cmd == "run":
        coro = cmd_run(settings, api=not args.no_api, duration_s=args.duration)
    elif args.cmd == "status":
        coro = cmd_status(settings)
    else:
        coro = cmd_verify(settings, hours=args.hours)
    return asyncio.run(coro)


if __name__ == "__main__":
    sys.exit(main())
