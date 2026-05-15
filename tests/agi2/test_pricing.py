"""Tests for arcsolver.agi2.pricing."""

from __future__ import annotations

import math

import pytest

from arcsolver.agi2.pricing import (
    DEFAULT_MODEL,
    PRICING,
    UnknownModelError,
    call_cost_usd,
    get_pricing,
)


def test_default_model_is_in_table() -> None:
    assert DEFAULT_MODEL in PRICING


def test_required_models_present() -> None:
    # Plan requires entries for opus-4-7 and at least one Sonnet.
    assert "claude-opus-4-7" in PRICING
    assert any(name.startswith("claude-sonnet-") for name in PRICING)


def test_unknown_model_raises() -> None:
    with pytest.raises(UnknownModelError, match="no-such-model"):
        get_pricing("no-such-model")


def test_pricing_invariants() -> None:
    """Cache writes are a premium over input; reads are a deep discount."""
    for name, p in PRICING.items():
        assert p.input > 0, name
        assert p.output > p.input, f"{name}: output should exceed input"
        assert p.cache_write > p.input, f"{name}: cache write should exceed input"
        assert p.cache_read < p.input, f"{name}: cache read should be cheaper than input"
        assert p.cache_read > 0, name


def test_input_only_cost() -> None:
    # Opus 4.7: $5/M input. 1M tokens => $5.
    cost = call_cost_usd(
        "claude-opus-4-7",
        input_tokens=1_000_000,
        output_tokens=0,
    )
    assert math.isclose(cost, 5.0)


def test_output_only_cost() -> None:
    # Opus 4.7: $25/M output. 1M tokens => $25.
    cost = call_cost_usd(
        "claude-opus-4-7",
        input_tokens=0,
        output_tokens=1_000_000,
    )
    assert math.isclose(cost, 25.0)


def test_cache_write_cost() -> None:
    # Opus 4.7 cache write: $6.25/M.
    cost = call_cost_usd(
        "claude-opus-4-7",
        input_tokens=0,
        cache_creation_input_tokens=1_000_000,
        output_tokens=0,
    )
    assert math.isclose(cost, 6.25)


def test_cache_read_cost() -> None:
    # Opus 4.7 cache read: $0.50/M.
    cost = call_cost_usd(
        "claude-opus-4-7",
        input_tokens=0,
        cache_read_input_tokens=1_000_000,
        output_tokens=0,
    )
    assert math.isclose(cost, 0.50)


def test_mixed_cached_and_uncached_input_on_same_call() -> None:
    # Sanity check that the four buckets add cleanly.
    # Sonnet 4.6: input $3, cache_write $3.75, cache_read $0.30, output $15.
    cost = call_cost_usd(
        "claude-sonnet-4-6",
        input_tokens=100_000,  # 100k * $3/M = $0.30
        cache_creation_input_tokens=200_000,  # 200k * $3.75/M = $0.75
        cache_read_input_tokens=500_000,  # 500k * $0.30/M = $0.15
        output_tokens=10_000,  # 10k * $15/M = $0.15
    )
    expected = 0.30 + 0.75 + 0.15 + 0.15
    assert math.isclose(cost, expected), f"{cost} vs {expected}"


def test_haiku_cheaper_than_opus() -> None:
    same_args = {"input_tokens": 1_000_000, "output_tokens": 1_000_000}
    opus = call_cost_usd("claude-opus-4-7", **same_args)
    haiku = call_cost_usd("claude-haiku-4-5", **same_args)
    assert haiku < opus
