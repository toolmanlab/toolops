"""Logs query routes."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Query

from toolops.api.deps import get_clickhouse
from toolops.storage.clickhouse import ClickHouseClient

router = APIRouter(prefix="/api/logs", tags=["logs"])


@router.get("/")
def list_logs(
    service: str | None = Query(None),
    level: str | None = Query(None),
    trace_id: str | None = Query(None),
    search: str | None = Query(None),
    start: datetime | None = Query(None),
    end: datetime | None = Query(None),
    limit: int = Query(1000, le=10000),
    ch: ClickHouseClient = Depends(get_clickhouse),
) -> list[dict[str, Any]]:
    """Query logs with optional filters."""
    return ch.query_logs(
        service=service, level=level, trace_id=trace_id,
        search=search, start=start, end=end, limit=limit,
    )
