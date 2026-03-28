"""Unit tests for the FastAPI API layer."""

from __future__ import annotations

from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from toolops.api.app import create_app
from toolops.api.deps import get_clickhouse


def _mock_ch() -> MagicMock:
    mock = MagicMock()
    mock.query_metrics.return_value = []
    mock.query_traces.return_value = []
    mock.query_logs.return_value = []
    mock.correlate.return_value = {"trace_id": "test", "traces": [], "logs": [], "metrics": []}
    return mock


class TestHealthEndpoint:
    def test_health(self) -> None:
        app = create_app()
        client = TestClient(app)
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"


class TestMetricsRoutes:
    def test_list_metrics(self) -> None:
        app = create_app()
        mock = _mock_ch()
        app.dependency_overrides[get_clickhouse] = lambda: mock
        client = TestClient(app)
        resp = client.get("/api/metrics/")
        assert resp.status_code == 200
        assert resp.json() == []


class TestTracesRoutes:
    def test_list_traces(self) -> None:
        app = create_app()
        mock = _mock_ch()
        app.dependency_overrides[get_clickhouse] = lambda: mock
        client = TestClient(app)
        resp = client.get("/api/traces/")
        assert resp.status_code == 200


class TestLogsRoutes:
    def test_list_logs(self) -> None:
        app = create_app()
        mock = _mock_ch()
        app.dependency_overrides[get_clickhouse] = lambda: mock
        client = TestClient(app)
        resp = client.get("/api/logs/")
        assert resp.status_code == 200


class TestCorrelateRoutes:
    def test_correlate(self) -> None:
        app = create_app()
        mock = _mock_ch()
        app.dependency_overrides[get_clickhouse] = lambda: mock
        client = TestClient(app)
        resp = client.get("/api/correlate/test-trace-id")
        assert resp.status_code == 200
        assert resp.json()["trace_id"] == "test"
