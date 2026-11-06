"""Synthetic 21-day history seeder.

Anchors a deterministic RNG to wall-clock so every demo run shows the same
story: Growth Backend inflected upward eight days ago, spiked 4.6x its 14:00
baseline, and is projected to exhaust its 30-day budget within two days —
exactly the situation Bifrost's static 100% cap cannot see coming.

seed() resets the demo dataset (usage events, alerts, sink, policy fires) and
rebuilds it. Live traffic is wiped along with the seed; do not run in prod.
"""
from __future__ import annotations

import math
import random
import time
from datetime import datetime, timezone
from typing import Any

from . import anomaly, store
from .pricing import price_for

DEMO_KEYS: list[dict[str, Any]] = [
    {"vk": "sk-bf-foresight-growth-0001", "name": "Growth Backend · prod", "team": "Platform",
     "budget": 500.0, "policy": "soft_cap", "downgrade_to": "gpt-4o-mini",
     "color": "#f472b6", "target_cost": 430.0, "trend": 0.55, "model": "acme-llm/gpt-4o"},
    {"vk": "sk-bf-foresight-support-0002", "name": "Support Agent Fleet", "team": "Support",
     "budget": 800.0, "policy": "pacing", "downgrade_to": "gpt-4o-mini",
     "color": "#7c5cff", "target_cost": 585.0, "trend": 0.18, "model": "acme-llm/gpt-4o"},
    {"vk": "sk-bf-foresight-staging-0003", "name": "Staging CI", "team": "Platform",
     "budget": 150.0, "policy": "notify", "downgrade_to": "gpt-4o-mini",
     "color": "#38bdf8", "target_cost": 38.0, "trend": 0.0, "model": "acme-llm/gpt-4o-mini"},
    {"vk": "sk-bf-foresight-sandbox-0004", "name": "Hackathon Sandbox", "team": "R&D",
     "budget": 50.0, "policy": "observe", "downgrade_to": "",
     "color": "#34d399", "target_cost": 3.0, "trend": 0.0, "model": "acme-llm/gpt-4o-mini"},
]

HOURS = 21 * 24


def _hour_weight(hour_of_day: int, weekday: int, trend: float, week_idx: float) -> float:
    # Weekly shape
    weekend = weekday >= 5
    day_mult = 0.32 if weekend else 1.0
    # Business-hours hump
    if 8 <= hour_of_day <= 19:
        hump = 1.0 + 0.5 * math.sin(math.pi * (hour_of_day - 8) / 11)
    else:
        hump = 0.14
    trend_mult = 1.0 + trend * week_idx
    return day_mult * hump * trend_mult


def _tokens_for_cost(model: str, cost: float) -> tuple[int, int]:
    pin, pout = price_for(model)
    # Assume ~70% of spend is output tokens (code-heavy agent traffic)
    out_share = 0.7
    ct = int(cost * out_share / pout * 1e6)
    pt = int(cost * (1 - out_share) / pin * 1e6) if pin > 0 else 0
    return pt, ct


def seed(now: float | None = None) -> dict[str, Any]:
    now = now if now is not None else time.time()
    rng = random.Random(42)
    store.clear_usage()
    store.clear_alerts()
    store.sink_clear()
    with store._lock, store.connect() as conn:
        conn.execute("DELETE FROM policy_fires")

    end_hour = int(now // 3600) * 3600
    start_hour = end_hour - (HOURS - 1) * 3600

    meta = {"events": 0, "keys": []}
    # Anchor the spike to the most recent 14:00 UTC. Seeding at 03:00 used to
    # put the "4.6x spike" in the dead of night, where it was invisible on the
    # 24h chart and barely moved the burn rate.
    anomaly_hour = end_hour - ((int(end_hour // 3600) - 14) % 24) * 3600

    for spec in DEMO_KEYS:
        weights: list[float] = []
        hours: list[int] = []
        t = start_hour
        for i in range(HOURS):
            ts = t + i * 3600
            week_idx = i / (24 * 7)  # 0..3 over the window
            dt = datetime.fromtimestamp(ts, tz=timezone.utc)
            hour_of_day = dt.hour
            weekday = dt.weekday()  # Monday=0 ... Sunday=6
            w = _hour_weight(hour_of_day, weekday, spec["trend"], week_idx)
            w *= rng.uniform(0.72, 1.34)
            if ts == anomaly_hour and spec["vk"] == "sk-bf-foresight-growth-0001":
                # Anchor to the 14:00 weekday baseline so the spike lands at a
                # predictable, high-traffic point regardless of seed time.
                w = _hour_weight(14, 2, spec["trend"], week_idx) * 4.6
            weights.append(w)
            hours.append(ts)

        total_w = sum(weights)
        scale = spec["target_cost"] / total_w if total_w else 0.0

        for i, w in enumerate(weights):
            cost = w * scale
            if cost <= 0:
                continue
            pt, ct = _tokens_for_cost(spec["model"], cost)
            reqs = max(1, int(cost / 0.028))
            latency = int(rng.uniform(140, 420))
            store.insert_event(spec["vk"], spec["model"], pt, ct, cost, latency,
                               source="seed", exact=True, ts=hours[i] + rng.uniform(60, 3500))
            meta["events"] += 1

        store.upsert_key(spec["vk"], spec["name"], spec["team"], spec["budget"],
                         policy=spec["policy"], downgrade_to=spec["downgrade_to"], color=spec["color"])
        meta["keys"].append({"vk": spec["vk"], "name": spec["name"], "target_cost": spec["target_cost"]})

    # Seeded alert history: the story the dashboard should tell on first paint
    growth = DEMO_KEYS[0]
    detected = anomaly.detect(store.hourly_series(growth["vk"], now - HOURS * 3600, now))
    hit = next((a for a in detected if int(a["hour"]) == anomaly_hour), None)
    ratio = hit["ratio"] if hit else 4.6
    z = hit["z"] if hit else 0.0
    store.insert_alert(
        growth["vk"], "anomaly", "critical",
        f"Traffic anomaly on Growth Backend · prod ({ratio:g}× baseline)",
        f"Hour bucket flagged at {ratio:g}x the same-hour-of-day median over 21 days "
        f"(robust z={z}). Possible runaway agent loop after a deploy window.",
        {"ratio": ratio, "seeded": True}, ts=anomaly_hour + 240)
    store.insert_alert(
        growth["vk"], "horizon_alert", "critical",
        "Budget for Growth Backend · prod is on a projected breach",
        "At the current burn rate the rolling 30-day window runs dry before "
        "it resets. Bifrost's static cap only trips at 100%.",
        {"seeded": True}, ts=anomaly_hour + 300)
    store.insert_alert(
        "sk-bf-foresight-support-0002", "budget_75", "warning",
        "Support Agent Fleet at 73% of 30d budget",
        "Rolling 30-day spend $585 of $800. Trend +18% over 21 days — pacing "
        "policy will downgrade to gpt-4o-mini when projected exhaustion ≤ 24h.",
        {"pct_used": 0.73, "seeded": True}, ts=now - 26 * 3600)

    store.sink_record(
        {"Content-Type": "application/json", "User-Agent": "bifrost-foresight/0.1"},
        '{"text":":warning: *Support Agent Fleet at 73% of 30d budget*",'
        '"attachments":[{"color":"#fbbf24","fields":[{"title":"key","value":"Support Agent Fleet"},'
        '{"title":"policy","value":"pacing"}],"footer":"Bifrost Foresight · predictive governance"}]}')
    store.sink_record(
        {"Content-Type": "application/json", "User-Agent": "bifrost-foresight/0.1"},
        f'{{"text":":red_circle: *Traffic anomaly on Growth Backend · prod ({ratio:g}× baseline)*",'
        f'"attachments":[{{"color":"#fb7185","fields":[{{"title":"key","value":"Growth Backend · prod"}},'
        f'{{"title":"policy","value":"soft_cap"}}],"footer":"Bifrost Foresight · predictive governance"}}]}}')

    return meta


if __name__ == "__main__":
    import json
    print(json.dumps(seed(), indent=2))
