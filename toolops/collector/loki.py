"""Loki configuration generator."""

from __future__ import annotations

from typing import Any

import yaml


def generate_loki_config(
    storage_path: str = "/loki/data",
    retention_period: str = "720h",
) -> str:
    """Generate a basic Loki local config."""
    config: dict[str, Any] = {
        "auth_enabled": False,
        "server": {"http_listen_port": 3100},
        "common": {
            "path_prefix": storage_path,
            "storage": {
                "filesystem": {
                    "chunks_directory": f"{storage_path}/chunks",
                    "rules_directory": f"{storage_path}/rules",
                }
            },
            "replication_factor": 1,
            "ring": {"instance_addr": "127.0.0.1", "kvstore": {"store": "inmemory"}},
        },
        "schema_config": {
            "configs": [
                {
                    "from": "2024-01-01",
                    "store": "tsdb",
                    "object_store": "filesystem",
                    "schema": "v13",
                    "index": {"prefix": "index_", "period": "24h"},
                }
            ]
        },
        "limits_config": {"retention_period": retention_period},
    }
    return yaml.dump(config, default_flow_style=False)
