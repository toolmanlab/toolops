"""End-to-end tests for demo app scenarios (requires full stack running)."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.e2e


class TestDemoScenarios:
    @pytest.mark.skip(reason="Requires full stack running")
    def test_normal_scenario(self) -> None:
        """Verify normal scenario produces expected telemetry."""
        pass

    @pytest.mark.skip(reason="Requires full stack running")
    def test_slow_retrieval_scenario(self) -> None:
        """Verify slow_retrieval scenario shows increased latency."""
        pass
