"""Faultline API — the developer reliability platform for AI agents."""
import copy
import threading
import uuid
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from faultline import agent as agent_mod
from faultline import debug, harness, judge, redteam, scenarios, store
from faultline import config as cfg

app = FastAPI(title="Faultline — Agent Reliability Platform", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Working resilience policy under test (mutable via /api/agent/policy).
_WORKING_POLICY: dict = copy.deepcopy(agent_mod.POLICY_PRESETS["baseline"])
_POLICY_LOCK = threading.Lock()


class ExecRequest(BaseModel):
    suite: str = "quick"                      # quick | full | tooling | gateway | redteam | custom
    scenario_ids: Optional[list[str]] = None  # when suite == "custom"
    policy: Optional[dict] = None             # policy override for this run


class PolicyRequest(BaseModel):
    policy: dict


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "service": "Faultline — Agent Reliability Platform",
        "track": "Track 2 · Bifrost / Maxim AI (Title Partner)",
        "problem_statement": "Developer reliability platform that automatically stresses, "
                             "benchmarks, and debugs AI agents against real-world failures.",
        "provider": cfg.PROVIDER,
        "model": (cfg.GEMINI_MODEL if cfg.PROVIDER == "gemini"
                  else cfg.BIFROST_MODEL if cfg.PROVIDER == "bifrost"
                  else cfg.OPENROUTER_MODEL),
        "gateway": {
            "bifrost_url": cfg.BIFROST_GATEWAY_URL or None,
            "otel_spans": True,
            "note": ("Agent traffic is routable through Bifrost by Maxim AI "
                     "(npx @maximhq/bifrost · OpenAI-compatible). Set BIFROST_* envs + "
                     "PROVIDER=bifrost to route runs through a Bifrost deployment.")
            if cfg.PROVIDER != "bifrost" else "routing through Bifrost gateway",
        },
        "judge_model": cfg.JUDGE_MODEL,
        "has_provider_key": bool(cfg.GEMINI_API_KEY or cfg.OPENROUTER_API_KEY
                                 or cfg.BIFROST_API_KEY),
    }


@app.get("/api/scenarios")
def get_scenarios():
    return {
        "scenarios": scenarios.catalog_for_api(),
        "suites": [{"id": k, **v} for k, v in scenarios.SUITES.items()],
    }


@app.get("/api/attacks")
def get_attacks():
    return {
        "attacks": [{k: a[k] for k in ("id", "name", "technique", "vector", "goal")}
                    for a in redteam.ATTACKS],
        "suite": {"id": "redteam", "label": "Red-team gauntlet (8 attacks)",
                  "description": "Authority spoofing, prompt leak, injection, exfiltration.",
                  "scenario_ids": [a["id"] for a in redteam.ATTACKS]},
    }


@app.get("/api/agent/policy")
def get_policy():
    with _POLICY_LOCK:
        return {
            "current": copy.deepcopy(_WORKING_POLICY),
            "presets": {k: copy.deepcopy(v) for k, v in agent_mod.POLICY_PRESETS.items()},
        }


@app.put("/api/agent/policy")
def put_policy(req: PolicyRequest):
    global _WORKING_POLICY
    merged = _validate_policy(req.policy)
    with _POLICY_LOCK:
        _WORKING_POLICY = merged
    return {"status": "ok", "current": copy.deepcopy(_WORKING_POLICY)}


def _validate_policy(policy: dict) -> dict:
    # A policy request that only names a preset (e.g. {"name": "hardened"})
    # expands that preset first; explicit keys still win over preset defaults.
    requested_name = (policy or {}).get("name", "")
    base_src = agent_mod.POLICY_PRESETS.get(requested_name) or \
        agent_mod.POLICY_PRESETS["baseline"]
    base = copy.deepcopy(base_src)
    merged = {**base, **{k: v for k, v in (policy or {}).items()
                         if k in base and v is not None}}
    for k in ("llm_retries", "tool_retries", "max_llm_steps", "max_tool_calls"):
        merged[k] = max(0, min(6 if k.endswith("retries") else 20, int(merged[k])))
    for k, v in list(merged.items()):
        if k.endswith("_s") and isinstance(v, (int, float)):
            merged[k] = max(0.1, min(120.0, float(v)))
    return merged


@app.post("/api/executions")
def start_execution(req: ExecRequest):
    suite = req.suite
    if suite == "redteam":
        scenario_ids = [a["id"] for a in redteam.ATTACKS]
    elif suite == "custom":
        if not req.scenario_ids:
            raise HTTPException(400, "suite=custom requires scenario_ids")
        ids = [s["id"] for s in scenarios.SCENARIOS]
        known_ids = ids + [a["id"] for a in redteam.ATTACKS]
        for sid in req.scenario_ids:
            if sid not in known_ids:
                raise HTTPException(400, f"unknown scenario/attack id {sid}")
        scenario_ids = list(req.scenario_ids)
    elif suite in scenarios.SUITES:
        scenario_ids = list(scenarios.SUITES[suite]["scenario_ids"])
    else:
        raise HTTPException(400, f"unknown suite '{suite}'")

    policy = _resolve_policy(req.policy)
    execution = store.make_execution(
        suite, policy.get("name", "custom"), policy, scenario_ids,
        seed=int(uuid.uuid4().hex[:6], 16))
    harness.start_execution(execution, policy)
    return {"exec_id": execution["exec_id"], "status": execution["status"],
            "progress": execution["progress"], "suite": suite,
            "policy_name": policy.get("name")}


def _resolve_policy(policy_override: Optional[dict]) -> dict:
    if policy_override:
        pol = _validate_policy(policy_override)
        pol["name"] = policy_override.get("name") or "custom"
        return pol
    with _POLICY_LOCK:
        return copy.deepcopy(_WORKING_POLICY)


@app.get("/api/executions")
def list_executions():
    return {"executions": store.list_execs()}


@app.get("/api/executions/{exec_id}")
def get_execution(exec_id: str):
    exec_rec = store.get_exec(exec_id)
    if not exec_rec:
        raise HTTPException(404, "execution not found")
    return exec_rec


@app.post("/api/executions/{exec_id}/debug")
def debug_execution(exec_id: str):
    exec_rec = store.get_exec(exec_id)
    if not exec_rec:
        raise HTTPException(404, "execution not found")
    if exec_rec["status"] != "done":
        raise HTTPException(409, "execution is not finished yet")
    analysis = debug.analyze(exec_rec)
    exec_rec["analysis"] = analysis
    store.put_exec(exec_rec)
    return analysis


@app.get("/api/runs/{run_id}")
def get_run(run_id: str):
    run = store.get_run(run_id)
    if not run:
        raise HTTPException(404, "run not found")
    return run


@app.post("/api/verify")
def quick_verify():
    """Sanity probe used by the UI: one tiny inference to confirm the gateway."""
    from faultline import llm as lm
    from faultline.agent import to_provider_messages
    msgs = [{"role": "user", "content": "Reply with the single word: ready"}]
    pol = {"llm_retries": 1, "llm_backoff_s": 0.4, "llm_timeout_s": 30}
    try:
        resp = lm.chat(to_provider_messages(msgs), None, system="You are a probe.",
                       policy=pol, faults=None, trace=None, purpose="probe",
                       force_json=False)
        return {"ok": True, "model": resp["model"], "reply": resp["text"][:40]}
    except Exception as e:
        return {"ok": False, "error": str(e)[:200]}
