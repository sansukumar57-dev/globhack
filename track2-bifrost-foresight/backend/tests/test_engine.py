"""Pure-function tests for the forecast and anomaly engines."""
from __future__ import annotations

import pytest
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


# ------------------------------------------------------------ burn / helpers

def test_burn_rate_empty_series_is_zero():
    assert forecast.burn_rate([], 6) == 0.0


def test_burn_rate_shorter_series_uses_what_exists():
    hourly = make_hourly(3.0, 3)  # 3 buckets of $1
    assert abs(forecast.burn_rate(hourly, 24) - 1.0) < 1e-6


def test_window_bounds_is_rolling_30d():
    lo, hi = forecast.window_bounds(now=1_000_000.0)
    assert hi == 1_000_000.0
    assert abs((hi - lo) - forecast.WINDOW_SECONDS) < 1e-6


def test_trend_is_positive_for_ramping_traffic():
    # Day d costs (d+1) * 0.5/h → daily totals 12, 24, …, 84.
    day0 = int(time.time() // 86400) * 86400
    hourly = []
    for d in range(7):
        for h in range(24):
            hourly.append({"hour": day0 + d * 86400 + h * 3600,
                           "cost": (d + 1) * 0.5, "requests": 1, "tokens": 10})
    assert abs(forecast.linear_trend_pct_per_day(hourly) - 25.0) < 0.1


def test_trend_flat_is_zero_and_needs_four_days():
    # day-aligned buckets keep every daily total identical
    day0 = int(time.time() // 86400) * 86400
    flat = [{"hour": day0 + h * 3600, "cost": 1.0, "requests": 1, "tokens": 10}
            for h in range(24 * 7)]
    assert abs(forecast.linear_trend_pct_per_day(flat)) < 0.05
    one_day = [{"hour": day0 + h * 3600, "cost": 1.0, "requests": 1, "tokens": 10}
               for h in range(24)]
    assert forecast.linear_trend_pct_per_day(one_day) == 0.0  # < 4 days
    assert forecast.linear_trend_pct_per_day([]) == 0.0


def test_trend_zero_spend_is_zero():
    hourly = [{"hour": h, "cost": 0.0, "requests": 0, "tokens": 0}
              for h in range(0, 24 * 7 * 3600, 3600)]
    assert forecast.linear_trend_pct_per_day(hourly) == 0.0


def test_stability_labels():
    flat = make_hourly(48.0, 48)  # $1/h
    assert forecast.stability_label(flat) == "steady"
    alt = []
    for h in range(48):
        alt.append({"hour": h * 3600, "cost": 1.0 if h % 2 == 0 else 9.0,
                    "requests": 1, "tokens": 10})
    assert forecast.stability_label(alt) == "volatile"
    bursty = [{"hour": h * 3600, "cost": 4.0 if h % 4 == 0 else 0.0,
               "requests": 1, "tokens": 10} for h in range(48)]
    assert forecast.stability_label(bursty) == "erratic"
    assert forecast.stability_label(make_hourly(12.0, 10)) == "unknown"  # too short
    zeros = [{"hour": h, "cost": 0.0, "requests": 0, "tokens": 0} for h in range(0, 96 * 3600, 3600)]
    assert forecast.stability_label(zeros) == "steady"  # zero-mean doesn't divide by zero


def test_forecast_without_history_is_honest():
    f = forecast.forecast(budget_usd=100.0, spent_usd=50.0, hourly=[], now=0.0)
    assert f["burn_rate_effective"] == 0.0
    assert f["hours_until_exhaustion"] is None
    assert f["exhaustion_ts"] is None
    assert f["status"] == "healthy"  # no projection fire without a burn signal


def test_forecast_watch_on_projection_not_usage():
    hourly = make_hourly(48.0, 24)  # $2/h → 30d projection $1440 ≫ $400 budget
    f = forecast.forecast(budget_usd=400.0, spent_usd=10.0, hourly=hourly,
                          now=time.time())
    assert f["status"] == "watch"       # far from exhaustion, but the 30d projection overshoots
    assert f["projected_30d_cost"] == pytest.approx(1440.0, abs=4.0)


def test_overall_severity_picks_worst_status():
    assert forecast.overall_severity(["healthy", "watch", "critical"]) == "critical"
    assert forecast.overall_severity(["watch", "exhausted"]) == "exhausted"
    assert forecast.overall_severity([]) == "healthy"
    assert forecast.overall_severity(["gibberish"]) == "healthy"


# ------------------------------------------------ seasonal anomaly awareness

def test_anomaly_baseline_is_same_hour_of_day_not_fleet_wide():
    """Business hours burn 50x overnight traffic; only a same-slot spike flags.

    A fleet-wide (non-seasonal) baseline would page every normal business
    hour; the same-hour-of-day baseline must stay quiet.
    """
    business = {1, 2, 3, 4, 5, 6, 7, 8}  # UTC slots treated as business hours
    end_hour = int(time.time() // 3600) * 3600
    hourly = []
    for i in range(200, 0, -1):
        h = end_hour - (i - 1) * 3600
        cost = 5.0 if (h // 3600) % 24 in business else 0.1
        hourly.append({"hour": h, "cost": cost, "requests": 1, "tokens": 100})

    # most recent business hour inside the trailing window
    spike_hour = next(h for h in range(end_hour - 3600, end_hour - 48 * 3600, -3600)
                      if (h // 3600) % 24 in business)
    hourly = [{**b, "cost": 45.0} if b["hour"] == spike_hour else b for b in hourly]

    flagged = anomaly.detect(hourly, threshold=3.0, min_cost=0.5)
    assert len(flagged) == 1
    assert flagged[0]["hour"] == spike_hour
    assert flagged[0]["baseline"] == pytest.approx(5.0)
    assert flagged[0]["ratio"] == pytest.approx(9.0)


def test_anomaly_ignores_sub_floor_buckets():
    end_hour = int(time.time() // 3600) * 3600
    hourly = make_hourly(0.4, 48)  # $0.01/h buckets, never above min_cost
    hourly[-1] = {**hourly[-1], "cost": 0.45}
    assert anomaly.detect(hourly, threshold=3.0, min_cost=0.75) == []


def test_anomaly_empty_series():
    assert anomaly.detect([], threshold=3.0, min_cost=0.75) == []
