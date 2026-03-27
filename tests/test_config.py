"""Tests for config loading and schema validation."""

from __future__ import annotations

import os
import textwrap
from pathlib import Path

import pytest
import yaml

from toolops.config.loader import load_config, write_config
from toolops.config.schema import ToolOpsConfig


class TestToolOpsConfig:
    """Unit tests for ToolOpsConfig Pydantic schema."""

    def test_defaults(self) -> None:
        """Config should load with safe defaults when nothing is set."""
        cfg = ToolOpsConfig()
        assert cfg.vectorstore == "chroma"
        assert cfg.cache == "memory"
        assert cfg.monitor == "null"
        assert cfg.env == "local"

    def test_normalize_vectorstore(self) -> None:
        """Backend names should be normalized to lowercase."""
        cfg = ToolOpsConfig(vectorstore="Milvus")  # type: ignore[arg-type]
        assert cfg.vectorstore == "milvus"

    def test_normalize_cache(self) -> None:
        cfg = ToolOpsConfig(cache="REDIS")  # type: ignore[arg-type]
        assert cfg.cache == "redis"

    def test_normalize_monitor(self) -> None:
        cfg = ToolOpsConfig(monitor="Phoenix")  # type: ignore[arg-type]
        assert cfg.monitor == "phoenix"

    def test_invalid_vectorstore_raises(self) -> None:
        """Invalid backend values should raise a ValidationError."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            ToolOpsConfig(vectorstore="pinecone")  # type: ignore[arg-type]

    def test_invalid_cache_raises(self) -> None:
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            ToolOpsConfig(cache="memcached")  # type: ignore[arg-type]

    def test_nested_chroma_config(self) -> None:
        """Nested backend config should be accessible."""
        cfg = ToolOpsConfig()
        assert cfg.chroma.port == 8000
        assert cfg.chroma.persist_dir == "./.chroma"

    def test_nested_redis_config(self) -> None:
        cfg = ToolOpsConfig()
        assert cfg.redis.port == 6379
        assert cfg.redis.db == 0

    def test_model_dump(self) -> None:
        """model_dump should serialize to a plain dict."""
        cfg = ToolOpsConfig()
        data = cfg.model_dump()
        assert isinstance(data, dict)
        assert "vectorstore" in data
        assert "chroma" in data


class TestConfigLoader:
    """Tests for load_config and write_config."""

    def test_load_defaults_when_no_file(self) -> None:
        """load_config with a non-existent path should return defaults."""
        cfg = load_config("/nonexistent/toolops.yaml")
        assert cfg.vectorstore == "chroma"

    def test_load_from_yaml(self, tmp_path: Path) -> None:
        """Values from toolops.yaml should be picked up."""
        yaml_file = tmp_path / "toolops.yaml"
        yaml_file.write_text(
            textwrap.dedent("""\
                vectorstore: qdrant
                cache: redis
                monitor: phoenix
                env: server
            """)
        )
        cfg = load_config(yaml_file)
        assert cfg.vectorstore == "qdrant"
        assert cfg.cache == "redis"
        assert cfg.monitor == "phoenix"
        assert cfg.env == "server"

    def test_env_var_overrides_yaml(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Environment variables should win over YAML file values."""
        yaml_file = tmp_path / "toolops.yaml"
        yaml_file.write_text("vectorstore: qdrant\n")
        monkeypatch.setenv("TOOLOPS_VECTORSTORE", "milvus")
        cfg = load_config(yaml_file)
        assert cfg.vectorstore == "milvus"

    def test_write_then_reload(self, tmp_path: Path) -> None:
        """write_config followed by load_config should round-trip correctly."""
        original = ToolOpsConfig(vectorstore="milvus", cache="redis", monitor="phoenix")  # type: ignore[arg-type]
        dest = tmp_path / "toolops.yaml"
        write_config(original, dest)

        assert dest.exists()
        reloaded = load_config(dest)
        assert reloaded.vectorstore == "milvus"
        assert reloaded.cache == "redis"
        assert reloaded.monitor == "phoenix"

    def test_written_yaml_is_valid(self, tmp_path: Path) -> None:
        """Written config file should be parseable plain YAML."""
        cfg = ToolOpsConfig()
        dest = tmp_path / "toolops.yaml"
        write_config(cfg, dest)
        with dest.open() as fh:
            data = yaml.safe_load(fh)
        assert isinstance(data, dict)

    def test_load_invalid_yaml_falls_back_to_defaults(self, tmp_path: Path) -> None:
        """A malformed YAML file should fall back to defaults without crashing."""
        yaml_file = tmp_path / "toolops.yaml"
        yaml_file.write_text(":: invalid yaml ::\n{broken")
        # Should not raise; returns defaults
        cfg = load_config(yaml_file)
        assert cfg.vectorstore == "chroma"
