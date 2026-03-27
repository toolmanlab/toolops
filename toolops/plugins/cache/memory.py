"""In-memory cache plugin — zero-dependency, suitable for testing and dev."""

from __future__ import annotations

import logging
import threading
import time

from toolops.plugins.cache.base import CachePlugin

logger = logging.getLogger(__name__)


class MemoryCache(CachePlugin):
    """Thread-safe in-process dictionary cache with TTL support.

    Data is lost on process restart.  Use for local dev and unit tests.
    """

    def __init__(self) -> None:
        self._store: dict[str, tuple[str, float | None]] = {}  # key -> (value, expires_at)
        self._lock = threading.Lock()

    # ── Internal helpers ──────────────────────────────────────

    def _is_expired(self, expires_at: float | None) -> bool:
        return expires_at is not None and time.monotonic() > expires_at

    def _evict_expired(self) -> None:
        """Remove expired entries (called lazily on every access)."""
        now = time.monotonic()
        expired = [k for k, (_, exp) in self._store.items() if exp is not None and now > exp]
        for k in expired:
            del self._store[k]

    # ── CachePlugin interface ─────────────────────────────────

    def get(self, key: str) -> str | None:
        """Return value for key, or None if missing / expired."""
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            value, expires_at = entry
            if self._is_expired(expires_at):
                del self._store[key]
                return None
            return value

    def set(self, key: str, value: str, ttl: int | None = None) -> bool:
        """Store value with optional TTL (seconds)."""
        expires_at = time.monotonic() + ttl if ttl is not None else None
        with self._lock:
            self._store[key] = (value, expires_at)
        return True

    def delete(self, key: str) -> bool:
        """Remove key from cache."""
        with self._lock:
            existed = key in self._store
            self._store.pop(key, None)
        return existed

    def exists(self, key: str) -> bool:
        """Return True if key exists and has not expired."""
        return self.get(key) is not None

    def clear(self) -> bool:
        """Flush all entries."""
        with self._lock:
            self._store.clear()
        return True

    def __len__(self) -> int:
        """Return number of non-expired keys."""
        with self._lock:
            self._evict_expired()
            return len(self._store)
