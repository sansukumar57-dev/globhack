"""Embedded model pricing table and cost computation.

Prices are USD per 1M tokens (input, output), mirroring public price lists.
Unknown models fall back to DEFAULT_PRICE so metering never silently drops cost.
"""
from __future__ import annotations

_PRICING: dict[str, tuple[float, float]] = {
    "gpt-4o": (2.50, 10.00),
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4o-2024-11-20": (2.50, 10.00),
    "gpt-4o-mini-2024-07-18": (0.15, 0.60),
    "gpt-4-turbo": (10.00, 30.00),
    "gpt-4": (30.00, 60.00),
    "gpt-4.1": (2.00, 8.00),
    "gpt-4.1-mini": (0.40, 1.60),
    "gpt-4.1-nano": (0.10, 0.40),
    "gpt-5": (1.25, 10.00),
    "gpt-5-mini": (0.25, 2.00),
    "o3": (2.00, 8.00),
    "o3-mini": (1.10, 4.40),
    "o4-mini": (1.10, 4.40),
    "claude-3-5-sonnet": (3.00, 15.00),
    "claude-3-7-sonnet": (3.00, 15.00),
    "claude-sonnet-4": (3.00, 15.00),
    "claude-opus-4": (15.00, 75.00),
    "claude-3-5-haiku": (0.80, 4.00),
    "claude-3-haiku": (0.25, 1.25),
    "claude-3-opus": (15.00, 75.00),
    "deepseek-chat": (0.27, 1.10),
    "deepseek-reasoner": (0.55, 2.19),
    "llama-3.3-70b": (0.59, 0.79),
    "llama-3.1-8b": (0.05, 0.08),
    "llama-3.1-70b": (0.52, 0.75),
    "mistral-large": (2.00, 6.00),
    "mistral-small": (0.10, 0.30),
    "mixtral-8x7b": (0.24, 0.24),
    "command-r-plus": (2.50, 10.00),
    "command-r": (0.15, 0.60),
    "gemini-2.5-pro": (1.25, 10.00),
    "gemini-2.5-flash": (0.30, 2.50),
    "gemini-2.0-flash": (0.10, 0.40),
    "gemini-1.5-pro": (1.25, 5.00),
    "gemini-1.5-flash": (0.075, 0.30),
    "grok-3": (3.00, 15.00),
    "grok-3-mini": (0.30, 0.50),
    "qwen-max": (1.60, 6.40),
    "qwen-plus": (0.40, 1.20),
}

DEFAULT_PRICE: tuple[float, float] = (1.00, 3.00)

# Downgrade path candidates used by the what-if simulator and pacing policy.
# Maps a model family to the suggested cheaper drop-in.
DOWNGRADE_MAP: dict[str, str] = {
    "gpt-4o": "gpt-4o-mini",
    "gpt-4.1": "gpt-4.1-mini",
    "gpt-5": "gpt-5-mini",
    "o3": "o3-mini",
    "claude-3-5-sonnet": "claude-3-5-haiku",
    "claude-sonnet-4": "claude-3-5-haiku",
    "claude-3-opus": "claude-3-5-sonnet",
    "deepseek-reasoner": "deepseek-chat",
    "mistral-large": "mistral-small",
    "gemini-2.5-pro": "gemini-2.0-flash",
    "gemini-1.5-pro": "gemini-1.5-flash",
    "command-r-plus": "command-r",
}


def strip_provider(model: str) -> str:
    """Drop any provider prefix: 'acme-llm/gpt-4o' -> 'gpt-4o'."""
    if not model:
        return "unknown"
    return model.split("/")[-1].strip().lower()


def price_for(model: str) -> tuple[float, float]:
    name = strip_provider(model)
    if name in _PRICING:
        return _PRICING[name]
    # Longest-prefix match handles dated snapshots, e.g. gpt-4o-2024-11-20.
    best: str | None = None
    for key in _PRICING:
        if name.startswith(key):
            if best is None or len(key) > len(best):
                best = key
    return _PRICING[best] if best else DEFAULT_PRICE


def cost_usd(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    pin, pout = price_for(model)
    return (prompt_tokens * pin + completion_tokens * pout) / 1_000_000.0


def unit_ratio(from_model: str, to_model: str) -> float:
    """Relative per-token cost of to_model vs from_model (blended 70/30 in/out)."""
    fi, fo = price_for(from_model)
    ti, to = price_for(to_model)
    f_blend = 0.3 * fi + 0.7 * fo
    t_blend = 0.3 * ti + 0.7 * to
    if f_blend <= 0:
        return 1.0
    return t_blend / f_blend


def suggest_downgrade(model: str) -> str | None:
    name = strip_provider(model)
    for key, target in DOWNGRADE_MAP.items():
        if target == name:
            continue  # a mini family prefix-matches its parent — never downgrade to itself
        if name.startswith(key):
            return target
    return None
