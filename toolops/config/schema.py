"""Pydantic Settings schema for ToolOps configuration."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class MilvusConfig(BaseSettings):
    """Milvus vector store connection settings."""

    host: str = Field(default="localhost", description="Milvus server host")
    port: int = Field(default=19530, description="Milvus server port")
    token: str = Field(default="", description="Milvus authentication token")

    model_config = SettingsConfigDict(env_prefix="MILVUS_", extra="ignore")


class QdrantConfig(BaseSettings):
    """Qdrant vector store connection settings."""

    host: str = Field(default="localhost", description="Qdrant server host")
    port: int = Field(default=6333, description="Qdrant server port")
    api_key: str = Field(default="", description="Qdrant API key")

    model_config = SettingsConfigDict(env_prefix="QDRANT_", extra="ignore")


class ChromaConfig(BaseSettings):
    """Chroma vector store connection settings."""

    host: str = Field(default="localhost", description="Chroma server host")
    port: int = Field(default=8000, description="Chroma server port")
    persist_dir: str = Field(default="./.chroma", description="Local persistence directory")

    model_config = SettingsConfigDict(env_prefix="CHROMA_", extra="ignore")


class RedisConfig(BaseSettings):
    """Redis cache connection settings."""

    host: str = Field(default="localhost", description="Redis server host")
    port: int = Field(default=6379, description="Redis server port")
    password: str = Field(default="", description="Redis password")
    db: int = Field(default=0, description="Redis database index")

    model_config = SettingsConfigDict(env_prefix="REDIS_", extra="ignore")


class PhoenixConfig(BaseSettings):
    """Arize Phoenix monitor connection settings."""

    host: str = Field(default="localhost", description="Phoenix server host")
    port: int = Field(default=6006, description="Phoenix server port")
    api_key: str = Field(default="", description="Phoenix API key")

    model_config = SettingsConfigDict(env_prefix="PHOENIX_", extra="ignore")


VectorStoreBackend = Literal["chroma", "milvus", "qdrant"]
CacheBackend = Literal["memory", "redis"]
MonitorBackend = Literal["null", "phoenix"]
Environment = Literal["local", "server", "cloud"]


class ToolOpsConfig(BaseSettings):
    """Top-level ToolOps configuration.

    Reads from environment variables and/or toolops.yaml.
    Environment variables take precedence over file values.
    """

    # ── Backend selection ─────────────────────────────────────
    vectorstore: VectorStoreBackend = Field(
        default="chroma",
        description="Active vector store backend",
    )
    cache: CacheBackend = Field(
        default="memory",
        description="Active cache backend",
    )
    monitor: MonitorBackend = Field(
        default="null",
        description="Active monitor backend",
    )
    env: Environment = Field(
        default="local",
        description="Deployment environment",
    )
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(
        default="INFO",
        description="Logging level",
    )

    # ── Backend configs ───────────────────────────────────────
    milvus: MilvusConfig = Field(default_factory=MilvusConfig)
    qdrant: QdrantConfig = Field(default_factory=QdrantConfig)
    chroma: ChromaConfig = Field(default_factory=ChromaConfig)
    redis: RedisConfig = Field(default_factory=RedisConfig)
    phoenix: PhoenixConfig = Field(default_factory=PhoenixConfig)

    model_config = SettingsConfigDict(
        env_prefix="TOOLOPS_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        nested_model_default_partial_update=True,
    )

    @field_validator("vectorstore", mode="before")
    @classmethod
    def normalize_vectorstore(cls, v: str) -> str:
        """Normalize vector store backend name to lowercase."""
        return str(v).lower()

    @field_validator("cache", mode="before")
    @classmethod
    def normalize_cache(cls, v: str) -> str:
        """Normalize cache backend name to lowercase."""
        return str(v).lower()

    @field_validator("monitor", mode="before")
    @classmethod
    def normalize_monitor(cls, v: str) -> str:
        """Normalize monitor backend name to lowercase."""
        return str(v).lower()
