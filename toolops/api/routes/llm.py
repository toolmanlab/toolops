"""LLM usage API routes — overview, sessions, projects, models, timeline, and manual collect."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from toolops.api.deps import get_clickhouse
from toolops.storage.clickhouse import ClickHouseClient

router = APIRouter(prefix="/api/llm", tags=["llm"])


@router.get("/overview")
def get_llm_overview(
    ch: ClickHouseClient = Depends(get_clickhouse),
) -> dict[str, Any]:
    """Return aggregate totals: tokens, sessions, top model, cost."""
    return ch.query_llm_overview()


@router.get("/sessions")
def get_llm_sessions(
    limit: int = 50,
    ch: ClickHouseClient = Depends(get_clickhouse),
) -> list[dict[str, Any]]:
    """Return session list ordered by total token consumption."""
    return ch.query_llm_sessions(limit=limit)


@router.get("/sessions/{session_id}")
def get_llm_session_detail(
    session_id: str,
    ch: ClickHouseClient = Depends(get_clickhouse),
) -> list[dict[str, Any]]:
    """Return per-message token breakdown for a single session."""
    return ch.query_llm_session_detail(session_id=session_id)


@router.get("/projects")
def get_llm_projects(
    limit: int = 20,
    ch: ClickHouseClient = Depends(get_clickhouse),
) -> list[dict[str, Any]]:
    """Return usage aggregated by project (cwd)."""
    return ch.query_llm_by_project(limit=limit)


@router.get("/models")
def get_llm_models(
    ch: ClickHouseClient = Depends(get_clickhouse),
) -> list[dict[str, Any]]:
    """Return usage aggregated by model name."""
    return ch.query_llm_by_model()


@router.get("/timeline")
def get_llm_timeline(
    interval: str = "day",
    ch: ClickHouseClient = Depends(get_clickhouse),
) -> list[dict[str, Any]]:
    """Return token usage over time.  interval='hour' or 'day'."""
    return ch.query_llm_timeline(interval=interval)


@router.get("/gateway/overview")
def get_gateway_overview(
    ch: ClickHouseClient = Depends(get_clickhouse),
) -> dict[str, Any]:
    """Return aggregate gateway stats: requests, tokens, cost, latency, error rate."""
    return ch.query_gateway_overview()


@router.get("/gateway/requests")
def get_gateway_requests(
    limit: int = 50,
    ch: ClickHouseClient = Depends(get_clickhouse),
) -> list[dict[str, Any]]:
    """Return recent gateway proxy requests ordered by time descending."""
    return ch.query_gateway_requests(limit=limit)


@router.get("/gateway/agents")
def get_gateway_agents(
    ch: ClickHouseClient = Depends(get_clickhouse),
) -> list[dict[str, Any]]:
    """Return gateway usage aggregated by agent_name."""
    return ch.query_gateway_by_agent()


@router.get("/gateway/latency")
def get_gateway_latency(
    interval: str = "hour",
    ch: ClickHouseClient = Depends(get_clickhouse),
) -> list[dict[str, Any]]:
    """Return P50/P95 latency over time bucketed by hour or day."""
    return ch.query_gateway_latency(interval=interval)


@router.get("/openclaw/overview")
def get_openclaw_overview(
    ch: ClickHouseClient = Depends(get_clickhouse),
) -> dict[str, Any]:
    """Return aggregate OpenClaw observer stats: requests, tokens, cost, avg latency."""
    return ch.query_openclaw_overview()


@router.get("/openclaw/agents")
def get_openclaw_agents(
    ch: ClickHouseClient = Depends(get_clickhouse),
) -> list[dict[str, Any]]:
    """Return OpenClaw usage aggregated by agent_id."""
    return ch.query_openclaw_by_agent()


@router.get("/openclaw/timeline")
def get_openclaw_timeline(
    interval: str = "hour",
    ch: ClickHouseClient = Depends(get_clickhouse),
) -> list[dict[str, Any]]:
    """Return OpenClaw token usage over time. interval='hour' or 'day'."""
    return ch.query_openclaw_timeline(interval=interval)


@router.get("/openclaw/requests")
def get_openclaw_requests(
    limit: int = 50,
    ch: ClickHouseClient = Depends(get_clickhouse),
) -> list[dict[str, Any]]:
    """Return recent OpenClaw requests ordered by time descending."""
    return ch.query_openclaw_requests(limit=limit)


@router.get("/collect")
@router.post("/collect")
def trigger_collect(
    ch: ClickHouseClient = Depends(get_clickhouse),
) -> dict[str, Any]:
    """Manually trigger a Claude Code collector run and ingest into ClickHouse."""
    try:
        from toolops.collector.cc_collector import ClaudeCodeCollector

        collector = ClaudeCodeCollector()
        usages = collector.collect()
        inserted = collector.ingest_to_clickhouse(ch, usages)
        return {"status": "ok", "collected": len(usages), "inserted": inserted}
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "detail": str(exc), "collected": 0, "inserted": 0}
