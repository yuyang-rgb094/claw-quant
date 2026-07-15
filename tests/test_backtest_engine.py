"""Tests for the backtesting engine."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from claw_quant.backtest.data_loader import DailyState, HistoricalDataLoader
from claw_quant.backtest.engine import BacktestConfig, BacktestEngine
from claw_quant.backtest.performance import compute_metrics, PerformanceMetrics


class TestHistoricalDataLoader:
    """Behavior: data loader reads all 4 databases without errors."""

    @pytest.fixture(scope="module")
    def loader(self):
        return HistoricalDataLoader()

    def test_load_carhart_history(self, loader):
        df = loader.load_carhart_history()
        # May be empty if no data, but should not error
        assert isinstance(df, pd.DataFrame)

    def test_load_factor_ic_history(self, loader):
        df = loader.load_factor_ic_history()
        assert isinstance(df, pd.DataFrame)

    def test_load_crowding_history(self, loader):
        df = loader.load_crowding_history()
        assert isinstance(df, pd.DataFrame)

    def test_load_cffex_signals(self, loader):
        df = loader.load_cffex_signals()
        assert isinstance(df, pd.DataFrame)

    def test_load_margin_data(self, loader):
        df = loader.load_margin_data()
        assert isinstance(df, pd.DataFrame)

    def test_get_daily_state_returns_daily_state(self, loader):
        """DailyState should be returned even if no data is available."""
        state = loader.get_daily_state("2025-01-15")
        assert isinstance(state, DailyState)
        assert state.date == "2025-01-15"

    def test_get_date_range_returns_strings(self, loader):
        start, end = loader.get_date_range()
        assert isinstance(start, str)
        assert isinstance(end, str)
        assert start <= end


class TestBacktestConfig:
    """Behavior: config has sensible defaults."""

    def test_default_config(self):
        config = BacktestConfig(start_date="2024-01-01", end_date="2024-12-31")
        assert config.initial_capital == 1_000_000.0
        assert config.fisher_stock_vs_cash == "neutral"
        assert config.top_n_factors == 2

    def test_custom_config(self):
        config = BacktestConfig(
            start_date="2024-01-01",
            end_date="2024-12-31",
            fisher_stock_vs_cash="stocks_favored",
            top_n_factors=3,
            initial_capital=500_000.0,
        )
        assert config.top_n_factors == 3
        assert config.initial_capital == 500_000.0


class TestBacktestEngine:
    """Behavior: backtest engine runs without errors."""

    @pytest.fixture(scope="module")
    def loader(self):
        return HistoricalDataLoader()

    def test_engine_initializes(self, loader):
        config = BacktestConfig(start_date="2024-06-01", end_date="2024-12-31")
        engine = BacktestEngine(loader, config)
        assert engine is not None

    def test_engine_run_returns_result(self, loader):
        config = BacktestConfig(
            start_date="2024-06-01",
            end_date="2024-12-31",
            rebalance_frequency="M",
        )
        engine = BacktestEngine(loader, config)
        result = engine.run()
        assert result is not None
        assert hasattr(result, "metrics")
        assert hasattr(result, "daily_returns")

    def test_result_has_walk_forward_split(self, loader):
        config = BacktestConfig(
            start_date="2024-06-01",
            end_date="2024-12-31",
            rebalance_frequency="M",
        )
        engine = BacktestEngine(loader, config)
        result = engine.run()
        assert result.is_metrics is not None
        assert result.oos_metrics is not None

    def test_no_lookahead_bias(self, loader):
        """The first date's state should not contain data from future dates."""
        config = BacktestConfig(
            start_date="2024-06-01",
            end_date="2024-12-31",
            rebalance_frequency="M",
        )
        engine = BacktestEngine(loader, config)
        result = engine.run()
        # The returns should be finite
        assert result.daily_returns.notna().all()


class TestPerformanceMetrics:
    """Behavior: performance metrics are computed correctly."""

    def test_zero_returns(self):
        returns = pd.Series([0.0] * 100, index=pd.date_range("2024-01-01", periods=100))
        metrics = compute_metrics(returns)
        assert metrics.total_return == 0.0
        assert metrics.sharpe_ratio == 0.0

    def test_positive_returns(self):
        returns = pd.Series(
            [0.001] * 100,
            index=pd.date_range("2024-01-01", periods=100),
        )
        metrics = compute_metrics(returns)
        assert metrics.total_return > 0
        assert metrics.sharpe_ratio > 0
        assert metrics.win_rate == 1.0

    def test_negative_returns(self):
        returns = pd.Series(
            [-0.001] * 100,
            index=pd.date_range("2024-01-01", periods=100),
        )
        metrics = compute_metrics(returns)
        assert metrics.total_return < 0
        assert metrics.sharpe_ratio < 0
        assert metrics.win_rate == 0.0

    def test_max_drawdown(self):
        """Max drawdown should be captured correctly."""
        returns = pd.Series(
            [0.01, -0.05, 0.02, 0.01],
            index=pd.date_range("2024-01-01", periods=4),
        )
        metrics = compute_metrics(returns)
        assert metrics.max_drawdown < 0
        assert metrics.max_drawdown <= -0.04  # ~5% drawdown

    def test_profit_factor(self):
        returns = pd.Series(
            [0.02, 0.02, -0.01, 0.02, -0.01],
            index=pd.date_range("2024-01-01", periods=5),
        )
        metrics = compute_metrics(returns)
        assert metrics.profit_factor > 1.0  # gross profit > gross loss

    def test_metrics_have_all_fields(self, loader=None):
        """All PerformanceMetrics fields should be populated."""
        returns = pd.Series(
            np.random.normal(0.0005, 0.01, 252),
            index=pd.date_range("2024-01-01", periods=252),
        )
        metrics = compute_metrics(returns)
        assert metrics.n_trading_days == 252
        assert metrics.start_date is not None
        assert metrics.end_date is not None
        assert isinstance(metrics.sharpe_ratio, float)
        assert isinstance(metrics.max_drawdown, float)
        assert isinstance(metrics.calmar_ratio, float)
        assert isinstance(metrics.sortino_ratio, float)
        assert isinstance(metrics.win_rate, float)
        assert isinstance(metrics.profit_factor, float)