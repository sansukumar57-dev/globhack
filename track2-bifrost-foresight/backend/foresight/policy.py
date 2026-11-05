"""Autopilot policy engine.

What Bifrost OSS deliberately does NOT do: act on projections before the money
is gone. Foresight policies are per virtual key:

  observe   - meter and alert only (default)
  notify    - page the webhook when pacing says the budget won't survive the window
  soft_cap  - hard-stop further spend for this key at the configured budget fraction
              (before Bifrost's own budget gate trips at 100%)
  pacing    - auto-downgrade this key's model to a cheaper drop-in for N hours when
              projected exhaustion is within 24h; lifts automatically
"""
from __future__ import annotations

import time
from typing import Any

import httpx

from . import store


def build_slack_payload(title: str, detail: str, severity: str, fields: dict[str, str] | None = None) -> dict[str, Any]:
    emoji = {"critical": ":red_circle:", "warning": ":large_orange_circle:", "info": ":large_blue_circle:",
             "healthy": ":large_green_circle:"}.get(severity, ":large_blue_circle:")
    return {
        "text": f"{emoji} *{title}*\n{detail}",
        "attachments": [{
            "color": {"critical": "#fb7185", "warning": "#fbbf24", "info": "#7c5cff", "healthy": "#34d399"}.get(severity, "#7c5cff"),
            "fields": [{"title": k, "value": str(v), "short": True} for k, v in (fields or {}).items()],
            "footer": "Bifrost Foresight · predictive governance",
            "ts": int(time.time()),
        }],
    }


async def fire_webhook(url: str, payload: dict[str, Any]) -> bool:
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(url, json=payload)
        return resp.status_code < 400
    except Exception:
        return False


def _settings_float(settings: dict[str, str], key: str, default: float) -> float:
    try:
        return float(settings.get(key, default))
    except (TypeError, ValueError):
        return default


async def check_request(key: dict[str, Any], fc: dict[str, Any]) -> dict[str, Any]:
    """Pre-request gate. Returns {action, reason, model_override}."""
    settings = store.get_settings()
    now = time.time()
    policy = key.get("policy", "observe")
    pct = float(fc.get("pct_used", 0.0))
    soft_cap_pct = _settings_float(settings, "soft_cap_pct", 0.95)
    hours_left = fc.get("hours_until_exhaustion")

    # Downgrade already armed (by us earlier) — apply until it expires.
    if key.get("downgrade_active") and now < float(key.get("downgrade_until") or 0):
        target = key.get("downgrade_to") or ""
        if target:
            return {"action": "downgrade", "reason": "pacing_downgrade_active", "model_override": target}

    if policy == "soft_cap" and pct >= soft_cap_pct:
        return {"action": "block",
                "reason": f"soft_cap: {pct:.0%} of the 30d budget is spent (cap {soft_cap_pct:.0%}) — "
                          f"Bifrost would let this ride until 100%; Foresight stops it at {soft_cap_pct:.0%}.",
                "model_override": None}

    if policy == "pacing" and pct >= 0.70 and hours_left is not None and hours_left <= 24.0:
        # Arm the downgrade rather than blocking: spend continues, on the cheap model.
        hours = _settings_float(settings, "pacing_downgrade_hours", 6.0)
        target = key.get("downgrade_to") or ""
        if target:
            store.update_key(key["vk"], {"downgrade_active": 1, "downgrade_until": now + hours * 3600})
            await _alert(key, "pacing_downgrade", "warning",
                         f"Pacing downgrade armed → {target}",
                         f"{key['name']} is projected to exhaust its budget in {hours_left:.1f}h; "
                         f"traffic moves to {target} for {hours:.0f}h.",
                         {"hours_left": round(hours_left, 2), "target": target},
                         notify=True, webhook=settings.get("webhook_url", ""), cooldown_seconds=3600)
            return {"action": "downgrade", "reason": "pacing_exhaustion_imminent", "model_override": target}

    return {"action": "allow", "reason": "within_policy", "model_override": None}


async def post_response(key: dict[str, Any], fc: dict[str, Any]) -> list[dict[str, Any]]:
    """Post-metering duties: threshold alerts + budget notifications. Returns actions taken."""
    settings = store.get_settings()
    policy = key.get("policy", "observe")
    fired: list[dict[str, Any]] = []
    pct = float(fc.get("pct_used", 0.0))
    webhook = settings.get("webhook_url", "")

    for level in (0.75, 0.90, 0.95):
        if pct >= level and policy != "observe":
            kind = f"budget_{int(level * 100)}"
            sev = "critical" if level >= 0.95 else "warning"
            title = f"{key['name']} at {pct:.0%} of 30d budget"
            detail = (f"Rolling 30-day spend ${fc['spent_usd']:.2f} of ${fc['budget_usd']:.2f} "
                      f"(${fc['remaining_usd']:.2f} left). Burn ${fc['burn_rate_6h']:.2f}/h.")
            fired.append(await _alert(key, kind, sev, title, detail,
                                      {"pct_used": pct, "burn_6h": fc["burn_rate_6h"]},
                                      notify=True, webhook=webhook, cooldown_seconds=6 * 3600))

    if policy in ("notify", "soft_cap", "pacing"):
        horizon = _settings_float(settings, "alert_horizon_hours", 48.0)
        hours_left = fc.get("hours_until_exhaustion")
        if hours_left is not None and hours_left <= horizon and fc.get("status") == "critical":
            title = f"Budget for {key['name']} exhausts in {hours_left:.1f}h"
            detail = (f"At the current burn rate (${fc['burn_rate_6h']:.2f}/h) the 30-day window "
                      f"runs dry before it resets. Bifrost's static cap only trips at 100%.")
            fired.append(await _alert(key, "horizon_alert", "critical", title, detail,
                                      {"hours_left": round(hours_left, 2)},
                                      notify=True, webhook=webhook, cooldown_seconds=3 * 3600))

    return fired


async def report_anomaly(key: dict[str, Any], anomaly: dict[str, Any]) -> dict[str, Any] | None:
    policy = key.get("policy", "observe")
    settings = store.get_settings()
    title = f"Traffic anomaly on {key['name']} ({anomaly['ratio']}× baseline)"
    detail = (f"Hour bucket at {anomaly['hour']}: ${anomaly['cost']:.2f} vs baseline "
              f"${anomaly['baseline']:.2f} (robust z={anomaly['z']}). "
              f"Possible runaway agent or leaked key.")
    return await _alert(key, "anomaly", "critical" if anomaly["ratio"] >= 3 else "warning",
                        title, detail, anomaly,
                        notify=policy != "observe",
                        webhook=settings.get("webhook_url", ""),
                        cooldown_kind=f"anomaly_{anomaly['hour']}")


async def _alert(key: dict[str, Any], kind: str, severity: str, title: str, detail: str,
                 meta: dict[str, Any] | None = None, *, notify: bool = True,
                 webhook: str = "", cooldown_kind: str | None = None, cooldown_seconds: float = 3600) -> dict[str, Any]:
    cooldown_kind = cooldown_kind or kind
    if not store.can_fire(key["vk"], cooldown_kind, cooldown_seconds=cooldown_seconds):
        return {"fired": False, "kind": kind}
    alert_id = store.insert_alert(key["vk"], kind, severity, title, detail, meta or {})
    if notify and webhook:
        payload = build_slack_payload(title, detail, severity,
                                      {"key": key["name"], "policy": key.get("policy", "observe")})
        ok = await fire_webhook(webhook, payload)
        return {"fired": True, "kind": kind, "alert_id": alert_id, "webhook_ok": ok}
    return {"fired": True, "kind": kind, "alert_id": alert_id}


async def send_test_webhook() -> dict[str, Any]:
    settings = store.get_settings()
    url = settings.get("webhook_url", "")
    payload = build_slack_payload(
        "Foresight test alert",
        "Webhook path verified — predictive governance alerts will land here.",
        "info",
        {"source": "bifrost-foresight", "mode": "test"},
    )
    ok = await fire_webhook(url, payload) if url else False
    return {"webhook_url": url, "delivered": ok, "payload": payload}
