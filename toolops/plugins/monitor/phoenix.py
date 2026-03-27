"""Arize Phoenix monitor plugin — LLM observability adapter."""

from __future__ import annotations

import logging
import time
import uuid
from typing import Any

from toolops.plugins.monitor.base import MonitorPlugin

logger = logging.getLogger(__name__)


class PhoenixMonitor(MonitorPlugin):
    """Arize Phoenix adapter for LLM tracing and evaluation.

    Sends OpenTelemetry spans to a Phoenix server for visualization.

    Args:
        host:    Phoenix server host.
        port:    Phoenix server port (default 6006).
        api_key: Phoenix Cloud API key (optional for self-hosted).
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 6006,
        api_key: str = "",
    ) -> None:
        self.host = host
        self.port = port
        self.api_key = api_key
        self._tracer: Any = None
        self._meter: Any = None

    def _endpoint(self) -> str:
        return f"http://{self.host}:{self.port}/v1/traces"

    # ── Lifecycle ─────────────────────────────────────────────

    def setup(self) -> bool:
        """Configure OpenTelemetry to export to Phoenix.

        Returns:
            True if setup succeeded, False otherwise.
        """
        try:
            from opentelemetry import trace  # type: ignore[import-untyped]
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import (  # type: ignore[import-untyped]
                OTLPSpanExporter,
            )
            from opentelemetry.sdk.resources import Resource  # type: ignore[import-untyped]
            from opentelemetry.sdk.trace import TracerProvider  # type: ignore[import-untyped]
            from opentelemetry.sdk.trace.export import SimpleSpanProcessor  # type: ignore[import-untyped]

            resource = Resource(attributes={"service.name": "toolops"})
            provider = TracerProvider(resource=resource)
            exporter = OTLPSpanExporter(endpoint=self._endpoint())
            provider.add_span_processor(SimpleSpanProcessor(exporter))
            trace.set_tracer_provider(provider)
            self._tracer = trace.get_tracer("toolops.phoenix")
            logger.info("PhoenixMonitor connected to %s", self._endpoint())
            return True
        except ImportError:
            logger.error(
                "Phoenix deps not installed. Run: pip install toolops[phoenix]"
            )
            return False
        except Exception as exc:
            logger.error("PhoenixMonitor setup failed: %s", exc)
            return False

    # ── MonitorPlugin interface ───────────────────────────────

    def trace(
        self,
        name: str,
        inputs: dict[str, object],
        outputs: dict[str, object],
        metadata: dict[str, object] | None = None,
    ) -> str:
        """Record a trace span in Phoenix."""
        trace_id = str(uuid.uuid4())
        if self._tracer is None:
            logger.warning("PhoenixMonitor not set up — call setup() first")
            return trace_id

        try:
            with self._tracer.start_as_current_span(name) as span:
                span.set_attribute("toolops.trace_id", trace_id)
                span.set_attribute("input.value", str(inputs))
                span.set_attribute("output.value", str(outputs))
                if metadata:
                    for k, v in metadata.items():
                        span.set_attribute(f"metadata.{k}", str(v))
        except Exception as exc:
            logger.error("Phoenix trace failed: %s", exc)

        return trace_id

    def log_metric(
        self,
        name: str,
        value: float,
        tags: dict[str, str] | None = None,
    ) -> bool:
        """Log a metric as a span event (Phoenix v1 metrics API).

        Phoenix does not yet have a native metrics push endpoint; we encode
        metrics as zero-duration spans so they appear in the trace timeline.
        """
        if self._tracer is None:
            return False
        try:
            with self._tracer.start_as_current_span(f"metric.{name}") as span:
                span.set_attribute("metric.name", name)
                span.set_attribute("metric.value", value)
                span.set_attribute("metric.timestamp", time.time())
                if tags:
                    for k, v in tags.items():
                        span.set_attribute(f"tag.{k}", v)
            return True
        except Exception as exc:
            logger.error("Phoenix log_metric failed: %s", exc)
            return False
