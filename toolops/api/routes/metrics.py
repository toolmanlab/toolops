"""Metrics query routes."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Query

from toolops.api.deps import get_clickhouse
from toolops.storage.clickhouse import ClickHouseClient

router = APIRouter(prefix="/api/metrics", tags=["metrics"])


@router.get("/")
def list_metrics(
    service: str | None = Query(None),
    metric_name: str | None = Query(None),
    start: datetime | None = Query(None),
    end: datetime | None = Query(None),
    limit: int = Query(1000, le=10000),
    ch: ClickHouseClient = Depends(get_clickhouse),
) -> list[dict[str, Any]]:
    """Query metrics with optional filters."""
    return ch.query_metrics(
        service=service, metric_name=metric_name, start=start, end=end, limit=limit
    )
