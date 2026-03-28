"""Unit tests for the ClickHouse client wrapper."""

from __future__ import annotations

from unittest.mock import MagicMock

from toolops.config.settings import ClickHouseSettings
from toolops.storage.clickhouse import ClickHouseClient


class TestClickHouseClient:
    def _make_client(self) -> tuple[ClickHouseClient, MagicMock]:
        settings = ClickHouseSettings()
        client = ClickHouseClient(settings)
        mock_driver = MagicMock()
        mock_driver.query.return_value = MagicMock(
            column_names=["timestamp", "service", "metric_name", "metric_value", "labels"],
            result_rows=[],
        )
        client._client = mock_driver
        return client, mock_driver

    def test_query_metrics_no_filter(self) -> None:
        client, mock = self._make_client()
        result = client.query_metrics()
        assert result == []
        call_args = mock.query.call_args
        sql = call_args[0][0]
        assert "FROM otel_metrics_sum" in sql
        assert "WHERE" not in sql

    def test_query_metrics_with_service_filter(self) -> None:
        client, mock = self._make_client()
        client.query_metrics(service="demo-app")
        call_args = mock.query.call_args
        sql = call_args[0][0]
        assert "WHERE" in sql
        assert "service" in sql

    def test_query_traces_with_trace_id(self) -> None:
        client, mock = self._make_client()
        mock.query.return_value = MagicMock(
            column_names=[
                "trace_id",
                "span_id",
                "parent_span_id",
                "service",
                "operation",
                "start_time",
                "duration_ms",
                "status_code",
                "attributes",
            ],
            result_rows=[],
        )
        result = client.query_traces(trace_id="abc123")
        assert result == []
        sql = mock.query.call_args[0][0]
        assert "trace_id" in sql

    def test_query_logs_with_level(self) -> None:
        client, mock = self._make_client()
        mock.query.return_value = MagicMock(
            column_names=["timestamp", "service", "level", "message", "trace_id", "attributes"],
            result_rows=[],
        )
        client.query_logs(level="ERROR")
        sql = mock.query.call_args[0][0]
        assert "level" in sql

    def test_correlate_empty(self) -> None:
        client, mock = self._make_client()
        mock.query.return_value = MagicMock(
            column_names=[
                "trace_id",
                "span_id",
                "parent_span_id",
                "service",
                "operation",
                "start_time",
                "duration_ms",
                "status_code",
                "attributes",
            ],
            result_rows=[],
        )
        result = client.correlate("nonexistent")
        assert result["trace_id"] == "nonexistent"
        assert result["traces"] == []
        assert result["logs"] == []

    def test_close(self) -> None:
        client, mock = self._make_client()
        client.close()
        mock.close.assert_called_once()
        assert client._client is None
