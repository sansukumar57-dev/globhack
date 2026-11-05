"""Deterministic OpenAI-compatible stand-in for a self-hosted LLM endpoint.

Used by the demo so the full chain — client -> Foresight -> Bifrost OSS ->
upstream — works with zero real API keys. Point Bifrost's custom provider at
http://localhost:9100/v1 and everything below behaves like a small vLLM server.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import random
import time

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse

app = FastAPI(title="acme-llm (demo upstream)", version="1.0.0")

_WORDS = (
    "gateway routing cache governance budget tokens latency fallback provider "
    "proxy inference request response semantic cluster failover billing alert "
    "pipeline deployment observability metrics export threshold policy"
).split()


def _rng(seed_text: str) -> random.Random:
    digest = hashlib.sha256(seed_text.encode()).hexdigest()
    return random.Random(int(digest[:16], 16))


def _reply(model: str, user_text: str) -> str:
    rng = _rng(user_text + model)
    n = rng.randint(90, 220)
    body = " ".join(rng.choice(_WORDS) for _ in range(n))
    return f"Here is a synthesized completion for: {user_text[:120]!r}. {body.capitalize()}."


def _usage(prompt_text: str, reply: str) -> dict:
    pt = max(1, len(prompt_text) // 4)
    ct = max(1, len(reply) // 4)
    return {"prompt_tokens": pt, "completion_tokens": ct, "total_tokens": pt + ct}


@app.get("/v1/models")
async def models():
    return {
        "object": "list",
        "data": [
            {"id": "gpt-4o", "object": "model", "owned_by": "acme"},
            {"id": "gpt-4o-mini", "object": "model", "owned_by": "acme"},
            {"id": "gpt-4.1", "object": "model", "owned_by": "acme"},
            {"id": "gpt-4.1-mini", "object": "model", "owned_by": "acme"},
            {"id": "claude-3-5-sonnet", "object": "model", "owned_by": "acme"},
            {"id": "deepseek-chat", "object": "model", "owned_by": "acme"},
        ],
    }


@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    body = await request.json()
    model = body.get("model", "gpt-4o")
    messages = body.get("messages") or []
    prompt_text = "\n".join(str(m.get("content") or "") for m in messages if isinstance(m, dict))
    user_text = next((str(m.get("content") or "") for m in reversed(messages)
                      if isinstance(m, dict) and m.get("role") == "user"), "ping")
    reply = _reply(model, user_text)
    usage = _usage(prompt_text, reply)
    created = int(time.time())
    completion_id = "chatcmpl-" + hashlib.sha256(f"{created}{prompt_text[:64]}".encode()).hexdigest()[:24]

    if body.get("stream"):
        include_usage = bool((body.get("stream_options") or {}).get("include_usage"))
        chunks = []

        def event(obj):
            return f"data: {json.dumps(obj)}\n\n".encode()

        base = {"id": completion_id, "object": "chat.completion.chunk", "created": created, "model": model}
        chunks.append(event({**base, "choices": [{"index": 0, "delta": {"role": "assistant", "content": ""}, "finish_reason": None}]}))
        words = reply.split(" ")
        step = max(1, len(words) // 24)
        for i in range(0, len(words), step):
            piece = " ".join(words[i:i + step]) + " "
            chunks.append(event({**base, "choices": [{"index": 0, "delta": {"content": piece}, "finish_reason": None}]}))
        chunks.append(event({**base, "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]}))
        if include_usage:
            chunks.append(event({**base, "choices": [], "usage": usage}))
        chunks.append(b"data: [DONE]\n\n")

        async def gen():
            for c in chunks:
                await asyncio.sleep(0.004)
                yield c

        return StreamingResponse(gen(), media_type="text/event-stream",
                                 headers={"Cache-Control": "no-cache", "x-demo-upstream": "acme-llm"})

    return JSONResponse({
        "id": completion_id,
        "object": "chat.completion",
        "created": created,
        "model": model,
        "choices": [{
            "index": 0,
            "message": {"role": "assistant", "content": reply},
            "finish_reason": "stop",
        }],
        "usage": usage,
        "system_fingerprint": "fp_acme_demo",
    })


@app.get("/health")
async def health():
    return {"status": "ok", "service": "acme-llm demo upstream"}


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=9100, log_level="warning")
