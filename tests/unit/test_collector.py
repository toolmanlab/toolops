"""Unit tests for the collector configuration generators."""

from __future__ import annotations

import yaml

from toolops.collector.loki import generate_loki_config
from toolops.collector.otel import generate_otel_config
from toolops.collector.prometheus import generate_scrape_config


class TestPrometheusConfig:
    def test_generates_valid_yaml(self) -> None:
        targets = [{"job_name": "test-app", "host": "localhost", "port": 8080}]
        result = generate_scrape_config(targets)
        config = yaml.safe_load(result)
        assert "scrape_configs" in config
        assert config["scrape_configs"][0]["job_name"] == "test-app"

    def test_custom_metrics_path(self) -> None:
        targets = [{"job_name": "app", "host": "app", "port": 9090, "metrics_path": "/custom"}]
        result = generate_scrape_config(targets)
        config = yaml.safe_load(result)
        assert config["scrape_configs"][0]["metrics_path"] == "/custom"

    def test_multiple_targets(self) -> None:
        targets = [
            {"job_name": "app1", "host": "h1", "port": 8080},
            {"job_name": "app2", "host": "h2", "port": 9090},
        ]
        result = generate_scrape_config(targets)
        config = yaml.safe_load(result)
        assert len(config["scrape_configs"]) == 2


class TestOtelConfig:
    def test_generates_valid_yaml(self) -> None:
        result = generate_otel_config()
        config = yaml.safe_load(result)
        assert "receivers" in config
        assert "exporters" in config
        assert "service" in config

    def test_custom_endpoint(self) -> None:
        result = generate_otel_config(clickhouse_endpoint="tcp://custom:9000")
        config = yaml.safe_load(result)
        assert config["exporters"]["clickhouse"]["endpoint"] == "tcp://custom:9000"

    def test_all_pipelines_present(self) -> None:
        result = generate_otel_config()
        config = yaml.safe_load(result)
        pipelines = config["service"]["pipelines"]
        assert "traces" in pipelines
        assert "metrics" in pipelines
        assert "logs" in pipelines


class TestLokiConfig:
    def test_generates_valid_yaml(self) -> None:
        result = generate_loki_config()
        config = yaml.safe_load(result)
        assert config["auth_enabled"] is False
        assert config["server"]["http_listen_port"] == 3100

    def test_custom_retention(self) -> None:
        result = generate_loki_config(retention_period="168h")
        config = yaml.safe_load(result)
        assert config["limits_config"]["retention_period"] == "168h"
