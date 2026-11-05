"""Robust anomaly detection for per-key hourly spend.

Compares each hourly bucket against the same hour-of-day across the trailing
window (median + MAD), which keeps the baseline tight for strongly
seasonal traffic — precisely the shape LLM gateway traffic has.
"""
from __future__ import annotations

import statistics
from typing import Any


def _robust_z(x: float, samples: list[float]) -> float:
    if len(samples) < 4:
        return 0.0
    med = statistics.median(samples)
    mad = statistics.median([abs(s - med) for s in samples])
    scale = mad * 1.4826 if mad > 1e-9 else max(med * 0.5, 0.5)
    if scale <= 1e-9:
        scale = 0.5
    return abs(x - med) / scale


def detect(hourly: list[dict[str, Any]], *, threshold: float = 3.5,
           min_cost: float = 0.75, trailing_hours: int = 48) -> list[dict[str, Any]]:
    """Flag anomalous buckets in the trailing window.

    Returns dicts: {hour, cost, baseline, ratio, z}.
    """
    if not hourly:
        return []
    by_slot: dict[int, list[float]] = {h: [] for h in range(24)}
    for b in hourly:
        by_slot[int(b["hour"] // 3600) % 24].append(float(b.get("cost", 0.0)))

    anomalies: list[dict[str, Any]] = []
    trailing = hourly[-trailing_hours:]
    for b in trailing:
        hour = int(b["hour"])
        cost = float(b.get("cost", 0.0))
        if cost < min_cost:
            continue
        slot = (hour // 3600) % 24
        others = list(by_slot[slot])
        try:
            others.remove(cost)
        except ValueError:
            pass
        baseline = statistics.median(others) if others else 0.0
        z = _robust_z(cost, others)
        if z >= threshold and baseline > 0 and cost > baseline * 1.8:
            anomalies.append({
                "hour": hour,
                "cost": round(cost, 4),
                "baseline": round(baseline, 4),
                "ratio": round(cost / baseline, 2),
                "z": round(z, 2),
            })
    return anomalies
