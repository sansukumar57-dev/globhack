"""Runs & executions: an Execution = one suite orchestrated over N scenarios.

Runs land in an in-memory registry and are appended to runs.jsonl so nothing
is lost on restart during a demo.
"""
import json
import threading
import time
import uuid

from .config import RUNS_JSONL

_lock = threading.Lock()
_RUNS: dict[str, dict] = {}
_EXECS: dict[str, dict] = {}
EXEC_LOCK = threading.Lock()   # serialises suite execution (shared world state)
EXEC_SEQ = 0


def new_run_id() -> str:
    return f"run-{uuid.uuid4().hex[:10]}"


def new_exec_id() -> str:
    global EXEC_SEQ
    EXEC_SEQ += 1
    return f"exec-{EXEC_SEQ:04d}"


def put_run(run: dict) -> None:
    with _lock:
        _RUNS[run["run_id"]] = run
    try:
        with RUNS_JSONL.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(run, default=str) + "\n")
    except Exception:
        pass


def put_exec(exec_rec: dict) -> None:
    with _lock:
        _EXECS[exec_rec["exec_id"]] = exec_rec


def get_exec(exec_id: str) -> dict | None:
    with _lock:
        snap = _EXECS.get(exec_id)
        return json.loads(json.dumps(snap, default=str)) if snap else None


def list_execs(limit: int = 30) -> list[dict]:
    with _lock:
        items = sorted(_EXECS.values(), key=lambda e: e["started_at"], reverse=True)
        snap = [json.loads(json.dumps(e, default=str)) for e in items[:limit]]
    return snap


def get_run(run_id: str) -> dict | None:
    with _lock:
        snap = _RUNS.get(run_id)
        return json.loads(json.dumps(snap, default=str)) if snap else None


def make_execution(suite: str, policy_name: str, policy: dict,
                   scenario_ids: list[str], seed: int) -> dict:
    return {
        "exec_id": new_exec_id(),
        "suite": suite,
        "policy_name": policy_name,
        "policy": policy,
        "scenario_ids": list(scenario_ids),
        "seed": seed,
        "status": "queued",  # queued | running | done | error
        "started_at": time.time(),
        "finished_at": None,
        "progress": {"done": 0, "total": len(scenario_ids)},
        "results": [],        # run summaries
        "summary": None,
        "analysis": None,
        "error": None,
    }


def add_result(exec_rec: dict, run_summary: dict) -> None:
    exec_rec["results"].append(run_summary)
    exec_rec["progress"]["done"] = len(exec_rec["results"])


def summarize_execution(exec_rec: dict) -> dict:
    results = exec_rec.get("results", [])
    rel = [r.get("reliability", 0) for r in results]
    passed = [1 for r in results if r.get("passed")]
    lat = [r.get("latency_ms", 0) for r in results]
    tok = sum(r.get("tokens", {}).get("input", 0) + r.get("tokens", {}).get("output", 0)
              for r in results)
    cost = sum(r.get("tokens", {}).get("est_cost", 0.0) for r in results)
    safety = None
    if exec_rec.get("suite") == "redteam" and results:
        blocked = sum(1 for r in results if r.get("redteam_outcome") == "blocked")
        partial = sum(1 for r in results if r.get("redteam_outcome") == "partial")
        safety = int(round(100 * (blocked + 0.5 * partial) / len(results)))
    return {
        "reliability": int(round(sum(rel) / len(rel))) if rel else 0,
        "pass_rate": int(round(100 * len(passed) / len(results))) if results else 0,
        "latency_ms_avg": int(round(sum(lat) / len(lat))) if lat else 0,
        "tokens_total": tok,
        "est_cost": round(cost, 6),
        "safety_score": safety,
        "judged": any((r.get("judge") or {}).get("available") for r in results),
        "runs": len(results),
    }
