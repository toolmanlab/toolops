"""Redis cache plugin — production-grade distributed cache adapter."""

from __future__ import annotations

import logging
from typing import Any

from toolops.plugins.cache.base import CachePlugin

logger = logging.getLogger(__name__)


class RedisCache(CachePlugin):
    """Redis adapter using the official redis-py client.

    Suitable for multi-process / multi-node deployments.

    Args:
        host:     Redis server host.
        port:     Redis server port (default 6379).
        password: Redis AUTH password (empty string for no-auth).
        db:       Redis database index (0–15).
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 6379,
        password: str = "",
        db: int = 0,
    ) -> None:
        self.host = host
        self.port = port
        self.password = password
        self.db = db
        self._client: Any = None

    # ── Lifecycle ─────────────────────────────────────────────

    def connect(self) -> bool:
        """Establish Redis connection and verify with PING."""
        try:
            import redis  # type: ignore[import-untyped]

            kwargs: dict[str, Any] = {
                "host": self.host,
                "port": self.port,
                "db": self.db,
                "decode_responses": True,
            }
            if self.password:
                kwargs["password"] = self.password
            self._client = redis.Redis(**kwargs)
            self._client.ping()
            logger.info("RedisCache connected to %s:%d db=%d", self.host, self.port, self.db)
            return True
        except ImportError:
            logger.error("redis not installed. Run: pip install toolops[redis]")
            return False
        except Exception as exc:
            logger.error("RedisCache connect failed: %s", exc)
            return False

    def disconnect(self) -> None:
        """Close Redis connection pool."""
        if self._client is not None:
            try:
                self._client.close()
            except Exception:
                pass
            self._client = None

    # ── CachePlugin interface ─────────────────────────────────

    def get(self, key: str) -> str | None:
        """Return value for key, or None if missing."""
        try:
            result: str | None = self._client.get(key)
            return result
        except Exception as exc:
            logger.error("Redis GET '%s' failed: %s", key, exc)
            return None

    def set(self, key: str, value: str, ttl: int | None = None) -> bool:
        """Store value with optional TTL (seconds)."""
        try:
            self._client.set(key, value, ex=ttl)
            return True
        except Exception as exc:
            logger.error("Redis SET '%s' failed: %s", key, exc)
            return False

    def delete(self, key: str) -> bool:
        """Remove key from Redis."""
        try:
            count: int = self._client.delete(key)
            return count > 0
        except Exception as exc:
            logger.error("Redis DEL '%s' failed: %s", key, exc)
            return False

    def exists(self, key: str) -> bool:
        """Return True if key exists in Redis."""
        try:
            return bool(self._client.exists(key))
        except Exception as exc:
            logger.error("Redis EXISTS '%s' failed: %s", key, exc)
            return False

    def clear(self) -> bool:
        """Flush the entire Redis database (FLUSHDB)."""
        try:
            self._client.flushdb()
            return True
        except Exception as exc:
            logger.error("Redis FLUSHDB failed: %s", exc)
            return False
