"""In-memory demo store.

A hackathon build should start with one command and no database. Runs and agents
live in memory, seeded with a reproducible reference benchmark. The API surface
is intentionally small so it can be swapped for Postgres later.
"""

from __future__ import annotations

import os
import threading
import uuid
from copy import deepcopy
from datetime import datetime, timedelta, timezone

from .agents import get_adapters, get_builtin_agents, make_agent
from .runner import build_run, utcnow
from .tasks import FAILURE_SIGNATURES, get_suite


LOCK = threading.RLock()
AGENTS: list[dict] = []
RUNS: dict[str, dict] = {}
SEEDED = False


def _run_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    return f"run-{stamp}-{uuid.uuid4().hex[:4]}"


def _copy_agent(agent: dict) -> dict:
    clean = deepcopy(agent)
    clean.pop("profile", None)
    return clean


def _history_for(agent_id: str, through_run_id: str | None = None) -> list[dict]:
    points = []
    for run in sorted(RUNS.values(), key=lambda r: r["created_at"]):
        if run["status"] != "complete":
            continue
        result = next((m for m in run.get("agent_results", []) if m["agent_id"] == agent_id), None)
        if result:
            points.append({
                "run_id": run["id"],
                "created_at": run["created_at"],
                "score": result["score"],
                "task_success": result["task_success"],
            })
        if through_run_id and run["id"] == through_run_id:
            break
    return points


def _agent_summary(agent: dict) -> dict:
    summary = _copy_agent(agent)
    history = _history_for(agent["id"])
    summary["history"] = history
    summary["score"] = history[-1]["score"] if history else None
    summary["delta"] = round(history[-1]["score"] - history[-2]["score"], 1) if len(history) > 1 else None
    summary["run_count"] = len(history)
    return summary


def _run_summary(run: dict) -> dict:
    return {
        "id": run["id"],
        "suite_id": run["suite_id"],
        "status": run["status"],
        "created_at": run["created_at"],
        "completed_at": run.get("completed_at"),
        "trials": run["trials"],
        "agent_ids": run["agent_ids"],
        "progress": run.get("progress", 0),
        "summary": deepcopy(run.get("summary")),
        "agent_results": deepcopy(run.get("agent_results", [])),
    }


def seed() -> None:
    global SEEDED
    with LOCK:
        if SEEDED:
            return
        AGENTS[:] = get_builtin_agents()
        now = datetime.now(timezone.utc)
        demo_specs = [
            ("run-demo-01", "seed-9", 1, now - timedelta(days=7, hours=2)),
            ("run-demo-02", "seed-2", 1, now - timedelta(days=3, hours=1)),
            ("run-demo-03", "demo-2026-11-04", 2, now - timedelta(hours=3, minutes=18)),
        ]
        for run_id, seed_value, trials, created in demo_specs:
            run = build_run(run_id, get_builtin_agents(), trials, seed_value, sleep_seconds=0)
            run["created_at"] = created.isoformat(timespec="seconds").replace("+00:00", "Z")
            completed = created + timedelta(minutes=2, seconds=17 + trials * 8)
            run["completed_at"] = completed.isoformat(timespec="seconds").replace("+00:00", "Z")
            RUNS[run_id] = run
        SEEDED = True


def health() -> dict:
    seed()
    with LOCK:
        latest = _latest_completed()
        return {
            "status": "ok",
            "product": "Criterion",
            "version": "0.3.0",
            "suite": "commerce-support-v3",
            "agents": len(AGENTS),
            "runs": len(RUNS),
            "latest_run_id": latest["id"] if latest else None,
            "gateway": {
                "name": "Bifrost",
                "configured": bool(os.getenv("BIFROST_BASE_URL")),
                "base_url": os.getenv("BIFROST_BASE_URL", "http://localhost:8080"),
                "note": "Live model calls can be routed through Bifrost. Sandbox reference agents need no key.",
            },
            "judge": {
                "mode": "deterministic-rubric",
                "version": "v3",
                "deterministic": True,
                "note": "Scores come from weighted task checks, not an LLM judge.",
            },
        }


def get_agents() -> list[dict]:
    seed()
    with LOCK:
        return [_agent_summary(agent) for agent in AGENTS]


def get_agent(agent_id: str) -> dict | None:
    seed()
    with LOCK:
        agent = next((a for a in AGENTS if a["id"] == agent_id), None)
        if not agent:
            return None
        latest = _latest_completed()
        result = next((m for m in latest.get("agent_results", []) if m["agent_id"] == agent_id), None) if latest else None
        history = _history_for(agent_id)
        failure_modes = []
        recent_tasks = []
        if latest and result:
            recent_tasks = [
                r for r in latest["task_results"]
                if r["agent_id"] == agent_id and r["trial"] == 1
            ]
            for signature, count in sorted(result.get("failure_counts", {}).items(), key=lambda item: -item[1]):
                meta = FAILURE_SIGNATURES.get(signature, {"label": signature, "description": "", "color": "#5A6472"})
                failure_modes.append({"id": signature, "count": count, **meta})
        summary = _agent_summary(agent)
        summary["latest_result"] = deepcopy(result)
        summary["failure_modes"] = failure_modes
        summary["recent_tasks"] = deepcopy(recent_tasks)
        summary["history"] = history
        return summary


def create_agent(payload: dict) -> dict:
    seed()
    name = (payload.get("name") or "").strip()
    if len(name) < 2:
        raise ValueError("Give the agent a name with at least two characters.")
    mode = payload.get("mode", "sandbox")
    endpoint = (payload.get("endpoint") or "").strip()
    if mode == "live" and not endpoint.startswith(("http://", "https://")):
        raise ValueError("Live agents need an http(s) endpoint.")
    agent = make_agent(payload)
    with LOCK:
        AGENTS.append(agent)
    return _agent_summary(agent)


def get_adapters_registry() -> list[dict]:
    return get_adapters()


def get_suite_data() -> dict:
    suite = get_suite()
    with LOCK:
        latest = _latest_completed()
        suite["latest_run_id"] = latest["id"] if latest else None
        suite["total_task_executions"] = sum(
            len(run["task_results"]) for run in RUNS.values() if run["status"] == "complete"
        )
    return suite


def _latest_completed() -> dict | None:
    completed = [run for run in RUNS.values() if run["status"] == "complete"]
    return max(completed, key=lambda run: run["created_at"]) if completed else None


def get_runs() -> list[dict]:
    seed()
    with LOCK:
        runs = sorted(RUNS.values(), key=lambda run: run["created_at"], reverse=True)
        return [_run_summary(run) for run in runs]


def get_run(run_id: str) -> dict | None:
    seed()
    with LOCK:
        run = RUNS.get(run_id)
        if not run:
            return None
        data = deepcopy(run)
        for result in data.get("agent_results", []):
            history = _history_for(result["agent_id"], through_run_id=run_id)
            result["history"] = history
            result["delta"] = round(history[-1]["score"] - history[-2]["score"], 1) if len(history) > 1 else None
            agent = next((a for a in AGENTS if a["id"] == result["agent_id"]), None)
            if agent:
                result["description"] = agent["description"]
                result["strengths"] = agent.get("strengths", [])
                result["watchouts"] = agent.get("watchouts", [])
        return data


def get_leaderboard() -> dict:
    seed()
    with LOCK:
        latest = _latest_completed()
        if not latest:
            return {"run": None, "agents": [], "history": []}
        agents = []
        for result in latest["agent_results"]:
            history = _history_for(result["agent_id"])
            agent = next((a for a in AGENTS if a["id"] == result["agent_id"]), None)
            item = deepcopy(result)
            item["history"] = history
            item["delta"] = round(history[-1]["score"] - history[-2]["score"], 1) if len(history) > 1 else None
            item["description"] = agent["description"] if agent else ""
            item["strengths"] = agent.get("strengths", []) if agent else []
            item["watchouts"] = agent.get("watchouts", []) if agent else []
            agents.append(item)
        return {
            "run": _run_summary(latest),
            "agents": agents,
            "history": [
                {
                    "run_id": run["id"],
                    "created_at": run["created_at"],
                    "avg_score": run["summary"]["avg_score"],
                    "pass_rate": run["summary"]["pass_rate"],
                }
                for run in sorted(RUNS.values(), key=lambda r: r["created_at"])
                if run["status"] == "complete"
            ],
        }


def get_failures() -> list[dict]:
    seed()
    with LOCK:
        latest = _latest_completed()
        if not latest:
            return []
        signatures = latest["summary"]["top_signatures"]
        examples = {}
        for result in latest["task_results"]:
            signature = result.get("failure_signature")
            if signature and signature not in examples:
                examples[signature] = {
                    "agent_id": result["agent_id"],
                    "task_id": result["task_id"],
                    "answer": result["answer"],
                }
        return [{**signature, "example": examples.get(signature["id"])} for signature in signatures]


def start_run(agent_ids: list[str], trials: int) -> dict:
    seed()
    if not agent_ids:
        raise ValueError("Select at least one agent.")
    if trials not in (1, 2, 3):
        raise ValueError("Trials must be 1, 2 or 3.")
    with LOCK:
        selected = [deepcopy(agent) for agent in AGENTS if agent["id"] in set(agent_ids)]
        if not selected:
            raise ValueError("None of the selected agents exist.")
        run_id = _run_id()
        placeholder = {
            "id": run_id,
            "suite_id": "commerce-support-v3",
            "status": "running",
            "created_at": utcnow(),
            "completed_at": None,
            "trials": trials,
            "agent_ids": [agent["id"] for agent in selected],
            "agent_results": [],
            "task_results": [],
            "summary": None,
            "progress": 0.0,
        }
        RUNS[run_id] = placeholder

    def worker() -> None:
        def on_progress(partial: dict) -> None:
            with LOCK:
                current = RUNS.get(run_id)
                if current:
                    current["progress"] = partial.get("progress", 0)
                    current["status"] = "running"

        try:
            completed = build_run(
                run_id,
                selected,
                trials,
                f"live-{run_id}",
                sleep_seconds=0.018,
                on_progress=on_progress,
            )
            with LOCK:
                RUNS[run_id] = completed
                for agent in AGENTS:
                    if agent["id"] in completed["agent_ids"]:
                        agent["status"] = "ready"
        except Exception as exc:  # noqa: BLE001 - keep the API alive and expose the failure
            with LOCK:
                current = RUNS.get(run_id)
                if current:
                    current["status"] = "failed"
                    current["progress"] = 1.0
                    current["error"] = f"{type(exc).__name__}: {exc}"

    thread = threading.Thread(target=worker, daemon=True, name=f"criterion-{run_id}")
    thread.start()
    return _run_summary(placeholder)


def stats() -> dict:
    seed()
    with LOCK:
        completed = [run for run in RUNS.values() if run["status"] == "complete"]
        executions = sum(len(run["task_results"]) for run in completed)
        return {
            "agents": len(AGENTS),
            "runs": len(completed),
            "executions": executions,
            "tasks": get_suite()["task_count"],
        }
