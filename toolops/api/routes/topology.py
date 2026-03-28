"""Topology API — expose parsed toolops.yaml to frontend."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException

from toolops.config.topology import load_topology

router = APIRouter(prefix="/api/topology", tags=["topology"])


@router.get("")
def get_topology() -> dict:
    """Return the parsed application topology."""
    try:
        topo = load_topology(Path("/app/toolops.yaml"))
    except FileNotFoundError:
        # Try local dev path
        try:
            topo = load_topology()
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail="toolops.yaml not found")

    return {
        "app": topo.app.model_dump(),
        "services": {
            name: {
                **svc.model_dump(exclude_none=True),
                "role": svc.role.value,
            }
            for name, svc in topo.services.items()
        },
        "dependency_graph": topo.get_dependency_graph(),
        "health_endpoints": topo.get_health_endpoints(),
    }


@router.get("/roles")
def list_roles() -> dict:
    """Return available built-in roles and their descriptions."""
    from toolops.config.topology import ServiceRole

    role_descriptions = {
        ServiceRole.API_GATEWAY: "Entry point — request rate, latency, errors",
        ServiceRole.AI_APP: "AI workload — pipeline stages, token usage",
        ServiceRole.VECTOR_STORE: "Embedding storage — query latency, recall",
        ServiceRole.METADATA_STORE: "Persistent storage — query performance",
        ServiceRole.CACHE: "Cache layer — hit/miss ratio",
        ServiceRole.LLM_PROVIDER: "LLM API — token cost, rate limits",
        ServiceRole.COLLECTOR: "Telemetry collector",
        ServiceRole.METRICS_SCRAPER: "Metrics pull agent",
        ServiceRole.LOG_AGGREGATOR: "Log ingestion",
        ServiceRole.GRAPH_STORE: "Graph database",
        ServiceRole.CUSTOM: "User-defined",
    }

    return {
        "roles": [
            {"value": role.value, "description": desc}
            for role, desc in role_descriptions.items()
        ]
    }
