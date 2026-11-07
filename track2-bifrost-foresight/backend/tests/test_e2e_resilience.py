"""Chaos & resilience: break the LIVE chain mid-flight and prove Foresight
degrades gracefully instead of lying, wedging, or losing spend attribution.

Runs after test_e2e_chain.py in a full suite and reuses its `chain` fixture
(real fakellm + real Bifrost binary + real Foresight process on random ports),
so the skip-guards (`FORESIGHT_E2E=skip`, Node missing) apply here too.

Each chaos test progressively sabotages the chain:
  1. burst 8 concurrent requests while the console is being read
  2. sever the upstream mid-SSE  → partial usage must still be metered
  3. kill the gateway entirely   → clean 502, console keeps rendering,
                                   health flips to <=truthful<= False
Plus a cheap standalone fixture: a Foresight pointed at a Bifrost that never
existed, asserting fail-fast 502 on BOTH the JSON and SSE paths with no metered
phantom events.
"""
from __future__ import annotations

import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor

import httpx
import pytest

from test_e2e_chain import (BACKEND, VK, AUTH, MODEL,
                            _free_port, _kill, _live_events, _poll, _spawn,
                            chain)   # noqa: F401 - chain is a pytest fixture


def test_burst_concurrent_metering_stays_consistent(chain):
    """8 parallel metered requests + concurrent console reads: nothing drops,
    nothing double-counts."""
    c = chain["client"]
    before = len(_live_events(chain))

    def fire(i: int):
        return c.post("/v1/chat/completions", headers=AUTH, json={
            "model": MODEL,
            "messages": [{"role": "user", "content": f"burst probe {i}"}],
        })

    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = [pool.submit(fire, i) for i in range(8)]
        console_ok = 0
        for _ in range(6):                      # console is read DURING the burst
            if c.get("/api/overview").status_code == 200:
                console_ok += 1
        results = [f.result() for f in futures]

    assert console_ok == 6
    ids = set()
    for r in results:
        assert r.status_code == 200
        assert r.headers["x-foresight-action"] == "allow"
        ids.add(r.json()["id"])
    assert len(ids) == 8                        # every response is a distinct completion

    events = _live_events(chain)
    assert len(events) == before + 8            # 8 requests -> exactly 8 metered events
    assert all(ev["exact"] == 1 for ev in events)   # non-stream => exact upstream usage
    assert all(ev["completion_tokens"] > 0 for ev in events)


def test_severing_upstream_mid_stream_meters_whatever_arrived(chain):
    """Kill fakellm while its SSE is mid-flight through Bifrost to Foresight.

    The old code aborted the whole relay here — truncated output and a LOST
    event. The fixed `relay()` catches upstream read errors, meters whatever
    reached the proxy, and closes the stream cleanly.
    """
    c = chain["client"]
    before = len(_live_events(chain))
    seen, killed, aborted = 0, False, False

    with c.stream("POST", "/v1/chat/completions", headers=AUTH, json={
            "model": MODEL,
            "messages": [{"role": "user", "content": "sever the stream"}],
            "stream": True,
            "stream_options": {"include_usage": True}}) as resp:
        assert resp.status_code == 200
        assert resp.headers["x-foresight-streamed"] == "1"
        try:
            for line in resp.iter_lines():
                if line.startswith("data:"):
                    seen += 1
                if seen >= 3 and not killed:     # mid-stream: pull fakellm's plug
                    _kill(chain["procs"]["fakellm"])
                    killed = True
        except httpx.HTTPError:                  # upstream death may also surface here
            aborted = True
    assert seen >= 1, "red relay produced no SSE frames at all"
    if not killed:                               # extremely fast stream beat the kill
        _kill(chain["procs"]["fakellm"])

    # the partial stream is STILL metered (estimate or exact) - spend is never lost
    events = _live_events(chain)
    assert len(events) == before + 1
    ev = events[0]
    assert ev["prompt_tokens"] > 0 and ev["completion_tokens"] > 0
    assert ev["cost_usd"] > 0

    # proxy survived the chaos and the console still renders the fleet
    r = c.get("/api/overview")
    assert r.status_code == 200
    assert len(r.json()["keys"]) == 4

    # a new request reports the dead upstream as an explicit failure, not a hang
    r2 = c.post("/v1/chat/completions", headers=AUTH, json={
        "model": MODEL, "messages": [{"role": "user", "content": "failure probe"}]})
    assert 400 <= r2.status_code < 600
    assert r2.json().get("object") != "chat.completion"   # never fabricate a success body
    assert len(_live_events(chain)) == before + 1        # failures never meter phantom spend


def test_gateway_down_console_renders_and_health_tells_the_truth(chain):
    """Kill the whole gateway: requests 502 cleanly, the console keeps showing
    the fleet, and /api/health converges to bifrost_reachable=False (probe
    cache TTL is 5s, so allow one refresh cycle)."""
    c = chain["client"]
    before = len(_live_events(chain))

    _kill(chain["procs"]["bifrost"])

    r = c.post("/v1/chat/completions", headers=AUTH, json={
        "model": MODEL, "messages": [{"role": "user", "content": "gateway gone"}]})
    assert r.status_code == 502
    assert "foresight_upstream_unreachable" in r.text
    assert "x-foresight-cost-usd" not in r.headers        # never price a failure

    o = c.get("/api/overview")
    assert o.status_code == 200
    assert len(o.json()["keys"]) == 4                 # dark gateway != broken console

    flipped = False
    for _ in range(20):                    # <=10s: one probe-cache cycle + margins
        if not c.get("/api/health").json()["bifrost_reachable"]:
            flipped = True
            break
        time.sleep(0.5)
    assert flipped, "health stayed stale after the gateway died"

    assert len(_live_events(chain)) == before             # the 502 was not metered


# ---------------------------------------------------------------- dead gateway

@pytest.fixture(scope="module")
def dead_app(tmp_path_factory):
    """A Foresight process whose BIFROST_URL points at a port nothing ever
    binds. Boot cost ~3s, no Node needed - proves the proxy's failure paths in
    complete isolation."""
    procs: list = []
    saved: dict[str, str | None] = {}
    try:
        if os.environ.get("FORESIGHT_E2E", "").lower() == "skip":
            pytest.skip("FORESIGHT_E2E=skip")
        for name in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY",
                     "http_proxy", "https_proxy", "all_proxy"):
            saved[name] = os.environ.get(name)
            os.environ.pop(name, None)
        saved["NO_PROXY"] = os.environ.get("NO_PROXY")
        os.environ["NO_PROXY"] = "127.0.0.1,localhost"

        port, blackhole = _free_port(), _free_port()
        url = f"http://127.0.0.1:{port}"
        env = os.environ.copy()
        env.update({"FORESIGHT_PORT": str(port),
                    "FORESIGHT_BIFROST_URL": f"http://127.0.0.1:{blackhole}",
                    "FORESIGHT_DB_PATH": str(tmp_path_factory.mktemp("fg-dead") / "foresight.db")})
        log_dir = tmp_path_factory.mktemp("resilience-logs")
        procs.append(_spawn([sys.executable, "main.py"], BACKEND, env,
                            "foresight-dead.log", log_dir))
        _poll(f"{url}/api/health", 60, "Foresight did not start (see resilience-logs)")

        client = httpx.Client(base_url=url, timeout=30.0, trust_env=False)
        seeded = False
        for _ in range(60):
            try:
                if len(client.get("/api/overview").json().get("keys", [])) == 4:
                    seeded = True
                    break
            except httpx.HTTPError:
                pass
            time.sleep(0.5)
        assert seeded, "Foresight never seeded the fleet"

        yield {"client": client}
    finally:
        for p in reversed(procs):
            _kill(p)
        for key, val in saved.items():
            if val is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = val


def test_fail_fast_502_when_bifrost_absent_json_path(dead_app):
    c = dead_app["client"]
    t0 = time.monotonic()
    r = c.post("/v1/chat/completions", headers=AUTH,
               json={"model": MODEL, "messages": [{"role": "user", "content": "who?"}]})
    elapsed = time.monotonic() - t0
    assert r.status_code == 502
    assert elapsed < 8, "with Bifrost absent the proxy must fail fast, not stall"
    assert "foresight_upstream_unreachable" in r.text


def test_fail_fast_502_when_bifrost_absent_stream_path(dead_app):
    """The STREAMED variant: an SDK calling with stream=True against a dead
    gateway must get an immediate 502 - the pre-fix relay only broke later,
    after the stream had started."""
    c = dead_app["client"]
    t0 = time.monotonic()
    r = c.post("/v1/chat/completions", headers=AUTH,
               json={"model": MODEL, "messages": [{"role": "user", "content": "who?"}],
                     "stream": True,
                     "stream_options": {"include_usage": True}})
    elapsed = time.monotonic() - t0
    assert r.status_code == 502
    assert elapsed < 8, "SSE against a dead gateway must fail fast, not stall"
    assert "foresight_upstream_unreachable" in r.text
