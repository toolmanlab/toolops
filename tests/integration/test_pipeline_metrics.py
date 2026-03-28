"""Integration tests for the metrics pipeline (requires Docker services)."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration


class TestMetricsPipeline:
    @pytest.mark.skip(reason="Requires running ClickHouse")
    def test_insert_and_query_metrics(self) -> None:
        """Verify metrics can be inserted and queried from ClickHouse."""
        # TODO: implement with real ClickHouse connection
        pass
