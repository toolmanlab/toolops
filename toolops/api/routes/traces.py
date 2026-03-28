"""Traces query routes."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Query

from toolops.api.deps import get_clickhouse
from toolops.storage.clickhouse import ClickHouseClient

router = APIRouter(prefix="/api/traces", tags=["traces"])


@router.get("/")
def list_traces(
    service: str | None = Query(None),
    trace_id: str | None = Query(None),
    start: datetime | None = Query(None),
    end: datetime | None = Query(None),
    limit: int = Query(100, le=10000),
    ch: ClickHouseClient = Depends(get_clickhouse),
) -> list[dict[str, Any]]:
    """Query traces with optional filters."""
    return ch.query_traces(service=service, trace_id=trace_id, start=start, end=end, limit=limit)
