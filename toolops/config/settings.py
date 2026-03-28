"""Application settings via pydantic-settings."""

from pydantic_settings import BaseSettings


class ClickHouseSettings(BaseSettings):
    """ClickHouse connection settings."""

    host: str = "localhost"
    port: int = 8123
    user: str = "default"
    password: str = ""
    database: str = "toolops"

    model_config = {"env_prefix": "CLICKHOUSE_"}


class APISettings(BaseSettings):
    """API server settings."""

    host: str = "0.0.0.0"
    port: int = 9000

    model_config = {"env_prefix": "API_"}


class Settings(BaseSettings):
    """Root settings aggregating all sub-settings."""

    clickhouse: ClickHouseSettings = ClickHouseSettings()
    api: APISettings = APISettings()
