"""Central pricing table for Anthropic Claude models.

This is the single source of truth for converting per-call usage to dollars.
`--max-cost-usd` and the cost summary in `summary.json` both read from here.
Snapshot taken from https://platform.claude.com/docs/en/docs/about-claude/pricing
on 2026-05-15. Update when Anthropic publishes new rates.

Each entry has four explicit USD/M-token rates:
- input: uncached input tokens
- cache_write: 5-minute cache write (the "cache_creation_input_tokens" bucket)
- cache_read: cache hit/refresh (the "cache_read_input_tokens" bucket)
- output: output tokens

Per Anthropic docs, cache_write is 1.25x input and cache_read is 0.10x input
for current models. The table holds the absolute USD numbers so callers
don't recompute multipliers.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ModelPricing:
    """USD per million tokens, broken out by usage bucket."""

    input: float
    cache_write: float
    cache_read: float
    output: float


# Snapshot: 2026-05-15 from https://platform.claude.com/docs/en/docs/about-claude/pricing
# Uses 5-minute cache write rate. 1-hour cache writes are 2x input; not used by this
# project so they're omitted to keep the table small.
PRICING: dict[str, ModelPricing] = {
    "claude-opus-4-7": ModelPricing(input=5.0, cache_write=6.25, cache_read=0.50, output=25.0),
    "claude-opus-4-6": ModelPricing(input=5.0, cache_write=6.25, cache_read=0.50, output=25.0),
    "claude-opus-4-5": ModelPricing(input=5.0, cache_write=6.25, cache_read=0.50, output=25.0),
    "claude-sonnet-4-6": ModelPricing(input=3.0, cache_write=3.75, cache_read=0.30, output=15.0),
    "claude-sonnet-4-5": ModelPricing(input=3.0, cache_write=3.75, cache_read=0.30, output=15.0),
    "claude-haiku-4-5": ModelPricing(input=1.0, cache_write=1.25, cache_read=0.10, output=5.0),
}

DEFAULT_MODEL = "claude-opus-4-7"


class UnknownModelError(KeyError):
    """Raised when a caller asks for pricing of a model not in PRICING."""


def get_pricing(model: str) -> ModelPricing:
    try:
        return PRICING[model]
    except KeyError as exc:
        raise UnknownModelError(
            f"No pricing entry for model {model!r}. Known models: {sorted(PRICING)}"
        ) from exc


def call_cost_usd(
    model: str,
    *,
    input_tokens: int,
    cache_creation_input_tokens: int = 0,
    cache_read_input_tokens: int = 0,
    output_tokens: int,
) -> float:
    """Compute the USD cost of a single API call from raw token counts.

    Mirrors the four usage buckets returned by the Anthropic SDK. Each bucket
    is priced at its own rate from the table.
    """
    p = get_pricing(model)
    return (
        (input_tokens * p.input)
        + (cache_creation_input_tokens * p.cache_write)
        + (cache_read_input_tokens * p.cache_read)
        + (output_tokens * p.output)
    ) / 1_000_000
