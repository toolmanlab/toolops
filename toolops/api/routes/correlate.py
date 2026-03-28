"""Cross-table correlation routes."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from toolops.api.deps import get_clickhouse
from toolops.storage.clickhouse import ClickHouseClient

router = APIRouter(prefix="/api/correlate", tags=["correlate"])


@router.get("/{trace_id}")
def correlate_by_trace(
    trace_id: str,
    ch: ClickHouseClient = Depends(get_clickhouse),
) -> dict[str, Any]:
    """Correlate metrics, traces, and logs by trace_id."""
    return ch.correlate(trace_id)
