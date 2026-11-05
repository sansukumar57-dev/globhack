"""Burn-rate forecasting and budget projection.

Pure functions over hourly bucket series so they are trivially testable.
Budgets are modelled as rolling 30-day caps (same model as Bifrost's
reset_duration rolling windows), which keeps projections honest for both
calendar-aligned and mid-month budgets.
"""
from __future__ import annotations

import math
import time
from typing import Any

WINDOW_SECONDS = 30 * 86400


def window_bounds(now: float | None = None) -> tuple[float, float]:
    now = now if now is not None else time.time()
    return now - WINDOW_SECONDS, now


def burn_rate(hourly: list[dict[str, Any]], hours: int) -> float:
    """Average USD/hour cost over the trailing `hours` buckets."""
    if not hourly:
        return 0.0
    window = hourly[-hours:]
    return sum(float(b.get("cost", 0.0)) for b in window) / max(len(window), 1)


def linear_trend_pct_per_day(hourly: list[dict[str, Any]]) -> float:
    """Least-squares slope of daily totals, expressed as % of daily mean per day."""
    days: dict[int, float] = {}
    for b in hourly:
        day = int(b["hour"] // 86400)
        days[day] = days.get(day, 0.0) + float(b.get("cost", 0.0))
    ys = [days[d] for d in sorted(days)]
    n = len(ys)
    if n < 4:
        return 0.0
    mean_y = sum(ys) / n
    if mean_y <= 1e-9:
        return 0.0
    xs = list(range(n))
    mean_x = sum(xs) / n
    denom = sum((x - mean_x) ** 2 for x in xs)
    if denom == 0:
        return 0.0
    slope = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys)) / denom
    return (slope / mean_y) * 100.0


def stability_label(hourly: list[dict[str, Any]]) -> str:
    costs = [float(b.get("cost", 0.0)) for b in hourly[-336:]]  # 14 days
    n = len(costs)
    if n < 24:
        return "unknown"
    mean = sum(costs) / n
    if mean <= 1e-9:
        return "steady"
    var = sum((c - mean) ** 2 for c in costs) / n
    cv = math.sqrt(var) / mean
    if cv < 0.75:
        return "steady"
    if cv < 1.4:
        return "volatile"
    return "erratic"


def forecast(*, budget_usd: float, spent_usd: float, hourly: list[dict[str, Any]],
             now: float | None = None, alert_horizon_hours: float = 48.0) -> dict[str, Any]:
    now = now if now is not None else time.time()
    burn_1h = burn_rate(hourly, 1)
    burn_6h = burn_rate(hourly, 6)
    burn_24h = burn_rate(hourly, 24)
    remaining = max(budget_usd - spent_usd, 0.0)
    pct_used = (spent_usd / budget_usd) if budget_usd > 0 else 0.0
    projected_30d = burn_24h * 24 * 30.0

    effective_burn = burn_6h if burn_6h > 0 else burn_24h
    exhaustion_hours: float | None = None
    if effective_burn > 1e-6:
        exhaustion_hours = remaining / effective_burn

    exhaustion_ts = now + exhaustion_hours * 3600 if exhaustion_hours is not None else None

    if pct_used >= 1.0:
        status = "exhausted"
    elif exhaustion_hours is not None and exhaustion_hours <= alert_horizon_hours:
        status = "critical"
    elif pct_used >= 0.70 or projected_30d > budget_usd:
        status = "watch"
    else:
        status = "healthy"

    return {
        "budget_usd": round(budget_usd, 2),
        "spent_usd": round(spent_usd, 4),
        "remaining_usd": round(remaining, 4),
        "pct_used": round(pct_used, 4),
        "burn_rate_1h": round(burn_1h, 4),
        "burn_rate_6h": round(burn_6h, 4),
        "burn_rate_24h": round(burn_24h, 4),
        "projected_30d_cost": round(burn_24h * 24 * 30, 2),
        "hours_until_exhaustion": round(exhaustion_hours, 2) if exhaustion_hours is not None else None,
        "exhaustion_ts": exhaustion_ts,
        "status": status,
        "stability": stability_label(hourly),
        "trend_pct_per_day": round(linear_trend_pct_per_day(hourly), 2),
    }


def overall_severity(statuses: list[str]) -> str:
    order = {"exhausted": 4, "critical": 3, "watch": 2, "healthy": 1, "unknown": 0}
    worst = max((order.get(s, 0) for s in statuses), default=0)
    return {4: "exhausted", 3: "critical", 2: "watch", 1: "healthy", 0: "healthy"}[worst]
