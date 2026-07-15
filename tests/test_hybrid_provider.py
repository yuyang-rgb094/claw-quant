"""Test HybridDataProvider — Wind → AKShare → Synthetic fallback chain.

Tests cover:
- Provider initialization and availability detection
- Factory registration (hybrid, wind_first aliases)
- Fallback chain: synthetic (always works, no Wind/AKShare in CI)
- Source tracking via source_stats
- Availability report
- Backward compatibility: synthetic/akshare/wind still work
"""

from __future__ import annotations

import pandas as pd
import pytest

from claw_quant.data_factory import get_data_provider, list_providers
from claw_quant.data_provider import DataProvider


class TestHybridProviderRegistration:
    """Test that hybrid provider is properly registered in the factory."""

    def test_hybrid_in_list_providers(self):
        """hybrid and wind_first should be listed."""
        providers = list_providers()
        assert "hybrid" in providers
        assert "wind_first" in providers

    def test_hybrid_returns_hybrid_provider(self):
        """get_data_provider('hybrid') returns a HybridDataProvider."""
        dp = get_data_provider("hybrid")
        assert dp.name == "hybrid"
        assert dp.is_synthetic is False

    def test_wind_first_is_alias(self):
        """wind_first should return the same type as hybrid."""
        dp = get_data_provider("wind_first")
        # Both should return the same name
        assert dp.name == "hybrid"

    def test_wind_first_aliases(self):
        """wind_first and hybrid are interchangeable."""
        dp1 = get_data_provider("hybrid")
        dp2 = get_data_provider("wind_first")
        assert type(dp1) is type(dp2)


class TestHybridProviderAvailability:
    """Test availability detection."""

    def test_availability_report_returns_expected_keys(self):
        """Report should have all required keys."""
        dp = get_data_provider("hybrid")
        report = dp.get_availability_report()
        assert "wind_available" in report
        assert "akshare_available" in report
        assert "synthetic_available" in report
        assert "source_stats" in report
        assert "summary" in report
        assert "recommendation" in report

    def test_synthetic_is_always_available(self):
        """Synthetic should always be true."""
        dp = get_data_provider("hybrid")
        report = dp.get_availability_report()
        assert report["synthetic_available"] is True

    def test_reset_availability(self):
        """reset_availability should clear cached checks."""
        dp = get_data_provider("hybrid")
        # First call caches
        dp.get_availability_report()
        # Reset
        dp.reset_availability()
        # Should not raise
        report2 = dp.get_availability_report()
        assert report2["synthetic_available"] is True


class TestHybridProviderFallback:
    """Test the Wind → AKShare → Synthetic fallback chain.

    In CI (no Wind CLI, no AKShare), all methods should fall back to synthetic.
    """

    @pytest.fixture
    def dp(self):
        return get_data_provider("hybrid")

    def test_get_stock_prices_fallback(self, dp):
        """Should return data even without Wind/AKShare."""
        result = dp.get_stock_prices(
            ["600519.SH", "000858.SZ"], "2024-01-01", "2024-06-30"
        )
        assert isinstance(result, pd.DataFrame)
        assert not result.empty
        assert "600519.SH" in result.columns
        assert "000858.SZ" in result.columns
        # Source should be tracked
        assert "get_stock_prices" in dp.source_stats

    def test_get_index_prices_fallback(self, dp):
        """Should return data even without Wind/AKShare."""
        result = dp.get_index_prices("000300.SH", "2024-01-01", "2024-06-30")
        assert isinstance(result, pd.Series)
        assert not result.empty
        assert "get_index_prices" in dp.source_stats

    def test_get_risk_free_rate_fallback(self, dp):
        """Should return data even without Wind/AKShare."""
        result = dp.get_risk_free_rate("2024-01-01", "2024-06-30")
        assert isinstance(result, pd.Series)
        assert not result.empty
        assert "get_risk_free_rate" in dp.source_stats

    def test_get_market_caps_fallback(self, dp):
        """Should return data even without Wind/AKShare."""
        result = dp.get_market_caps(
            ["600519.SH", "000858.SZ"], "2024-01-01", "2024-06-30"
        )
        assert isinstance(result, pd.DataFrame)
        assert not result.empty
        assert "get_market_caps" in dp.source_stats

    def test_get_book_to_market_fallback(self, dp):
        """Should return data even without Wind/AKShare."""
        result = dp.get_book_to_market(
            ["600519.SH", "000858.SZ"], "2024-01-01", "2024-06-30"
        )
        assert isinstance(result, pd.DataFrame)
        assert not result.empty
        assert "get_book_to_market" in dp.source_stats

    def test_get_margin_data_fallback(self, dp):
        """Should return data even without Wind/AKShare."""
        result = dp.get_margin_data("2024-01-01", "2024-06-30")
        assert isinstance(result, pd.DataFrame)
        assert not result.empty
        assert "get_margin_data" in dp.source_stats

    def test_all_methods_track_sources(self, dp):
        """After calling all methods, source_stats should be populated."""
        dp.get_stock_prices(["600519.SH"], "2024-01-01", "2024-01-31")
        dp.get_index_prices("000300.SH", "2024-01-01", "2024-01-31")
        dp.get_risk_free_rate("2024-01-01", "2024-01-31")
        dp.get_market_caps(["600519.SH"], "2024-01-01", "2024-01-31")
        dp.get_book_to_market(["600519.SH"], "2024-01-01", "2024-01-31")
        dp.get_margin_data("2024-01-01", "2024-01-31")

        assert len(dp.source_stats) >= 6
        # In CI, all should be "synthetic" since Wind/AKShare are unavailable
        report = dp.get_availability_report()
        assert report["synthetic_available"] is True


class TestHybridNorthboundFlow:
    """Test northbound flow methods."""

    @pytest.fixture
    def dp(self):
        return get_data_provider("hybrid")

    def test_get_northbound_flow_returns_dataframe(self, dp):
        """Should return a DataFrame (may be empty if no data source)."""
        result = dp.get_northbound_flow("2024-01-01", "2024-06-30")
        assert isinstance(result, pd.DataFrame)

    def test_get_northbound_summary_returns_dict(self, dp):
        """Should return a dict with expected keys."""
        result = dp.get_northbound_summary()
        assert isinstance(result, dict)
        assert "latest_net_flow" in result
        assert "flow_5d" in result
        assert "flow_20d" in result
        assert "trend" in result


class TestHybridMacroIndicator:
    """Test macro indicator methods."""

    @pytest.fixture
    def dp(self):
        return get_data_provider("hybrid")

    def test_get_macro_indicator_no_wind(self, dp):
        """Without Wind, should return None gracefully."""
        result = dp.get_macro_indicator("中国CPI同比", "2024-01-01", "2024-06-30")
        # Without Wind, this should be None (no fallback to synthetic for macro)
        assert result is None or isinstance(result, pd.Series)

    def test_get_index_indicators_no_wind(self, dp):
        """Without Wind, should return empty dict."""
        result = dp.get_index_indicators("000300.SH")
        assert isinstance(result, dict)


class TestBackwardCompatibility:
    """Test that existing providers still work."""

    def test_synthetic_provider_unchanged(self):
        dp = get_data_provider("synthetic")
        assert dp.name == "synthetic"
        assert dp.is_synthetic is True
        prices = dp.get_stock_prices(["600519.SH"], "2024-01-01", "2024-01-31")
        assert not prices.empty

    def test_akshare_provider_unchanged(self):
        """AKShare may fail if not installed, but should not crash."""
        try:
            dp = get_data_provider("akshare")
            assert dp.name == "akshare"
            assert dp.is_synthetic is False
        except ImportError:
            pytest.skip("AKShare not installed")

    def test_wind_provider_unchanged(self):
        """Wind should initialize without crash even if CLI is missing."""
        dp = get_data_provider("wind")
        assert dp.name == "wind"
        assert dp.is_synthetic is False


class TestHybridProviderInterface:
    """Test that HybridDataProvider satisfies the DataProvider interface."""

    def test_is_instance_of_data_provider(self):
        dp = get_data_provider("hybrid")
        assert isinstance(dp, DataProvider)

    def test_has_name_property(self):
        dp = get_data_provider("hybrid")
        assert hasattr(dp, "name")
        assert isinstance(dp.name, str)

    def test_has_is_synthetic_property(self):
        dp = get_data_provider("hybrid")
        assert hasattr(dp, "is_synthetic")
        assert isinstance(dp.is_synthetic, bool)

    def test_has_all_required_methods(self):
        dp = get_data_provider("hybrid")
        required = [
            "get_stock_prices",
            "get_index_prices",
            "get_risk_free_rate",
            "get_market_caps",
            "get_book_to_market",
            "get_margin_data",
        ]
        for method in required:
            assert hasattr(dp, method), f"Missing method: {method}"
            assert callable(getattr(dp, method)), f"Not callable: {method}"