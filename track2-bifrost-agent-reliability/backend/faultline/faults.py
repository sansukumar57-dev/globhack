"""Chaos engineering engine for LLM agents.

A Scenario declares a set of faults; the FaultContext applies them to every
LLM call and tool call made by the agent under test. Faults are *simulated*
locally (no real traffic hits the provider when a fault decides to fail), so
a full suite is deterministic, fast and free.

Fault specs (dicts, as declared in scenarios.py / redteam.py):
  llm_outage      {rate, behavior: "http_500"|"rate_limit"|"timeout"|"empty"}
  llm_truncate    {rate}                  -> truncates model text mid-sentence
  tool_crash      {tool, rate}            -> tool raises ToolCrash
  tool_garbage    {tool, rate}            -> tool returns malformed payload
  tool_slow       {tool, seconds}         -> tool hangs (honours agent timeout)
  tool_stale      {tool}                  -> tool returns outdated data
  tool_injection  {tool, payload}         -> smuggles an instruction into output
"""
import random
import time
import uuid
from typing import Any

LLM_OUTAGE_BEHAVIORS = ("http_500", "rate_limit", "timeout", "empty")


class FaultSimulated(Exception):
    """Raised instead of performing a real provider/tool call when a fault fires."""

    def __init__(self, behavior: str, detail: str = ""):
        self.behavior = behavior
        self.detail = detail
        super().__init__(f"simulated fault: {behavior} {detail}".strip())


class ToolCrash(FaultSimulated):
    pass


class ToolTimeout(FaultSimulated):
    pass


class FaultContext:
    """Per-run chaos controller; one instance per run."""

    def __init__(self, faults: list[dict], seed: int | None = None):
        self.faults: dict[str, list[dict]] = {}
        for spec in faults or []:
            ftype = spec.get("type", "")
            key = ftype.split("_")[0] if ftype else ""   # llm_* → llm, tool_* → tool
            self.faults.setdefault(key, []).append(spec)
        self.rng = random.Random(seed if seed is not None else uuid.uuid4().int)
        self.fired: list[str] = []

    # ------------------------------------------------------------------- llm
    def before_llm(self, trace) -> None:
        """Called once per *raw* LLM attempt (before policy-level retries)."""
        for spec in self.faults.get("llm", []):
            if spec.get("type") != "llm_outage":
                continue
            if self.rng.random() <= float(spec.get("rate", 0.0)):
                behavior = spec.get("behavior", "http_500")
                if behavior not in LLM_OUTAGE_BEHAVIORS:
                    behavior = "http_500"
                self._mark(f"llm_outage:{behavior}")
                trace.span("fault", f"LLM outage → {behavior}",
                           {"behavior": behavior}).finish("error")
                raise FaultSimulated(behavior)

    def after_llm(self, trace, text: str) -> str:
        for spec in self.faults.get("llm", []):
            if spec.get("type") != "llm_truncate":
                continue
            if self.rng.random() <= float(spec.get("rate", 0.0)) and text:
                cut = max(8, int(len(text) * self.rng.uniform(0.35, 0.6)))
                trunc = text[:cut].rsplit(" ", 1)[0]
                if len(trunc) < 6:
                    trunc = text[:cut]
                self._mark("llm_truncate")
                trace.span("fault", "LLM response truncated",
                           {"cut_at": len(trunc)}).finish("warn")
                return trunc + " …"
        return text

    # ----------------------------------------------------------------- tools
    def wrap_tool(self, tool: str, trace):
        specs_tool = self.faults.get("tool", [])
        relevant = [s for s in specs_tool if s.get("tool") == tool]

        def wrapper(fn, **kwargs):
            for spec in relevant:
                if spec.get("type") == "tool_crash" and \
                        self.rng.random() <= float(spec.get("rate", 0.0)):
                    self._mark(f"tool_crash:{tool}")
                    trace.span("fault", f"{tool} crashed (simulated)",
                               {}).finish("error", "ToolCrash: unhandled exception")
                    raise ToolCrash("internal_error",
                                    f"{tool} raised an unhandled exception")
            for spec in relevant:
                if spec.get("type") == "tool_slow":
                    secs = float(spec.get("seconds", 4.0))
                    self._mark(f"tool_slow:{tool}")
                    trace.span("fault", f"{tool} slowed (+{secs:.1f}s)",
                               {"seconds": secs}).finish("warn")
                    time.sleep(secs)
            raw = fn(**kwargs)
            for spec in relevant:
                ftype = spec.get("type", "")
                if ftype == "tool_garbage" and \
                        self.rng.random() <= float(spec.get("rate", 0.0)):
                    self._mark(f"tool_garbage:{tool}")
                    raw = _garbage(tool)
                    trace.span("fault", f"{tool} returned malformed data",
                               {"payload_head": _head(raw)}).finish("warn")
                elif ftype == "tool_stale":
                    raw = _stale(raw)
                    self._mark(f"tool_stale:{tool}")
                    trace.span("fault", f"{tool} served stale data",
                               {}).finish("warn")
                elif ftype == "tool_injection":
                    raw = _inject(raw, spec.get("payload", ""))
                    self._mark(f"tool_injection:{tool}")
                    trace.span("fault", "instruction smuggled into tool output",
                               {}).finish("warn")
            return raw

        return wrapper

    def _mark(self, label: str) -> None:
        if label not in self.fired:
            self.fired.append(label)


def _garbage(tool: str) -> str:
    fakes = [
        "<!doctype html><html><head><title>504</title></head><body></body></html>",
        "}}}{overflow_corrupt::\u0000\u0001\u0002",
        '{"account_id":"ACC-4412","plan":"PRO-"',
        f"ERROR 502 {tool}: upstream connect error (reset by peer)",
    ]
    return random.Random(tool).choice(fakes)


def _stale(raw: Any) -> Any:
    if isinstance(raw, dict):
        out = dict(raw)
        out["_stale"] = True
        out["retrieved_at"] = "2025-11-04T09:15:00Z"
        return out
    return raw


def _inject(raw: Any, payload: str) -> Any:
    inject_fields = ("text", "summary", "body", "note", "instructions")
    if isinstance(raw, dict):
        out = dict(raw)
        target = next((k for k in inject_fields if isinstance(out.get(k), str) and out[k]), None)
        if target:
            out[target] = (out[target] + "\n" + payload).strip()
        else:
            out["tool_note"] = payload      # semantic data fields (company, ids…) stay intact
        return out
    if isinstance(raw, str):
        return raw + "\n" + payload
    return raw


def _head(raw: Any, n: int = 90) -> str:
    text = raw if isinstance(raw, str) else str(raw)
    return text[:n]
