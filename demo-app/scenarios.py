"""Fault scenario generators for the demo RAG application.

Each scenario function returns a dict of parameters that modify
the behavior of the simulated RAG pipeline steps.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field


@dataclass
class ScenarioParams:
    """Parameters controlling simulated RAG pipeline behavior."""

    # Embedding step
    embed_latency_range: tuple[float, float] = (0.03, 0.08)

    # Vector search step
    retrieval_latency_range: tuple[float, float] = (0.05, 0.2)
    retrieval_timeout_rate: float = 0.05

    # LLM generation step
    llm_latency_range: tuple[float, float] = (0.5, 3.0)
    llm_rate_limit_rate: float = 0.03
    llm_model: str = "gpt-4o-mini"
    llm_input_tokens_range: tuple[int, int] = (200, 800)
    llm_output_tokens_range: tuple[int, int] = (50, 300)

    # Cache
    cache_hit_rate: float = 0.4

    # Memory (MB increase per request)
    memory_growth_mb: float = 0.0


SCENARIOS: dict[str, ScenarioParams] = {
    "normal": ScenarioParams(),
    "slow_retrieval": ScenarioParams(
        retrieval_latency_range=(0.5, 2.0),
        retrieval_timeout_rate=0.15,
    ),
    "llm_rate_limit": ScenarioParams(
        llm_rate_limit_rate=0.30,
    ),
    "cache_cold_start": ScenarioParams(
        cache_hit_rate=0.0,
    ),
    "memory_pressure": ScenarioParams(
        memory_growth_mb=0.5,
    ),
    "cascade_failure": ScenarioParams(
        retrieval_latency_range=(1.0, 5.0),
        retrieval_timeout_rate=0.30,
        llm_latency_range=(2.0, 8.0),
        llm_rate_limit_rate=0.15,
    ),
    "cost_spike": ScenarioParams(
        llm_model="gpt-4o",
        llm_input_tokens_range=(500, 2000),
        llm_output_tokens_range=(200, 1000),
    ),
}


def get_scenario(name: str) -> ScenarioParams:
    """Return scenario params by name. 'mixed' picks randomly each call."""
    if name == "mixed":
        chosen = random.choice(list(SCENARIOS.values()))
        return chosen
    return SCENARIOS.get(name, SCENARIOS["normal"])
