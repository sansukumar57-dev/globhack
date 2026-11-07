"""Unit tests for the autopilot policy engine (isolated store + stub webhook)."""
from __future__ import annotations

import asyncio
import time

import pytest

from foresight import policy, store


# ------------------------------------------------------------------ helpers

def make_fc(*, pct: float, hours_left: float | None = None, status: str = "critical") -> dict:
    """Minimal forecast payload shaped like forecast.forecast() output."""
    return {
        "budget_usd": 100.0,
        "spent_usd": round(pct * 100.0, 4),
        "remaining_usd": round(100.0 * (1 - pct), 4),
        "pct_used": pct,
        "burn_rate_1h": 0.5,
        "burn_rate_6h": 0.5,
        "burn_rate_24h": 0.5,
        "burn_rate_effective": 0.5,
        "projected_30d_cost": 360.0,
        "hours_until_exhaustion": hours_left,
        "exhaustion_ts": None,
        "status": status,
        "stability": "steady",
        "trend_pct_per_day": 0.0,
    }


def make_key(**kw) -> dict:
    base = {"vk": "sk-a", "name": "Growth", "policy": "observe",
            "downgrade_active": 0, "downgrade_until": 0, "downgrade_to": ""}
    base.update(kw)
    return base


@pytest.fixture()
def hooked(tmp_db, monkeypatch):
    """Stub the outbound webhook so no HTTP happens; record the payloads."""
    sent: list[tuple[str, dict]] = []

    async def fake_fire(url, payload):
        sent.append((url, payload))
        return True

    monkeypatch.setattr(policy, "fire_webhook", fake_fire)
    return sent


# ------------------------------------------------------------ slack payload

class TestSlackPayload:
    def test_severity_maps_emoji_and_color(self):
        p = policy.build_slack_payload("Title", "Detail", "critical", {"Key": "Growth"})
        assert p["text"] == ":red_circle: *Title*\nDetail"
        att = p["attachments"][0]
        assert att["color"] == "#fb7185"
        assert att["fields"] == [{"title": "Key", "value": "Growth", "short": True}]
        assert isinstance(att["ts"], int)

    def test_unknown_severity_falls_back(self):
        p = policy.build_slack_payload("t", "d", "mystery", None)
        assert p["text"] == ":large_blue_circle: *t*\nd"
        assert p["attachments"][0]["fields"] == []


# ------------------------------------------------------------ check_request

class TestCheckRequest:
    def test_active_downgrade_short_circuits_everything(self, tmp_db):
        key = make_key(downgrade_active=1, downgrade_until=time.time() + 3600,
                       downgrade_to="gpt-4o-mini")
        out = asyncio.run(policy.check_request(key, make_fc(pct=0.1)))
        assert out == {"action": "downgrade", "reason": "pacing_downgrade_active",
                       "model_override": "gpt-4o-mini"}

    def test_expired_downgrade_is_not_applied(self, tmp_db):
        key = make_key(policy="observe", downgrade_active=1,
                       downgrade_until=time.time() - 1, downgrade_to="gpt-4o-mini")
        out = asyncio.run(policy.check_request(key, make_fc(pct=0.1)))
        assert out["action"] == "allow"

    def test_soft_cap_blocks_above_fraction(self, tmp_db):
        out = asyncio.run(policy.check_request(
            make_key(policy="soft_cap"), make_fc(pct=0.96)))
        assert out["action"] == "block"
        assert out["reason"].startswith("soft_cap")
        assert "96%" in out["reason"] and "95%" in out["reason"]
        assert out["model_override"] is None

    def test_soft_cap_allows_below_fraction(self, tmp_db):
        out = asyncio.run(policy.check_request(
            make_key(policy="soft_cap"), make_fc(pct=0.50)))
        assert out["action"] == "allow"

    def test_soft_cap_threshold_configurable_via_settings(self, tmp_db):
        store.set_setting("soft_cap_pct", "0.50")
        out = asyncio.run(policy.check_request(
            make_key(policy="soft_cap"), make_fc(pct=0.60)))
        assert out["action"] == "block"

    def test_pacing_arms_timebox_downgrade_and_pages(self, tmp_db, hooked):
        tmp_db.upsert_key("sk-a", "Growth", "backend", 800.0)  # row must exist for the arm write
        before = time.time()
        key = make_key(policy="pacing", downgrade_to="gpt-4o-mini")
        out = asyncio.run(policy.check_request(
            key, make_fc(pct=0.75, hours_left=12.0)))
        assert out["action"] == "downgrade"
        assert out["reason"] == "pacing_exhaustion_imminent"
        assert out["model_override"] == "gpt-4o-mini"

        stored = store.get_key("sk-a")
        assert stored["downgrade_active"] == 1
        assert before + 6 * 3600 <= stored["downgrade_until"] <= time.time() + 6 * 3600 + 5
        assert len(hooked) == 1  # the arm walked to the webhook
        kinds = [a["kind"] for a in store.list_alerts()]
        assert kinds == ["pacing_downgrade"]

    def test_pacing_without_target_model_falls_through_to_allow(self, tmp_db, hooked):
        key = make_key(policy="pacing", downgrade_to="")
        out = asyncio.run(policy.check_request(
            key, make_fc(pct=0.75, hours_left=12.0)))
        assert out["action"] == "allow"
        assert hooked == []

    def test_pacing_needs_a_projected_exhaustion_eta(self, tmp_db):
        key = make_key(policy="pacing", downgrade_to="gpt-4o-mini")
        out = asyncio.run(policy.check_request(
            key, make_fc(pct=0.75, hours_left=None)))
        assert out["action"] == "allow"

    def test_pacing_gate_not_armed_well_before_window(self, tmp_db):
        key = make_key(policy="pacing", downgrade_to="gpt-4o-mini")
        out = asyncio.run(policy.check_request(
            key, make_fc(pct=0.75, hours_left=40.0)))  # > 24h
        assert out["action"] == "allow"


# ------------------------------------------------------------ post_response

class TestPostResponse:
    def _key(self, **kw):
        return make_key(policy="notify", **kw)

    def test_budget_thresholds_and_horizon_fire_once_each(self, tmp_db, hooked):
        out = asyncio.run(policy.post_response(
            self._key(), make_fc(pct=0.96, hours_left=10.0, status="critical")))
        kinds = [a["kind"] for a in out]
        assert kinds == ["budget_75", "budget_90", "budget_95", "horizon_alert"]
        assert all(a["fired"] for a in out)
        assert len(hooked) == 4
        persisted = {a["kind"] for a in store.list_alerts()}
        assert persisted == {"budget_75", "budget_90", "budget_95", "horizon_alert"}
        severities = {a["kind"]: a["severity"] for a in store.list_alerts()}
        assert severities["budget_95"] == "critical"
        assert severities["budget_75"] == "warning"

    def test_observe_policy_stays_silent(self, tmp_db, hooked):
        out = asyncio.run(policy.post_response(
            make_key(policy="observe"),
            make_fc(pct=0.96, hours_left=10.0, status="critical")))
        assert out == []
        assert hooked == []
        assert store.list_alerts() == []

    def test_cooldown_suppresses_immediate_repeat(self, tmp_db, hooked):
        first = asyncio.run(policy.post_response(
            self._key(), make_fc(pct=0.96, hours_left=10.0, status="critical")))
        second = asyncio.run(policy.post_response(
            self._key(), make_fc(pct=0.96, hours_left=10.0, status="critical")))
        assert all(a["fired"] for a in first)
        assert all(not a["fired"] for a in second)
        assert len(hooked) == 4  # webhook only paged on the first pass

    def test_horizon_alert_requires_critical_status(self, tmp_db):
        out = asyncio.run(policy.post_response(
            self._key(), make_fc(pct=0.50, hours_left=10.0, status="watch")))
        assert out == []

    def test_exhaustion_outside_horizon_ignores_eta(self, tmp_db):
        out = asyncio.run(policy.post_response(
            self._key(), make_fc(pct=0.50, hours_left=100.0, status="critical")))
        assert out == []


# ----------------------------------------------------------- report_anomaly

class TestReportAnomaly:
    def _key(self, **kw):
        return make_key(policy="notify", **kw)

    def test_big_ratio_is_critical_and_pages(self, tmp_db, hooked):
        anomaly = {"hour": 1_700_000_000, "cost": 9.0, "baseline": 1.0, "ratio": 9.0, "z": 12.0}
        result = asyncio.run(policy.report_anomaly(self._key(), anomaly))
        assert result["fired"] is True
        assert len(hooked) == 1
        alert = store.list_alerts()[0]
        assert alert["kind"] == "anomaly"
        assert alert["severity"] == "critical"
        assert alert["meta"] == anomaly

    def test_small_ratio_is_warning(self, tmp_db, hooked):
        anomaly = {"hour": 1_700_000_000, "cost": 2.0, "baseline": 1.0, "ratio": 2.0, "z": 4.0}
        asyncio.run(policy.report_anomaly(self._key(), anomaly))
        assert store.list_alerts()[0]["severity"] == "warning"

    def test_observe_records_but_never_pages(self, tmp_db, hooked):
        anomaly = {"hour": 1_700_000_000, "cost": 9.0, "baseline": 1.0, "ratio": 9.0, "z": 12.0}
        result = asyncio.run(policy.report_anomaly(make_key(policy="observe"), anomaly))
        assert result["fired"] is True   # audited
        assert hooked == []              # but silent
        assert len(store.list_alerts()) == 1

    def test_anomaly_cooldown_is_per_hour_bucket(self, tmp_db, hooked):
        a1 = {"hour": 1_700_000_000, "cost": 9.0, "baseline": 1.0, "ratio": 9.0, "z": 12.0}
        a2 = {"hour": 1_700_003_600, "cost": 9.0, "baseline": 1.0, "ratio": 9.0, "z": 12.0}
        first = asyncio.run(policy.report_anomaly(self._key(), a1))
        second = asyncio.run(policy.report_anomaly(self._key(), a2))
        assert first["fired"] and second["fired"]
        assert len(hooked) == 2


# ------------------------------------------------------------ test webhook

class TestSendTestWebhook:
    def test_delivers_to_configured_webhook(self, tmp_db, hooked):
        out = asyncio.run(policy.send_test_webhook())
        assert out["delivered"] is True
        assert out["webhook_url"] == store.get_settings()["webhook_url"]
        assert "test alert" in out["payload"]["text"]
        assert len(hooked) == 1
