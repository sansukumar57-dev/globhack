"""Token-usage extraction from OpenAI-compatible payloads, with estimation fallback."""
from __future__ import annotations

from typing import Any


def estimate_tokens(text: str) -> int:
    if not text:
        return 0
    return max(1, len(text) // 4)


def message_text(messages: list[dict[str, Any]] | None) -> str:
    parts: list[str] = []
    for msg in messages or []:
        content = msg.get("content")
        if isinstance(content, str):
            parts.append(content)
        elif isinstance(content, list):
            for block in content:
                if isinstance(block, dict):
                    parts.append(str(block.get("text", "")))
        parts.append(str(msg.get("name") or msg.get("role") or ""))
    return "\n".join(parts)


def completion_text(response_json: dict[str, Any]) -> str:
    out: list[str] = []
    for choice in response_json.get("choices") or []:
        message = choice.get("message") or {}
        if message:
            out.append(str(message.get("content") or ""))
        else:
            out.append(str(choice.get("text") or ""))  # legacy text completions
    return "\n".join(out)


def meter_chat_request(body: dict[str, Any], response_json: dict[str, Any]) -> tuple[int, int, bool]:
    """Best-effort metering for a chat.completion request/response pair.

    Returns (prompt_tokens, completion_tokens, exact). exact=True when the
    provider reported usage, False when we estimated from text length.
    """
    usage = response_json.get("usage")
    if isinstance(usage, dict):
        pt = usage.get("prompt_tokens", usage.get("input_tokens"))
        ct = usage.get("completion_tokens", usage.get("output_tokens"))
        try:
            if pt is not None and ct is not None:
                return int(pt), int(ct), True
        except (TypeError, ValueError):
            pass
    prompt_est = estimate_tokens(message_text(body.get("messages")))
    completion_est = estimate_tokens(completion_text(response_json))
    return prompt_est, completion_est, False
