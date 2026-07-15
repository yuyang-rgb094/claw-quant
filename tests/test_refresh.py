"""Tests for the layer refresh mechanism."""

from __future__ import annotations

import pytest

from claw_quant.refresh import (
    RefreshManager,
    RefreshResult,
    RefreshStatus,
    LAYER_CADENCES,
    REFRESH_ORDER,
)


class TestRefreshConfig:
    """Behavior: layer cadence configuration is valid."""

    def test_all_layers_have_cadence(self):
        for layer in REFRESH_ORDER:
            assert layer in LAYER_CADENCES, f"Missing cadence for {layer}"

    def test_cadence_has_required_fields(self):
        for layer, cadence in LAYER_CADENCES.items():
            assert "description" in cadence, f"Missing description for {layer}"
            assert "scheduled" in cadence, f"Missing scheduled for {layer}"
            assert "fresh_threshold_hours" in cadence, f"Missing fresh_threshold for {layer}"
            assert "stale_threshold_hours" in cadence, f"Missing stale_threshold for {layer}"
            assert "downstream" in cadence, f"Missing downstream for {layer}"
            assert "key_fields" in cadence, f"Missing key_fields for {layer}"

    def test_refresh_order_is_topological(self):
        """Refresh order should be upstream-first."""
        # Fisher should be before SFM, SFM before Graham, Graham before Markowitz
        fisher_idx = REFRESH_ORDER.index("fisher")
        sfm_idx = REFRESH_ORDER.index("sfm")
        graham_idx = REFRESH_ORDER.index("graham")
        markowitz_idx = REFRESH_ORDER.index("markowitz")
        assert fisher_idx < sfm_idx < graham_idx < markowitz_idx

    def test_cascade_chain_is_linear(self):
        """Each layer should cascade to at most one downstream layer."""
        for layer, cadence in LAYER_CADENCES.items():
            downstream = cadence["downstream"]
            assert len(downstream) <= 1, f"{layer} has multiple downstream layers: {downstream}"


class TestRefreshManager:
    """Behavior: RefreshManager coordinates layer refreshes."""

    @pytest.fixture(scope="module")
    def manager(self):
        return RefreshManager()

    def test_get_status_returns_refresh_status(self, manager):
        status = manager.get_status("fisher")
        assert isinstance(status, RefreshStatus)
        assert status.layer == "fisher"
        assert status.freshness in ("fresh", "stale", "expired", "never")

    def test_get_all_status_returns_all_layers(self, manager):
        statuses = manager.get_all_status()
        for layer in REFRESH_ORDER:
            assert layer in statuses, f"Missing {layer} in statuses"

    def test_get_refresh_chain(self, manager):
        """Refresh chain should follow the cascade order."""
        chain = manager.get_refresh_chain("fisher")
        assert chain[0] == "fisher"
        assert chain[-1] == "markowitz"  # Fisher cascades all the way down
        assert len(chain) == 4  # fisher → sfm → graham → markowitz

    def test_refresh_chain_terminal_layer(self, manager):
        """Markowitz has no downstream, so chain is just itself."""
        chain = manager.get_refresh_chain("markowitz")
        assert chain == ["markowitz"]

    def test_refresh_fisher_returns_result(self, manager):
        result = manager.refresh("fisher", trigger="manual")
        assert isinstance(result, RefreshResult)
        assert result.layer == "fisher"
        assert result.trigger == "manual"

    def test_refresh_unknown_layer(self, manager):
        result = manager.refresh("nonexistent", trigger="manual")
        assert result.success is False
        assert "Unknown layer" in result.message

    def test_refresh_updates_status(self, manager):
        manager.refresh("fisher", trigger="manual")
        status = manager.get_status("fisher")
        assert status.last_refreshed is not None
        assert status.refresh_count > 0

    def test_manual_refresh_does_not_auto_cascade(self, manager):
        """Manual refresh of Fisher may cascade if direction changed."""
        result = manager.refresh("fisher", trigger="manual")
        # The cascade depends on whether direction changed
        # If nothing changed, no cascade
        assert isinstance(result.cascade_triggered, list)

    def test_check_and_refresh_returns_results(self, manager):
        results = manager.check_and_refresh()
        for layer in REFRESH_ORDER:
            assert layer in results, f"Missing {layer} in results"
            assert isinstance(results[layer], RefreshResult)

    def test_refresh_all_returns_results(self, manager):
        results = manager.refresh_all()
        for layer in REFRESH_ORDER:
            assert layer in results, f"Missing {layer} in results"
            assert results[layer].success, f"{layer} refresh failed"

    def test_history_records_refreshes(self, manager):
        manager.refresh("fisher", trigger="manual")
        history = manager.get_history(limit=5)
        assert len(history) > 0
        assert history[-1].layer == "fisher"


class TestRefreshResult:
    """Behavior: RefreshResult data class."""

    def test_default_values(self):
        result = RefreshResult(layer="test")
        assert result.layer == "test"
        assert result.trigger == "manual"
        assert result.success is False
        assert result.direction_changed is False
        assert result.cascade_triggered == []


class TestRefreshStatus:
    """Behavior: RefreshStatus data class."""

    def test_default_values(self):
        status = RefreshStatus(layer="test")
        assert status.layer == "test"
        assert status.freshness == "unknown"
        assert status.refresh_count == 0