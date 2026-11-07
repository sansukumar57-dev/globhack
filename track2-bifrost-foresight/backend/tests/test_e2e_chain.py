"""End-to-end chain test: a REAL request through Fakellm → Bifrost OSS → Foresight.

Unlike the pure unit tests, this module starts the full demo architecture as
live processes on random free ports (exactly what scripts/run-demo.ps1 launches,
sandboxed so it can never touch the developer's own demo or databases):

  1. the demo upstream (foresight.fakellm, the acme-llm stand-in),
  2. the actual Bifrost gateway binary via `npx @maximhq/bifrost`, pointed at a
     patched copy of bifrost-config (upstream base_url rewritten to the test port),
  3. Foresight itself (`main.py`) as a real uvicorn process — using the
     FORESIGHT_PORT / FORESIGHT_BIFROST_URL / FORESIGHT_DB_PATH env hooks.

It then proves the README story end to end: an OpenAI SDK-shaped request is
relayed through the gateway, metered with exact upstream usage, priced by the
embedded catalog, attributed to the virtual key that Bifrost itself authenticates
— and Bifrost's own token enforcement rejects foreign keys.

Every HTTP call is made with a hard timeout, so a wedged daemon surfaces as a
test failure instead of a hang. Skipped (not failed) when Node/npx is
unavailable, the repo's bifrost-config is absent, or a daemon cannot come up.
Set FORESIGHT_E2E=skip to force skip.
"""
from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest
import httpx

ROOT = Path(__file__).resolve().parents[2]          # track2-bifrost-foresight/
BACKEND = ROOT / "backend"                          # cwd: makes `foresight` importable
CONFIG_SRC = ROOT / "bifrost-config"

VK = "sk-bf-foresight-sandbox-0004"                 # Hackathon Sandbox — observe policy
AUTH = {"Authorization": f"Bearer {VK}"}
MODEL = "acme-llm/gpt-4o"

_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))  # never via a system proxy


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _poll(url: str, timeout: float, what: str) -> None:
    """Wait until `url` gets served at all.

    ANY HTTP response (even 403/401) proves the daemon is up — newer Bifrost
    versions lock the admin /api surface until a setup token exists, so the
    probe must not treat 4xx as absence.
    """
    deadline, last = time.time() + timeout, "no attempts"
    while time.time() < deadline:
        try:
            with _OPENER.open(url, timeout=2) as resp:
                resp.read()
                return
        except urllib.error.HTTPError as exc:      # 4xx/5xx ⇒ server is speaking HTTP
            try:
                exc.read()
            except Exception:
                pass
            return
        except Exception as exc:                    # connection refused/reset ⇒ not yet
            last = f"{type(exc).__name__}: {exc}"
        time.sleep(0.4)
    raise TimeoutError(what, last)


def _kill(proc: subprocess.Popen | None) -> None:
    if proc is None or proc.poll() is not None:
        return
    try:
        if os.name == "nt":
            subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                           capture_output=True, timeout=15)
        else:
            proc.terminate()
        proc.wait(timeout=15)
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass


def _spawn(args: list[str], cwd: Path, env: dict[str, str], log_name: str,
           log_dir: Path) -> subprocess.Popen:
    log = (log_dir / log_name).open("w", encoding="utf-8")
    return subprocess.Popen(args, cwd=str(cwd), env=env, stdout=log, stderr=subprocess.STDOUT)


@pytest.fixture(scope="module")
def chain(tmp_path_factory, request):
    procs: list[subprocess.Popen] = []
    saved: dict[str, str | None] = {}
    log_dir = tmp_path_factory.mktemp("e2e-logs")
    try:
        if os.environ.get("FORESIGHT_E2E", "").lower() == "skip":
            pytest.skip("FORESIGHT_E2E=skip")
        if shutil.which("node") is None or shutil.which("npx") is None:
            pytest.skip("Node/npx not on PATH — needed to launch the real Bifrost gateway")
        if not (CONFIG_SRC / "config.json").exists():
            pytest.skip("bifrost-config/config.json is missing")

        # Loopback hops must bypass any configured system proxy.
        for name in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy",
                     "https_proxy", "all_proxy"):
            saved[name] = os.environ.get(name)
            os.environ.pop(name, None)
        saved["NO_PROXY"] = os.environ.get("NO_PROXY")
        os.environ["NO_PROXY"] = "127.0.0.1,localhost"

        fake_port, bif_port, fg_port = _free_port(), _free_port(), _free_port()
        fake_url = f"http://127.0.0.1:{fake_port}"
        bif_url = f"http://127.0.0.1:{bif_port}"
        saga_url = f"http://127.0.0.1:{fg_port}"

        # --- 1. demo upstream (acme-llm stand-in)
        procs.append(_spawn(
            [sys.executable, "-c",
             f"import uvicorn; from foresight.fakellm import app; "
             f"uvicorn.run(app, host='127.0.0.1', port={fake_port}, log_level='warning')"],
            BACKEND, os.environ.copy(), "fakellm.log", log_dir))
        _poll(f"{fake_url}/health", 60, "demo upstream did not start")

        # --- 2. Bifrost OSS from a patched copy of the demo config
        appdir = tmp_path_factory.mktemp("bifrost-e2e") / "config"
        shutil.copytree(CONFIG_SRC, appdir)
        cfg_path = appdir / "config.json"
        cfg = json.loads(cfg_path.read_text())
        cfg["providers"]["acme-llm"]["network_config"]["base_url"] = fake_url
        cfg_path.write_text(json.dumps(cfg, indent=2))

        npx = shutil.which("npx")
        if npx is None:
            pytest.skip("npx unavailable")
        procs.append(_spawn([npx, "-y", "@maximhq/bifrost",
                             "-app-dir", str(appdir), "-port", str(bif_port)],
                            BACKEND, os.environ.copy(), "bifrost.log", log_dir))
        try:
            _poll(f"{bif_url}/api/config", 240,
                  "Bifrost gateway did not come up (first npx download can be slow)")
        except TimeoutError:
            pytest.skip("Bifrost did not become reachable — start it per the README "
                        "quickstart and re-run this module")

        # --- 3. Foresight itself as a real uvicorn process on a throwaway DB
        child_env = os.environ.copy()
        child_env.update({
            "FORESIGHT_PORT": str(fg_port),
            "FORESIGHT_BIFROST_URL": bif_url,
            "FORESIGHT_DB_PATH": str(tmp_path_factory.mktemp("foresight-e2e") / "foresight.db"),
        })
        procs.append(_spawn([sys.executable, "main.py"], BACKEND, child_env,
                            "foresight.log", log_dir))
        _poll(f"{saga_url}/api/health", 90, "Foresight did not start (see e2e-logs)")

        client = httpx.Client(base_url=saga_url, timeout=60.0, trust_env=False)
        seeded = False
        for _ in range(120):                        # lifespan seeds the demo fleet on first boot
            try:
                body = client.get("/api/overview").json()
            except httpx.HTTPError:                 # still booting; uvicorn binds after lifespan
                time.sleep(0.5)
                continue
            if len(body.get("keys", [])) == 4:
                seeded = True
                break
            time.sleep(0.5)
        assert seeded, "Foresight never seeded the 4 virtual keys"

        # keep the pager quiet; sink delivery assertions live in the unit tests
        client.put("/api/settings", json={"webhook_url": ""})

        yield {"client": client, "fake_port": fake_port,
               "bifrost_port": bif_port, "fg_port": fg_port,
               "procs": {"fakellm": procs[0], "bifrost": procs[1], "foresight": procs[2]}}
    finally:
        for p in reversed(procs):
            _kill(p)
        for key, val in saved.items():
            if val is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = val


# ---------------------------------------------------------------------- tests

def test_health_sees_the_live_gateway(chain):
    r = chain["client"].get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["bifrost_reachable"] is True
    assert body["bifrost_url"].endswith(f":{chain['bifrost_port']}")


def test_models_proxy_passthrough(chain):
    r = chain["client"].get("/v1/models", headers=AUTH)
    assert r.status_code == 200
    assert "gpt-4o" in r.text


def test_bifrost_auth_rejects_foreign_keys(chain):
    events_before = _live_events(chain)
    r = chain["client"].post("/v1/chat/completions", headers={"Authorization": "Bearer sk-not-real"},
                             json={"model": MODEL,
                                   "messages": [{"role": "user", "content": "nope"}]})
    assert 400 <= r.status_code < 500
    assert _live_events(chain) == events_before     # failures are never metered


def test_completion_relayed_metered_priced_attributed(chain):
    c = chain["client"]
    r = c.post("/v1/chat/completions", headers=AUTH, json={
        "model": MODEL,
        "messages": [{"role": "user", "content": "foresight e2e probe"}],
    })
    assert r.status_code == 200
    body = r.json()
    assert body["object"] == "chat.completion"
    assert "Here is a synthesized completion" in body["choices"][0]["message"]["content"]

    # the gateway chain answered and the proxy labeled the response
    assert r.headers["x-foresight-action"] == "allow"
    assert r.headers["x-foresight-reason"] == "within_policy"

    # exact usage from the upstream, priced by the embedded gpt-4o catalog
    usage = body["usage"]
    pt, ct = usage["prompt_tokens"], usage["completion_tokens"]
    expected = (pt * 2.50 + ct * 10.00) / 1_000_000.0
    assert float(r.headers["x-foresight-cost-usd"]) == pytest.approx(expected, abs=1e-6)

    events = _live_events(chain)
    assert len(events) == 1
    ev = events[0]
    assert ev["model_short"] == "gpt-4o"
    assert ev["exact"] == 1
    assert ev["prompt_tokens"] == pt and ev["completion_tokens"] == ct
    assert ev["cost_usd"] == pytest.approx(expected, rel=1e-4)


def test_streamed_completion_meters_sse(chain):
    c = chain["client"]
    before = len(_live_events(chain))
    r = c.post("/v1/chat/completions", headers=AUTH, json={
        "model": MODEL,
        "messages": [{"role": "user", "content": "foresight sse probe"}],
        "stream": True,
        "stream_options": {"include_usage": True},
    })
    assert r.status_code == 200
    assert "text/event-stream" in r.headers.get("content-type", "")
    assert r.headers["x-foresight-streamed"] == "1"

    # reassemble the relayed SSE frames: deltas rebuild the completion,
    # the final chunk carries the upstream's own usage
    content, usage = "", None
    for line in r.text.splitlines():
        line = line.strip()
        if not line.startswith("data:"):
            continue
        payload = line[5:].strip()
        if payload == "[DONE]":
            break
        try:
            obj = json.loads(payload)
        except json.JSONDecodeError:
            continue
        if isinstance(obj.get("usage"), dict):
            usage = obj["usage"]
        for choice in obj.get("choices") or []:
            delta = choice.get("delta") or {}
            content += str(delta.get("content") or "")
    assert "Here is a synthesized completion" in content
    assert usage is not None and usage["prompt_tokens"] > 0

    events = _live_events(chain)
    assert len(events) == before + 1
    ev = events[0]
    assert ev["prompt_tokens"] == usage["prompt_tokens"]
    assert ev["completion_tokens"] == usage["completion_tokens"]
    assert ev["exact"] == 1
    assert ev["cost_usd"] > 0


def test_console_renders_the_seeded_fleet_with_live_traffic(chain):
    r = chain["client"].get("/api/overview")
    assert r.status_code == 200
    body = r.json()

    by_vk = {k["vk"]: k for k in body["keys"]}
    assert set(by_vk) == {"sk-bf-foresight-growth-0001", "sk-bf-foresight-support-0002",
                          "sk-bf-foresight-staging-0003", VK}

    growth = by_vk["sk-bf-foresight-growth-0001"]
    assert 0.80 <= growth["pct_used"] <= 0.95            # the seeded 86%-burned story
    assert growth["hours_until_exhaustion"] is not None  # a real projection, not a placeholder
    assert growth["status"] in ("critical", "exhausted")

    sandbox = by_vk[VK]
    assert 0 < sandbox["pct_used"] <= 0.10               # small live spend on the dormant key
    models = {mb["model"] for mb in sandbox["model_breakdown"]}
    assert MODEL in models                               # both live requests landed, priced & named
    assert "acme-llm/gpt-4o-mini" in models               # seeded history still there

    assert body["spend_window"] >= sandbox["spent_usd"] > 0   # 30d window ⊇ the key's spend
    assert body["bifrost_reachable"] is True


# -------------------------------------------------------------------- helpers

def _live_events(chain: dict) -> list[dict]:
    """Read live-source events for the sandbox VK straight from the temp DB."""
    r = chain["client"].get("/api/requests", params={"limit": 100})
    rows = r.json()
    rows = rows if isinstance(rows, list) else rows.get("requests", [])
    return [e for e in rows if e.get("vk") == VK and e.get("source") == "live"]
