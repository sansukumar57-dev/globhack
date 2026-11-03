"""Provider-agnostic LLM client used by both the agent and the judge.

All calls flow through `chat()`, which implements the *policy* layer of the
agent under test (retries + backoff + timeout) and emits one span per call.
Faults from a FaultContext are simulated BEFORE any HTTP request is made, so
chaos is local, deterministic and free; real provider errors (429/5xx/timeout)
flow through the identical retry code path.

Providers:
  gemini     — Google AI Studio REST (native function calling)
  bifrost    — Bifrost gateway by Maxim AI (OpenAI-compatible surface,
               https://docs.getbifrost.ai · npx @maximhq/bifrost)
  openrouter — OpenRouter (OpenAI-compatible)
"""
import json
import random
import time
from typing import Any

import requests

from . import config
from .faults import FaultSimulated
from .tracer import TraceCollector


class GatewayUnavailable(Exception):
    """All retries exhausted — the model gateway was not reachable."""


class ProviderError(Exception):
    """Non-retryable provider error (bad request, auth, etc.)."""


class FaultLike(Exception):
    """Maps provider-side transient failures onto the retry taxonomy
    (rate_limit / http_5xx / empty_completion)."""

    def __init__(self, bucket: str, detail: str = ""):
        self.bucket = bucket
        super().__init__(detail or bucket)


def est_cost(model: str, input_tok: int, output_tok: int) -> float:
    for key, (ci, co) in config.COST_PER_MTOK.items():
        if model == key or model.startswith(key):
            return round(ci * input_tok / 1_000_000 + co * output_tok / 1_000_000, 6)
    return 0.0


# ------------------------------------------------------------------- schemas
def gemini_tool_declarations(tool_defs: list[dict]) -> list[dict]:
    decls = []
    for ti in tool_defs:
        decls.append({
            "name": ti["name"],
            "description": ti["description"],
            "parameters": {
                "type": "OBJECT",
                "properties": {pname: dict(spec)
                               for pname, spec in ti["params"].items()},
                "required": ti.get("required", []),
            },
        })
    return [{"functionDeclarations": decls}]


_SCHEMA_TYPE = {"STRING": "string", "NUMBER": "number", "BOOLEAN": "boolean",
                "OBJECT": "object", "ARRAY": "array"}


def openai_tool_schema(tool_defs: list[dict]) -> list[dict]:
    tools = []
    for ti in tool_defs:
        props = {pname: {"type": _SCHEMA_TYPE.get(spec.get("type", "STRING"), "string"),
                         **({"description": spec["description"]}
                            if spec.get("description") else {})}
                 for pname, spec in ti["params"].items()}
        tools.append({"type": "function", "function": {
            "name": ti["name"], "description": ti["description"],
            "parameters": {"type": "object", "properties": props,
                           "required": ti.get("required", [])},
        }})
    return tools


# ------------------------------------------------------------ provider calls
def _call_gemini(model: str, system: str, contents: list[dict], use_tools: bool,
                 tool_defs: list[dict], timeout_s: float, force_json: bool,
                 max_tokens: int) -> dict:
    body: dict[str, Any] = {
        "contents": contents,
        "generationConfig": {"temperature": 0.25, "maxOutputTokens": max_tokens},
    }
    if system:
        body["systemInstruction"] = {"parts": [{"text": system}]}
    if use_tools:
        body["tools"] = gemini_tool_declarations(tool_defs)
    if force_json:
        body["generationConfig"]["responseMimeType"] = "application/json"
    url = f"{config.GEMINI_BASE}/models/{model}:generateContent"
    r = requests.post(url, json=body, timeout=(5, timeout_s),
                      headers={"x-goog-api-key": config.GEMINI_API_KEY})
    if r.status_code >= 400:
        try:
            detail = r.json().get("error", {}).get("message", r.text[:200])
        except Exception:
            detail = r.text[:200]
        if r.status_code == 429:
            raise FaultLike("rate_limit", detail)
        if r.status_code >= 500:
            raise FaultLike("http_5xx", detail)
        raise ProviderError(f"{r.status_code}: {detail}")
    return r.json()


def _call_openai_compat(base_url: str, api_key: str, model: str, system: str,
                        messages: list[dict], use_tools: bool, tool_defs: list[dict],
                        timeout_s: float, force_json: bool, max_tokens: int) -> dict:
    """OpenAI-compatible chat endpoint (Bifrost gateway, OpenRouter, …)."""
    msgs = [{"role": "system", "content": system}] if system else []
    msgs += list(messages)
    body: dict[str, Any] = {"model": model, "messages": msgs,
                            "temperature": 0.25, "max_tokens": max_tokens}
    if use_tools:
        body["tools"] = openai_tool_schema(tool_defs)
    if force_json:
        body["response_format"] = {"type": "json_object"}
    r = requests.post(f"{base_url}/chat/completions", json=body,
                      timeout=(5, timeout_s),
                      headers={"Authorization": f"Bearer {api_key}"})
    if r.status_code >= 400:
        if r.status_code == 429:
            raise FaultLike("rate_limit", r.text[:200])
        if r.status_code >= 500:
            raise FaultLike("http_5xx", r.text[:200])
        raise ProviderError(f"{r.status_code}: {r.text[:200]}")
    return r.json()


def _openai_endpoint() -> tuple[str, str]:
    if config.PROVIDER == "bifrost":
        return (config.BIFROST_GATEWAY_URL or "http://localhost:8080/openai/v1",
                config.BIFROST_API_KEY or "local")
    return ("https://openrouter.ai/api/v1", config.OPENROUTER_API_KEY)


# ------------------------------------------------------------------- parsing
def _parse_gemini_response(data: dict) -> tuple[str, list[dict], dict]:
    cand = (data.get("candidates") or [{}])[0]
    parts = ((cand.get("content") or {}).get("parts")) or []
    text = "".join(p.get("text", "") for p in parts
                   if isinstance(p, dict) and "text" in p and not p.get("thought"))
    calls = [{"name": p["functionCall"].get("name", "unknown"),
              "args": p["functionCall"].get("args", {}) if
              isinstance(p["functionCall"].get("args"), dict) else {},
              "sig": p.get("thoughtSignature")}
             for p in parts
             if isinstance(p, dict) and "functionCall" in p]
    usage = data.get("usageMetadata") or {}
    tok = {"input": usage.get("promptTokenCount", 0),
           "output": usage.get("candidatesTokenCount", 0),
           "thoughts": usage.get("thoughtsTokenCount", 0)}
    return text.strip(), calls, tok


def _parse_openai_response(data: dict) -> tuple[str, list[dict], dict]:
    msg = (data.get("choices") or [{}])[0].get("message") or {}
    text = (msg.get("content") or "").strip()
    calls = []
    for tc in msg.get("tool_calls") or []:
        fn = tc.get("function", {})
        try:
            args = json.loads(fn.get("arguments") or "{}")
        except Exception:
            args = {"_raw": fn.get("arguments", "")}
        calls.append({"name": fn.get("name", "unknown"), "args": args})
    usage = data.get("usage") or {}
    tok = {"input": usage.get("prompt_tokens", 0),
           "output": usage.get("completion_tokens", 0), "thoughts": 0}
    return text, calls, tok


# -------------------------------------------------------------- default model
def default_model() -> str:
    if config.PROVIDER == "gemini":
        return config.GEMINI_MODEL
    if config.PROVIDER == "bifrost":
        return config.BIFROST_MODEL
    return config.OPENROUTER_MODEL


# ------------------------------------------------------------------- pacing
_last_call = 0.0
_PACING_MIN = 2.0   # free-tier RPM safety between REAL provider calls


def _pace() -> None:
    """Space out real provider calls to avoid ambient 429 noise."""
    global _last_call
    now = time.time()
    gap = now - _last_call
    if gap < _PACING_MIN:
        time.sleep(_PACING_MIN - gap + random.uniform(0.0, 0.7))
    _last_call = time.time()


# ----------------------------------------------------------------------- chat
def chat(messages: list[dict], tool_defs: list[dict] | None = None,
         *, system: str = "", policy: dict | None = None,
         faults: Any | None = None, trace: TraceCollector | None = None,
         model: str | None = None, purpose: str = "agent",
         force_json: bool = False, max_tokens: int | None = None) -> dict:
    """One policy-aware inference round.

    Returns {"text", "tool_calls", "usage", "model", "tries"}.
    Raises GatewayUnavailable when retries are exhausted.
    """
    policy = policy or {}
    if model is None:
        model = default_model()
    retries = int(policy.get("llm_retries", 0))
    backoff = float(policy.get("llm_backoff_s", 0.5))
    timeout_s = float(policy.get("llm_timeout_s", 45))
    use_tools = bool(tool_defs)
    if max_tokens is None:
        max_tokens = 768 if purpose in ("judge", "probe") else 4096

    span = trace.span("llm", f"{model} · {purpose}",
                      {"purpose": purpose}) if trace else None
    attempts_allowed = retries + 1
    last_exc: Exception | None = None

    for attempt in range(1, attempts_allowed + 1):
        try:
            if faults is not None:
                faults.before_llm(trace)
            _pace()
            if config.PROVIDER == "gemini":
                raw = _call_gemini(model, system, messages, use_tools,
                                   tool_defs, timeout_s, force_json, max_tokens)
                text, calls, tok = _parse_gemini_response(raw)
            else:
                base_url, api_key = _openai_endpoint()
                raw = _call_openai_compat(base_url, api_key, model, system,
                                          messages, use_tools, tool_defs,
                                          timeout_s, force_json, max_tokens)
                text, calls, tok = _parse_openai_response(raw)
            if faults is not None and text:
                text = faults.after_llm(trace, text)
            if not text and not calls:
                raise FaultLike("empty_completion", "gateway returned no content")
            if span:
                span.usage = dict(tok, est_cost=est_cost(
                    model, tok["input"], tok["output"] + tok["thoughts"]))
                span.add_attempt(n=attempt, status="ok", simulated=False,
                                 recovered=attempt > 1)
                span.meta["recovered"] = attempt > 1
                span.finish("warn" if attempt > 1 else "ok")
            return {"text": text, "tool_calls": calls, "usage": tok,
                    "model": model, "tries": attempt}

        except FaultSimulated as e:      # injected fault fired locally
            last_exc = GatewayUnavailable(str(e))
            if span:
                span.add_attempt(n=attempt, status="error", simulated=True,
                                 behavior=e.behavior)
        except FaultLike as e:           # provider-side transient error
            last_exc = GatewayUnavailable(f"{e.bucket}: {e}")
            if span:
                span.add_attempt(n=attempt, status="error", simulated=False,
                                 behavior=e.bucket)
        except requests.Timeout:
            last_exc = GatewayUnavailable(f"timeout after {timeout_s}s")
            if span:
                span.add_attempt(n=attempt, status="error", simulated=False,
                                 behavior="timeout")
        except requests.ConnectionError:
            last_exc = GatewayUnavailable("connection error")
            if span:
                span.add_attempt(n=attempt, status="error", simulated=False,
                                 behavior="connection_error")
        except ProviderError as e:       # non-retryable — give up immediately
            if span:
                span.add_attempt(n=attempt, status="error", behavior="bad_request")
                span.finish("error", str(e))
            raise GatewayUnavailable(f"provider rejected: {e}") from e
        if attempt < attempts_allowed:
            time.sleep(min(backoff * (2 ** (attempt - 1)), 3.0))

    if span:
        span.finish("error", str(last_exc))
    raise GatewayUnavailable(str(last_exc or "gateway unavailable"))
