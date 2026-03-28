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

    # -- LLM Gateway query helpers --------------------------------------------

    _GATEWAY_TABLE = "llm_gateway"

    def insert_llm_gateway(self, records: list[dict[str, Any]]) -> None:
        """Batch-insert LLM gateway proxy records into the llm_gateway table.

        Args:
            records: List of gateway record dicts.  Each dict must contain the
                keys defined in the ``llm_gateway`` schema (all column names).
        """
        if not records:
            return
        columns = [
            "timestamp", "request_id", "method", "path", "upstream_url",
            "model", "provider",
            "input_tokens", "output_tokens", "cache_creation_tokens",
            "cache_read_tokens", "total_tokens", "cost_usd",
            "latency_ms", "ttfb_ms",
            "status_code", "request_bytes", "response_bytes",
            "is_streaming", "error_message",
            "agent_name", "session_key", "skill_name", "channel",
            "api_key_hash", "trace_id",
        ]
        data = [[r.get(c, "") for c in columns] for r in records]
        self.client.insert(self._GATEWAY_TABLE, data, column_names=columns)

    def query_gateway_overview(self) -> dict[str, Any]:
        """Aggregate gateway stats: total requests, tokens, cost, latency."""
        try:
            result = self.client.query(
                f"SELECT count() AS total_requests, "
                f"sum(input_tokens) AS total_input_tokens, "
                f"sum(output_tokens) AS total_output_tokens, "
                f"sum(total_tokens) AS total_tokens, "
                f"sum(cost_usd) AS total_cost_usd, "
                f"avg(latency_ms) AS avg_latency_ms, "
                f"avg(ttfb_ms) AS avg_ttfb_ms, "
                f"countIf(status_code >= 400) AS error_count, "
                f"countIf(is_streaming = 1) AS streaming_count "
                f"FROM {self._GATEWAY_TABLE}"
            )
            row = result.result_rows[0] if result.result_rows else (0,) * 9
            return dict(zip(result.column_names, row, strict=False))
        except Exception:
            return {
                "total_requests": 0, "total_input_tokens": 0,
                "total_output_tokens": 0, "total_tokens": 0,
                "total_cost_usd": 0.0, "avg_latency_ms": 0.0,
                "avg_ttfb_ms": 0.0, "error_count": 0, "streaming_count": 0,
            }

    def query_gateway_by_provider(self) -> list[dict[str, Any]]:
        """Aggregate gateway usage grouped by provider."""
        try:
            result = self.client.query(
                f"SELECT provider, "
                f"count() AS request_count, "
                f"sum(total_tokens) AS total_tokens, "
                f"sum(cost_usd) AS cost_usd, "
                f"avg(latency_ms) AS avg_latency_ms "
                f"FROM {self._GATEWAY_TABLE} "
                f"GROUP BY provider ORDER BY request_count DESC"
            )
            return self._rows_to_dicts(result)
        except Exception:
            return []

    def query_gateway_by_agent(self) -> list[dict[str, Any]]:
        """Aggregate gateway usage grouped by agent_name."""
        try:
            result = self.client.query(
                f"SELECT agent_name, "
                f"count() AS request_count, "
                f"sum(total_tokens) AS total_tokens, "
                f"sum(cost_usd) AS cost_usd, "
                f"avg(latency_ms) AS avg_latency_ms "
                f"FROM {self._GATEWAY_TABLE} "
                f"WHERE agent_name != '' "
                f"GROUP BY agent_name ORDER BY total_tokens DESC"
            )
            return self._rows_to_dicts(result)
        except Exception:
            return []

    def query_gateway_timeline(self, interval: str = "hour") -> list[dict[str, Any]]:
        """Aggregate gateway request volume over time.

        Args:
            interval: Bucket size — ``"hour"`` or ``"day"``.

        Returns:
            List of time-bucketed aggregation rows.
        """
        trunc_fn = "toStartOfHour" if interval == "hour" else "toStartOfDay"
        try:
            result = self.client.query(
                f"SELECT {trunc_fn}(timestamp) AS bucket, "
                f"count() AS request_count, "
                f"sum(total_tokens) AS total_tokens, "
                f"sum(cost_usd) AS cost_usd "
                f"FROM {self._GATEWAY_TABLE} "
                f"GROUP BY bucket ORDER BY bucket"
            )
            return self._rows_to_dicts(result)
        except Exception:
            return []

    # -- LLM usage query helpers ----------------------------------------------

    _LLM_TABLE = "llm_usage"

    def insert_llm_usage(self, records: list[dict[str, Any]]) -> None:
        """Batch-insert LLM usage records into the llm_usage table."""
        if not records:
            return
        columns = [
            "timestamp", "session_id", "project", "git_branch", "model",
            "input_tokens", "output_tokens", "cache_creation_tokens",
            "cache_read_tokens", "total_tokens", "service_tier", "source",
            "cc_version", "cost_usd",
        ]
        data = [[r[c] for c in columns] for r in records]
        self.client.insert(self._LLM_TABLE, data, column_names=columns)

    def query_llm_overview(self) -> dict[str, Any]:
        """Aggregate totals: tokens, sessions, top model, cost."""
        try:
            result = self.client.query(
                f"SELECT count() AS total_records, "
                f"uniq(session_id) AS total_sessions, "
                f"sum(total_tokens) AS total_tokens, "
                f"sum(input_tokens) AS total_input_tokens, "
                f"sum(output_tokens) AS total_output_tokens, "
                f"sum(cache_creation_tokens) AS total_cache_creation_tokens, "
                f"sum(cache_read_tokens) AS total_cache_read_tokens, "
                f"sum(cost_usd) AS total_cost_usd "
                f"FROM {self._LLM_TABLE}"
            )
            row = result.result_rows[0] if result.result_rows else (0,) * 8
            names = result.column_names
            stats = dict(zip(names, row, strict=False))
        except Exception:
            stats = {
                "total_records": 0, "total_sessions": 0, "total_tokens": 0,
                "total_input_tokens": 0, "total_output_tokens": 0,
                "total_cache_creation_tokens": 0, "total_cache_read_tokens": 0,
                "total_cost_usd": 0,
            }

        # Top model
        try:
            result = self.client.query(
                f"SELECT model, count() AS cnt FROM {self._LLM_TABLE} "
                f"GROUP BY model ORDER BY cnt DESC LIMIT 1"
            )
            stats["top_model"] = result.result_rows[0][0] if result.result_rows else ""
        except Exception:
            stats["top_model"] = ""

        return stats

    def query_llm_sessions(self, limit: int = 50) -> list[dict[str, Any]]:
        """Return sessions ordered by total token consumption (descending)."""
        try:
            result = self.client.query(
                f"SELECT session_id, project, git_branch, model, "
                f"sum(total_tokens) AS total_tokens, "
                f"sum(input_tokens) AS input_tokens, "
                f"sum(output_tokens) AS output_tokens, "
                f"sum(cost_usd) AS cost_usd, "
                f"count() AS message_count, "
                f"min(timestamp) AS first_seen, "
                f"max(timestamp) AS last_seen "
                f"FROM {self._LLM_TABLE} "
                f"GROUP BY session_id, project, git_branch, model "
                f"ORDER BY total_tokens DESC "
                f"LIMIT {limit}"
            )
            return self._rows_to_dicts(result)
        except Exception:
            return []

    def query_llm_session_detail(self, session_id: str) -> list[dict[str, Any]]:
        """Return individual usage records for a single session."""
        try:
            result = self.client.query(
                f"SELECT timestamp, model, input_tokens, output_tokens, "
                f"cache_creation_tokens, cache_read_tokens, total_tokens, "
                f"service_tier, cc_version "
                f"FROM {self._LLM_TABLE} "
                f"WHERE session_id = {{session_id:String}} "
                f"ORDER BY timestamp",
                parameters={"session_id": session_id},
            )
            return self._rows_to_dicts(result)
        except Exception:
            return []

    def query_llm_by_project(self, limit: int = 20) -> list[dict[str, Any]]:
        """Aggregate usage grouped by project (cwd)."""
        try:
            result = self.client.query(
                f"SELECT project, "
                f"uniq(session_id) AS total_sessions, "
                f"sum(total_tokens) AS total_tokens, "
                f"sum(input_tokens) AS input_tokens, "
                f"sum(output_tokens) AS output_tokens "
                f"FROM {self._LLM_TABLE} "
                f"GROUP BY project "
                f"ORDER BY total_tokens DESC "
                f"LIMIT {limit}"
            )
            return self._rows_to_dicts(result)
        except Exception:
            return []

    def query_llm_by_model(self) -> list[dict[str, Any]]:
        """Aggregate usage grouped by model."""
        try:
            result = self.client.query(
                f"SELECT model, "
                f"count() AS message_count, "
                f"uniq(session_id) AS session_count, "
                f"sum(total_tokens) AS total_tokens, "
                f"sum(input_tokens) AS input_tokens, "
                f"sum(output_tokens) AS output_tokens "
                f"FROM {self._LLM_TABLE} "
                f"GROUP BY model "
                f"ORDER BY total_tokens DESC"
            )
            return self._rows_to_dicts(result)
        except Exception:
            return []

    def query_llm_timeline(self, interval: str = "day") -> list[dict[str, Any]]:
        """Aggregate token usage over time bucketed by hour or day."""
        trunc_fn = "toStartOfHour" if interval == "hour" else "toStartOfDay"
        try:
            result = self.client.query(
                f"SELECT {trunc_fn}(timestamp) AS bucket, "
                f"sum(total_tokens) AS total_tokens, "
                f"sum(input_tokens) AS input_tokens, "
                f"sum(output_tokens) AS output_tokens, "
                f"sum(cache_read_tokens) AS cache_read_tokens, "
                f"count() AS message_count "
                f"FROM {self._LLM_TABLE} "
                f"GROUP BY bucket "
                f"ORDER BY bucket"
            )
            return self._rows_to_dicts(result)
        except Exception:
            return []

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
