"""Infrastructure health check routes."""

from __future__ import annotations

import httpx
from fastapi import APIRouter

router = APIRouter(prefix="/api/infra", tags=["infra"])

_COMPONENTS = [
    {"name": "ClickHouse", "port": 8123, "url": "http://clickhouse:8123/ping"},
    {"name": "OTel Collector", "port": 4318, "url": "http://otel-collector:4318/"},
    {"name": "Prometheus", "port": 9090, "url": "http://prometheus:9090/-/healthy"},
    {"name": "Loki", "port": 3100, "url": "http://loki:3100/ready"},
    {"name": "Demo App", "port": 8080, "url": "http://demo-app:8080/health"},
]


@router.get("/health")
async def infra_health() -> list[dict[str, str | int | bool]]:
    """Check health of all infrastructure components."""
    results = []
    async with httpx.AsyncClient(timeout=3.0) as client:
        for comp in _COMPONENTS:
            try:
                resp = await client.get(comp["url"])
                healthy = resp.status_code < 500
            except Exception:
                healthy = False
            results.append({
                "name": comp["name"],
                "port": comp["port"],
                "healthy": healthy,
            })
    return results
