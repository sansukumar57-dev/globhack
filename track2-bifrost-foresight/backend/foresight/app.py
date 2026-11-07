"""Bifrost Foresight — the missing predictive layer for the open-source gateway.

One process, three jobs:
  1. Metering sidecar: OpenAI-compatible /v1/* proxy that sits in front of
     Bifrost, attributes every token to a virtual key and computes cost.
  2. Autopilot: acts on what Bifrost OSS cannot see — projected budget
     exhaustion and same-hour traffic anomalies — before money is gone.
  3. Operator console API consumed by the Foresight dashboard.
"""
from __future__ import annotations

import asyncio
import json
import os
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import anomaly as anomaly_mod
from . import forecast as forecast_mod
from . import model as model_mod
from . import policy as policy_mod
from . import store
from .metering import meter_chat_request
from .pricing import cost_usd, suggest_downgrade, unit_ratio
from .seed import seed as run_seed

BIFROST_URL = os.environ.get("FORESIGHT_BIFROST_URL", "http://localhost:8080").rstrip("/")
STATIC_DIR = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"
WINDOW_S = forecast_mod.WINDOW_SECONDS


@asynccontextmanager
async def lifespan(app: FastAPI):
    store.init_db()
    if store.count_since(None, 0) == 0:
        # First boot: load the demo dataset so the console is alive immediately.
        run_seed()

    async def _warm() -> None:
        try:
            await asyncio.to_thread(model_mod.intelligence)
            await asyncio.to_thread(model_mod.anomaly_scan)
        except Exception:
            pass

    # Warm the trained model's cache off the critical path — the first
    # page load after boot shouldn't pay the backtest cost.
    asyncio.create_task(_warm())
    yield


app = FastAPI(
    title="Bifrost Foresight",
    description="Predictive spend and traffic-anomaly autopilot for the open-source Bifrost gateway.",
    version="0.1.0",
    lifespan=lifespan,
)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=False,
                   allow_methods=["*"], allow_headers=["*"])

_bifrost_probe: dict[str, Any] = {"ts": 0.0, "ok": False}


async def bifrost_reachable() -> bool:
    if time.time() - _bifrost_probe["ts"] < 5.0:
        return _bifrost_probe["ok"]
    ok = False
    try:
        async with httpx.AsyncClient(timeout=1.5) as client:
            resp = await client.get(f"{BIFROST_URL}/api/config")
            ok = resp.status_code < 500
    except Exception:
        ok = False
    _bifrost_probe.update(ts=time.time(), ok=ok)
    return ok


# ------------------------------------------------------------------ helpers

def _forecast_for(key: dict[str, Any], now: float) -> dict[str, Any]:
    hourly = store.hourly_series(key["vk"], now - 21 * 86400, now)
    spent = store.spend_since(key["vk"], now - WINDOW_S)
    settings = store.get_settings()
    horizon = float(settings.get("alert_horizon_hours", "48"))
    fc = forecast_mod.forecast(budget_usd=key["budget_usd"], spent_usd=spent,
                               hourly=hourly, now=now, alert_horizon_hours=horizon)
    fc["hourly"] = hourly
    return fc


def _key_payload(key: dict[str, Any], now: float) -> dict[str, Any]:
    fc = _forecast_for(key, now)
    alerts = [a for a in store.list_alerts(200) if a["vk"] == key["vk"]][:5]
    return {
        "vk": key["vk"],
        "name": key["name"],
        "team": key["team"],
        "color": key.get("color") or "#7c5cff",
        "policy": key["policy"],
        "downgrade_to": key.get("downgrade_to") or "",
        "downgrade_active": bool(key.get("downgrade_active")) and now < float(key.get("downgrade_until") or 0),
        "model_breakdown": store.model_breakdown(key["vk"], now - WINDOW_S),
        "recent_alerts": alerts,
        **{k: v for k, v in fc.items() if k != "hourly"},
        "hourly": fc["hourly"],
    }


def _record_usage(vk: str, model: str, prompt_tokens: int, completion_tokens: int,
                  latency_ms: int, source: str, exact: bool) -> dict[str, Any]:
    cost = cost_usd(model, prompt_tokens, completion_tokens)
    store.insert_event(vk, model, prompt_tokens, completion_tokens, cost,
                       latency_ms, source=source, exact=exact)
    return {"cost_usd": cost, "prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens}


async def _post_metering_actions(key: dict[str, Any], now: float) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []
    try:
        fc = _forecast_for(key, now)
        actions.extend(await policy_mod.post_response(key, fc))
        settings = store.get_settings()
        hourly = fc["hourly"]
        anomalies = anomaly_mod.detect(hourly,
                                       threshold=float(settings.get("anomaly_z", "3.5")),
                                       min_cost=0.5, trailing_hours=12)
        for a in anomalies:
            # only act on anomalies from the last 3 hours and only once per bucket
            if now - a["hour"] < 3 * 3600:
                result = await policy_mod.report_anomaly(key, a)
                if result:
                    actions.append(result)
    except Exception as exc:  # never let alerting break the data path
        actions.append({"fired": False, "error": str(exc)})
    return actions


def _key_from_auth(request: Request) -> tuple[str, dict[str, Any] | None]:
    auth = request.headers.get("authorization", "")
    token = ""
    if auth.lower().startswith("bearer "):
        token = auth.split(" ", 1)[1].strip()
    if not token:
        token = (request.headers.get("x-foresight-key") or "").strip()
    if not token:
        return "unattributed", None
    return token, store.get_key(token)


# =====================================================================
# 1) OpenAI-compatible metering proxy (point your SDK here, not at Bifrost)
# =====================================================================

@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    vk, key = _key_from_auth(request)
    now = time.time()

    action = "allow"
    reason = "within_policy"
    model_override: str | None = None
    if key:
        fc = _forecast_for(key, now)
        gate = await policy_mod.check_request(key, fc)
        action = gate["action"]
        reason = gate["reason"]
        model_override = gate["model_override"]
        if action == "block":
            return JSONResponse(
                status_code=429,
                headers={"Retry-After": "900", "X-Foresight-Action": "block",
                         "X-Foresight-Reason": "soft_cap"},
                content={"error": {"message": reason,
                                   "type": "foresight_soft_cap",
                                   "code": "budget_pacing_block",
                                   "hint": "Raise the key's budget or switch its policy in the Foresight console."}})
        if model_override:
            original = str(body.get("model", ""))
            prefix, sep, _ = original.rpartition("/")
            body["model"] = f"{prefix}/{model_override}" if sep else model_override

    fwd_headers = {k: v for k, v in request.headers.items()
                   if k.lower() not in ("host", "content-length", "connection")}
    fwd_headers["content-type"] = "application/json"

    is_stream = bool(body.get("stream"))
    start = time.time()
    # NOTE: no `async with` here — `return StreamingResponse(...)` inside an
    # async-with closes the client before the SSE body is pumped, which aborts
    # Bifrost mid-stream (RST) and kills the metering. For streaming, relay()
    # owns the client and closes it after the stream ends.
    http_client = httpx.AsyncClient(timeout=httpx.Timeout(120.0, connect=10.0))
    try:
        if is_stream:
            req = http_client.build_request("POST", f"{BIFROST_URL}/v1/chat/completions",
                                            json=body, headers=fwd_headers)
            upstream = await http_client.send(req, stream=True)
            collected = bytearray()

            async def relay():
                try:
                    async for chunk in upstream.aiter_bytes():
                        collected.extend(chunk)
                        yield chunk
                    await upstream.aclose()
                except httpx.HTTPError:
                    pass  # upstream died mid-stream — meter whatever arrived below
                await _meter_streamed(vk, body, bytes(collected), start, key, now)
                await http_client.aclose()

            return StreamingResponse(relay(), status_code=upstream.status_code,
                                     media_type="text/event-stream",
                                     headers={"Cache-Control": "no-cache",
                                              "X-Foresight-Action": action,
                                              "X-Foresight-Reason": reason,
                                              "X-Foresight-Streamed": "1"})

        upstream = await http_client.post(f"{BIFROST_URL}/v1/chat/completions",
                                          json=body, headers=fwd_headers)
    except httpx.ConnectError:
        await http_client.aclose()
        return JSONResponse(status_code=502, content={
            "error": {"message": f"Foresight could not reach Bifrost at {BIFROST_URL}. "
                                 "Start the gateway (see README quickstart).",
                      "type": "foresight_upstream_unreachable"}})
    except Exception as exc:
        await http_client.aclose()
        return JSONResponse(status_code=502, content={
            "error": {"message": f"Upstream error: {exc}", "type": "foresight_upstream_error"}})

    latency_ms = int((time.time() - start) * 1000)
    try:
        upstream_json = upstream.json()
    except Exception:
        upstream_json = None

    if upstream_json is not None and upstream.status_code < 400:
        pt, ct, exact = meter_chat_request(body, upstream_json)
        model_used = str(body.get("model", "unknown"))
        _record_usage(vk, model_used, pt, ct, latency_ms, source="live", exact=exact)
        if key:
            await _post_metering_actions(key, time.time())

    resp_headers = {k: v for k, v in upstream.headers.items()
                    if k.lower() not in ("transfer-encoding", "content-length", "connection")}
    resp_headers["x-foresight-action"] = action
    resp_headers["x-foresight-reason"] = reason
    if upstream_json is not None and upstream.status_code < 400:
        resp_headers["x-foresight-cost-usd"] = f"{cost_usd(str(body.get('model', 'unknown')), pt, ct):.6f}"
    await http_client.aclose()   # upstream was fully consumed; release the pool
    return JSONResponse(status_code=upstream.status_code, content=upstream_json if upstream_json is not None else {"raw": upstream.text},
                        headers=resp_headers)


async def _meter_streamed(vk: str, body: dict[str, Any], raw: bytes, start: float,
                    key: dict[str, Any] | None, now: float) -> None:
    text = raw.decode("utf-8", errors="ignore")
    usage = None
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("data:"):
            continue
        payload = line[5:].strip()
        if payload == "[DONE]":
            continue
        try:
            obj = json.loads(payload)
        except json.JSONDecodeError:
            continue
        if isinstance(obj.get("usage"), dict):
            usage = obj["usage"]
    latency_ms = int((time.time() - start) * 1000)
    prompt_est = 0
    completion_est = 0
    exact = False
    if usage:
        try:
            prompt_est = int(usage.get("prompt_tokens", 0))
            completion_est = int(usage.get("completion_tokens", 0))
            exact = True
        except (TypeError, ValueError):
            usage = None
    if not exact:
        from .metering import estimate_tokens, message_text
        prompt_est = estimate_tokens(message_text(body.get("messages")))
        completion_est = estimate_tokens(text)
    model_used = str(body.get("model", "unknown"))
    _record_usage(vk, model_used, prompt_est, completion_est, latency_ms, source="live", exact=exact)
    if key:
        await _post_metering_actions(key, time.time())


@app.api_route("/v1/models", methods=["GET"])
async def models_proxy(request: Request):
    auth = request.headers.get("authorization", "")
    headers = {"authorization": auth} if auth else {}
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            upstream = await client.get(f"{BIFROST_URL}/v1/models", headers=headers)
        return JSONResponse(status_code=upstream.status_code, content=upstream.json())
    except Exception:
        return JSONResponse(status_code=502, content={"error": {"message": "Bifrost unreachable"}})


# =====================================================================
# 2) Operator console API
# =====================================================================

@app.get("/api/health")
async def api_health():
    return {"status": "ok", "service": "bifrost-foresight", "version": "0.1.0",
            "bifrost_url": BIFROST_URL, "bifrost_reachable": await bifrost_reachable(),
            "forecaster_loaded": model_mod.load() is not None}


@app.get("/api/overview")
async def api_overview():
    now = time.time()
    keys = store.list_keys()
    payloads = [_key_payload(k, now) for k in keys]
    statuses = [p["status"] for p in payloads]
    hourly_all = store.hourly_series(None, now - 24 * 3600, now)
    intel = model_mod.intelligence_cached()
    model_forecast = intel["forecast"] if intel else None
    model_meta = intel["forecast_meta"] if intel else None
    model_risk = intel["risk"] if intel else None
    model_paths = intel.get("paths") if intel else None
    today_start = now - (now % 86400)
    return {
        "generated_at": now,
        "bifrost_url": BIFROST_URL,
        "bifrost_reachable": await bifrost_reachable(),
        "spend_today": round(store.spend_since(None, today_start), 4),
        "spend_window": round(store.spend_since(None, now - WINDOW_S), 4),
        "requests_today": store.count_since(None, today_start),
        "burn_rate_6h": round(sum(float(b["cost"]) for b in hourly_all[-6:]) / 6, 4),
        "burn_rate_24h": round(sum(float(b["cost"]) for b in hourly_all) / max(len(hourly_all), 1), 4),
        "projected_30d_cost": round(sum(float(b["cost"]) for b in hourly_all) / max(len(hourly_all), 1) * 24 * 30, 2),
        "keys_critical": sum(1 for s in statuses if s in ("critical", "exhausted")),
        "keys_watch": sum(1 for s in statuses if s == "watch"),
        "keys_healthy": sum(1 for s in statuses if s == "healthy"),
        "overall_status": forecast_mod.overall_severity(statuses),
        "keys": payloads,
        "hourly_all": hourly_all,
        "model_forecast": model_forecast,
        "model_meta": model_meta,
        "model_risk": model_risk,
        "model_paths": model_paths,
        "top_models": store.model_breakdown(None, now - WINDOW_S)[:6],
        "recent_alerts": store.list_alerts(5),
    }


@app.get("/api/keys")
async def api_keys():
    now = time.time()
    return {"keys": [_key_payload(k, now) for k in store.list_keys()]}


@app.get("/api/keys/{vk}")
async def api_key_detail(vk: str):
    key = store.get_key(vk)
    if not key:
        raise HTTPException(status_code=404, detail="Unknown virtual key")
    now = time.time()
    payload = _key_payload(key, now)
    payload["recent_requests"] = [r for r in store.recent_requests(200) if r["vk"] == vk][:25]
    return payload


@app.patch("/api/keys/{vk}")
async def api_key_update(vk: str, request: Request):
    key = store.get_key(vk)
    if not key:
        raise HTTPException(status_code=404, detail="Unknown virtual key")
    body = await request.json()
    fields: dict[str, Any] = {}
    if "budget_usd" in body:
        fields["budget_usd"] = max(1.0, float(body["budget_usd"]))
    if "policy" in body:
        policy = str(body["policy"])
        if policy not in ("observe", "notify", "soft_cap", "pacing"):
            raise HTTPException(status_code=400, detail="policy must be observe|notify|soft_cap|pacing")
        fields["policy"] = policy
    if "downgrade_to" in body:
        fields["downgrade_to"] = str(body["downgrade_to"])[:64]
    if fields:
        store.update_key(vk, fields)
    now = time.time()
    return _key_payload(store.get_key(vk), now)


@app.post("/api/keys/{vk}/downgrade")
async def api_key_downgrade(vk: str, request: Request):
    key = store.get_key(vk)
    if not key:
        raise HTTPException(status_code=404, detail="Unknown virtual key")
    body = await request.json() if await _has_json_body(request) else {}
    target = str(body.get("model") or key.get("downgrade_to") or "").strip()
    if not target:
        raise HTTPException(status_code=400, detail="No downgrade target configured for this key")
    hours = float(body.get("hours", 6))
    store.update_key(vk, {"downgrade_active": 1, "downgrade_until": time.time() + hours * 3600,
                          "downgrade_to": target})
    store.insert_alert(vk, "manual_downgrade", "info",
                       f"Manual downgrade → {target}",
                       f"Operator armed a {hours:.0f}h downgrade to {target} for {key['name']}.",
                       {"target": target, "hours": hours})
    return {"ok": True, "downgrade_to": target, "downgrade_until": time.time() + hours * 3600}


@app.post("/api/keys/{vk}/release")
async def api_key_release(vk: str):
    key = store.get_key(vk)
    if not key:
        raise HTTPException(status_code=404, detail="Unknown virtual key")
    store.update_key(vk, {"downgrade_active": 0, "downgrade_until": 0})
    return {"ok": True}


async def _has_json_body(request: Request) -> bool:
    try:
        body = await request.body()
        return bool(body.strip())
    except Exception:
        return False


@app.get("/api/anomalies")
async def api_anomalies():
    now = time.time()
    settings = store.get_settings()
    threshold = float(settings.get("anomaly_z", "3.5"))
    keys = {k["vk"]: k for k in store.list_keys()}
    out: list[dict[str, Any]] = []
    for vk, key in keys.items():
        hourly = store.hourly_series(vk, now - 21 * 86400, now)
        for a in anomaly_mod.detect(hourly, threshold=threshold, min_cost=0.5, trailing_hours=24 * 7):
            out.append({"vk": vk, "key_name": key["name"], "team": key["team"],
                        "color": key.get("color"), **a})
    out.sort(key=lambda x: x["hour"], reverse=True)
    names = {k["vk"]: k for k in store.list_keys()}
    scores = model_mod.anomaly_scan_cached() or []
    for s in scores:
        k = names.get(s["vk"])
        if k:
            s["key_name"] = k.get("name", s["vk"])
            s["team"] = k.get("team", "")
            s["color"] = k.get("color")
    return {"anomalies": out[:30], "threshold": threshold, "window_days": 7,
            "model_scores": scores, "model_sigma": model_mod.status().get("anomaly_resid_sigma")}


@app.get("/api/alerts")
async def api_alerts(limit: int = 50):
    keys = {k["vk"]: k.get("name", k["vk"]) for k in store.list_keys()}
    alerts = store.list_alerts(limit)
    for a in alerts:
        a["key_name"] = keys.get(a["vk"], a["vk"])
    return {"alerts": alerts}


@app.get("/api/requests")
async def api_requests(limit: int = 60):
    return {"requests": store.recent_requests(min(limit, 200))}


@app.post("/api/simulator")
async def api_simulator(request: Request):
    body = await request.json()
    vk = str(body.get("vk", ""))
    key = store.get_key(vk)
    if not key:
        raise HTTPException(status_code=404, detail="Unknown virtual key")
    shift_pct = float(body.get("shift_pct", 50)) / 100.0
    to_model = str(body.get("to_model", "gpt-4o-mini"))
    breakdown = store.model_breakdown(vk, time.time() - WINDOW_S)
    from_model = str(body.get("from_model") or (breakdown[0]["model"] if breakdown else "acme-llm/gpt-4o"))
    from_short = from_model.split("/")[-1]
    share_cost = next((b["cost"] for b in breakdown if b["model"] == from_model), 0.0)
    ratio = unit_ratio(from_model, to_model)
    savings_30d = share_cost * shift_pct * (1.0 - ratio)
    now = time.time()
    spent = store.spend_since(vk, now - WINDOW_S)
    burn24 = sum(float(b["cost"]) for b in store.hourly_series(vk, now - 24 * 3600, now)) / 24
    fc = forecast_mod.forecast(budget_usd=key["budget_usd"], spent_usd=spent,
                               hourly=store.hourly_series(vk, now - 21 * 86400, now), now=now)
    return {
        "key": {"vk": key["vk"], "name": key["name"], "budget_usd": key["budget_usd"]},
        "from_model": from_model, "from_model_short": from_short,
        "to_model": to_model,
        "share_cost_30d": round(share_cost, 2),
        "unit_cost_ratio": round(ratio, 3),
        "shift_pct": int(shift_pct * 100),
        "savings_30d": round(savings_30d, 2),
        "savings_year": round(savings_30d * 12, 2),
        "projected_30d_after": round(max(0.0, fc["projected_30d_cost"] - savings_30d), 2),
        "burn_rate_24h": round(burn24, 4),
        "budget_pct_after": round(min(1.0, (fc["projected_30d_cost"] - savings_30d) / key["budget_usd"]), 3)
        if key["budget_usd"] else None,
        "suggestion": suggest_downgrade(from_model),
    }


class StressRequest(BaseModel):
    vk: str
    multiplier: float = 2.0


@app.post("/api/simulator/stress")
def api_simulator_stress(body: StressRequest):
    """Counterfactual rollout through the trained committee.

    "What if key <vk> spent <multiplier>x its current spend shape?" — every
    member re-runs with the target key's trailing buckets scaled, and the
    response reports the fleet curve and per-key breach metrics under both
    demand regimes. Synchronous on purpose: FastAPI runs it in the threadpool,
    off the event loop.
    """
    key = store.get_key(body.vk)
    if not key:
        raise HTTPException(status_code=404, detail="Unknown virtual key")
    out = model_mod.stress_projection(body.vk, body.multiplier)
    if out is None:
        raise HTTPException(
            status_code=503,
            detail="Stress test unavailable — the trained model is not loaded (try /api/model/train).",
        )
    now = time.time()
    out["hourly_all"] = store.hourly_series(None, now - 24 * 3600, now)
    return out


@app.get("/api/recommendations")
async def api_recommendations():
    """Fleet right-sizing: for each key, estimate savings from switching its
    dominant model to the cheapest viable drop-in for 100% of traffic."""
    now = time.time()
    out = []
    for key in store.list_keys():
        breakdown = store.model_breakdown(key["vk"], now - WINDOW_S)
        if not breakdown:
            continue
        dominant = breakdown[0]
        target = key.get("downgrade_to") or suggest_downgrade(dominant["model"])
        if not target or target.split("/")[-1] == str(dominant["model"]).split("/")[-1]:
            continue
        ratio = unit_ratio(dominant["model"], target)
        savings = dominant["cost"] * (1.0 - ratio)
        if savings <= 0.01:
            continue
        out.append({
            "vk": key["vk"], "name": key["name"], "team": key["team"], "color": key.get("color"),
            "dominant_model": dominant["model"], "dominant_cost": round(dominant["cost"], 2),
            "target": target, "savings_30d": round(savings, 2), "savings_year": round(savings * 12, 2),
        })
    out.sort(key=lambda r: r["savings_30d"], reverse=True)
    return {"recommendations": out, "total_savings_30d": round(sum(r["savings_30d"] for r in out), 2)}


@app.get("/api/model")
async def api_model():
    """Status of the compact trained forecaster (artifact, metrics, size)."""
    return model_mod.status()


@app.post("/api/model/train")
def api_model_train():
    """Train the forecaster on the live metered history. Runs in the threadpool:
    a full committee pass takes long enough that we must not block the loop."""
    try:
        return model_mod.retrain_from_store()
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/settings")
async def api_get_settings():
    settings = store.get_settings()
    return {"settings": settings, "defaults": store.DEFAULT_SETTINGS}


@app.put("/api/settings")
async def api_put_settings(request: Request):
    body = await request.json()
    allowed = {"webhook_url", "soft_cap_pct", "alert_horizon_hours", "anomaly_z", "pacing_downgrade_hours"}
    updated = {}
    for k, v in body.items():
        if k in allowed:
            store.set_setting(k, str(v))
            updated[k] = str(v)
    return {"updated": updated, "settings": store.get_settings()}


@app.post("/api/settings/test-webhook")
async def api_test_webhook():
    return await policy_mod.send_test_webhook()


@app.get("/api/webhook-sink")
async def api_webhook_sink(limit: int = 10):
    return {"sink": store.sink_list(limit)}


@app.delete("/api/webhook-sink")
async def api_webhook_sink_clear():
    store.sink_clear()
    return {"ok": True}


@app.post("/api/webhook-sink")
async def api_webhook_sink_ingest(request: Request):
    body = await request.body()
    store.sink_record(dict(request.headers), body.decode("utf-8", errors="ignore"))
    return {"ok": True}


@app.post("/api/seed")
async def api_seed():
    meta = run_seed()
    return {"ok": True, **meta}


_DEMO_PROMPTS = [
    "Summarize our canary analysis for the checkout service and flag regressions.",
    "Generate a Terraform module for an S3-backed static site with CloudFront.",
    "Explain why our p99 latency spiked after the last deploy and propose fixes.",
    "Draft a postmortem for yesterday's database failover incident.",
    "Refactor this retry loop to use exponential backoff with jitter.",
    "Write SQL to find accounts whose usage grew 3x week-over-week.",
    "Review the CI pipeline config and suggest cost reductions.",
    "What are the failure modes of our semantic cache under high cardinality?",
]


@app.post("/api/replay/live")
async def api_replay_live(request: Request):
    """Fire N real requests through the full stack (Foresight -> Bifrost -> upstream)."""
    body = await request.json() if await _has_json_body(request) else {}
    n = max(1, min(int(body.get("n", 8)), 25))
    vk = str(body.get("vk", "sk-bf-foresight-growth-0001"))
    model = str(body.get("model", "acme-llm/gpt-4o"))
    port = int(os.environ.get("FORESIGHT_PORT", "8400"))
    key = store.get_key(vk)
    if not key:
        raise HTTPException(status_code=404, detail="Unknown virtual key")

    results = []
    async with httpx.AsyncClient(timeout=30.0) as client:
        for i in range(n):
            prompt = _DEMO_PROMPTS[i % len(_DEMO_PROMPTS)]
            try:
                resp = await client.post(
                    f"http://127.0.0.1:{port}/v1/chat/completions",
                    headers={"authorization": f"Bearer {vk}", "content-type": "application/json"},
                    json={"model": model,
                          "messages": [{"role": "system", "content": "You are a senior infrastructure engineer."},
                                       {"role": "user", "content": prompt}],
                          "max_tokens": 400})
                cost = resp.headers.get("x-foresight-cost-usd")
                results.append({"i": i, "status": resp.status_code, "cost_usd": cost,
                                "action": resp.headers.get("x-foresight-action")})
            except Exception as exc:
                results.append({"i": i, "status": 0, "error": str(exc)})
    return {"fired": len(results), "results": results}


# --------------------------------------------------------------- static UI

if STATIC_DIR.exists():
    app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="ui")
