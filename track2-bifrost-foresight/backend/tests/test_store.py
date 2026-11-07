"""Unit tests for the SQLite store layer (isolated temp database per test)."""
from __future__ import annotations

import json

import pytest

from foresight import store

BASE = 1_700_000_000.0  # fixed reference timestamp, not on an hour boundary


# ------------------------------------------------------------ virtual keys

class TestVirtualKeys:
    def test_upsert_and_get(self, tmp_db):
        tmp_db.upsert_key("sk-a", "Growth", "backend", 500.0, policy="pacing",
                          downgrade_to="gpt-4o-mini", color="#ff0000")
        k = tmp_db.get_key("sk-a")
        assert k["vk"] == "sk-a"
        assert k["name"] == "Growth" and k["team"] == "backend"
        assert k["budget_usd"] == 500.0
        assert k["policy"] == "pacing" and k["downgrade_to"] == "gpt-4o-mini"
        assert k["color"] == "#ff0000"
        assert k["downgrade_active"] == 0 and k["downgrade_until"] == 0
        assert k["created_ts"] > 0

    def test_upsert_conflict_updates_config_keeps_one_row(self, tmp_db):
        tmp_db.upsert_key("sk-a", "Growth", "backend", 100.0)
        tmp_db.upsert_key("sk-a", "Growth v2", "platform", 250.0)
        keys = tmp_db.list_keys()
        assert len(keys) == 1
        assert keys[0]["name"] == "Growth v2" and keys[0]["team"] == "platform"
        assert keys[0]["budget_usd"] == 250.0

    def test_get_missing_key_returns_none(self, tmp_db):
        assert tmp_db.get_key("sk-none") is None

    def test_list_orders_by_budget_desc(self, tmp_db):
        tmp_db.upsert_key("sk-small", "s", "t", 10.0)
        tmp_db.upsert_key("sk-big", "b", "t", 900.0)
        assert [k["vk"] for k in tmp_db.list_keys()] == ["sk-big", "sk-small"]

    def test_update_key_allowed_fields(self, tmp_db):
        tmp_db.upsert_key("sk-a", "Growth", "backend", 100.0)
        updated = tmp_db.update_key("sk-a", {"policy": "soft_cap", "budget_usd": 40.0})
        assert updated["policy"] == "soft_cap" and updated["budget_usd"] == 40.0

    def test_update_key_ignores_fields_outside_allowlist(self, tmp_db):
        # 'color' is not in update_key's allowlist — must not be writable here
        tmp_db.upsert_key("sk-a", "Growth", "backend", 100.0)
        assert tmp_db.update_key("sk-a", {"color": "#00ff00"})["color"] == "#7c5cff"

    def test_update_key_noop_returns_current_state(self, tmp_db):
        tmp_db.upsert_key("sk-a", "Growth", "backend", 100.0)
        assert tmp_db.update_key("sk-a", {"not_a_field": 1})["vk"] == "sk-a"

    def test_update_missing_key_returns_none(self, tmp_db):
        assert tmp_db.update_key("sk-ghost", {"policy": "notify"}) is None


# ------------------------------------------------------------------- usage

class TestUsage:
    def test_spend_and_count_scoped_by_key(self, tmp_db):
        tmp_db.insert_event("sk-a", "gpt-4o", 100, 50, 1.5, 20, ts=BASE)
        tmp_db.insert_event("sk-a", "gpt-4o", 200, 50, 2.5, 30, ts=BASE + 10)
        tmp_db.insert_event("sk-b", "gpt-4o-mini", 10, 10, 0.1, 5, ts=BASE + 20)
        assert tmp_db.spend_since("sk-a", BASE) == pytest.approx(4.0)
        assert tmp_db.spend_since("sk-a", BASE + 15) == pytest.approx(0.0)
        assert tmp_db.spend_since(None, BASE) == pytest.approx(4.1)
        assert tmp_db.count_since("sk-a", BASE) == 2
        assert tmp_db.count_since("sk-b", BASE + 21) == 0
        assert tmp_db.count_since(None, BASE) == 3

    def test_hourly_series_zero_fills_and_buckets_correctly(self, tmp_db):
        hour0 = int(BASE // 3600) * 3600
        tmp_db.insert_event("sk-a", "gpt-4o", 100, 50, 1.0, 5, ts=hour0 + 60)
        tmp_db.insert_event("sk-a", "gpt-4o", 200, 50, 2.0, 5, ts=hour0 + 3599)
        tmp_db.insert_event("sk-a", "gpt-4o", 10, 10, 4.0, 5, ts=hour0 + 3600 + 30)
        series = tmp_db.hourly_series("sk-a", hour0 - 3600, hour0 + 7200)
        assert [b["hour"] for b in series] == [hour0 - 3600, hour0, hour0 + 3600, hour0 + 7200]
        assert [b["cost"] for b in series] == [0.0, 3.0, 4.0, 0.0]
        assert [b["requests"] for b in series] == [0, 2, 1, 0]
        assert [b["tokens"] for b in series] == [0, 400, 20, 0]

    def test_hourly_series_across_all_keys_when_vk_none(self, tmp_db):
        hour0 = int(BASE // 3600) * 3600
        tmp_db.insert_event("sk-a", "gpt-4o", 10, 10, 1.0, 5, ts=hour0 + 10)
        tmp_db.insert_event("sk-b", "gpt-4o-mini", 10, 10, 2.0, 5, ts=hour0 + 20)
        series = tmp_db.hourly_series(None, hour0, hour0 + 3600 - 1)
        assert len(series) == 1  # until_ts still inside the first hour bucket
        assert series[0]["hour"] == hour0
        assert series[0]["cost"] == pytest.approx(3.0)
        assert series[0]["requests"] == 2

    def test_model_breakdown_groups_by_model_ordered_by_cost(self, tmp_db):
        tmp_db.insert_event("sk-a", "gpt-4o", 10, 10, 5.0, 5, ts=BASE)
        tmp_db.insert_event("sk-a", "acme-llm/gpt-4o-mini", 10, 10, 2.0, 5, ts=BASE + 1)
        tmp_db.insert_event("sk-a", "gpt-4o", 10, 10, 3.0, 5, ts=BASE + 2)
        rows = tmp_db.model_breakdown("sk-a", BASE - 10)
        assert rows[0]["model"] == "gpt-4o"
        assert rows[0]["cost"] == pytest.approx(8.0)
        assert rows[0]["requests"] == 2
        assert rows[1]["model"] == "acme-llm/gpt-4o-mini"
        assert rows[1]["cost"] == pytest.approx(2.0)

    def test_recent_requests_join_key_name_and_short_model(self, tmp_db):
        tmp_db.upsert_key("sk-a", "Growth", "backend", 100.0)
        tmp_db.insert_event("sk-a", "acme-llm/gpt-4o", 10, 10, 1.0, 40)
        row = tmp_db.recent_requests(limit=5)[0]
        assert row["key_name"] == "Growth"
        assert row["model_short"] == "gpt-4o"

    def test_clear_usage_scopes_to_source(self, tmp_db):
        tmp_db.insert_event("sk-a", "m", 1, 1, 1.0, 5, source="live")
        tmp_db.insert_event("sk-a", "m", 1, 1, 1.0, 5, source="seed")
        tmp_db.clear_usage(source="seed")
        assert tmp_db.count_since(None, 0) == 1
        tmp_db.clear_usage()
        assert tmp_db.count_since(None, 0) == 0


# ------------------------------------------------------------------ alerts

class TestAlerts:
    def test_insert_and_list_roundtrip_with_meta(self, tmp_db):
        aid = tmp_db.insert_alert("sk-a", "budget_95", "critical", "Title", "Detail", {"pct": 0.96})
        rows = tmp_db.list_alerts()
        assert rows[0]["id"] == aid
        assert rows[0]["kind"] == "budget_95"
        assert rows[0]["severity"] == "critical"
        assert rows[0]["meta"] == {"pct": 0.96}

    def test_corrupt_meta_json_falls_back_to_empty(self, tmp_db):
        with tmp_db._lock, tmp_db.connect() as conn:
            conn.execute(
                "INSERT INTO alerts(ts, vk, kind, severity, title, detail, meta) "
                "VALUES (?,?,?,?,?,?,?)",
                (1.0, "sk-a", "kind", "info", "t", "d", "{not json"),
            )
        assert tmp_db.list_alerts()[0]["meta"] == {}

    def test_list_orders_desc_and_respects_limit(self, tmp_db):
        for i in range(5):
            tmp_db.insert_alert("sk-a", "kind", "info", f"a{i}", ts=1000.0 + i)
        rows = tmp_db.list_alerts(limit=3)
        assert [r["title"] for r in rows] == ["a4", "a3", "a2"]

    def test_clear_alerts(self, tmp_db):
        tmp_db.insert_alert("sk-a", "kind", "info", "t")
        tmp_db.clear_alerts()
        assert tmp_db.list_alerts() == []


# ---------------------------------------------------------- sink / settings

class TestSinkAndSettings:
    def test_sink_roundtrip_and_clear(self, tmp_db):
        tmp_db.sink_record({"content-type": "application/json"}, '{"text": "hi"}')
        rows = tmp_db.sink_list()
        assert rows[0]["headers"] == {"content-type": "application/json"}
        assert rows[0]["body"] == '{"text": "hi"}'
        tmp_db.sink_clear()
        assert tmp_db.sink_list() == []

    def test_default_settings_seeded_on_init(self, tmp_db):
        s = tmp_db.get_settings()
        for key in ("webhook_url", "soft_cap_pct", "alert_horizon_hours",
                    "anomaly_z", "pacing_downgrade_hours"):
            assert key in s
        assert s["soft_cap_pct"] == "0.95"

    def test_set_setting_overrides_without_losing_others(self, tmp_db):
        webhook_before = tmp_db.get_settings()["webhook_url"]
        tmp_db.set_setting("soft_cap_pct", "0.80")
        s = tmp_db.get_settings()
        assert s["soft_cap_pct"] == "0.80"
        assert s["webhook_url"] == webhook_before


# ------------------------------------------------------------ policy fires

class TestPolicyFires:
    def test_cooldown_blocks_repeat_within_window(self, tmp_db):
        assert tmp_db.can_fire("sk-a", "budget_95", cooldown_seconds=3600) is True
        assert tmp_db.can_fire("sk-a", "budget_95", cooldown_seconds=3600) is False

    def test_cooldown_isolated_by_kind_and_key(self, tmp_db):
        assert tmp_db.can_fire("sk-a", "budget_95", 3600) is True
        assert tmp_db.can_fire("sk-a", "anomaly_123", 3600) is True   # other kind
        assert tmp_db.can_fire("sk-b", "budget_95", 3600) is True     # other key

    def test_cooldown_expires_after_window(self, tmp_db, monkeypatch):
        clock = {"t": 1_000_000.0}
        monkeypatch.setattr(store.time, "time", lambda: clock["t"])
        assert tmp_db.can_fire("sk-a", "kind", cooldown_seconds=60) is True
        clock["t"] += 10
        assert tmp_db.can_fire("sk-a", "kind", cooldown_seconds=60) is False
        clock["t"] += 61
        assert tmp_db.can_fire("sk-a", "kind", cooldown_seconds=60) is True
