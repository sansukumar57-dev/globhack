"""Compact trained forecaster for gateway spend.

Trains a small gradient-boosted regressor on Foresight's own metered hourly
buckets (per virtual key) to predict spend for the next hours. The artifact
is written to backend/models/ and is deliberately tiny — the 100 MB budget in
the problem constraints is treated as a hard ceiling, and a few hundred KB of
boosted trees is enough for this signal.

Governance keeps using the conservative statistical ETA in forecast.py; this
model shapes the *curve* (next-hour desk look-ahead) rather than the verdict.
Every loader degrades gracefully: no artifact, no sklearn, or too little
history simply returns "not available" and the console falls back.
"""
from __future__ import annotations

import math
import time
from pathlib import Path
from typing import Any

ARTIFACT = Path(__file__).resolve().parent.parent / "models" / "spend_forecaster_v1.joblib"
MAX_ARTIFACT_BYTES = 100 * 1024 * 1024  # hard ceiling: 100 MB
VERSION = 1
ALGORITHM = "HistGradientBoostingRegressor"
FEATURES = [
    "hour_sin", "hour_cos", "day_of_week", "key_id",
    "lag_1h", "lag_24h", "lag_168h", "roll_mean_6h", "roll_mean_24h",
]

_loaded: dict[str, Any] = {"mtime": None, "artifact": None}
_fc_cache: dict[str, Any] = {"ts": 0.0, "key": None, "data": None, "meta": None}


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
    for vk, series in series_by_key.items():
        costs = {int(b["hour"]): float(b.get("cost") or 0.0) for b in series}
        hours = sorted(costs)
        n = len(hours)
        if n < 48:
            continue  # not enough contiguous history from this key
        val_start = max(24, n - val_hours)
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
    return X, y, v_X, v_y, v_naive


# ---------------------------------------------------------------------- train

def train(series_by_key: dict[str, list[dict[str, Any]]], *,
          max_iter: int = 160, val_hours: int = 72) -> dict[str, Any]:
    """Train on per-key hourly buckets, validate time-ordered, save artifact."""
    try:
        import joblib
        from sklearn.ensemble import HistGradientBoostingRegressor
    except Exception as exc:  # pragma: no cover - environment without ML deps
        raise RuntimeError(f"scikit-learn is required to train: {exc}") from exc

    X, y, v_X, v_y, v_naive = _training_rows(series_by_key, val_hours)
    if len(X) < 60:
        raise ValueError(
            f"Not enough history to train (got {len(X)} supervised rows, need 60+). "
            "Keep metering traffic or reseed the demo fleet first."
        )

    cat_idx = [FEATURES.index("key_id")]
    mdl = HistGradientBoostingRegressor(
        max_iter=max_iter, learning_rate=0.08, max_leaf_nodes=15,
        min_samples_leaf=10, l2_regularization=0.5, random_state=7,
        categorical_features=cat_idx,
    )
    import numpy as np
    mdl.fit(np.asarray(X, dtype=np.float64), np.asarray(y, dtype=np.float64))

    val_mae = 0.0
    val_wape = 0.0
    baseline_mae = 0.0
    if v_X:
        pred = mdl.predict(v_X)
        errs = [abs(p - t) for p, t in zip(pred, v_y)]
        val_mae = sum(errs) / len(errs)
        val_wape = sum(errs) / max(sum(v_y), 1e-9)
        baseline_mae = sum(abs(n - t) for n, t in zip(v_naive, v_y)) / len(v_y)

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
        "model": mdl,
    }
    ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(artifact, ARTIFACT)
    size = ARTIFACT.stat().st_size
    if size > MAX_ARTIFACT_BYTES:  # pragma: no cover - guard on the stated budget
        ARTIFACT.unlink(missing_ok=True)
        raise RuntimeError(f"artifact {size} bytes exceeds the {MAX_ARTIFACT_BYTES}-byte budget")
    _loaded["mtime"], _loaded["artifact"] = None, None  # force reload
    result = {k: v for k, v in artifact.items() if k != "model"}
    result["artifact_bytes"] = size
    result["artifact"] = ARTIFACT.name
    return result


def retrain_from_store() -> dict[str, Any]:
    """Convenience for the API: pull live per-key series out of the store."""
    from . import store
    now = time.time()
    series = {}
    for key in store.list_keys():
        series[key["vk"]] = store.hourly_series(key["vk"], now - 14 * 86400, now)
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
        "keys": art.get("keys"),
        "artifact_bytes": ARTIFACT.stat().st_size,
        "under_budget": ARTIFACT.stat().st_size <= MAX_ARTIFACT_BYTES,
    })
    return base


# ------------------------------------------------------------------- predict

def _recursive_key_preds(costs: list[float], hours0: int, key_id: int,
                         mdl, steps: int) -> list[float]:
    """Predict `steps` future hours for one key, feeding lag_1h recursively."""
    known = list(costs)
    out: list[float] = []
    for j in range(1, steps + 1):
        hour = hours0 + j * 3600
        lag1 = known[-1]
        lag24 = known[-24] if len(known) >= 24 else 0.0
        # lag168 lands strictly inside the trailing window for steps <= 24
        lag168 = known[-168] if len(known) >= 168 else 0.0
        roll6 = sum(known[-6:]) / min(6, len(known))
        roll24 = sum(known[-24:]) / min(24, len(known))
        pred = float(mdl.predict([_features(hour, key_id, lag1, lag24, lag168, roll6, roll24)])[0])
        pred = max(pred, 0.0)
        out.append(pred)
        known.append(pred)
    return out


def fleet_forecast(steps: int = 12, *, series_by_key: dict[str, list[dict[str, Any]]] | None = None,
                   now: float | None = None, min_history_hours: int = 36) -> tuple[list[dict[str, Any]] | None, dict[str, Any] | None]:
    """Project the next `steps` hours of fleet spend, or (None, None) if unable.

    `series_by_key` is optional trailing hourly buckets; when omitted the
    trailing 7-day series is pulled from the live store. Only keys that the
    artifact was trained on are forecast — an unseen key must retrain first.
    """
    try:
        art = load()
        if art is None:
            return None, None
        now = time.time() if now is None else now
        now_hour = int(now // 3600) * 3600
        known_keys = list(art["keys"])

        cacheable = series_by_key is None
        if cacheable:
            from . import store
            mtime = ARTIFACT.stat().st_mtime
            cache_key = (now_hour, round(mtime, 3), steps)
            if _fc_cache["key"] == cache_key and now - _fc_cache["ts"] < 60:
                return _fc_cache["data"], _fc_cache["meta"]
            series_by_key = {vk: store.hourly_series(vk, now_hour - 7 * 86400, now) for vk in known_keys}

        key_ids = {vk: i for i, vk in enumerate(known_keys)}
        totals = [0.0] * steps
        used = 0
        for vk, series in series_by_key.items():
            if vk not in key_ids:
                continue  # artifact never saw this key
            costs = [float(b["cost"] or 0.0) for b in series]
            if not costs or sum(costs) <= 0.0:
                continue  # no metered history for this key
            if sum(c for c in costs[-min_history_hours:]) <= 0.0:
                continue
            preds = _recursive_key_preds(costs, now_hour, key_ids[vk], art["model"], steps)
            for j, p in enumerate(preds):
                totals[j] += p
            used += 1
        if used == 0:
            return None, None
        points = [{"hour": now_hour + (j + 1) * 3600, "cost": round(totals[j], 4)} for j in range(steps)]
        meta = {
            "trained_at": art["trained_at"],
            "algorithm": art["algorithm"],
            "val_mae": art.get("val_mae"),
            "hours": steps,
            "keys_used": used,
        }
        if cacheable:
            _fc_cache.update(ts=now, key=cache_key, data=points, meta=meta)
        return points, meta
    except Exception:
        return None, None
