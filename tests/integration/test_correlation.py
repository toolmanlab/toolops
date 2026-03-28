"""Integration tests for cross-table correlation (requires Docker services)."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration


class TestCorrelation:
    @pytest.mark.skip(reason="Requires running ClickHouse")
    def test_correlate_across_tables(self) -> None:
        """Verify correlation across metrics, traces, and logs tables."""
        pass
