"""Abstract base class for monitor / tracing plugins."""

from __future__ import annotations

from abc import ABC, abstractmethod


class MonitorPlugin(ABC):
    """Unified observability interface for AI pipeline tracing and metrics.

    Implement this ABC to add a new monitoring backend.
    """

    @abstractmethod
    def trace(
        self,
        name: str,
        inputs: dict[str, object],
        outputs: dict[str, object],
        metadata: dict[str, object] | None = None,
    ) -> str:
        """Record a single LLM / pipeline invocation trace.

        Args:
            name:     Human-readable span name (e.g. "chat_completion").
            inputs:   Input data dict (e.g. {"prompt": "..."}).
            outputs:  Output data dict (e.g. {"response": "..."}).
            metadata: Optional extra tags (model, latency, cost, …).

        Returns:
            Unique trace / span ID string.
        """

    @abstractmethod
    def log_metric(
        self,
        name: str,
        value: float,
        tags: dict[str, str] | None = None,
    ) -> bool:
        """Emit a numeric metric data point.

        Args:
            name:  Metric name (e.g. "token_count", "latency_ms").
            value: Numeric value.
            tags:  Optional key-value label pairs.

        Returns:
            True if the metric was accepted by the backend.
        """

    def flush(self) -> None:
        """Flush any buffered telemetry to the backend.

        Override if the backend batches writes internally.
        """
