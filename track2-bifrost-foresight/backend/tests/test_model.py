"""Tests for the compact trained forecaster (foresight.model)."""
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


@pytest.fixture()
def clean_artifact(tmp_path, monkeypatch):
    monkeypatch.setattr(model_mod, "ARTIFACT", tmp_path / "test_forecaster.joblib")
    model_mod._loaded["mtime"], model_mod._loaded["artifact"] = None, None
    model_mod._fc_cache.update(ts=0.0, key=None, data=None, meta=None)
    yield tmp_path / "test_forecaster.joblib"
    model_mod._loaded["mtime"], model_mod._loaded["artifact"] = None, None


def test_train_predict_roundtrip(clean_artifact):
    now = time.time()
    series = {
        "sk-a": _series("sk-a", 21 * 24, 1.5, 2, now),
        "sk-b": _series("sk-b", 21 * 24, 0.4, 9, now),
    }
    result = model_mod.train(series, max_iter=40, val_hours=72)

    assert result["n_train"] > 60
    assert result["n_val"] > 0
    assert result["val_mae"] >= 0.0
    assert result["artifact_bytes"] < model_mod.MAX_ARTIFACT_BYTES  # the 100 MB budget
    assert clean_artifact.exists()

    status = model_mod.status()
    assert status["loaded"] is True
    assert status["under_budget"] is True
    assert status["val_mae"] == result["val_mae"]

    points, meta = model_mod.fleet_forecast(steps=12, series_by_key=series, now=now)
    assert points is not None and len(points) == 12
    assert meta is not None and meta["keys_used"] == 2
    assert all(p["cost"] > 0.0 for p in points)


def test_fallback_without_artifact(clean_artifact):
    assert model_mod.load() is None
    assert model_mod.status()["loaded"] is False
    points, meta = model_mod.fleet_forecast(steps=6)
    assert points is None and meta is None


def test_train_rejects_thin_history(clean_artifact):
    now = time.time()
    series = {"sk-a": _series("sk-a", 40, 1.0, 3, now)}
    with pytest.raises(ValueError):
        model_mod.train(series, max_iter=10, val_hours=12)
