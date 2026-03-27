"""Null monitor plugin — silently discards all telemetry.

Use this when monitoring is disabled (TOOLOPS_MONITOR=null).
"""

from __future__ import annotations

import uuid

from toolops.plugins.monitor.base import MonitorPlugin


class NullMonitor(MonitorPlugin):
    """No-op monitor that satisfies the MonitorPlugin interface without side effects.

    Useful as a safe default and in unit tests that should not emit real traces.
    """

    def trace(
        self,
        name: str,
        inputs: dict[str, object],
        outputs: dict[str, object],
        metadata: dict[str, object] | None = None,
    ) -> str:
        """Discard trace and return a synthetic trace ID."""
        return f"null-{uuid.uuid4()}"

    def log_metric(
        self,
        name: str,
        value: float,
        tags: dict[str, str] | None = None,
    ) -> bool:
        """Discard metric silently."""
        return True

    def flush(self) -> None:
        """No-op flush."""
