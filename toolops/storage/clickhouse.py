"""ClickHouse client wrapper and query helpers for OTel-exported tables."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import clickhouse_connect
from clickhouse_connect.driver.client import Client

from toolops.config.settings import ClickHouseSettings

# OTel Collector auto-created table names
_TRACES_TABLE = "traces"
_LOGS_TABLE = "logs"
_METRICS_GAUGE = "otel_metrics_gauge"
_METRICS_HISTOGRAM = "otel_metrics_histogram"
_METRICS_SUM = "otel_metrics_sum"


class ClickHouseClient:
    """Thin wrapper around clickhouse-connect providing typed query methods."""

    def __init__(self, settings: ClickHouseSettings | None = None) -> None:
        self._settings = settings or ClickHouseSettings()
        self._client: Client | None = None

    @property
    def client(self) -> Client:
        """Lazy-initialize the underlying driver client."""
        if self._client is None:
            self._client = clickhouse_connect.get_client(
                host=self._settings.host,
                port=self._settings.port,
                username=self._settings.user,
                password=self._settings.password,
                database=self._settings.database,
            )
        return self._client

    def close(self) -> None:
        """Close the underlying connection."""
        if self._client is not None:
            self._client.close()
            self._client = None

    # -- helpers --------------------------------------------------------------

    def _rows_to_dicts(self, result: Any) -> list[dict[str, Any]]:
        """Convert query result to list of dicts."""
        return [dict(zip(result.column_names, row, strict=False)) for row in result.result_rows]

    # -- Query helpers --------------------------------------------------------

    def query_traces(
        self,
        service: str | None = None,
        trace_id: str | None = None,
        start: datetime | None = None,
        end: datetime | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Query traces table with optional filters.

        Returns spans with Duration converted from nanoseconds to milliseconds.
        """
        conditions: list[str] = []
        params: dict[str, Any] = {}
        if service:
            conditions.append("ServiceName = {service:String}")
            params["service"] = service
        if trace_id:
            conditions.append("TraceId = {trace_id:String}")
            params["trace_id"] = trace_id
        if start:
            conditions.append("Timestamp >= {start:DateTime64(9)}")
            params["start"] = start
        if end:
            conditions.append("Timestamp <= {end:DateTime64(9)}")
            params["end"] = end

        where = f" WHERE {' AND '.join(conditions)}" if conditions else ""
        sql = (
            f"SELECT Timestamp, TraceId, SpanId, ParentSpanId, SpanName, SpanKind, "
            f"ServiceName, ResourceAttributes, SpanAttributes, "
            f"Duration / 1000000 AS DurationMs, StatusCode, StatusMessage "
            f"FROM {_TRACES_TABLE}{where} ORDER BY Timestamp DESC LIMIT {limit}"
        )
        result = self.client.query(sql, parameters=params)
        return self._rows_to_dicts(result)

    def query_metrics(
        self,
        service: str | None = None,
        metric_name: str | None = None,
        start: datetime | None = None,
        end: datetime | None = None,
        limit: int = 1000,
    ) -> list[dict[str, Any]]:
        """Query metrics from gauge/sum/histogram tables with optional filters."""
        conditions: list[str] = []
        params: dict[str, Any] = {}
        if service:
            conditions.append("ServiceName = {service:String}")
            params["service"] = service
        if metric_name:
            conditions.append("MetricName = {metric_name:String}")
            params["metric_name"] = metric_name
        if start:
            conditions.append("TimeUnix >= {start:DateTime64(9)}")
            params["start"] = start
        if end:
            conditions.append("TimeUnix <= {end:DateTime64(9)}")
            params["end"] = end

        where = f" WHERE {' AND '.join(conditions)}" if conditions else ""

        # Query gauge and sum tables (both have Value column)
        results: list[dict[str, Any]] = []
        for table in (_METRICS_GAUGE, _METRICS_SUM):
            sql = (
                f"SELECT ServiceName, MetricName, MetricDescription, "
                f"Attributes, TimeUnix, Value "
                f"FROM {table}{where} ORDER BY TimeUnix DESC LIMIT {limit}"
            )
            try:
                result = self.client.query(sql, parameters=params)
                results.extend(self._rows_to_dicts(result))
            except Exception:
                # Table may not exist yet
                pass

        # Sort combined results by time descending, trim to limit
        results.sort(key=lambda r: r.get("TimeUnix", ""), reverse=True)
        return results[:limit]

    def query_metrics_histogram(
        self,
        service: str | None = None,
        metric_name: str | None = None,
        start: datetime | None = None,
        end: datetime | None = None,
        limit: int = 1000,
    ) -> list[dict[str, Any]]:
        """Query histogram metrics (for latency percentiles etc.)."""
        conditions: list[str] = []
        params: dict[str, Any] = {}
        if service:
            conditions.append("ServiceName = {service:String}")
            params["service"] = service
        if metric_name:
            conditions.append("MetricName = {metric_name:String}")
            params["metric_name"] = metric_name
        if start:
            conditions.append("TimeUnix >= {start:DateTime64(9)}")
            params["start"] = start
        if end:
            conditions.append("TimeUnix <= {end:DateTime64(9)}")
            params["end"] = end

        where = f" WHERE {' AND '.join(conditions)}" if conditions else ""
        sql = (
            f"SELECT * FROM {_METRICS_HISTOGRAM}{where} "
            f"ORDER BY TimeUnix DESC LIMIT {limit}"
        )
        try:
            result = self.client.query(sql, parameters=params)
            return self._rows_to_dicts(result)
        except Exception:
            return []

    def query_logs(
        self,
        service: str | None = None,
        level: str | None = None,
        trace_id: str | None = None,
        search: str | None = None,
        start: datetime | None = None,
        end: datetime | None = None,
        limit: int = 1000,
    ) -> list[dict[str, Any]]:
        """Query logs table with optional filters."""
        conditions: list[str] = []
        params: dict[str, Any] = {}
        if service:
            conditions.append("ServiceName = {service:String}")
            params["service"] = service
        if level:
            conditions.append("SeverityText = {level:String}")
            params["level"] = level
        if trace_id:
            conditions.append("TraceId = {trace_id:String}")
            params["trace_id"] = trace_id
        if search:
            conditions.append("Body LIKE {search:String}")
            params["search"] = f"%{search}%"
        if start:
            conditions.append("Timestamp >= {start:DateTime64(9)}")
            params["start"] = start
        if end:
            conditions.append("Timestamp <= {end:DateTime64(9)}")
            params["end"] = end

        where = f" WHERE {' AND '.join(conditions)}" if conditions else ""
        sql = (
            f"SELECT Timestamp, TraceId, SpanId, SeverityText, SeverityNumber, "
            f"ServiceName, Body, ResourceAttributes, LogAttributes "
            f"FROM {_LOGS_TABLE}{where} ORDER BY Timestamp DESC LIMIT {limit}"
        )
        result = self.client.query(sql, parameters=params)
        return self._rows_to_dicts(result)

    def correlate(
        self,
        trace_id: str,
    ) -> dict[str, Any]:
        """Correlate metrics, traces, and logs by trace_id."""
        traces = self.query_traces(trace_id=trace_id, limit=100)
        logs = self.query_logs(trace_id=trace_id, limit=100)
        # Find time range from traces to query related metrics
        services = {t["ServiceName"] for t in traces}
        metrics: list[dict[str, Any]] = []
        if traces:
            start = min(t["Timestamp"] for t in traces)
            end = max(t["Timestamp"] for t in traces)
            for svc in services:
                metrics.extend(self.query_metrics(service=svc, start=start, end=end))
        return {"trace_id": trace_id, "traces": traces, "logs": logs, "metrics": metrics}

    def query_overview(self) -> dict[str, Any]:
        """Get overview stats: total requests, avg latency, error rate, cache hit rate."""
        stats: dict[str, Any] = {}

        # Total requests & avg latency (last 1 hour)
        try:
            result = self.client.query(
                f"SELECT count() AS total, avg(Duration / 1000000) AS avg_latency_ms "
                f"FROM {_TRACES_TABLE} WHERE Timestamp >= now() - INTERVAL 1 HOUR "
                f"AND ParentSpanId = ''"
            )
            row = result.result_rows[0] if result.result_rows else (0, 0)
            stats["total_requests"] = row[0]
            stats["avg_latency_ms"] = round(row[1], 2) if row[1] else 0
        except Exception:
            stats["total_requests"] = 0
            stats["avg_latency_ms"] = 0

        # Error rate
        try:
            result = self.client.query(
                f"SELECT countIf(StatusCode = 'STATUS_CODE_ERROR') / count() * 100 "
                f"FROM {_TRACES_TABLE} WHERE Timestamp >= now() - INTERVAL 1 HOUR "
                f"AND ParentSpanId = ''"
            )
            row = result.result_rows[0] if result.result_rows else (0,)
            stats["error_rate"] = round(row[0], 2) if row[0] else 0
        except Exception:
            stats["error_rate"] = 0

        # Cache hit rate from span attributes
        try:
            result = self.client.query(
                f"SELECT countIf(SpanAttributes['cache.hit'] = 'true') / "
                f"countIf(SpanAttributes['cache.hit'] != '') * 100 "
                f"FROM {_TRACES_TABLE} WHERE Timestamp >= now() - INTERVAL 1 HOUR"
            )
            row = result.result_rows[0] if result.result_rows else (0,)
            stats["cache_hit_rate"] = round(row[0], 2) if row[0] and row[0] == row[0] else 0
        except Exception:
            stats["cache_hit_rate"] = 0

        return stats
