"""Versioned Polymarket US fee schedule (docs.polymarket.us/fees, read 2026-10-17).

Exact Decimal arithmetic throughout. Rules implemented:

- Taker fee per fill:  Θ_taker · C · p · (1 − p), with p the trade price of the instrument (long side). The formula is
  symmetric in p, so Up and Down fills of the same trade carry the same fee.
- Maker rebate per fill: Θ_maker · C · p · (1 − p) (Θ_maker ≤ 0, i.e. a credit), credited at the fill. Tiered by
  prior-month maker volume from 2026-10-19 13:00 ET; Tier 1 (< $10M) receives **no** rebate.
- Rounding: every fee/rebate is rounded to $0.01 with banker's rounding (ROUND_HALF_EVEN). For a multi-fill
  aggressive order, each fill's charge is reduced if needed so the order's total never exceeds the banker's rounding
  of the cumulative exact fee ("the adjustment can only reduce a fill's charge, never increase it").
- Taker rebates are paid weekly on prior-month volume (periodic, not per fill). They are tracked as a separate,
  unrealised item and never netted into per-trade PnL.
- No fee at settlement (the docs only mention fees on executed trades).

Unknown history: the standard schedule is documented as effective from 2026-10-07 10:00 ET. Earlier timestamps raise
`FeeScheduleUnknown` rather than silently applying today's rates to the past.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import ROUND_HALF_EVEN, Decimal
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
CENT = Decimal("0.01")
ZERO = Decimal(0)
ONE = Decimal(1)


class FeeScheduleUnknown(LookupError):
    pass


def bankers_cents(x: Decimal) -> Decimal:
    return x.quantize(CENT, rounding=ROUND_HALF_EVEN)


def capped_taker_charge(exact: Decimal, cum_exact_before: Decimal,
                        collected_before: Decimal) -> tuple[Decimal, Decimal, Decimal]:
    """Charge for one taker fill of a multi-fill order: the fill's banker's-rounded fee, reduced (never increased) so
    the order's total never exceeds the banker's rounding of its cumulative exact fee.
    Returns (charge, cum_exact_after, collected_after)."""
    cum = cum_exact_before + exact
    charge = max(ZERO, min(bankers_cents(exact), bankers_cents(cum) - collected_before))
    return charge, cum, collected_before + charge


@dataclass(frozen=True, slots=True)
class FeeVersion:
    name: str
    effective_from: datetime  # aware
    taker_theta: Decimal
    # maker rebate coefficient by maker tier (1-based). Values ≤ 0 (credits).
    maker_theta_by_tier: dict[int, Decimal]
    # taker rebate fraction by taker tier (periodic, informational only)
    taker_rebate_by_tier: dict[int, Decimal] = field(default_factory=dict)
    notes: str = ""

    def maker_theta(self, tier: int) -> Decimal:
        if tier not in self.maker_theta_by_tier:
            raise FeeScheduleUnknown(f"{self.name}: no maker tier {tier}")
        return self.maker_theta_by_tier[tier]


def _et(y: int, m: int, d: int, hh: int, mm: int = 0) -> datetime:
    return datetime(y, m, d, hh, mm, tzinfo=ET)


# Ordered by effective_from. Values verbatim from docs.polymarket.us/fees (2026-10-17).
DEFAULT_VERSIONS: tuple[FeeVersion, ...] = (
    FeeVersion(
        name="2026-10-07-standard",
        effective_from=_et(2026, 10, 7, 10),
        taker_theta=Decimal("0.0695"),
        # Standard maker rebate -0.0125 for all makers. The "additional 17% weekly crypto maker rebate" (ended
        # 2026-10-15 08:00 ET) was a weekly program, not a per-fill rate, so it is deliberately not modelled.
        maker_theta_by_tier={1: Decimal("-0.0125"), 2: Decimal("-0.0125"), 3: Decimal("-0.0125"),
                             4: Decimal("-0.0125")},
        taker_rebate_by_tier={1: ZERO, 2: Decimal("0.10"), 3: Decimal("0.25"), 4: Decimal("0.50")},
        notes="Taker rebate tiers: <$250k none, $250k-1M 10%, $1M-10M 25%, $10M+ 50% (weekly).",
    ),
    FeeVersion(
        name="2026-10-15-crypto-bonus-ended",
        effective_from=_et(2026, 10, 15, 8),
        taker_theta=Decimal("0.0695"),
        maker_theta_by_tier={1: Decimal("-0.0125"), 2: Decimal("-0.0125"), 3: Decimal("-0.0125"),
                             4: Decimal("-0.0125")},
        taker_rebate_by_tier={1: ZERO, 2: Decimal("0.10"), 3: Decimal("0.25"), 4: Decimal("0.50")},
    ),
    FeeVersion(
        name="2026-10-19-volume-tiers",
        effective_from=_et(2026, 10, 19, 13),
        taker_theta=Decimal("0.0695"),
        maker_theta_by_tier={1: ZERO, 2: Decimal("-0.0035"), 3: Decimal("-0.0070"), 4: Decimal("-0.0104")},
        taker_rebate_by_tier={1: ZERO, 2: Decimal("0.03"), 3: Decimal("0.05"), 4: Decimal("0.10"),
                              5: Decimal("0.15"), 6: Decimal("0.30")},
        notes="Maker tiers by prior-month maker volume: <$10M, $10-50M, $50-200M, $200M+. Launch-day tiers use the "
              "higher of Sep volume or 4x Oct 12-18 volume; monthly resets from Nov 1 (ET calendar month).",
    ),
)


@dataclass(frozen=True, slots=True)
class FillFee:
    exact: Decimal  # unrounded (positive = charge, negative = rebate)
    charged: Decimal  # rounded amount actually debited (negative = credit)
    version: str
    theta: Decimal
    liquidity: str  # "taker" | "maker"


class FeeSchedule:
    """Implements interfaces.FeeModel. `maker_tier` defaults to 1, the tier a small account is in."""

    def __init__(self, versions: tuple[FeeVersion, ...] = DEFAULT_VERSIONS, *, maker_tier: int = 1,
                 taker_tier: int = 1) -> None:
        if not versions:
            raise ValueError("no fee versions")
        self.versions = tuple(sorted(versions, key=lambda v: v.effective_from))
        self.maker_tier = maker_tier
        self.taker_tier = taker_tier

    def version_at(self, at: datetime) -> FeeVersion:
        if at.tzinfo is None:
            raise ValueError("naive datetime")
        current = None
        for v in self.versions:
            if v.effective_from <= at:
                current = v
            else:
                break
        if current is None:
            raise FeeScheduleUnknown(f"no documented fee schedule before {self.versions[0].effective_from} ({at})")
        return current

    @staticmethod
    def _base(qty: Decimal, price: Decimal) -> Decimal:
        if not (ZERO < price < ONE):
            raise ValueError(f"price {price} outside (0, 1)")
        if qty <= 0:
            raise ValueError("qty must be positive")
        return qty * price * (ONE - price)

    def taker_fee(self, qty: Decimal, price: Decimal, at: datetime) -> Decimal:
        """Rounded taker fee for a single fill (FeeModel protocol)."""
        v = self.version_at(at)
        return bankers_cents(v.taker_theta * self._base(qty, price))

    def maker_rebate(self, qty: Decimal, price: Decimal, at: datetime) -> Decimal:
        """Rounded maker amount for one fill (≤ 0 means a credit)."""
        v = self.version_at(at)
        return bankers_cents(v.maker_theta(self.maker_tier) * self._base(qty, price))

    def order_fills(self, fills: list[tuple[Decimal, Decimal]], at: datetime, *, liquidity: str,
                    theta_override: Decimal | None = None) -> list[FillFee]:
        """Fees for all fills of one order, applying the cumulative cap for taker fills.

        `theta_override` lets the caller apply a market-specific coefficient (e.g. a higher one from market metadata).
        """
        v = self.version_at(at)
        if liquidity == "taker":
            theta = theta_override if theta_override is not None else v.taker_theta
        elif liquidity == "maker":
            theta = v.maker_theta(self.maker_tier)
        else:
            raise ValueError(liquidity)
        out: list[FillFee] = []
        cum_exact = ZERO
        collected = ZERO
        for qty, price in fills:
            exact = theta * self._base(qty, price)
            if liquidity == "taker":
                charge, cum_exact, collected = capped_taker_charge(exact, cum_exact, collected)
            else:
                charge = bankers_cents(exact)
            out.append(FillFee(exact=exact, charged=charge, version=v.name, theta=theta, liquidity=liquidity))
        return out

    def taker_rebate_fraction(self, at: datetime) -> Decimal:
        """Periodic (weekly) taker rebate fraction for the configured tier. Informational; not netted per trade."""
        v = self.version_at(at)
        return v.taker_rebate_by_tier.get(self.taker_tier, ZERO)
