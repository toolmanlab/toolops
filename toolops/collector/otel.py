"""OpenTelemetry Collector configuration generator."""

from __future__ import annotations

from typing import Any

import yaml


def generate_otel_config(
    clickhouse_endpoint: str = "tcp://clickhouse:9000",
    otlp_grpc_port: int = 4317,
    otlp_http_port: int = 4318,
) -> str:
    """Generate an OTel Collector config that receives OTLP and exports to ClickHouse."""
    config: dict[str, Any] = {
        "receivers": {
            "otlp": {
                "protocols": {
                    "grpc": {"endpoint": f"0.0.0.0:{otlp_grpc_port}"},
                    "http": {"endpoint": f"0.0.0.0:{otlp_http_port}"},
                }
            }
        },
        "processors": {"batch": {"timeout": "5s", "send_batch_size": 1000}},
        "exporters": {
            "clickhouse": {
                "endpoint": clickhouse_endpoint,
                "database": "toolops",
                "logs_table_name": "logs",
                "traces_table_name": "traces",
                "metrics_table_name": "metrics",
                "ttl_days": 30,
            }
        },
        "service": {
            "pipelines": {
                "traces": {
                    "receivers": ["otlp"],
                    "processors": ["batch"],
                    "exporters": ["clickhouse"],
                },
                "metrics": {
                    "receivers": ["otlp"],
                    "processors": ["batch"],
                    "exporters": ["clickhouse"],
                },
                "logs": {
                    "receivers": ["otlp"],
                    "processors": ["batch"],
                    "exporters": ["clickhouse"],
                },
            }
        },
    }
    return yaml.dump(config, default_flow_style=False)
