"""Abstract base class for cache plugins."""

from __future__ import annotations

from abc import ABC, abstractmethod


class CachePlugin(ABC):
    """Unified key-value cache interface.

    Implement this ABC to add a new cache backend.
    Keys and values are strings; serialization is the caller's responsibility.
    """

    @abstractmethod
    def get(self, key: str) -> str | None:
        """Retrieve a cached value.

        Args:
            key: Cache key.

        Returns:
            Cached string value, or None if key does not exist / is expired.
        """

    @abstractmethod
    def set(self, key: str, value: str, ttl: int | None = None) -> bool:
        """Store a value in the cache.

        Args:
            key:   Cache key.
            value: String value to store.
            ttl:   Time-to-live in seconds.  None means no expiry.

        Returns:
            True on success, False on failure.
        """

    @abstractmethod
    def delete(self, key: str) -> bool:
        """Remove a key from the cache.

        Args:
            key: Cache key to remove.

        Returns:
            True if key existed and was removed, False otherwise.
        """

    @abstractmethod
    def exists(self, key: str) -> bool:
        """Check whether a key exists in the cache.

        Args:
            key: Cache key to check.

        Returns:
            True if key exists and has not expired.
        """

    def clear(self) -> bool:
        """Flush all keys from the cache.

        Returns:
            True on success.  Default implementation raises NotImplementedError.
        """
        raise NotImplementedError
