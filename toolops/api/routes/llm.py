"""LLM usage API routes — overview, sessions, projects, models, timeline, and manual collect."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query

from toolops.api.deps import get_clickhouse
from toolops.storage.clickhouse import ClickHouseClient

router = APIRouter(prefix="/api/llm", tags=["llm"])

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_filters(
    *,
    agent_id: str | None = None,
    session_id: str | None = None,
    model: str | None = None,
    start: str | None = None,
    end: str | None = None,
    offset: int | None = None,
) -> dict:
    """Collect non-None filter values into a dict for ClickHouseClient methods."""
    filters: dict = {}
    if agent_id:
        filters["agent_id"] = agent_id
    if session_id:
        filters["session_id"] = session_id
    if model:
        filters["model"] = model
    if start:
        filters["start"] = start
    if end:
        filters["end"] = end
    if offset is not None and offset > 0:
        filters["offset"] = offset
    return filters


# ---------------------------------------------------------------------------
# LLM usage (Claude Code collector) endpoints
# ---------------------------------------------------------------------------

@router.get("/overview")
def get_llm_overview(
    session_id: str | None = Query(None),
    model: str | None = Query(None),
    start: str | None = Query(None, description="ISO 8601 start datetime"),
    end: str | None = Query(None, description="ISO 8601 end datetime"),
    ch: ClickHouseClient = Depends(get_clickhouse),
) -> dict[str, Any]:
    """Return aggregate totals: tokens, sessions, top model, cost."""
    filters = _build_filters(session_id=session_id, model=model, start=start, end=end)
    return ch.query_llm_overview(filters=filters or None)


@router.get("/sessions")
def get_llm_sessions(
    session_id: str | None = Query(None),
    model: str | None = Query(None),
    start: str | None = Query(None, description="ISO 8601 start datetime"),
    end: str | None = Query(None, description="ISO 8601 end datetime"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    ch: ClickHouseClient = Depends(get_clickhouse),
) -> list[dict[str, Any]]:
    """Return session list ordered by total token consumption."""
    filters = _build_filters(
        session_id=session_id, model=model, start=start, end=end, offset=offset
    )
    return ch.query_llm_sessions(limit=limit, filters=filters or None)


@router.get("/sessions/{session_id}")
def get_llm_session_detail(
    session_id: str,
    ch: ClickHouseClient = Depends(get_clickhouse),
) -> list[dict[str, Any]]:
    """Return per-message token breakdown for a single session."""
    return ch.query_llm_session_detail(session_id=session_id)


@router.get("/projects")
def get_llm_projects(
    limit: int = Query(20, ge=1, le=500),
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
    interval: str = Query("day", pattern="^(hour|day)$"),
    ch: ClickHouseClient = Depends(get_clickhouse),
) -> list[dict[str, Any]]:
    """Return token usage over time.  interval='hour' or 'day'."""
    return ch.query_llm_timeline(interval=interval)


# ---------------------------------------------------------------------------
# LLM Gateway endpoints
# ---------------------------------------------------------------------------

@router.get("/gateway/overview")
def get_gateway_overview(
    agent_id: str | None = Query(None),
    model: str | None = Query(None),
    start: str | None = Query(None, description="ISO 8601 start datetime"),
    end: str | None = Query(None, description="ISO 8601 end datetime"),
    ch: ClickHouseClient = Depends(get_clickhouse),
) -> dict[str, Any]:
    """Return aggregate gateway stats: requests, tokens, cost, latency, error rate."""
    filters = _build_filters(agent_id=agent_id, model=model, start=start, end=end)
    return ch.query_gateway_overview(filters=filters or None)


@router.get("/gateway/requests")
def get_gateway_requests(
    agent_id: str | None = Query(None),
    model: str | None = Query(None),
    start: str | None = Query(None, description="ISO 8601 start datetime"),
    end: str | None = Query(None, description="ISO 8601 end datetime"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    ch: ClickHouseClient = Depends(get_clickhouse),
) -> list[dict[str, Any]]:
    """Return recent gateway proxy requests ordered by time descending."""
    filters = _build_filters(
        agent_id=agent_id, model=model, start=start, end=end, offset=offset
    )
    return ch.query_gateway_requests(limit=limit, filters=filters or None)


@router.get("/gateway/agents")
def get_gateway_agents(
    agent_id: str | None = Query(None),
    model: str | None = Query(None),
    start: str | None = Query(None, description="ISO 8601 start datetime"),
    end: str | None = Query(None, description="ISO 8601 end datetime"),
    ch: ClickHouseClient = Depends(get_clickhouse),
) -> list[dict[str, Any]]:
    """Return gateway usage aggregated by agent_name."""
    filters = _build_filters(agent_id=agent_id, model=model, start=start, end=end)
    return ch.query_gateway_by_agent(filters=filters or None)


@router.get("/gateway/latency")
def get_gateway_latency(
    interval: str = Query("hour", pattern="^(hour|day)$"),
    agent_id: str | None = Query(None),
    model: str | None = Query(None),
    start: str | None = Query(None, description="ISO 8601 start datetime"),
    end: str | None = Query(None, description="ISO 8601 end datetime"),
    ch: ClickHouseClient = Depends(get_clickhouse),
) -> list[dict[str, Any]]:
    """Return P50/P95 latency over time bucketed by hour or day."""
    filters = _build_filters(agent_id=agent_id, model=model, start=start, end=end)
    return ch.query_gateway_latency(interval=interval, filters=filters or None)


# ---------------------------------------------------------------------------
# OpenClaw observer endpoints
# ---------------------------------------------------------------------------

@router.get("/openclaw/overview")
def get_openclaw_overview(
    agent_id: str | None = Query(None),
    session_id: str | None = Query(None),
    model: str | None = Query(None),
    start: str | None = Query(None, description="ISO 8601 start datetime"),
    end: str | None = Query(None, description="ISO 8601 end datetime"),
    ch: ClickHouseClient = Depends(get_clickhouse),
) -> dict[str, Any]:
    """Return aggregate OpenClaw observer stats: requests, tokens, cost, avg latency."""
    filters = _build_filters(agent_id=agent_id, session_id=session_id, model=model, start=start, end=end)
    return ch.query_openclaw_overview(filters=filters or None)


@router.get("/openclaw/agents")
def get_openclaw_agents(
    model: str | None = Query(None),
    start: str | None = Query(None, description="ISO 8601 start datetime"),
    end: str | None = Query(None, description="ISO 8601 end datetime"),
    ch: ClickHouseClient = Depends(get_clickhouse),
) -> list[dict[str, Any]]:
    """Return OpenClaw usage aggregated by agent_id."""
    filters = _build_filters(model=model, start=start, end=end)
    return ch.query_openclaw_by_agent(filters=filters or None)


@router.get("/openclaw/timeline")
def get_openclaw_timeline(
    interval: str = Query("hour", pattern="^(hour|day)$"),
    agent_id: str | None = Query(None),
    session_id: str | None = Query(None),
    model: str | None = Query(None),
    start: str | None = Query(None, description="ISO 8601 start datetime"),
    end: str | None = Query(None, description="ISO 8601 end datetime"),
    ch: ClickHouseClient = Depends(get_clickhouse),
) -> list[dict[str, Any]]:
    """Return OpenClaw token usage over time. interval='hour' or 'day'."""
    filters = _build_filters(agent_id=agent_id, session_id=session_id, model=model, start=start, end=end)
    return ch.query_openclaw_timeline(interval=interval, filters=filters or None)


@router.get("/openclaw/requests")
def get_openclaw_requests(
    agent_id: str | None = Query(None),
    session_id: str | None = Query(None),
    model: str | None = Query(None),
    start: str | None = Query(None, description="ISO 8601 start datetime"),
    end: str | None = Query(None, description="ISO 8601 end datetime"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    ch: ClickHouseClient = Depends(get_clickhouse),
) -> list[dict[str, Any]]:
    """Return recent OpenClaw requests ordered by time descending."""
    filters = _build_filters(agent_id=agent_id, session_id=session_id, model=model, start=start, end=end)
    return ch.query_openclaw_requests(limit=limit, offset=offset, filters=filters or None)


@router.get("/openclaw/sessions")
def get_openclaw_sessions(
    agent_id: str | None = Query(None),
    model: str | None = Query(None),
    start: str | None = Query(None, description="ISO 8601 start datetime"),
    end: str | None = Query(None, description="ISO 8601 end datetime"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    ch: ClickHouseClient = Depends(get_clickhouse),
) -> list[dict[str, Any]]:
    """Return OpenClaw sessions grouped by session_key with aggregate stats."""
    filters = _build_filters(agent_id=agent_id, model=model, start=start, end=end)
    return ch.query_openclaw_sessions(limit=limit, offset=offset, filters=filters or None)


@router.get("/openclaw/sessions/{session_key:path}")
def get_openclaw_session_detail(
    session_key: str,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    ch: ClickHouseClient = Depends(get_clickhouse),
) -> list[dict[str, Any]]:
    """Return all requests belonging to a single OpenClaw session."""
    return ch.query_openclaw_session_detail(session_key=session_key, limit=limit, offset=offset)


# ---------------------------------------------------------------------------
# Manual collect
# ---------------------------------------------------------------------------

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
