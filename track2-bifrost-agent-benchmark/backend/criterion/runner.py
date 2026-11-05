"""Deterministic benchmark execution and scoring.

The sandbox runner uses a seeded simulation so every demo run is reproducible.
A live adapter gets the same task payload and can return its own check verdicts.
"""

from __future__ import annotations

import hashlib
import math
import random
import re
import time
from copy import deepcopy
from datetime import datetime, timezone
from typing import Iterable

import httpx

from .tasks import CHECK_TO_SIGNATURE, FAILURE_SIGNATURES, TASKS, CATEGORIES


PRIORITY = ["safety", "identity", "policy", "outcome", "tool", "escalation", "tone"]


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def rng_for(*parts: object) -> random.Random:
    raw = "|".join(str(part) for part in parts).encode("utf-8")
    digest = hashlib.sha256(raw).digest()
    return random.Random(int.from_bytes(digest[:8], "big"))


def round1(value: float) -> float:
    return round(value + 1e-9, 1)


def task_by_id(task_id: str) -> dict:
    return next(task for task in TASKS if task["id"] == task_id)


def category_by_id(category_id: str) -> dict:
    return next(category for category in CATEGORIES if category["id"] == category_id)


def weighted_check_score(checks: list[dict]) -> float:
    total = sum(c["weight"] for c in checks) or 1
    passed = sum(c["weight"] for c in checks if c["passed"])
    return round1(100 * passed / total)


def choose_failed_checks(rng: random.Random, task: dict, profile: dict) -> list[dict]:
    checks = task["checks"]
    weaknesses = profile.get("check_weakness", {})
    max_failures = min(3, max(1, len(checks) - 1))
    count = 1 if rng.random() < 0.62 else (2 if rng.random() < 0.78 else max_failures)
    count = min(count, max_failures)
    pool = list(checks)
    failed = []
    for _ in range(count):
        weights = [max(0.15, weaknesses.get(c["kind"], 1.0)) for c in pool]
        picked = rng.choices(pool, weights=weights, k=1)[0]
        failed.append(picked)
        pool.remove(picked)
    return failed


def synthetic_trace(rng: random.Random, task: dict, profile: dict, failed: list[dict]) -> tuple[list[dict], int]:
    target = profile.get("latency_ms", 2400) * (0.82 + rng.random() * 0.36)
    tools = task.get("tools", [])
    steps = [("agent.plan", "agent", "Plan the resolution and select tools")]
    for tool in tools:
        steps.append((f"tool.{tool}", "tool", f"Call {tool}"))
    steps.append(("agent.draft", "agent", "Draft the customer response"))
    steps.append(("judge.rubric", "judge", "Score deterministic checks"))
    if failed:
        steps.append(("agent.self_check", "agent", "Review failed policy or safety check"))

    weights = []
    for name, kind, _ in steps:
        if kind == "judge":
            weights.append(0.02)
        elif kind == "tool":
            weights.append(0.10 + rng.random() * 0.05)
        else:
            weights.append(0.20 + rng.random() * 0.12)
    weight_sum = sum(weights) or 1
    durations = [max(18, int(target * w / weight_sum)) for w in weights]
    # Keep the total close to the sampled target.
    durations[-1] += max(0, int(target) - sum(durations))

    failed_kinds = {c["kind"] for c in failed}
    failed_ids = {c["id"] for c in failed}
    spans = []
    cursor = 0
    for (name, kind, detail), duration in zip(steps, durations):
        status = "ok"
        span_detail = detail
        if name.startswith("tool."):
            tool_name = name.split(".", 1)[1]
            if "tool" in failed_kinds and tool_name in task.get("tools", [])[:1]:
                status = "error"
                span_detail = f"{tool_name} returned an unusable result"
        if name == "agent.self_check" and failed:
            status = "error"
            span_detail = f"Failed: {', '.join(c['label'] for c in failed)}"
        if name == "judge.rubric":
            status = "ok"
            span_detail = f"{sum(1 for c in task['checks'] if c['id'] not in failed_ids)}/{len(task['checks'])} checks passed"
        spans.append({
            "name": name,
            "kind": kind,
            "start_ms": cursor,
            "duration_ms": duration,
            "status": status,
            "detail": span_detail,
        })
        cursor += duration
    return spans, cursor


def simulate_task(agent: dict, task: dict, trial: int, run_seed: str) -> dict:
    profile = agent["profile"]
    rng = rng_for(run_seed, agent["id"], task["id"], trial)
    pass_prob = clamp(profile.get("base_success", 0.84) + profile.get("category_bias", {}).get(task["category"], 0), 0.35, 0.995)
    passed_task = rng.random() < pass_prob

    if passed_task:
        checks = [{**c, "passed": True} for c in task["checks"]]
        status = "passed"
        failed = []
        answer = task["resolution"]
        failure_signature = None
    else:
        failed = choose_failed_checks(rng, task, profile)
        failed_ids = {c["id"] for c in failed}
        checks = [{**c, "passed": c["id"] not in failed_ids} for c in task["checks"]]
        score = weighted_check_score(checks)
        status = "partial" if score >= 50 else "failed"
        answer = task["trap"]
        ordered = sorted(failed, key=lambda c: PRIORITY.index(c["kind"]) if c["kind"] in PRIORITY else 99)
        failure_signature = CHECK_TO_SIGNATURE.get(ordered[0]["kind"], "wrong_resolution")

    spans, latency = synthetic_trace(rng, task, profile, failed)
    base_tokens = profile.get("tokens", 1900)
    tokens = max(180, int(base_tokens * (0.78 + rng.random() * 0.44) + len(task["context"]) / 5))
    cost = profile.get("cost_per_task", 0.01) * (tokens / max(1, base_tokens))

    tool_calls = []
    for index, tool in enumerate(task.get("tools", [])):
        tool_status = "ok"
        if failed and "tool" in {c["kind"] for c in failed} and index == 0:
            tool_status = "error"
        tool_calls.append({
            "tool": tool,
            "status": tool_status,
            "latency_ms": 90 + int(rng.random() * 180),
            "args": {"task_id": task["id"]},
        })

    return {
        "id": f"{agent['id']}:{task['id']}:{trial}",
        "agent_id": agent["id"],
        "task_id": task["id"],
        "trial": trial,
        "status": status,
        "score": weighted_check_score(checks),
        "checks": checks,
        "failure_signature": failure_signature,
        "latency_ms": latency,
        "tokens": tokens,
        "cost_usd": round(cost, 5),
        "answer": answer,
        "tool_calls": tool_calls,
        "trace": spans,
        "mode": "sandbox",
    }


def _similarity(a: str, b: str) -> float:
    words_a = set(re.findall(r"[a-z0-9$]+", a.lower()))
    words_b = set(re.findall(r"[a-z0-9$]+", b.lower()))
    if not words_a or not words_b:
        return 0.0
    return len(words_a & words_b) / len(words_a | words_b)


def live_task(agent: dict, task: dict, trial: int, run_seed: str) -> dict:
    started = time.perf_counter()
    # Never send the ground-truth resolution or the common trap to a live
    # agent. The adapter gets the same customer-facing task a human would.
    public_task = {
        key: deepcopy(task[key])
        for key in ("id", "number", "title", "category", "difficulty", "prompt", "context", "goal", "policy", "tools")
        if key in task
    }
    payload = {
        "task": public_task,
        "trial": trial,
        "run_seed": run_seed,
        "expected_checks": [{"id": c["id"], "label": c["label"], "kind": c["kind"]} for c in task["checks"]],
    }
    try:
        with httpx.Client(timeout=25.0) as client:
            response = client.post(agent["endpoint"], json=payload)
            response.raise_for_status()
            data = response.json()
    except Exception as exc:  # noqa: BLE001 - an adapter failure is a benchmark result
        latency = int((time.perf_counter() - started) * 1000)
        checks = [{**c, "passed": False} for c in task["checks"]]
        return {
            "id": f"{agent['id']}:{task['id']}:{trial}",
            "agent_id": agent["id"],
            "task_id": task["id"],
            "trial": trial,
            "status": "error",
            "score": 0.0,
            "checks": checks,
            "failure_signature": "adapter_error",
            "latency_ms": latency,
            "tokens": 0,
            "cost_usd": 0.0,
            "answer": f"Adapter error: {type(exc).__name__}: {str(exc)[:220]}",
            "tool_calls": [],
            "trace": [{
                "name": "adapter.request",
                "kind": "tool",
                "start_ms": 0,
                "duration_ms": latency,
                "status": "error",
                "detail": str(exc)[:220],
            }],
            "mode": "live",
        }

    answer = str(data.get("answer", ""))
    verdicts = data.get("checks") or {}
    if isinstance(verdicts, dict):
        checks = [{**c, "passed": bool(verdicts.get(c["id"], False))} for c in task["checks"]]
    elif isinstance(verdicts, list):
        passed_ids = {str(item.get("id")) for item in verdicts if item.get("passed")}
        checks = [{**c, "passed": c["id"] in passed_ids} for c in task["checks"]]
    else:
        # Coarse fallback when an adapter returns only text. The adapter contract
        # recommends returning check verdicts for exact scoring.
        closer_to_good = _similarity(answer, task["resolution"]) >= _similarity(answer, task["trap"])
        checks = [{**c, "passed": closer_to_good} for c in task["checks"]]

    score = weighted_check_score(checks)
    failed = [c for c in checks if not c["passed"]]
    status = "passed" if score >= 99.9 else ("partial" if score >= 50 else "failed")
    failure_signature = None
    if failed:
        ordered = sorted(failed, key=lambda c: PRIORITY.index(c["kind"]) if c["kind"] in PRIORITY else 99)
        failure_signature = CHECK_TO_SIGNATURE.get(ordered[0]["kind"], "wrong_resolution")
    latency = int(data.get("latency_ms") or (time.perf_counter() - started) * 1000)
    tokens = int(data.get("tokens") or 0)
    cost = float(data.get("cost_usd") or 0.0)
    trace = data.get("trace") or [{
        "name": "adapter.request",
        "kind": "tool",
        "start_ms": 0,
        "duration_ms": latency,
        "status": "ok",
        "detail": "Live adapter responded",
    }]
    return {
        "id": f"{agent['id']}:{task['id']}:{trial}",
        "agent_id": agent["id"],
        "task_id": task["id"],
        "trial": trial,
        "status": status,
        "score": score,
        "checks": checks,
        "failure_signature": failure_signature,
        "latency_ms": latency,
        "tokens": tokens,
        "cost_usd": round(cost, 5),
        "answer": answer,
        "tool_calls": data.get("tool_calls") or [],
        "trace": trace,
        "mode": "live",
    }


def p95(values: Iterable[float]) -> int:
    ordered = sorted(values)
    if not ordered:
        return 0
    index = max(0, math.ceil(0.95 * len(ordered)) - 1)
    return int(ordered[index])


def metric_from_checks(results: list[dict], kinds: set[str]) -> float:
    relevant = []
    for result in results:
        for check in result["checks"]:
            if check["kind"] in kinds:
                relevant.append(check)
    if not relevant:
        return 100.0
    total = sum(c["weight"] for c in relevant) or 1
    passed = sum(c["weight"] for c in relevant if c["passed"])
    return round1(100 * passed / total)


def consistency_score(results: list[dict]) -> float:
    by_task: dict[str, list[dict]] = {}
    for result in results:
        by_task.setdefault(result["task_id"], []).append(result)
    if not by_task:
        return 100.0
    agreements = []
    for trials in by_task.values():
        if len(trials) < 2:
            agreements.append(1.0)
            continue
        pass_rate = sum(1 for r in trials if r["status"] == "passed") / len(trials)
        agreements.append(2 * abs(pass_rate - 0.5))
    return round1(100 * sum(agreements) / len(agreements))


def category_breakdown(results: list[dict]) -> list[dict]:
    out = []
    for category in CATEGORIES:
        cat_results = [r for r in results if task_by_id(r["task_id"])["category"] == category["id"]]
        if not cat_results:
            out.append({"id": category["id"], "name": category["name"], "success": 0.0, "score": 0.0})
            continue
        passed = sum(1 for r in cat_results if r["status"] == "passed")
        out.append({
            "id": category["id"],
            "name": category["name"],
            "success": round1(100 * passed / len(cat_results)),
            "score": round1(sum(r["score"] for r in cat_results) / len(cat_results)),
        })
    return out


def compute_agent_metrics(agent: dict, results: list[dict]) -> dict:
    total = len(results) or 1
    passed = sum(1 for r in results if r["status"] == "passed")
    partial = sum(1 for r in results if r["status"] == "partial")
    failed = sum(1 for r in results if r["status"] == "failed")
    errors = sum(1 for r in results if r["status"] == "error")
    task_success = round1(100 * passed / total)
    policy = metric_from_checks(results, {"policy", "identity", "escalation"})
    tool_accuracy = metric_from_checks(results, {"tool"})
    safety = metric_from_checks(results, {"safety"})
    consistency = consistency_score(results)
    failure_counts: dict[str, int] = {}
    for result in results:
        signature = result.get("failure_signature")
        if signature:
            failure_counts[signature] = failure_counts.get(signature, 0) + 1
    top_failure = max(failure_counts, key=failure_counts.get) if failure_counts else None
    return {
        "agent_id": agent["id"],
        "task_success": task_success,
        "policy": policy,
        "tool_accuracy": tool_accuracy,
        "safety": safety,
        "consistency": consistency,
        "passed": passed,
        "partial": partial,
        "failed": failed,
        "errors": errors,
        "total": len(results),
        "failure_counts": failure_counts,
        "top_failure": top_failure,
        "category_scores": category_breakdown(results),
        "p95_latency_ms": p95(r["latency_ms"] for r in results),
        "avg_latency_ms": int(sum(r["latency_ms"] for r in results) / total),
        "cost_per_task": round(sum(r["cost_usd"] for r in results) / total, 5),
        "tokens_per_task": int(sum(r["tokens"] for r in results) / total),
        "total_cost_usd": round(sum(r["cost_usd"] for r in results), 4),
    }


def finalize_run(run: dict) -> dict:
    agents_by_id = {agent["id"]: agent for agent in run["_agents"]}
    results = run["task_results"]
    metrics = []
    for agent_id in run["agent_ids"]:
        agent_results = [r for r in results if r["agent_id"] == agent_id]
        metrics.append(compute_agent_metrics(agents_by_id[agent_id], agent_results))

    costs = [m["cost_per_task"] for m in metrics]
    latencies = [m["p95_latency_ms"] for m in metrics]
    min_cost, max_cost = min(costs), max(costs)
    min_lat, max_lat = min(latencies), max(latencies)
    for metric in metrics:
        if max_cost > min_cost:
            cost_score = 100 - 45 * (metric["cost_per_task"] - min_cost) / (max_cost - min_cost)
        else:
            cost_score = 100.0
        if max_lat > min_lat:
            latency_score = 100 - 35 * (metric["p95_latency_ms"] - min_lat) / (max_lat - min_lat)
        else:
            latency_score = 100.0
        metric["efficiency"] = round1(0.55 * cost_score + 0.45 * latency_score)
        metric["score"] = round1(
            0.35 * metric["task_success"]
            + 0.20 * metric["policy"]
            + 0.15 * metric["tool_accuracy"]
            + 0.15 * metric["consistency"]
            + 0.10 * metric["safety"]
            + 0.05 * metric["efficiency"]
        )

    metrics.sort(key=lambda m: (-m["score"], m["p95_latency_ms"], m["cost_per_task"]))
    for index, metric in enumerate(metrics, start=1):
        metric["rank"] = index
        agent = agents_by_id[metric["agent_id"]]
        metric["name"] = agent["name"]
        metric["operator"] = agent["operator"]
        metric["adapter"] = agent["adapter"]
        metric["adapter_kind"] = agent["adapter_kind"]
        metric["color"] = agent["color"]
        metric["initials"] = agent["initials"]
        metric["mode"] = agent["mode"]

    # The live run's wall clock is the slowest agent, not the sum of all agents.
    per_agent_wall = {}
    for agent_id in run["agent_ids"]:
        per_agent_wall[agent_id] = sum(r["latency_ms"] for r in results if r["agent_id"] == agent_id)
    duration_ms = max(per_agent_wall.values()) if per_agent_wall else 0

    total_executions = len(results)
    pass_rate = round1(100 * sum(1 for r in results if r["status"] == "passed") / (total_executions or 1))
    total_failures: dict[str, int] = {}
    for result in results:
        signature = result.get("failure_signature")
        if signature:
            total_failures[signature] = total_failures.get(signature, 0) + 1
    top_signatures = [
        {"id": key, "count": count, **FAILURE_SIGNATURES.get(key, {"label": key, "description": "", "color": "#5A6472"})}
        for key, count in sorted(total_failures.items(), key=lambda item: -item[1])[:4]
    ]

    run["agent_results"] = metrics
    run["summary"] = {
        "best_agent": metrics[0]["name"] if metrics else None,
        "best_score": metrics[0]["score"] if metrics else 0,
        "pass_rate": pass_rate,
        "avg_score": round1(sum(m["score"] for m in metrics) / (len(metrics) or 1)),
        "total_executions": total_executions,
        "total_cost_usd": round(sum(r["cost_usd"] for r in results), 3),
        "duration_ms": duration_ms,
        "top_signatures": top_signatures,
    }
    run["progress"] = 1.0
    run["status"] = "complete"
    run["completed_at"] = utcnow()
    run.pop("_agents", None)
    return run


def build_run(run_id: str, agents: list[dict], trials: int, run_seed: str, sleep_seconds: float = 0.0, on_progress=None) -> dict:
    run = {
        "id": run_id,
        "suite_id": "commerce-support-v3",
        "status": "running",
        "created_at": utcnow(),
        "completed_at": None,
        "trials": trials,
        "agent_ids": [a["id"] for a in agents],
        "agent_results": [],
        "task_results": [],
        "summary": None,
        "progress": 0.0,
        "_agents": agents,
        "seed": run_seed,
    }
    total_steps = max(1, len(agents) * len(TASKS) * trials)
    step = 0
    for agent in agents:
        for task in TASKS:
            for trial in range(1, trials + 1):
                if agent.get("mode") == "live":
                    result = live_task(agent, task, trial, run_seed)
                else:
                    result = simulate_task(agent, task, trial, run_seed)
                run["task_results"].append(result)
                step += 1
                run["progress"] = round(step / total_steps, 3)
                if on_progress:
                    on_progress(run)
                if sleep_seconds:
                    time.sleep(sleep_seconds)
    return finalize_run(run)
