"""Tests for plugin ABCs and concrete implementations."""

from __future__ import annotations

import time

import pytest

from toolops.plugins.cache.base import CachePlugin
from toolops.plugins.cache.memory import MemoryCache
from toolops.plugins.monitor.base import MonitorPlugin
from toolops.plugins.monitor.null import NullMonitor
from toolops.plugins.vectorstore.base import VectorStorePlugin


# ── ABC contract checks ───────────────────────────────────────

class TestABCContracts:
    """Verify that ABCs cannot be instantiated directly."""

    def test_vectorstore_is_abstract(self) -> None:
        with pytest.raises(TypeError):
            VectorStorePlugin()  # type: ignore[abstract]

    def test_cache_is_abstract(self) -> None:
        with pytest.raises(TypeError):
            CachePlugin()  # type: ignore[abstract]

    def test_monitor_is_abstract(self) -> None:
        with pytest.raises(TypeError):
            MonitorPlugin()  # type: ignore[abstract]


# ── MemoryCache ───────────────────────────────────────────────

class TestMemoryCache:
    """Full interface coverage for MemoryCache."""

    @pytest.fixture()
    def cache(self) -> MemoryCache:
        return MemoryCache()

    def test_set_and_get(self, cache: MemoryCache) -> None:
        assert cache.set("k", "v") is True
        assert cache.get("k") == "v"

    def test_get_missing_key(self, cache: MemoryCache) -> None:
        assert cache.get("nonexistent") is None

    def test_exists_true(self, cache: MemoryCache) -> None:
        cache.set("x", "1")
        assert cache.exists("x") is True

    def test_exists_false(self, cache: MemoryCache) -> None:
        assert cache.exists("nope") is False

    def test_delete_existing(self, cache: MemoryCache) -> None:
        cache.set("del_me", "bye")
        assert cache.delete("del_me") is True
        assert cache.get("del_me") is None

    def test_delete_missing(self, cache: MemoryCache) -> None:
        assert cache.delete("ghost") is False

    def test_ttl_expiry(self, cache: MemoryCache) -> None:
        cache.set("ttl_key", "value", ttl=1)
        assert cache.get("ttl_key") == "value"
        time.sleep(1.1)
        assert cache.get("ttl_key") is None

    def test_no_ttl_persists(self, cache: MemoryCache) -> None:
        cache.set("perm", "forever")
        time.sleep(0.05)
        assert cache.get("perm") == "forever"

    def test_overwrite(self, cache: MemoryCache) -> None:
        cache.set("k", "old")
        cache.set("k", "new")
        assert cache.get("k") == "new"

    def test_clear(self, cache: MemoryCache) -> None:
        cache.set("a", "1")
        cache.set("b", "2")
        assert cache.clear() is True
        assert len(cache) == 0

    def test_len(self, cache: MemoryCache) -> None:
        assert len(cache) == 0
        cache.set("x", "1")
        cache.set("y", "2")
        assert len(cache) == 2

    def test_thread_safety(self, cache: MemoryCache) -> None:
        """Concurrent writes should not cause data races."""
        import threading

        errors: list[Exception] = []

        def writer(n: int) -> None:
            try:
                for i in range(50):
                    cache.set(f"key-{n}-{i}", str(i))
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=writer, args=(t,)) for t in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors


# ── NullMonitor ───────────────────────────────────────────────

class TestNullMonitor:
    """NullMonitor should satisfy the MonitorPlugin interface without side effects."""

    @pytest.fixture()
    def monitor(self) -> NullMonitor:
        return NullMonitor()

    def test_trace_returns_string(self, monitor: NullMonitor) -> None:
        trace_id = monitor.trace("test_span", {"prompt": "hello"}, {"response": "hi"})
        assert isinstance(trace_id, str)
        assert len(trace_id) > 0

    def test_trace_ids_are_unique(self, monitor: NullMonitor) -> None:
        ids = {monitor.trace("span", {}, {}) for _ in range(20)}
        assert len(ids) == 20

    def test_log_metric_returns_true(self, monitor: NullMonitor) -> None:
        assert monitor.log_metric("latency_ms", 42.5) is True

    def test_log_metric_with_tags(self, monitor: NullMonitor) -> None:
        result = monitor.log_metric("tokens", 1024, tags={"model": "gpt-4o"})
        assert result is True

    def test_flush_no_exception(self, monitor: NullMonitor) -> None:
        monitor.flush()  # base-class default; should not raise

    def test_is_monitor_plugin_subclass(self, monitor: NullMonitor) -> None:
        assert isinstance(monitor, MonitorPlugin)
