"""Prometheus scrape configuration generator."""

from __future__ import annotations

from typing import Any

import yaml


def generate_scrape_config(
    targets: list[dict[str, Any]],
    scrape_interval: str = "15s",
) -> str:
    """Generate a prometheus.yml scrape config from target definitions.

    Each target dict should have: job_name, host, port, metrics_path (optional).
    """
    scrape_configs: list[dict[str, Any]] = []
    for target in targets:
        job: dict[str, Any] = {
            "job_name": target["job_name"],
            "scrape_interval": scrape_interval,
            "static_configs": [{"targets": [f"{target['host']}:{target['port']}"]}],
        }
        if "metrics_path" in target:
            job["metrics_path"] = target["metrics_path"]
        scrape_configs.append(job)

    config = {"global": {"scrape_interval": scrape_interval}, "scrape_configs": scrape_configs}
    return yaml.dump(config, default_flow_style=False)
