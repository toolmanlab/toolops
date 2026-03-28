"""LLM model pricing table and cost calculation utilities.

All prices are in USD per 1,000,000 tokens.
"""

from __future__ import annotations

import logging
from typing import TypedDict

logger = logging.getLogger(__name__)


class ModelPricing(TypedDict):
    """Per-token pricing for a single model (prices in USD / 1M tokens)."""

    input_per_m: float
    output_per_m: float
    cache_write_per_m: float
    cache_read_per_m: float


# ---------------------------------------------------------------------------
# Pricing table
# ---------------------------------------------------------------------------
# Keys are canonical model name prefixes / substrings used for fuzzy matching.
# Exact match is tried first; then substring (``key in model_name``).
# ---------------------------------------------------------------------------

PRICING_TABLE: dict[str, ModelPricing] = {
    # Anthropic Claude Opus 4 series
    "claude-opus-4-6": ModelPricing(
        input_per_m=5.00,
        output_per_m=25.00,
        cache_write_per_m=10.00,
        cache_read_per_m=0.50,
    ),
    # Anthropic Claude Sonnet 4 series
    "claude-sonnet-4-6": ModelPricing(
        input_per_m=3.00,
        output_per_m=15.00,
        cache_write_per_m=6.00,
        cache_read_per_m=0.30,
    ),
    # Anthropic Claude Haiku 4 series
    "claude-haiku-4-5": ModelPricing(
        input_per_m=1.00,
        output_per_m=5.00,
        cache_write_per_m=2.00,
        cache_read_per_m=0.10,
    ),
    # Moonshot Kimi K2 series (no distinct cache pricing; use base input price)
    "kimi-k2": ModelPricing(
        input_per_m=0.60,
        output_per_m=3.00,
        cache_write_per_m=0.60,
        cache_read_per_m=0.10,
    ),
}


def _lookup_pricing(model: str) -> ModelPricing | None:
    """Return pricing for *model*, trying exact match then substring match.

    Args:
        model: The model identifier string as returned by the API.

    Returns:
        A :class:`ModelPricing` dict when a match is found, otherwise ``None``.
    """
    # 1. Exact match
    if model in PRICING_TABLE:
        return PRICING_TABLE[model]

    # 2. Substring match — model string *contains* the key
    for key, pricing in PRICING_TABLE.items():
        if key in model:
            return pricing

    return None


def calculate_cost(
    model: str,
    input_tokens: int,
    output_tokens: int,
    cache_creation_tokens: int = 0,
    cache_read_tokens: int = 0,
) -> float:
    """Calculate the USD cost for a single LLM API call.

    The Claude Code JSONL ``input_tokens`` field already *includes*
    ``cache_creation_input_tokens`` and ``cache_read_input_tokens``, so the
    non-cached input token count is derived as::

        non_cache_input = input_tokens - cache_creation_tokens - cache_read_tokens

    Args:
        model: Model identifier, e.g. ``"claude-opus-4-6-20251001"``.
        input_tokens: Total input tokens (including cache hits and cache writes).
        output_tokens: Generated output tokens.
        cache_creation_tokens: Tokens written to the prompt cache.
        cache_read_tokens: Tokens read from the prompt cache.

    Returns:
        Estimated cost in USD, rounded to 8 decimal places.
        Returns ``0.0`` if the model is not found in :data:`PRICING_TABLE`.
    """
    pricing = _lookup_pricing(model)
    if pricing is None:
        logger.debug("No pricing found for model %r — returning 0.0", model)
        return 0.0

    # Non-cache standard input tokens
    non_cache_input = max(0, input_tokens - cache_creation_tokens - cache_read_tokens)

    cost = (
        non_cache_input * pricing["input_per_m"]
        + output_tokens * pricing["output_per_m"]
        + cache_creation_tokens * pricing["cache_write_per_m"]
        + cache_read_tokens * pricing["cache_read_per_m"]
    ) / 1_000_000

    return round(cost, 8)
