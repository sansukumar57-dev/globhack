"""Unit tests for the embedded pricing catalog and downgrade suggestions."""
from __future__ import annotations

import pytest

from foresight import pricing


# -------------------------------------------------------------------- strip

@pytest.mark.parametrize("raw,expected", [
    ("acme-llm/gpt-4o", "gpt-4o"),
    ("GPT-4O", "gpt-4o"),
    ("  gpt-4o  ", "gpt-4o"),
    ("gpt-4o", "gpt-4o"),
    ("", "unknown"),
])
def test_strip_provider(raw, expected):
    assert pricing.strip_provider(raw) == expected


# -------------------------------------------------------------------- price

def test_price_for_exact_entry():
    assert pricing.price_for("gpt-4o") == (2.50, 10.00)
    assert pricing.price_for("gpt-4o-mini") == (0.15, 0.60)


def test_price_for_provider_prefixed_model():
    assert pricing.price_for("acme-llm/gpt-4o") == (2.50, 10.00)
    assert pricing.price_for("acme-llm/gpt-4o-mini") == (0.15, 0.60)


def test_price_for_dated_snapshot_via_longest_prefix():
    assert pricing.price_for("gpt-4.1-mini-2025-04-14") == (0.40, 1.60)
    assert pricing.price_for("acme-llm/claude-3-5-sonnet-20241022") == (3.00, 15.00)
    assert pricing.price_for("gpt-4o-2024-11-20") == (2.50, 10.00)


def test_price_for_longest_prefix_wins_between_related_models():
    # "o3-mini-2025-01-31" matches both "o3" and "o3-mini"; the longer wins.
    assert pricing.price_for("o3-mini-2025-01-31") == (1.10, 4.40)


def test_unknown_model_uses_conservative_default():
    assert pricing.price_for("totally-unknown-model") == pricing.DEFAULT_PRICE
    assert pricing.price_for("") == pricing.DEFAULT_PRICE


# --------------------------------------------------------------------- cost

def test_cost_usd_exact_math():
    assert pricing.cost_usd("gpt-4o", 1_000_000, 1_000_000) == pytest.approx(12.50)
    assert pricing.cost_usd("gpt-4o", 0, 1_000_000) == pytest.approx(10.00)
    assert pricing.cost_usd("gpt-4o", 1_000_000, 0) == pytest.approx(2.50)


def test_cost_usd_fractional_tokens():
    expected = (1000 * 0.15 + 2000 * 0.60) / 1_000_000.0
    assert pricing.cost_usd("gpt-4o-mini", 1_000, 2_000) == pytest.approx(expected)


def test_cost_usd_unknown_model_falls_back():
    assert pricing.cost_usd("mystery-model", 1_000_000, 0) == pytest.approx(1.00)
    assert pricing.cost_usd("mystery-model", 0, 1_000_000) == pytest.approx(3.00)


# -------------------------------------------------------------- unit ratio

def test_unit_ratio_identity_is_one():
    assert pricing.unit_ratio("gpt-4o", "gpt-4o") == pytest.approx(1.0)


def test_unit_ratio_gpt4o_to_mini():
    from_blend = 0.3 * 2.50 + 0.7 * 10.00   # 7.75
    to_blend = 0.3 * 0.15 + 0.7 * 0.60      # 0.465
    assert pricing.unit_ratio("gpt-4o", "gpt-4o-mini") == pytest.approx(to_blend / from_blend)


def test_unit_ratio_with_unknown_models():
    # DEFAULT_PRICE (1.00, 3.00) blended: 0.3*1 + 0.7*3 = 2.4
    assert pricing.unit_ratio("unknown-a", "unknown-b") == pytest.approx(1.0)


# --------------------------------------------------------- suggest downgrade

@pytest.mark.parametrize("model,expected", [
    ("gpt-4o", "gpt-4o-mini"),
    ("acme-llm/gpt-5", "gpt-5-mini"),
    ("GPT-4.1", "gpt-4.1-mini"),
    ("acme-llm/claude-sonnet-4", "claude-3-5-haiku"),
    ("o3", "o3-mini"),
    ("acme-llm/gemini-2.5-pro", "gemini-2.0-flash"),
    # regression: mini families prefix-match their parent — never downgrade to self
    ("gpt-4o-mini", None),
    ("gpt-4.1-mini", None),
    ("o3-mini", None),
    ("claude-3-5-haiku", None),
    ("llama-3.1-8b", None),
    ("", None),
])
def test_suggest_downgrade(model, expected):
    assert pricing.suggest_downgrade(model) == expected
