"""toolops.yaml parser and topology model.

Parses the application topology descriptor and provides typed access
to service definitions, roles, and dependency graphs.
"""

from __future__ import annotations

import os
from enum import Enum
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, field_validator, model_validator


class ServiceRole(str, Enum):
    """Built-in service roles that ToolOps understands."""

    API_GATEWAY = "api-gateway"
    AI_APP = "ai-app"
    VECTOR_STORE = "vector-store"
    METADATA_STORE = "metadata-store"
    CACHE = "cache"
    LLM_PROVIDER = "llm-provider"
    COLLECTOR = "collector"
    METRICS_SCRAPER = "metrics-scraper"
    LOG_AGGREGATOR = "log-aggregator"
    GRAPH_STORE = "graph-store"
    CUSTOM = "custom"


class MetricsConfig(BaseModel):
    """Metrics endpoint configuration."""

    path: str
    format: str  # prometheus | otlp

    @field_validator("format")
    @classmethod
    def validate_format(cls, v: str) -> str:
        allowed = {"prometheus", "otlp"}
        if v not in allowed:
            msg = f"metrics format must be one of {allowed}, got '{v}'"
            raise ValueError(msg)
        return v


class AIPipeline(BaseModel):
    """AI pipeline declaration for ai-app services."""

    pipeline: str  # rag | agent | chain | chat
    stages: list[str] = []
    model: str | None = None

    @field_validator("pipeline")
    @classmethod
    def validate_pipeline(cls, v: str) -> str:
        allowed = {"rag", "agent", "chain", "chat"}
        if v not in allowed:
            msg = f"pipeline must be one of {allowed}, got '{v}'"
            raise ValueError(msg)
        return v


class StorageConfig(BaseModel):
    """Storage details for *-store role services."""

    engine: str
    tables: list[str] = []


class ServiceConfig(BaseModel):
    """Single service definition in the topology."""

    role: ServiceRole
    port: int | None = None
    ports: dict[str, int] | None = None
    healthcheck: str | None = None
    metrics: MetricsConfig | None = None
    ai: AIPipeline | None = None
    storage: StorageConfig | None = None
    receivers: list[str] | None = None
    exporters: list[str] | None = None
    scrape_targets: list[str] | None = None
    depends_on: list[str] | None = None
    labels: dict[str, str] | None = None

    @model_validator(mode="after")
    def validate_role_fields(self) -> "ServiceConfig":
        if self.port is not None and self.ports is not None:
            msg = "port and ports are mutually exclusive"
            raise ValueError(msg)
        if self.ai is not None and self.role != ServiceRole.AI_APP:
            msg = "ai section is only valid for ai-app role"
            raise ValueError(msg)
        return self


class AppConfig(BaseModel):
    """Application metadata."""

    name: str
    description: str | None = None


class Topology(BaseModel):
    """Root model for toolops.yaml."""

    version: str
    app: AppConfig
    services: dict[str, ServiceConfig]

    @field_validator("version")
    @classmethod
    def validate_version(cls, v: str) -> str:
        if v != "1":
            msg = f"unsupported toolops.yaml version '{v}', expected '1'"
            raise ValueError(msg)
        return v

    @model_validator(mode="after")
    def validate_references(self) -> "Topology":
        """Validate that all cross-references point to existing services."""
        service_names = set(self.services.keys())

        for name, svc in self.services.items():
            if svc.depends_on:
                for dep in svc.depends_on:
                    if dep not in service_names:
                        msg = f"service '{name}' depends_on '{dep}' which is not defined"
                        raise ValueError(msg)

            if svc.scrape_targets:
                for target in svc.scrape_targets:
                    if target not in service_names:
                        msg = f"service '{name}' scrape_target '{target}' is not defined"
                        raise ValueError(msg)

        return self

    # --- Query helpers ---

    def get_services_by_role(self, role: ServiceRole) -> dict[str, ServiceConfig]:
        """Return services matching a specific role."""
        return {k: v for k, v in self.services.items() if v.role == role}

    def get_ai_apps(self) -> dict[str, ServiceConfig]:
        """Return all ai-app services."""
        return self.get_services_by_role(ServiceRole.AI_APP)

    def get_dependency_graph(self) -> dict[str, list[str]]:
        """Return adjacency list of service dependencies."""
        return {
            name: svc.depends_on or []
            for name, svc in self.services.items()
        }

    def get_health_endpoints(self) -> dict[str, str]:
        """Return service_name → health URL mapping."""
        endpoints: dict[str, str] = {}
        for name, svc in self.services.items():
            if svc.healthcheck and svc.port:
                endpoints[name] = f"http://{name}:{svc.port}{svc.healthcheck}"
        return endpoints


# --- Loader ---

_SEARCH_PATHS = [
    "toolops.yaml",
    "config/toolops.yaml",
]


def find_topology_file(base_dir: str | Path | None = None) -> Path | None:
    """Find toolops.yaml in standard locations."""
    env_path = os.environ.get("TOOLOPS_CONFIG")
    if env_path:
        p = Path(env_path)
        return p if p.is_file() else None

    base = Path(base_dir) if base_dir else Path.cwd()
    for rel in _SEARCH_PATHS:
        candidate = base / rel
        if candidate.is_file():
            return candidate
    return None


def load_topology(path: str | Path | None = None) -> Topology:
    """Load and validate toolops.yaml.

    Args:
        path: Explicit path to toolops.yaml. If None, searches standard locations.

    Returns:
        Validated Topology model.

    Raises:
        FileNotFoundError: If no toolops.yaml found.
        ValueError: If validation fails.
    """
    if path is None:
        found = find_topology_file()
        if found is None:
            msg = "toolops.yaml not found in standard locations"
            raise FileNotFoundError(msg)
        path = found

    with open(path) as f:
        raw: dict[str, Any] = yaml.safe_load(f)

    if not isinstance(raw, dict):
        msg = f"toolops.yaml must be a YAML mapping, got {type(raw).__name__}"
        raise ValueError(msg)

    return Topology.model_validate(raw)
