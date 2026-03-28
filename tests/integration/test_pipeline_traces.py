"""Integration tests for the traces pipeline (requires Docker services)."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration


class TestTracesPipeline:
    @pytest.mark.skip(reason="Requires running ClickHouse")
    def test_insert_and_query_traces(self) -> None:
        """Verify traces can be inserted and queried from ClickHouse."""
        pass
