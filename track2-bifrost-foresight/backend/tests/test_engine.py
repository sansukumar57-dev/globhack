"""Pure-function tests for the forecast and anomaly engines."""
from __future__ import annotations

import time

from foresight import anomaly, forecast


def make_hourly(total: float, hours: int = 168, now: float | None = None) -> list[dict]:
    now = now if now is not None else time.time()
    end_hour = int(now // 3600) * 3600
    per_hour = total / hours
    return [{"hour": end_hour - (hours - 1 - i) * 3600, "cost": per_hour,
             "requests": 10, "tokens": 5000} for i in range(hours)]


def test_burn_rate_average():
    hourly = make_hourly(24.0, 24)
    assert abs(forecast.burn_rate(hourly, 6) - 1.0) < 1e-6
    assert abs(forecast.burn_rate(hourly, 24) - 1.0) < 1e-6


def test_exhaustion_projected():
    hourly = make_hourly(48.0, 24)  # $2/h over the last 24h
    f = forecast.forecast(budget_usd=100.0, spent_usd=96.0, hourly=hourly,
                          now=time.time(), alert_horizon_hours=48.0)
    assert f["status"] == "critical"
    assert f["hours_until_exhaustion"] is not None
    assert 1.0 < f["hours_until_exhaustion"] < 3.0
    assert f["pct_used"] == 0.96


def test_healthy_when_far_from_budget():
    hourly = make_hourly(1.0, 24)
    f = forecast.forecast(budget_usd=1000.0, spent_usd=10.0, hourly=hourly, now=time.time())
    assert f["status"] == "healthy"


def test_exhausted_budget_caps_out():
    hourly = make_hourly(1.0, 24)
    f = forecast.forecast(budget_usd=10.0, spent_usd=11.0, hourly=hourly, now=time.time())
    assert f["status"] == "exhausted"
    assert f["remaining_usd"] == 0.0


def test_spike_older_than_six_hours_still_drives_eta():
    hourly = make_hourly(24.0, 24)  # $1/h
    hourly[-10] = {**hourly[-10], "cost": 10.0}  # spike 10h ago: outside 6h, inside 24h
    f = forecast.forecast(budget_usd=100.0, spent_usd=95.0, hourly=hourly,
                          now=time.time(), alert_horizon_hours=48.0)
    assert f["burn_rate_6h"] == 1.0
    assert f["burn_rate_24h"] > 1.0
    assert f["burn_rate_effective"] == f["burn_rate_24h"]
    assert abs(f["hours_until_exhaustion"] - round(5.0 / f["burn_rate_24h"], 2)) < 1e-6
    assert f["status"] == "critical"


def test_anomaly_flags_spike_only():
    base = 1.0
    hourly = make_hourly(base * 200, 200)
    spike_hour = hourly[-10]["hour"]
    hourly[-10] = {**hourly[-10], "cost": base * 9}
    flagged = anomaly.detect(hourly, threshold=3.0, min_cost=0.5)
    assert any(a["hour"] == spike_hour for a in flagged)
    assert all(a["cost"] >= base * 1.8 for a in flagged)
