"""Store layer: SQLite persistence for keys, usage events, alerts and settings.

All times are unix epoch seconds (UTC). Budgets use a rolling 30-day window,
matching how Bifrost expresses rolling budget windows via reset_duration.
"""
from __future__ import annotations

import json
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any

DB_PATH = Path(__file__).resolve().parent.parent / "foresight.db"

_lock = threading.Lock()

DEFAULT_SETTINGS = {
    "webhook_url": "http://127.0.0.1:8400/api/webhook-sink",
    "soft_cap_pct": "0.95",          # soft cap engages at this budget fraction
    "alert_horizon_hours": "48",     # warn when projected exhaustion is within this horizon
    "anomaly_z": "3.5",              # robust z threshold for anomaly alerts
    "pacing_downgrade_hours": "6",   # how long a pacing-triggered downgrade stays active
}

SCHEMA = """
CREATE TABLE IF NOT EXISTS virtual_keys(
  vk TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  team TEXT NOT NULL,
  budget_usd REAL NOT NULL,
  policy TEXT NOT NULL DEFAULT 'observe',
  downgrade_to TEXT NOT NULL DEFAULT '',
  downgrade_active INTEGER NOT NULL DEFAULT 0,
  downgrade_until REAL NOT NULL DEFAULT 0,
  color TEXT NOT NULL DEFAULT '#7c5cff',
  created_ts REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS usage_events(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts REAL NOT NULL,
  vk TEXT NOT NULL,
  model TEXT NOT NULL,
  prompt_tokens INTEGER NOT NULL DEFAULT 0,
  completion_tokens INTEGER NOT NULL DEFAULT 0,
  cost_usd REAL NOT NULL DEFAULT 0,
  latency_ms INTEGER NOT NULL DEFAULT 0,
  source TEXT NOT NULL DEFAULT 'live',
  exact INTEGER NOT NULL DEFAULT 1
);
CREATE INDEX IF NOT EXISTS idx_usage_vk_ts ON usage_events(vk, ts);
CREATE INDEX IF NOT EXISTS idx_usage_ts ON usage_events(ts);
CREATE TABLE IF NOT EXISTS alerts(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts REAL NOT NULL,
  vk TEXT NOT NULL DEFAULT '',
  kind TEXT NOT NULL,
  severity TEXT NOT NULL,
  title TEXT NOT NULL,
  detail TEXT NOT NULL DEFAULT '',
  meta TEXT NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_alerts_ts ON alerts(ts);
CREATE TABLE IF NOT EXISTS webhook_sink(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts REAL NOT NULL,
  headers TEXT NOT NULL DEFAULT '{}',
  body TEXT NOT NULL DEFAULT '{}'
);
CREATE TABLE IF NOT EXISTS settings(k TEXT PRIMARY KEY, v TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS policy_fires(
  vk TEXT NOT NULL,
  kind TEXT NOT NULL,
  last_ts REAL NOT NULL,
  PRIMARY KEY(vk, kind)
);
"""


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


def init_db() -> None:
    with _lock, connect() as conn:
        conn.executescript(SCHEMA)
        for k, v in DEFAULT_SETTINGS.items():
            conn.execute("INSERT OR IGNORE INTO settings(k, v) VALUES (?, ?)", (k, v))


def _rows(cur) -> list[dict[str, Any]]:
    return [dict(r) for r in cur.fetchall()]


# ---------------------------------------------------------------- virtual keys

def upsert_key(vk: str, name: str, team: str, budget_usd: float, policy: str = "observe",
               downgrade_to: str = "", color: str = "#7c5cff") -> None:
    with _lock, connect() as conn:
        conn.execute(
            """INSERT INTO virtual_keys(vk, name, team, budget_usd, policy, downgrade_to, color, created_ts)
               VALUES (?,?,?,?,?,?,?,?)
               ON CONFLICT(vk) DO UPDATE SET name=excluded.name, team=excluded.team,
                 budget_usd=excluded.budget_usd, policy=excluded.policy,
                 downgrade_to=excluded.downgrade_to, color=excluded.color""",
            (vk, name, team, budget_usd, policy, downgrade_to, color, time.time()),
        )


def get_key(vk: str) -> dict[str, Any] | None:
    with _lock, connect() as conn:
        row = conn.execute("SELECT * FROM virtual_keys WHERE vk = ?", (vk,)).fetchone()
        return dict(row) if row else None


def list_keys() -> list[dict[str, Any]]:
    with _lock, connect() as conn:
        return _rows(conn.execute("SELECT * FROM virtual_keys ORDER BY budget_usd DESC"))


def update_key(vk: str, fields: dict[str, Any]) -> dict[str, Any] | None:
    allowed = {"budget_usd", "policy", "downgrade_to", "downgrade_active", "downgrade_until", "name", "team"}
    sets, vals = [], []
    for k, v in fields.items():
        if k in allowed:
            sets.append(f"{k} = ?")
            vals.append(v)
    if not sets:
        return get_key(vk)
    vals.append(vk)
    with _lock, connect() as conn:
        conn.execute(f"UPDATE virtual_keys SET {', '.join(sets)} WHERE vk = ?", vals)
    return get_key(vk)


# ------------------------------------------------------------------- usage

def insert_event(vk: str, model: str, prompt_tokens: int, completion_tokens: int,
                 cost_usd: float, latency_ms: int, source: str = "live", exact: bool = True,
                 ts: float | None = None) -> int:
    with _lock, connect() as conn:
        cur = conn.execute(
            """INSERT INTO usage_events(ts, vk, model, prompt_tokens, completion_tokens, cost_usd, latency_ms, source, exact)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (ts if ts is not None else time.time(), vk, model, prompt_tokens, completion_tokens,
             cost_usd, latency_ms, source, 1 if exact else 0),
        )
        return int(cur.lastrowid)


def spend_since(vk: str | None, since_ts: float) -> float:
    with _lock, connect() as conn:
        if vk:
            row = conn.execute("SELECT COALESCE(SUM(cost_usd),0) AS s FROM usage_events WHERE vk = ? AND ts >= ?",
                               (vk, since_ts)).fetchone()
        else:
            row = conn.execute("SELECT COALESCE(SUM(cost_usd),0) AS s FROM usage_events WHERE ts >= ?",
                               (since_ts,)).fetchone()
        return float(row["s"])


def count_since(vk: str | None, since_ts: float) -> int:
    with _lock, connect() as conn:
        if vk:
            row = conn.execute("SELECT COUNT(*) AS c FROM usage_events WHERE vk = ? AND ts >= ?",
                               (vk, since_ts)).fetchone()
        else:
            row = conn.execute("SELECT COUNT(*) AS c FROM usage_events WHERE ts >= ?",
                               (since_ts,)).fetchone()
        return int(row["c"])


def hourly_series(vk: str | None, since_ts: float, until_ts: float | None = None) -> list[dict[str, Any]]:
    """Hourly cost buckets, ascending. Hours without events are zero-filled."""
    until = until_ts if until_ts is not None else time.time()
    start_hour = int(since_ts // 3600) * 3600
    end_hour = int(until // 3600) * 3600
    buckets: dict[int, dict[str, Any]] = {}
    t = start_hour
    while t <= end_hour:
        buckets[t] = {"hour": t, "cost": 0.0, "requests": 0, "tokens": 0}
        t += 3600
    with _lock, connect() as conn:
        if vk:
            rows = _rows(conn.execute(
                "SELECT (CAST(ts / 3600 AS INTEGER) * 3600) AS hour, SUM(cost_usd) AS cost, COUNT(*) AS requests, "
                "SUM(prompt_tokens + completion_tokens) AS tokens FROM usage_events WHERE vk = ? AND ts >= ? AND ts <= ? GROUP BY hour",
                (vk, since_ts, until)))
        else:
            rows = _rows(conn.execute(
                "SELECT (CAST(ts / 3600 AS INTEGER) * 3600) AS hour, SUM(cost_usd) AS cost, COUNT(*) AS requests, "
                "SUM(prompt_tokens + completion_tokens) AS tokens FROM usage_events WHERE ts >= ? AND ts <= ? GROUP BY hour",
                (since_ts, until)))
    for r in rows:
        h = int(r["hour"])
        if h in buckets:
            buckets[h] = {"hour": h, "cost": float(r["cost"] or 0), "requests": int(r["requests"] or 0), "tokens": int(r["tokens"] or 0)}
    return [buckets[k] for k in sorted(buckets)]


def model_breakdown(vk: str | None, since_ts: float) -> list[dict[str, Any]]:
    with _lock, connect() as conn:
        if vk:
            rows = _rows(conn.execute(
                "SELECT model, SUM(cost_usd) AS cost, COUNT(*) AS requests FROM usage_events WHERE vk = ? AND ts >= ? GROUP BY model ORDER BY cost DESC",
                (vk, since_ts)))
        else:
            rows = _rows(conn.execute(
                "SELECT model, SUM(cost_usd) AS cost, COUNT(*) AS requests FROM usage_events WHERE ts >= ? GROUP BY model ORDER BY cost DESC",
                (since_ts,)))
    return [{"model": r["model"], "cost": float(r["cost"] or 0), "requests": int(r["requests"] or 0)} for r in rows]


def recent_requests(limit: int = 50) -> list[dict[str, Any]]:
    with _lock, connect() as conn:
        rows = _rows(conn.execute(
            "SELECT u.*, k.name AS key_name FROM usage_events u LEFT JOIN virtual_keys k ON k.vk = u.vk "
            "ORDER BY u.ts DESC LIMIT ?", (limit,)))
    for r in rows:
        r["model_short"] = str(r["model"]).split("/")[-1]
    return rows


def clear_usage(source: str | None = None) -> None:
    with _lock, connect() as conn:
        if source:
            conn.execute("DELETE FROM usage_events WHERE source = ?", (source,))
        else:
            conn.execute("DELETE FROM usage_events")


# ------------------------------------------------------------------- alerts

def insert_alert(vk: str, kind: str, severity: str, title: str, detail: str = "", meta: dict | None = None,
                 ts: float | None = None) -> int:
    with _lock, connect() as conn:
        cur = conn.execute(
            "INSERT INTO alerts(ts, vk, kind, severity, title, detail, meta) VALUES (?,?,?,?,?,?,?)",
            (ts if ts is not None else time.time(), vk, kind, severity, title, detail,
             json.dumps(meta or {})))
        return int(cur.lastrowid)


def list_alerts(limit: int = 50) -> list[dict[str, Any]]:
    with _lock, connect() as conn:
        rows = _rows(conn.execute("SELECT * FROM alerts ORDER BY ts DESC LIMIT ?", (limit,)))
    for r in rows:
        try:
            r["meta"] = json.loads(r.get("meta") or "{}")
        except json.JSONDecodeError:
            r["meta"] = {}
    return rows


def clear_alerts() -> None:
    with _lock, connect() as conn:
        conn.execute("DELETE FROM alerts")


# --------------------------------------------------------------- sink/settings

def sink_record(headers: dict, body: str) -> None:
    with _lock, connect() as conn:
        conn.execute("INSERT INTO webhook_sink(ts, headers, body) VALUES (?,?,?)",
                     (time.time(), json.dumps(headers), body))


def sink_list(limit: int = 20) -> list[dict[str, Any]]:
    with _lock, connect() as conn:
        rows = _rows(conn.execute("SELECT * FROM webhook_sink ORDER BY ts DESC LIMIT ?", (limit,)))
    for r in rows:
        try:
            r["headers"] = json.loads(r.get("headers") or "{}")
        except json.JSONDecodeError:
            r["headers"] = {}
    return rows


def sink_clear() -> None:
    with _lock, connect() as conn:
        conn.execute("DELETE FROM webhook_sink")


def get_settings() -> dict[str, str]:
    with _lock, connect() as conn:
        return {r["k"]: r["v"] for r in conn.execute("SELECT k, v FROM settings")}


def set_setting(k: str, v: str) -> None:
    with _lock, connect() as conn:
        conn.execute("INSERT INTO settings(k, v) VALUES (?,?) ON CONFLICT(k) DO UPDATE SET v=excluded.v", (k, v))


# --------------------------------------------------------------- policy fires

def can_fire(vk: str, kind: str, cooldown_seconds: float) -> bool:
    with _lock, connect() as conn:
        row = conn.execute("SELECT last_ts FROM policy_fires WHERE vk=? AND kind=?", (vk, kind)).fetchone()
        if row and (time.time() - float(row["last_ts"])) < cooldown_seconds:
            return False
        conn.execute(
            "INSERT INTO policy_fires(vk, kind, last_ts) VALUES (?,?,?) "
            "ON CONFLICT(vk, kind) DO UPDATE SET last_ts=excluded.last_ts",
            (vk, kind, time.time()))
        return True
