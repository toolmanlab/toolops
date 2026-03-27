"""Configuration loader — merges toolops.yaml with environment variables."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]

from toolops.config.schema import ToolOpsConfig

logger = logging.getLogger(__name__)

_CONFIG_FILE_NAMES = ("toolops.yaml", "toolops.yml")

# Top-level ToolOpsConfig fields that map to a simple scalar in toolops.yaml
_TOP_LEVEL_SCALAR_FIELDS = ("vectorstore", "cache", "monitor", "env", "log_level")
_NESTED_SECTION_FIELDS = ("milvus", "qdrant", "chroma", "redis", "phoenix")


def _find_config_file(search_dir: Path | None = None) -> Path | None:
    """Walk up the directory tree looking for a toolops config file."""
    start = search_dir or Path.cwd()
    current = start.resolve()
    for _ in range(10):  # max 10 levels up
        for name in _CONFIG_FILE_NAMES:
            candidate = current / name
            if candidate.is_file():
                return candidate
        parent = current.parent
        if parent == current:
            break
        current = parent
    return None


def _load_yaml(path: Path) -> dict[str, Any]:
    """Load and parse a YAML config file."""
    try:
        with path.open("r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
        logger.debug("Loaded config from %s", path)
        return data
    except yaml.YAMLError as exc:
        logger.warning("Failed to parse %s: %s", path, exc)
        return {}


def load_config(config_path: str | Path | None = None) -> ToolOpsConfig:
    """Load ToolOpsConfig from YAML file + environment variables.

    Resolution order (later wins):
    1. Pydantic field defaults
    2. toolops.yaml values (auto-discovered or explicit path)
    3. Environment variables / .env file

    Args:
        config_path: Explicit path to toolops.yaml.  Auto-discovered when None.

    Returns:
        Fully resolved ToolOpsConfig instance.
    """
    path: Path | None
    if config_path is not None:
        path = Path(config_path)
        if not path.is_file():
            logger.warning("Config file not found: %s — using defaults", path)
            path = None
    else:
        path = _find_config_file()

    yaml_data: dict[str, Any] = _load_yaml(path) if path else {}
    config = _merge_yaml_under_env(yaml_data)
    logger.debug("Active config: %s", config.model_dump())
    return config


def _merge_yaml_under_env(yaml_data: dict[str, Any]) -> ToolOpsConfig:
    """Build a ToolOpsConfig honouring correct priority order.

    Priority (highest wins):
      3. Environment variables / .env file
      2. toolops.yaml values
      1. Pydantic field defaults

    Strategy: only promote yaml values for fields whose env var is absent,
    then let Pydantic Settings fill the rest from env / defaults.
    """
    prefix = "TOOLOPS_"
    merged: dict[str, Any] = {}

    for field in _TOP_LEVEL_SCALAR_FIELDS:
        env_key = f"{prefix}{field.upper()}"
        if env_key not in os.environ and field in yaml_data:
            merged[field] = yaml_data[field]

    # Nested sections use their own env prefixes (MILVUS_, REDIS_, …);
    # passing yaml dict here is safe because nested BaseSettings still
    # reads their own env vars with higher priority.
    for section in _NESTED_SECTION_FIELDS:
        if section in yaml_data and isinstance(yaml_data[section], dict):
            merged[section] = yaml_data[section]

    return ToolOpsConfig.model_validate(merged)  # type: ignore[no-any-return]


def write_config(config: ToolOpsConfig, dest: Path | None = None) -> Path:
    """Serialize a ToolOpsConfig back to toolops.yaml.

    Args:
        config: The config instance to persist.
        dest:   Target file path.  Defaults to ./toolops.yaml.

    Returns:
        The path that was written.
    """
    target = dest or (Path.cwd() / "toolops.yaml")
    data = config.model_dump(exclude_none=True)
    with target.open("w", encoding="utf-8") as fh:
        yaml.safe_dump(data, fh, default_flow_style=False, sort_keys=False)
    logger.info("Config written to %s", target)
    return target
