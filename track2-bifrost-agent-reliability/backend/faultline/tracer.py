"""Span-level tracing: OTel-style spans for every LLM call, tool call, fault event."""
import time


class Span:
    _seq = 1

    def __init__(self, kind: str, name: str, meta: dict | None = None):
        self.id = f"sp{Span._seq:04d}"
        Span._seq += 1
        self.kind = kind  # "llm" | "tool" | "fault" | "agent" | "eval"
        self.name = name
        self.meta = dict(meta or {})
        self.t0_wall = time.time()
        self.t1_wall = None
        self.status = "running"  # ok | warn | error
        self.attempts: list[dict] = []
        self.usage: dict = {}
        self.error: str | None = None

    def add_attempt(self, **info) -> None:
        self.attempts.append({"n": len(self.attempts) + 1, **info})

    def finish(self, status: str = "ok", error: str | None = None) -> None:
        self.t1_wall = time.time()
        self.status = status
        self.error = error

    @property
    def duration(self) -> float:
        if self.t1_wall is None:
            return 0.0
        return self.t1_wall - self.t0_wall

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "kind": self.kind,
            "name": self.name,
            "duration_ms": round(self.duration * 1000),
            "status": self.status,
            "attempts": self.attempts,
            "usage": self.usage,
            "error": self.error,
            "meta": self.meta,
        }


class TraceCollector:
    def __init__(self, run_id: str, t_start: float | None = None):
        self.run_id = run_id
        self.t_start = t_start if t_start is not None else time.time()
        self.spans: list[Span] = []

    def span(self, kind: str, name: str, meta: dict | None = None) -> Span:
        sp = Span(kind, name, meta)
        self.spans.append(sp)
        return sp

    def total_duration(self) -> float:
        return time.time() - self.t_start

    def as_dict(self) -> dict:
        spans = []
        for sp in self.spans:
            d = sp.as_dict()
            d["t_rel_ms"] = int((sp.t0_wall - self.t_start) * 1000)
            spans.append(d)
        return {"run_id": self.run_id, "spans": spans,
                "total_ms": int((time.time() - self.t_start) * 1000)}
