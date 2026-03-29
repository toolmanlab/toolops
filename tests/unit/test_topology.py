"""Unit tests for toolops.yaml topology parser."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from toolops.config.topology import (
    ServiceRole,
    Topology,
    find_topology_file,
    load_topology,
)

MINIMAL_YAML = {
    "version": "1",
    "app": {"name": "test-app"},
    "services": {
        "api": {"role": "api-gateway", "port": 8000},
    },
}


FULL_YAML = {
    "version": "1",
    "app": {"name": "test-app", "description": "Test application"},
    "services": {
        "api": {
            "role": "api-gateway",
            "port": 8000,
            "healthcheck": "/health",
            "metrics": {"path": "/metrics", "format": "prometheus"},
            "depends_on": ["db", "cache"],
        },
        "worker": {
            "role": "ai-app",
            "port": 8080,
            "ai": {
                "pipeline": "rag",
                "stages": ["embedding", "search", "generate"],
                "model": "gpt-4o",
            },
            "depends_on": ["api"],
        },
        "db": {
            "role": "metadata-store",
            "port": 5432,
            "storage": {"engine": "postgresql", "tables": ["docs", "chunks"]},
        },
        "cache": {
            "role": "cache",
            "port": 6379,
        },
        "prom": {
            "role": "metrics-scraper",
            "port": 9090,
            "scrape_targets": ["api", "worker"],
        },
    },
}


class TestTopologyValidation:
    def test_minimal(self) -> None:
        t = Topology.model_validate(MINIMAL_YAML)
        assert t.app.name == "test-app"
        assert len(t.services) == 1
        assert t.services["api"].role == ServiceRole.API_GATEWAY

    def test_full(self) -> None:
        t = Topology.model_validate(FULL_YAML)
        assert len(t.services) == 5
        assert t.services["worker"].ai is not None
        assert t.services["worker"].ai.pipeline == "rag"
        assert t.services["worker"].ai.stages == ["embedding", "search", "generate"]
        assert t.services["db"].storage is not None
        assert t.services["db"].storage.engine == "postgresql"

    def test_invalid_version(self) -> None:
        data = {**MINIMAL_YAML, "version": "2"}
        with pytest.raises(Exception, match="unsupported"):
            Topology.model_validate(data)

    def test_invalid_depends_on_reference(self) -> None:
        data = {
            "version": "1",
            "app": {"name": "test"},
            "services": {
                "api": {"role": "api-gateway", "depends_on": ["nonexistent"]},
            },
        }
        with pytest.raises(Exception, match="nonexistent"):
            Topology.model_validate(data)

    def test_invalid_scrape_target_reference(self) -> None:
        data = {
            "version": "1",
            "app": {"name": "test"},
            "services": {
                "prom": {"role": "metrics-scraper", "scrape_targets": ["ghost"]},
            },
        }
        with pytest.raises(Exception, match="ghost"):
            Topology.model_validate(data)

    def test_port_and_ports_exclusive(self) -> None:
        data = {
            "version": "1",
            "app": {"name": "test"},
            "services": {
                "otel": {"role": "collector", "port": 4317, "ports": {"grpc": 4317}},
            },
        }
        with pytest.raises(Exception, match="mutually exclusive"):
            Topology.model_validate(data)

    def test_ai_only_for_ai_app(self) -> None:
        data = {
            "version": "1",
            "app": {"name": "test"},
            "services": {
                "api": {
                    "role": "api-gateway",
                    "ai": {"pipeline": "rag"},
                },
            },
        }
        with pytest.raises(Exception, match="ai-app"):
            Topology.model_validate(data)

    def test_invalid_metrics_format(self) -> None:
        data = {
            "version": "1",
            "app": {"name": "test"},
            "services": {
                "api": {
                    "role": "api-gateway",
                    "metrics": {"path": "/metrics", "format": "graphite"},
                },
            },
        }
        with pytest.raises(Exception, match="format"):
            Topology.model_validate(data)

    def test_named_ports(self) -> None:
        data = {
            "version": "1",
            "app": {"name": "test"},
            "services": {
                "otel": {
                    "role": "collector",
                    "ports": {"grpc": 4317, "http": 4318},
                },
            },
        }
        t = Topology.model_validate(data)
        assert t.services["otel"].ports == {"grpc": 4317, "http": 4318}

    def test_custom_role(self) -> None:
        data = {
            "version": "1",
            "app": {"name": "test"},
            "services": {
                "sidecar": {"role": "custom", "labels": {"team": "infra"}},
            },
        }
        t = Topology.model_validate(data)
        assert t.services["sidecar"].role == ServiceRole.CUSTOM
        assert t.services["sidecar"].labels == {"team": "infra"}


class TestTopologyHelpers:
    def test_get_services_by_role(self) -> None:
        t = Topology.model_validate(FULL_YAML)
        caches = t.get_services_by_role(ServiceRole.CACHE)
        assert "cache" in caches
        assert len(caches) == 1

    def test_get_ai_apps(self) -> None:
        t = Topology.model_validate(FULL_YAML)
        ai = t.get_ai_apps()
        assert "worker" in ai
        assert len(ai) == 1

    def test_get_dependency_graph(self) -> None:
        t = Topology.model_validate(FULL_YAML)
        graph = t.get_dependency_graph()
        assert set(graph["api"]) == {"db", "cache"}
        assert graph["worker"] == ["api"]
        assert graph["db"] == []

    def test_get_health_endpoints(self) -> None:
        t = Topology.model_validate(FULL_YAML)
        endpoints = t.get_health_endpoints()
        assert endpoints["api"] == "http://api:8000/health"
        assert "cache" not in endpoints  # no healthcheck defined


class TestTopologyLoader:
    def test_load_from_explicit_path(self, tmp_path: Path) -> None:
        f = tmp_path / "toolops.yaml"
        f.write_text(yaml.dump(MINIMAL_YAML))
        t = load_topology(f)
        assert t.app.name == "test-app"

    def test_load_file_not_found(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("TOOLOPS_CONFIG", raising=False)
        with pytest.raises(FileNotFoundError):
            load_topology()

    def test_find_in_project_root(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        f = tmp_path / "toolops.yaml"
        f.write_text(yaml.dump(MINIMAL_YAML))
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("TOOLOPS_CONFIG", raising=False)
        found = find_topology_file()
        assert found is not None
        assert found.name == "toolops.yaml"

    def test_find_in_config_dir(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        f = config_dir / "toolops.yaml"
        f.write_text(yaml.dump(MINIMAL_YAML))
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("TOOLOPS_CONFIG", raising=False)
        found = find_topology_file()
        assert found is not None
        assert str(found).endswith("config/toolops.yaml")

    def test_env_override(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        f = tmp_path / "custom.yaml"
        f.write_text(yaml.dump(MINIMAL_YAML))
        monkeypatch.setenv("TOOLOPS_CONFIG", str(f))
        found = find_topology_file()
        assert found is not None
        assert found.name == "custom.yaml"
