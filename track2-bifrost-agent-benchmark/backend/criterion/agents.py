"""Reference agents and the adapter registry.

Criterion measures agents, not model names. An agent is an endpoint plus the
scaffolding around it: tools, policies, retries, prompts. The four built-in
agents are deterministic sandbox fixtures so the demo is reproducible without
API keys. A live HTTP adapter can be registered from the UI.
"""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from copy import deepcopy


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


BUILTIN_AGENTS = [
    {
        "id": "helio",
        "name": "Helio",
        "operator": "Northstar Labs",
        "adapter": "Bifrost · OpenAI-compatible",
        "adapter_kind": "bifrost",
        "model": "gpt-4.1",
        "endpoint": "gateway://bifrost/helio",
        "description": "Generalist support agent with a strong policy layer and a careful verification step.",
        "mode": "sandbox",
        "status": "ready",
        "color": "#2F6B4F",
        "initials": "HE",
        "strengths": ["Policy reasoning", "Identity checks", "Tool sequencing"],
        "watchouts": ["Occasionally over-explains", "Slower on multi-tool returns"],
        "profile": {
            "base_success": 0.945,
            "category_bias": {"orders": 0.012, "returns": -0.020, "account": 0.010, "policy": 0.018},
            "check_weakness": {"policy": 1.15, "tool": 0.9, "identity": 0.65, "outcome": 1.0, "safety": 0.8, "tone": 0.7, "escalation": 0.9},
            "latency_ms": 2180,
            "tokens": 1840,
            "cost_per_task": 0.0142,
        },
    },
    {
        "id": "meridian",
        "name": "Meridian",
        "operator": "Fieldwork",
        "adapter": "LangGraph · HTTP",
        "adapter_kind": "langgraph",
        "model": "claude-sonnet-4.5",
        "endpoint": "https://agents.fieldwork.dev/meridian",
        "description": "Fast triage agent optimized for short resolutions and low latency.",
        "mode": "sandbox",
        "status": "ready",
        "color": "#3B6E8F",
        "initials": "ME",
        "strengths": ["Speed", "Clear summaries", "Order lookups"],
        "watchouts": ["Escalation policy", "High-stakes account changes"],
        "profile": {
            "base_success": 0.892,
            "category_bias": {"orders": 0.014, "returns": 0.018, "account": -0.032, "policy": -0.040},
            "check_weakness": {"policy": 1.35, "tool": 0.8, "identity": 1.0, "outcome": 1.0, "safety": 1.1, "tone": 0.8, "escalation": 1.7},
            "latency_ms": 1420,
            "tokens": 1310,
            "cost_per_task": 0.0078,
        },
    },
    {
        "id": "tessera",
        "name": "Tessera",
        "operator": "Arc Systems",
        "adapter": "CrewAI · HTTP",
        "adapter_kind": "crewai",
        "model": "gemini-2.5-pro",
        "endpoint": "https://arc.example.com/tessera",
        "description": "Multi-agent crew with a research step before every customer reply.",
        "mode": "sandbox",
        "status": "ready",
        "color": "#6B5B95",
        "initials": "TE",
        "strengths": ["Complex bundles", "Thorough context gathering", "Empathy"],
        "watchouts": ["Tool selection", "Long traces", "Cost per task"],
        "profile": {
            "base_success": 0.842,
            "category_bias": {"orders": -0.018, "returns": 0.022, "account": -0.030, "policy": 0.010},
            "check_weakness": {"policy": 1.0, "tool": 1.8, "identity": 1.0, "outcome": 1.2, "safety": 0.9, "tone": 0.6, "escalation": 1.1},
            "latency_ms": 3260,
            "tokens": 2540,
            "cost_per_task": 0.0224,
        },
    },
    {
        "id": "drift",
        "name": "Drift",
        "operator": "Internal",
        "adapter": "Custom · HTTP",
        "adapter_kind": "http",
        "model": "llama-4-maverick",
        "endpoint": "https://support.internal.example/drift",
        "description": "Low-cost in-house agent. Good at simple lookups, weak under policy pressure.",
        "mode": "sandbox",
        "status": "ready",
        "color": "#B7791F",
        "initials": "DR",
        "strengths": ["Cost", "Simple order status", "Direct answers"],
        "watchouts": ["Policy overreach", "Safety language", "Tone under pressure"],
        "profile": {
            "base_success": 0.742,
            "category_bias": {"orders": -0.028, "returns": -0.050, "account": -0.042, "policy": -0.062},
            "check_weakness": {"policy": 1.9, "tool": 1.1, "identity": 1.3, "outcome": 1.4, "safety": 1.8, "tone": 1.4, "escalation": 1.2},
            "latency_ms": 4620,
            "tokens": 2810,
            "cost_per_task": 0.0084,
        },
    },
]


SANDBOX_PROFILES = {
    "balanced": {
        "label": "Balanced",
        "description": "A reasonable middle-of-the-road agent.",
        "base_success": 0.855,
        "category_bias": {"orders": 0.0, "returns": 0.0, "account": -0.01, "policy": -0.01},
        "check_weakness": {"policy": 1.0, "tool": 1.0, "identity": 1.0, "outcome": 1.0, "safety": 1.0, "tone": 1.0, "escalation": 1.0},
        "latency_ms": 2400,
        "tokens": 1900,
        "cost_per_task": 0.011,
    },
    "careful": {
        "label": "Careful",
        "description": "High verification, slower, policy-first.",
        "base_success": 0.915,
        "category_bias": {"orders": 0.0, "returns": 0.01, "account": 0.01, "policy": 0.0},
        "check_weakness": {"policy": 0.8, "tool": 0.9, "identity": 0.55, "outcome": 0.9, "safety": 0.7, "tone": 0.8, "escalation": 0.8},
        "latency_ms": 3550,
        "tokens": 2450,
        "cost_per_task": 0.0165,
    },
    "fast": {
        "label": "Fast",
        "description": "Low latency, shorter context, more shortcuts.",
        "base_success": 0.805,
        "category_bias": {"orders": 0.01, "returns": 0.0, "account": -0.02, "policy": -0.03},
        "check_weakness": {"policy": 1.4, "tool": 0.9, "identity": 1.2, "outcome": 1.0, "safety": 1.2, "tone": 0.9, "escalation": 1.3},
        "latency_ms": 1180,
        "tokens": 1120,
        "cost_per_task": 0.0052,
    },
    "budget": {
        "label": "Budget",
        "description": "Cheapest possible loop, minimal context.",
        "base_success": 0.765,
        "category_bias": {"orders": -0.01, "returns": -0.03, "account": -0.03, "policy": -0.05},
        "check_weakness": {"policy": 1.8, "tool": 1.3, "identity": 1.5, "outcome": 1.3, "safety": 1.6, "tone": 1.2, "escalation": 1.2},
        "latency_ms": 2750,
        "tokens": 890,
        "cost_per_task": 0.0024,
    },
    "frontier": {
        "label": "Frontier",
        "description": "Largest model, most tools, highest cost.",
        "base_success": 0.928,
        "category_bias": {"orders": 0.01, "returns": 0.01, "account": 0.01, "policy": 0.01},
        "check_weakness": {"policy": 0.8, "tool": 0.8, "identity": 0.7, "outcome": 0.8, "safety": 0.7, "tone": 0.7, "escalation": 0.8},
        "latency_ms": 4180,
        "tokens": 3120,
        "cost_per_task": 0.0248,
    },
}


ADAPTERS = [
    {
        "id": "bifrost",
        "name": "Bifrost gateway",
        "kind": "OpenAI-compatible",
        "description": "Route the agent's model calls through Bifrost for a single gateway, trace and cost layer.",
        "contract": "POST /v1/chat/completions",
        "status": "ready",
    },
    {
        "id": "langgraph",
        "name": "LangGraph",
        "kind": "HTTP",
        "description": "Point Criterion at a LangGraph server or any HTTP wrapper around a compiled graph.",
        "contract": "POST /run",
        "status": "ready",
    },
    {
        "id": "crewai",
        "name": "CrewAI",
        "kind": "HTTP",
        "description": "Benchmark a crew behind a thin HTTP endpoint. Criterion only needs the final answer and tool calls.",
        "contract": "POST /run",
        "status": "ready",
    },
    {
        "id": "http",
        "name": "Any HTTP agent",
        "kind": "HTTP",
        "description": "The smallest adapter: send a task, return an answer, tool calls and optional check verdicts.",
        "contract": "POST /run",
        "status": "ready",
    },
]


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug[:32] or "agent"


def make_agent(payload: dict) -> dict:
    name = (payload.get("name") or "Untitled agent").strip()[:48]
    adapter = (payload.get("adapter") or "http").strip().lower()
    adapter_meta = next((a for a in ADAPTERS if a["id"] == adapter), ADAPTERS[-1])
    mode = payload.get("mode") if payload.get("mode") in {"sandbox", "live"} else "sandbox"
    profile_key = payload.get("sandbox_profile") or "balanced"
    profile = deepcopy(SANDBOX_PROFILES.get(profile_key, SANDBOX_PROFILES["balanced"]))
    if mode == "live":
        profile["base_success"] = 0.5
        profile["latency_ms"] = 3000
        profile["tokens"] = 1600
        profile["cost_per_task"] = 0.01

    agent_id = f"{slugify(name)}-{uuid.uuid4().hex[:4]}"
    initials = "".join(part[0] for part in name.split()[:2]).upper() or "AG"
    return {
        "id": agent_id,
        "name": name,
        "operator": (payload.get("operator") or "Connected workspace").strip()[:48],
        "adapter": f"{adapter_meta['name']} · {adapter_meta['kind']}",
        "adapter_kind": adapter_meta["id"],
        "model": (payload.get("model") or "endpoint-defined").strip()[:48],
        "endpoint": (payload.get("endpoint") or "").strip(),
        "description": (payload.get("description") or "A newly connected agent waiting for its first benchmark.").strip()[:180],
        "mode": mode,
        "status": "ready" if mode == "live" else "untested",
        "color": payload.get("color") or "#5A6472",
        "initials": initials,
        "strengths": ["Not measured yet"],
        "watchouts": ["Run the suite to establish a baseline"],
        "profile": profile,
        "created_at": utcnow(),
    }


def get_adapters() -> list[dict]:
    return deepcopy(ADAPTERS)


def get_builtin_agents() -> list[dict]:
    return deepcopy(BUILTIN_AGENTS)
