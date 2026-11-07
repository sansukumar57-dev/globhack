"""Trained spend-intelligence model — one artifact, three heads.

v2: a bootstrap committee of gradient-boosted regressors trained on
Foresight's own metered hourly buckets (per virtual key). One artifact
powers all of the desk's trained intelligence:

1. Forecast: committee median of recursive next-hour predictions, plus a
   p10-p90 band taken across member paths (choir disagreement = spread).
2. Breach risk: per key, the share of member paths whose cumulative
   projected spend crosses the remaining soft-cap budget inside the alert
   horizon — an ensemble-implied probability, no hand labels.
3. Expected-cost anomalies: a deeper expectation head scores every recent
   hour as (actual - expected) / validation residual sigma.

The artifact is written to backend/models/ and the 100 MB budget from the
problem constraints is treated as a hard ceiling, enforced at save time.
Governance ETAs in forecast.py stay statistical by design; this model
shapes the curve, the band, the risk signal and the residual scan.
Every loader degrades gracefully: no artifact, no sklearn, or too little
history simply returns "not available" and the console falls back.
"""
from __future__ import annotations

import math
import time
from pathlib import Path
from typing import Any

ARTIFACT = Path(__file__).resolve().parent.parent / "models" / "spend_intelligence_v2.joblib"
MAX_ARTIFACT_BYTES = 100 * 1024 * 1024  # hard ceiling: 100 MB
VERSION = 2
ALGORITHM = "HistGradientBoosting committee (multi-head)"
FEATURES = [
    "hour_sin", "hour_cos", "day_of_week", "key_id",
    "lag_1h", "lag_24h", "lag_168h", "roll_mean_6h", "roll_mean_24h",
]
SKILLS = ["forecast band", "breach risk", "expected-cost anomalies"]

_loaded: dict[str, Any] = {"mtime": None, "artifact": None}
_intel_cache: dict[str, Any] = {"ts": 0.0, "key": None, "data": None}
_scan_cache: dict[str, Any] = {"ts": 0.0, "key": None, "data": None}
_intel_build = {"running": False}
_scan_build = {"running": False}
_stress_cache: dict[str, Any] = {"ts": 0.0, "key": None, "data": None}


def _percentile(sorted_vals: list[float], p: float) -> float:
    if not sorted_vals:
        return 0.0
    k = (len(sorted_vals) - 1) * p
    f = math.floor(k)
    c = min(f + 1, len(sorted_vals) - 1)
    return sorted_vals[f] + (sorted_vals[c] - sorted_vals[f]) * (k - f)


def _mtime() -> float:
    try:
        return ARTIFACT.stat().st_mtime
    except OSError:
        return 0.0


CACHE_TTL_SECONDS = 1800  # the committee rollout costs seconds; refresh rarely, not every poll


def _intel_cached_fresh(steps: int, horizon: int) -> Any:
    if _intel_cache["key"] == (int(time.time() // 3600) * 3600, round(_mtime(), 3), steps, horizon) \
            and time.time() - _intel_cache["ts"] < CACHE_TTL_SECONDS:
        return _intel_cache["data"]
    return None


def intelligence_cached(steps: int = 12, *, horizon: int = 48) -> dict[str, Any] | None:
    """Non-blocking twin of intelligence(): serve the cache if fresh, else kick off
    one background build and return None (the console polls again in seconds)."""
    cached = _intel_cached_fresh(steps, horizon)
    if cached is not None:
        return cached
    if _intel_build["running"]:
        return None
    _intel_build["running"] = True
    import threading
    def _build() -> None:
        try:
            intelligence(steps=steps, horizon=horizon)
        except Exception:
            pass
        finally:
            _intel_build["running"] = False
    threading.Thread(target=_build, daemon=True).start()
    return None


def _scan_cached_fresh(hours: int, top: int) -> Any:
    if _scan_cache["key"] == (int(time.time() // 3600) * 3600, round(_mtime(), 3), hours, top) \
            and time.time() - _scan_cache["ts"] < CACHE_TTL_SECONDS:
        return _scan_cache["data"]
    return None


def anomaly_scan_cached(hours: int = 48, *, top: int = 12) -> list[dict[str, Any]] | None:
    """Non-blocking twin of anomaly_scan(): cache-or-background-build."""
    cached = _scan_cached_fresh(hours, top)
    if cached is not None:
        return cached
    if _scan_build["running"]:
        return None
    _scan_build["running"] = True
    import threading
    def _build() -> None:
        try:
            anomaly_scan(hours=hours, top=top)
        except Exception:
            pass
        finally:
            _scan_build["running"] = False
    threading.Thread(target=_build, daemon=True).start()
    return None


# ---------------------------------------------------------------- featurising

def _features(hour: int, key_id: int, lag1: float, lag24: float, lag168: float,
              roll6: float, roll24: float) -> list[float]:
    hod = (hour // 3600) % 24  # epoch hours are UTC; consistent across train/inference
    return [
        math.sin(2 * math.pi * hod / 24.0),
        math.cos(2 * math.pi * hod / 24.0),
        (hour // 86400) % 7,
        float(key_id),
        lag1, lag24, lag168, roll6, roll24,
    ]


def _training_rows(series_by_key: dict[str, list[dict[str, Any]]], val_hours: int):
    X: list[list[float]] = []
    y: list[float] = []
    v_X: list[list[float]] = []
    v_y: list[float] = []
    v_naive: list[float] = []
    key_ids = {vk: i for i, vk in enumerate(sorted(series_by_key))}
    per_key: dict[str, dict[str, Any]] = {}
    for vk, series in series_by_key.items():
        costs = {int(b["hour"]): float(b.get("cost") or 0.0) for b in series}
        hours = sorted(costs)
        n = len(hours)
        if n < 48:
            continue  # not enough contiguous history from this key
        val_start = max(24, n - val_hours)
        per_key[vk] = {"hours": hours, "costs": [costs[h] for h in hours], "val_start": val_start}
        for i in range(1, n):
            h = hours[i]
            lag1 = costs[hours[i - 1]]
            lag24 = costs[hours[i - 24]] if i >= 24 else 0.0
            lag168 = costs[hours[i - 168]] if i >= 168 else 0.0
            win6 = [costs[hours[j]] for j in range(max(0, i - 6), i)]
            win24 = [costs[hours[j]] for j in range(max(0, i - 24), i)]
            feats = _features(h, key_ids[vk], lag1, lag24, lag168,
                              sum(win6) / len(win6), sum(win24) / len(win24))
            target = costs[h]
            if i >= val_start:
                v_X.append(feats)
                v_y.append(target)
                naive = lag168 if i >= 168 else (lag24 if i >= 24 else 0.0)
                v_naive.append(naive)
            else:
                X.append(feats)
                y.append(target)
    return X, y, v_X, v_y, v_naive, per_key, key_ids


def _calibrate_band(per_key: dict[str, dict[str, Any]], key_ids: dict[str, int],
                    committee: list, *, origins_count: int = 12, max_steps: int = 24):
    """Rolling-origin backtest through the committee for the p10-p90 band.

    Runs multi-step recursive forecasts from `origins_count` evenly spaced
    origins across the held-out window, collects the fleet error at each
    step, then derives the per-step 80% band width on alternating origins
    and measures how often the actual landed inside the band on the rest
    (out-of-sample coverage). Returns (band_q80, coverage) or (None, None)
    when the window layout makes the backtest meaningless.
    """
    import numpy as np
    if not per_key or not committee:
        return None, None
    vks = list(per_key)
    n = len(per_key[vks[0]]["hours"])
    base_hours = per_key[vks[0]]["hours"]
    vs = per_key[vks[0]]["val_start"]
    for vk in vks:
        info = per_key[vk]
        if len(info["hours"]) != n or info["val_start"] != vs:
            return None, None  # need one shared zero-filled time grid
    lo = max(vs, 24)
    hi = n - 2
    if hi <= lo:
        return None, None
    span = hi - lo
    origins = sorted({int(round(lo + span * k / (origins_count - 1)))
                      for k in range(origins_count)})
    errs: dict[int, list[list[float]]] = {o: [[] for _ in range(max_steps)] for o in origins}
    histories = {vk: per_key[vk]["costs"] for vk in vks}
    for origin in origins:
        smax = min(max_steps, n - 1 - origin)
        if smax <= 0:
            continue
        for member in committee:
            states = [{"vk": vk, "key_id": key_ids[vk],
                       "known": list(histories[vk][:origin + 1])} for vk in vks]
            for j in range(1, smax + 1):
                hour = base_hours[origin] + j * 3600
                rows = []
                for st in states:
                    known = st["known"]
                    lag1 = known[-1]
                    lag24 = known[-24] if len(known) >= 24 else 0.0
                    lag168 = known[-168] if len(known) >= 168 else 0.0
                    roll6 = sum(known[-6:]) / min(6, len(known))
                    roll24 = sum(known[-24:]) / min(24, len(known))
                    rows.append(_features(hour, st["key_id"], lag1, lag24, lag168, roll6, roll24))
                preds = member.predict(rows)
                fleet = 0.0
                for st, p in zip(states, preds):
                    p = max(float(p), 0.0)
                    st["known"].append(p)
                    fleet += p
                actual = sum(histories[vk][origin + j] for vk in vks)
                errs[origin][j - 1].append(fleet - actual)

    def _q80(vals: list[float]) -> float:
        if not vals:
            return 0.0
        return float(np.percentile(np.abs(np.asarray(vals)), 80))

    cal_origins = origins[0::2]
    test_origins = origins[1::2] or origins[0::2]
    band_q80 = []
    for j in range(max_steps):
        cal_vals = [e for o in cal_origins for e in errs[o][j]]
        band_q80.append(round(_q80(cal_vals), 4))
    hits = total = 0
    for o in test_origins:
        for j in range(max_steps):
            for e in errs[o][j]:
                total += 1
                if abs(e) <= band_q80[j]:
                    hits += 1
    coverage = (hits / total) if total else None
    return band_q80, coverage


# ---------------------------------------------------------------------- train

def train(series_by_key: dict[str, list[dict[str, Any]]], *,
          val_hours: int = 72, committee_size: int = 24, seed: int = 7) -> dict[str, Any]:
    """Train the committee + expectation heads, validate time-ordered, save."""
    try:
        import joblib
        import numpy as np
        from sklearn.ensemble import HistGradientBoostingRegressor
    except Exception as exc:  # pragma: no cover - environment without ML deps
        raise RuntimeError(f"scikit-learn is required to train: {exc}") from exc

    X, y, v_X, v_y, v_naive, per_key, key_ids = _training_rows(series_by_key, val_hours)
    if len(X) < 60:
        raise ValueError(
            f"Not enough history to train (got {len(X)} supervised rows, need 60+). "
            "Keep metering traffic or reseed the demo fleet first."
        )

    X_arr = np.asarray(X, dtype=np.float64)
    y_arr = np.asarray(y, dtype=np.float64)
    cat_idx = [FEATURES.index("key_id")]
    common = dict(learning_rate=0.07, max_leaf_nodes=31, min_samples_leaf=10,
                  l2_regularization=0.5, early_stopping=False, random_state=seed,
                  categorical_features=cat_idx)

    # Forecast committee: bootstrap replicates, each member a full boosted ensemble.
    committee = []
    rng = np.random.default_rng(seed)
    for b in range(committee_size):
        member = HistGradientBoostingRegressor(max_iter=200, **common)
        member.random_state = seed + b
        rows = rng.integers(0, len(X_arr), size=len(X_arr))
        member.fit(X_arr[rows], y_arr[rows])
        committee.append(member)

    # Expectation head: deeper single model for the anomaly residual scan.
    expect = HistGradientBoostingRegressor(max_iter=320, **common)
    expect.random_state = seed + 991
    expect.fit(X_arr, y_arr)

    val_mae = val_wape = baseline_mae = val_coverage = resid_sigma = 0.0
    band_q80: list[float] | None = None
    if v_X:
        v_arr = np.asarray(v_X, dtype=np.float64)
        v_y_arr = np.asarray(v_y, dtype=np.float64)
        member_pred = np.vstack([m.predict(v_arr) for m in committee])
        mean_pred = member_pred.mean(axis=0)
        errs = np.abs(mean_pred - v_y_arr)
        val_mae = float(errs.mean())
        val_wape = float(errs.sum() / max(float(v_y_arr.sum()), 1e-9))
        baseline_mae = float(np.mean(np.abs(np.asarray(v_naive) - v_y_arr)))
        r = v_y_arr - expect.predict(v_arr)
        resid_sigma = float(r.std()) or float(np.abs(r).mean())
        if resid_sigma <= 1e-6:
            resid_sigma = 1e-6
        band_q80, val_coverage = _calibrate_band(per_key, key_ids, committee)

    trained_at = time.time()
    all_hours = [int(b["hour"]) for s in series_by_key.values() for b in s]
    hours_covered = ((max(all_hours) - min(all_hours)) // 3600 + 1) if all_hours else 0
    artifact = {
        "version": VERSION,
        "algorithm": ALGORITHM,
        "features": FEATURES,
        "keys": sorted(series_by_key),
        "trained_at": trained_at,
        "hours_covered": hours_covered,
        "n_train": len(X),
        "n_val": len(v_X),
        "val_mae": round(val_mae, 4),
        "val_wape": round(val_wape, 4),
        "baseline_mae": round(baseline_mae, 4),
        "val_coverage": round(val_coverage, 4),
        "band_q80": band_q80,
        "committee_size": committee_size,
        "anomaly_resid_sigma": round(resid_sigma, 4),
        "max_horizon_steps": 48,
        "committee": committee,
        "expect": expect,
        "resid_sigma": resid_sigma,
    }
    ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(artifact, ARTIFACT)
    size = ARTIFACT.stat().st_size
    if size > MAX_ARTIFACT_BYTES:  # pragma: no cover - guard on the stated budget
        ARTIFACT.unlink(missing_ok=True)
        raise RuntimeError(f"artifact {size} bytes exceeds the {MAX_ARTIFACT_BYTES}-byte budget")
    _loaded["mtime"], _loaded["artifact"] = None, None  # force reload
    try:
        intelligence_cached()  # kick background refresh on the NEW artifact mtime
        anomaly_scan_cached()
    except Exception:
        pass
    result = {k: v for k, v in artifact.items()
              if k not in ("committee", "expect", "resid_sigma")}
    result["artifact_bytes"] = size
    result["artifact"] = ARTIFACT.name
    return result


def retrain_from_store() -> dict[str, Any]:
    """Convenience for the API: pull the live 30-day per-key series."""
    from . import store
    now = time.time()
    series = {}
    for key in store.list_keys():
        series[key["vk"]] = store.hourly_series(key["vk"], now - 30 * 86400, now)
    return train(series)


# ----------------------------------------------------------------------- load

def load() -> dict[str, Any] | None:
    """Load the artifact if present (cached by mtime). Never raises."""
    if not ARTIFACT.exists():
        return None
    try:
        mtime = ARTIFACT.stat().st_mtime
        if _loaded["mtime"] != mtime:
            import joblib
            _loaded["artifact"] = joblib.load(ARTIFACT)
            _loaded["mtime"] = mtime
        return _loaded["artifact"]
    except Exception:
        return None


def status() -> dict[str, Any]:
    art = load()
    base = {
        "loaded": art is not None,
        "algorithm": ALGORITHM,
        "artifact": ARTIFACT.name,
        "max_artifact_bytes": MAX_ARTIFACT_BYTES,
        "features": FEATURES,
        "skills": SKILLS,
    }
    if art is None:
        base["note"] = "No trained artifact. Governance falls back to statistical burn-rate projection."
        return base
    base.update({
        "trained_at": art["trained_at"],
        "hours_covered": art.get("hours_covered"),
        "n_train": art.get("n_train"),
        "n_val": art.get("n_val"),
        "val_mae": art.get("val_mae"),
        "val_wape": art.get("val_wape"),
        "baseline_mae": art.get("baseline_mae"),
        "val_coverage": art.get("val_coverage"),
        "committee_size": art.get("committee_size"),
        "anomaly_resid_sigma": art.get("anomaly_resid_sigma"),
        "keys": art.get("keys"),
        "artifact_bytes": ARTIFACT.stat().st_size,
        "under_budget": ARTIFACT.stat().st_size <= MAX_ARTIFACT_BYTES,
    })
    return base


# ------------------------------------------------------------------- predict

def _member_paths(member, states: list[dict[str, Any]], now_hour: int,
                  steps: int) -> tuple[list[float], dict[str, list[float]]]:
    """One member's recursive run: fleet totals per step plus per-key paths.

    `states` is mutated (each key's `known` grows with its own predictions),
    so callers pass fresh copies of the state list per member.
    """
    totals = [0.0] * steps
    per_key: dict[str, list[float]] = {st["vk"]: [0.0] * steps for st in states}
    for j in range(1, steps + 1):
        hour = now_hour + j * 3600
        rows = []
        for st in states:
            known = st["known"]
            lag1 = known[-1]
            lag24 = known[-24] if len(known) >= 24 else 0.0
            # lag168 lands strictly inside the trailing window for steps <= 24;
            # at longer horizons it becomes recursive, which widens the band honestly
            lag168 = known[-168] if len(known) >= 168 else 0.0
            roll6 = sum(known[-6:]) / min(6, len(known))
            roll24 = sum(known[-24:]) / min(24, len(known))
            rows.append(_features(hour, st["key_id"], lag1, lag24, lag168, roll6, roll24))
        preds = member.predict(rows)
        for st, p in zip(states, preds):
            p = max(float(p), 0.0)
            st["known"].append(p)
            totals[j - 1] += p
            per_key[st["vk"]][j - 1] = p
    return totals, per_key


def _rollout(states: list[dict[str, Any]], members: list, now_hour: int,
             total_steps: int) -> list[tuple[list[float], dict[str, list[float]]]]:
    """Run the recursive rollout for every member, concurrently.

    Returns one (fleet path, per-key paths) tuple per member, in the same
    order as `members`.
    """
    from concurrent.futures import ThreadPoolExecutor

    def _run_member(member):
        member_states = [{k: (list(v) if isinstance(v, list) else v) for k, v in s.items()}
                         for s in states]
        return _member_paths(member, member_states, now_hour, total_steps)

    if len(members) > 1:
        with ThreadPoolExecutor(max_workers=min(4, len(members))) as pool:
            return list(pool.map(_run_member, members))
    return [_run_member(members[0])]


def stress_projection(stress_vk: str, multiplier: float, *,
                      steps: int = 24,
                      series_by_key: dict[str, list[dict[str, Any]]] | None = None,
                      budgets: dict[str, float] | None = None,
                      now: float | None = None) -> dict[str, Any] | None:
    """Counterfactual rollout: "what if `stress_vk` ran at `multiplier`× its
    current spend shape?".

    Only the *recursive history* the target key sees is scaled; metered history
    and remaining-cap figures always use the unscaled metered data. Returns the
    fleet curve (p50 median + p10–p90 band) and per-key breach probabilities
    under both demand regimes. None when no artifact exists.
    """
    try:
        art = load()
        if art is None:
            return None
        multiplier = max(0.1, min(8.0, float(multiplier or 1.0)))
        now = time.time() if now is None else now
        now_hour = int(now // 3600) * 3600
        known_keys = list(art["keys"])
        if stress_vk not in known_keys:
            return None
        key_ids = {vk: i for i, vk in enumerate(known_keys)}

        cache_key = (now_hour, round(_mtime(), 3), stress_vk, round(multiplier, 4), steps)
        live = series_by_key is None and budgets is None
        if live:
            if _stress_cache["key"] == cache_key and now - _stress_cache["ts"] < CACHE_TTL_SECONDS:
                return _stress_cache["data"]
            from . import store
            budgets = {k["vk"]: float(k.get("budget_usd") or 0.0) for k in store.list_keys()}
        else:
            series_by_key = {vk: s for vk, s in (series_by_key or {}).items() if vk in key_ids}
            budgets = budgets or {}

        def evaluate(scaled: bool) -> dict[str, Any] | None:
            states = []
            feed = series_by_key
            if live:
                from . import store
                feed = {vk: store.hourly_series(vk, now_hour - 30 * 86400, now) for vk in known_keys}
            for vk in known_keys:
                series = (feed or {}).get(vk)
                if not series:
                    continue
                costs = [float(b["cost"] or 0.0) for b in series]
                if not costs or sum(costs) <= 0.0 or sum(costs[-36:]) <= 0.0:
                    continue
                known = list(costs)
                if scaled and vk == stress_vk:
                    known = [c * multiplier for c in costs]
                states.append({"vk": vk, "key_id": key_ids[vk], "known": known,
                               "history": costs})
            if not states:
                return None
            rollout = _rollout(states, art["committee"], now_hour, steps)
            fleet_paths = [r[0] for r in rollout]
            key_member_paths = {s["vk"]: [r[1][s["vk"]] for r in rollout] for s in states}
            band_q = art.get("band_q80") or []

            pts = []
            for j in range(steps):
                vals = sorted(p[j] for p in fleet_paths)
                median = _percentile(vals, 0.5)
                half_spread = max(_percentile(vals, 0.9) - median, median - _percentile(vals, 0.1))
                width = half_spread
                if j < len(band_q) and band_q[j] is not None:
                    width = max(width, float(band_q[j]))
                pts.append({
                    "hour": now_hour + (j + 1) * 3600,
                    "cost": round(median, 4),
                    "p10": round(max(median - width, 0.0), 4),
                    "p90": round(median + width, 4),
                })
            fleet = sum(p["cost"] for p in pts)
            risk = {}
            for s in states:
                vk = s["vk"]
                budget = float(budgets.get(vk) or 0.0)
                if budget <= 0:
                    continue
                history = s["history"]
                remaining = budget - sum(history[-24 * 30:])
                cums = sorted(sum(p[:steps]) for p in key_member_paths[vk])
                median_cum = cums[len(cums) // 2]
                breaches = sum(1 for c in cums if c >= remaining) if remaining > 0 else len(cums)
                risk[vk] = {"remaining_usd": round(remaining, 2),
                            "median_cum": round(median_cum, 2),
                            f"p_{steps}h": round(breaches / len(cums), 3)}
            return {"curve": pts, "fleet_24h": round(fleet, 2), "risk": risk}

        base = evaluate(False)
        stressed = evaluate(True)
        if base is None or stressed is None:
            return None
        out = {
            "multiplier": multiplier, "stress_vk": stress_vk, "steps": steps,
            "algorithm": art["algorithm"], "committee": art.get("committee_size"),
            "baseline": base, "stressed": stressed,
            "delta_fleet_24h": round(stressed["fleet_24h"] - base["fleet_24h"], 2),
            "delta_pct": round(stressed["fleet_24h"] / max(base["fleet_24h"], 1e-9) * 100 - 100, 1),
        }
        if live:
            _stress_cache.update(ts=now, key=cache_key, data=out)
        return out
    except Exception:
        return None


def intelligence(steps: int = 12, *, horizon: int = 48,
                 series_by_key: dict[str, list[dict[str, Any]]] | None = None,
                 budgets: dict[str, float] | None = None,
                 now: float | None = None,
                 min_history_hours: int = 36) -> dict[str, Any] | None:
    """Run all heads: forecast band, per-key breach probabilities.

    Returns None when no artifact exists or nothing can be scored.
    `series_by_key` / `budgets` are injectable for tests; when omitted both
    come from the live store (30-day trailing series per training key).
    """
    try:
        art = load()
        if art is None:
            return None
        now = time.time() if now is None else now
        now_hour = int(now // 3600) * 3600
        known_keys = list(art["keys"])
        live = series_by_key is None and budgets is None
        if live:
            from . import store
            cache_key = (now_hour, round(_mtime(), 3), steps, horizon)
            if _intel_cache["key"] == cache_key and now - _intel_cache["ts"] < CACHE_TTL_SECONDS:
                return _intel_cache["data"]
            series_by_key = {vk: store.hourly_series(vk, now_hour - 30 * 86400, now)
                             for vk in known_keys}
            budgets = {k["vk"]: float(k.get("budget_usd") or 0.0) for k in store.list_keys()}

        key_ids = {vk: i for i, vk in enumerate(known_keys)}
        states = []
        for vk, series in series_by_key.items():
            if vk not in key_ids:
                continue
            costs = [float(b["cost"] or 0.0) for b in series]
            if not costs or sum(costs) <= 0.0 or sum(costs[-min_history_hours:]) <= 0.0:
                continue  # key has no metered history in the trailing window
            states.append({"vk": vk, "key_id": key_ids[vk], "known": costs,
                           "history": costs})
        if not states:
            return None

        # Warm the recursion once per member, capped at what the heads were trained for.
        total_steps = min(max(steps, horizon), int(art.get("max_horizon_steps", 48)))
        rollout = _rollout(states, art["committee"], now_hour, total_steps)
        fleet_paths: list[list[float]] = [r[0] for r in rollout]   # member -> fleet total per step
        key_member_paths: dict[str, list[list[float]]] = {s["vk"]: [] for s in states}
        for _totals, per_key in rollout:
            for vk, path in per_key.items():
                key_member_paths[vk].append(path)

        band_q = art.get("band_q80") or []
        points = []
        for j in range(steps):
            step_vals = sorted(p[j] for p in fleet_paths)
            median = _percentile(step_vals, 0.5)
            half_spread = max(_percentile(step_vals, 0.9) - median, median - _percentile(step_vals, 0.1))
            width = half_spread
            if j - 1 < len(band_q) and band_q[j - 1] is not None:
                width = max(width, float(band_q[j - 1]))
            points.append({
                "hour": now_hour + (j + 1) * 3600,
                "cost": round(median, 4),
                "p10": round(max(median - width, 0.0), 4),
                "p90": round(median + width, 4),
            })

        # Breach risk from the same member paths: how many members' cumulative
        # projected spend for a key crosses its remaining soft-cap budget
        # inside 24h / the alert horizon.
        risk: dict[str, dict[str, Any]] | None = None if budgets is None else {}
        if risk is not None:
            for s in states:
                vk = s["vk"]
                budget = float(budgets.get(vk) or 0.0)
                if budget <= 0:
                    continue
                history = s["history"]
                window_spend = sum(history[-24 * 30:])
                remaining = budget - window_spend
                entry = {
                    "remaining_usd": round(remaining, 2),
                    "p_24h": None,
                    f"p_{horizon}h": None,
                }
                for h, key_p, key_m in (
                    (24, "p_24h", "median_cum_24h"),
                    (horizon, f"p_{horizon}h", f"median_cum_{horizon}h"),
                ):
                    hh = min(h, total_steps)
                    if hh <= 0:
                        continue
                    cums = sorted(sum(path[:hh]) for path in key_member_paths[vk])
                    entry[key_m] = round(cums[len(cums) // 2], 2)
                    breaches = sum(1 for c in cums if c >= remaining)
                    entry[key_p] = 1.0 if remaining <= 0 else round(breaches / len(cums), 3)
                risk[vk] = entry

        meta = {
            "trained_at": art["trained_at"],
            "algorithm": art["algorithm"],
            "val_mae": art.get("val_mae"),
            "val_coverage": art.get("val_coverage"),
            "committee": art.get("committee_size"),
            "hours": steps,
            "keys_used": len(states),
            "horizon": horizon,
        }
        data = {"forecast": points, "forecast_meta": meta, "risk": risk,
                "paths": [p[:steps] for p in fleet_paths]}
        if live:
            _intel_cache.update(ts=now, key=cache_key, data=data)
        return data
    except Exception:
        return None


def anomaly_scan(hours: int = 48, *, series_by_key: dict[str, list[dict[str, Any]]] | None = None,
                 now: float | None = None, top: int = 12) -> list[dict[str, Any]] | None:
    """Score recent hourly buckets against the trained expectation head.

    z = (actual - expected) / validation residual sigma. Only upper
    residuals matter (spend spikes), so entries below z=1 are dropped.
    Returns None when there is no trained model.
    """
    try:
        art = load()
        if art is None:
            return None
        now = time.time() if now is None else now
        now_hour = int(now // 3600) * 3600
        live = series_by_key is None
        key_ids = {vk: i for i, vk in enumerate(art["keys"])}
        if live:
            from . import store
            cache_key = (now_hour, round(_mtime(), 3), hours, top)
            if _scan_cache["key"] == cache_key and now - _scan_cache["ts"] < CACHE_TTL_SECONDS:
                return _scan_cache["data"]
            series_by_key = {vk: store.hourly_series(vk, now_hour - hours * 3600, now)
                             for vk in art["keys"]}

        expect = art["expect"]
        sigma = float(art.get("resid_sigma") or 1e-6) or 1e-6
        scan_start = now_hour - hours * 3600 + 3600
        out: list[dict[str, Any]] = []
        for vk, series in series_by_key.items():
            if vk not in key_ids:
                continue
            hours_list = [int(b["hour"]) for b in series]
            costs = [float(b["cost"] or 0.0) for b in series]
            n = len(hours_list)
            for i in range(1, n):
                h = hours_list[i]
                if h < scan_start:
                    continue
                actual = costs[i]
                if actual <= 0.0:
                    continue
                lag1 = costs[i - 1]
                lag24 = costs[i - 24] if i >= 24 else 0.0
                lag168 = costs[i - 168] if i >= 168 else 0.0
                roll6 = sum(costs[max(0, i - 6):i]) / max(min(6, i), 1)
                roll24 = sum(costs[max(0, i - 24):i]) / max(min(24, i), 1)
                expected = float(expect.predict(
                    [_features(h, key_ids[vk], lag1, lag24, lag168, roll6, roll24)])[0])
                model_z = (actual - expected) / sigma
                if model_z < 1.0:
                    continue
                out.append({"vk": vk, "hour": h, "actual": round(actual, 4),
                            "expected": round(expected, 4), "model_z": round(model_z, 2),
                            "key_id": key_ids[vk]})
        out.sort(key=lambda r: r["model_z"], reverse=True)
        out = out[:top]
        if live:
            _scan_cache.update(ts=now, key=cache_key, data=out)
        return out
    except Exception:
        return None
