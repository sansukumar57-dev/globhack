"""Tests for the trained spend-intelligence model (foresight.model, v2).

A full committee train + rolling-origin backtest is the expensive part of
this suite, so the module trains exactly once in the `trained` fixture and
every test reuses that artifact: all heads accept injected series/budgets,
so no retrain is needed to exercise breach risk or the anomaly scan.
"""
import math
import time

import pytest

from foresight import model as model_mod


def _series(vk: str, hours: int, base: float, phase: int, now: float) -> list[dict]:
    """Synthetic hourly buckets with daily + weekly structure, like real traffic."""
    end_hour = int(now // 3600) * 3600
    out = []
    for i in range(hours, 0, -1):
        hour = end_hour - (i - 1) * 3600
        hod = (hour // 3600) % 24
        dow = (hour // 86400) % 7
        wave = 0.55 + 0.45 * math.sin(2 * math.pi * (hod + phase) / 24.0)
        week = 1.25 if dow < 5 else 0.55
        cost = base * wave * week
        out.append({"hour": hour, "cost": round(cost, 4), "requests": 4, "tokens": 5000})
    return out


@pytest.fixture(scope="module")
def trained(request):
    """Isolate the artifact in a temp dir, train once, assert the roundtrip."""
    from pathlib import Path
    tmp_dir = Path(__file__).resolve().parent.parent / ".test_tmp"
    tmp_dir.mkdir(exist_ok=True)
    now = time.time()
    series = {
        "sk-a": _series("sk-a", 21 * 24, 1.5, 2, now),
        "sk-b": _series("sk-b", 21 * 24, 0.4, 9, now),
    }
    backup = model_mod.ARTIFACT
    model_mod.ARTIFACT = tmp_dir / "test_intelligence.joblib"
    model_mod._loaded["mtime"], model_mod._loaded["artifact"] = None, None
    model_mod._intel_cache.update(ts=0.0, key=None, data=None)
    model_mod._scan_cache.update(ts=0.0, key=None, data=None)

    result = model_mod.train(series, committee_size=4, val_hours=72)

    def restore():
        model_mod.ARTIFACT = backup
        model_mod._loaded["mtime"], model_mod._loaded["artifact"] = None, None
        model_mod._intel_cache.update(ts=0.0, key=None, data=None)
        model_mod._scan_cache.update(ts=0.0, key=None, data=None)

    request.addfinalizer(restore)
    return {"result": result, "series": series, "now": now, "artifact": model_mod.ARTIFACT}


def test_train_roundtrip_and_heads(trained):
    result, series, now = trained["result"], trained["series"], trained["now"]

    assert trained["artifact"].exists()
    assert result["n_train"] > 60
    assert result["committee_size"] == 4
    assert 0.0 <= result["val_coverage"] <= 1.0
    assert result["val_mae"] >= 0.0
    assert result["anomaly_resid_sigma"] > 0.0
    assert result["artifact_bytes"] < model_mod.MAX_ARTIFACT_BYTES  # the 100 MB budget

    status = model_mod.status()
    assert status["loaded"] is True
    assert status["under_budget"] is True
    assert status["val_mae"] == result["val_mae"]
    assert status["committee_size"] == 4
    assert status["skills"] == model_mod.SKILLS

    intel = model_mod.intelligence(steps=12, series_by_key=series, now=now)
    assert intel is not None
    points = intel["forecast"]
    assert len(points) == 12
    for p in points:
        assert p["p10"] <= p["cost"] <= p["p90"]
        assert p["cost"] > 0.0
    meta = intel["forecast_meta"]
    assert meta["committee"] == 4 and meta["keys_used"] == 2
    assert intel["risk"] is None  # budgets not supplied


def test_breach_risk_from_budgets(trained):
    series, now = trained["series"], trained["now"]

    intel = model_mod.intelligence(
        steps=12, series_by_key=series, now=now,
        budgets={"sk-a": 50_000.0, "sk-b": 10.0},
    )
    assert intel is not None and intel["risk"] is not None
    risk = intel["risk"]
    # rich key: remaining budget dwarfs any path's cumulative spend → ~no breach
    assert 0.0 <= risk["sk-a"]["p_24h"] <= 0.2
    assert 0.0 <= risk["sk-a"]["p_48h"] <= 0.2
    assert risk["sk-a"]["remaining_usd"] > 0
    # drained key: budget already below its 30d spend → certainty
    assert risk["sk-b"]["p_24h"] == 1.0
    assert "p_48h" in risk["sk-b"]


def test_anomaly_scan_flags_spike(trained):
    now = trained["now"]

    # Spike the last complete hour hard (fresh copies; the fixture series is shared).
    end_hour = int(now // 3600) * 3600
    spiked = []
    for b in trained["series"]["sk-a"]:
        row = dict(b)
        if row["hour"] == end_hour - 3600:
            row["cost"] = round(row["cost"] + 40.0, 4)
        spiked.append(row)

    scored = model_mod.anomaly_scan(
        hours=48, series_by_key={"sk-a": spiked, "sk-b": trained["series"]["sk-b"]}, now=now)
    assert scored is not None and len(scored) >= 1
    top = scored[0]
    assert top["vk"] == "sk-a"
    assert top["hour"] == end_hour - 3600
    assert top["actual"] - top["expected"] > 30.0
    assert top["model_z"] >= scored[-1]["model_z"]  # sorted descending


def test_fallback_without_artifact(monkeypatch):
    from pathlib import Path
    tmp_dir = Path(__file__).resolve().parent.parent / ".test_tmp"
    monkeypatch.setattr(model_mod, "ARTIFACT", tmp_dir / "missing.joblib")
    model_mod._loaded["mtime"], model_mod._loaded["artifact"] = None, None
    assert model_mod.load() is None
    assert model_mod.status()["loaded"] is False
    assert model_mod.intelligence(steps=6) is None
    assert model_mod.anomaly_scan(hours=24) is None


def test_train_rejects_thin_history():
    now = time.time()
    series = {"sk-a": _series("sk-a", 40, 1.0, 3, now)}
    with pytest.raises(ValueError):
        model_mod.train(series, committee_size=2, val_hours=12)
