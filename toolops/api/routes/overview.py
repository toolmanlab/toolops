"""Overview stats route."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from toolops.api.deps import get_clickhouse
from toolops.storage.clickhouse import ClickHouseClient

router = APIRouter(prefix="/api/overview", tags=["overview"])


@router.get("/")
def get_overview(
    ch: ClickHouseClient = Depends(get_clickhouse),
) -> dict[str, Any]:
    """Get overview statistics."""
    return ch.query_overview()
