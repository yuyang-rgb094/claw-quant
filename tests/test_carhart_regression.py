"""Tests for carhart_regression.py — SFM Layer Module 1a: Carhart Baseline.

Tests the core computational functions through their public interfaces,
using the module's own synthetic data generator for reproducibility.

ADR-014 defines the SFM Layer; this script implements Module 1a
(Carhart four-factor rolling regression for manifold shape estimation).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from carhart_regression import (
    DEFAULT_UNIVERSE,
    FactorResult,
    RegressionResult,
    compute_factor_premia,
    compute_vif,
    construct_hml_factor,
    construct_mkt_factor,
    construct_mom_factor,
    construct_smb_factor,
    generate_synthetic_data,
    run_carhart_regression,
)


@pytest.fixture(scope="module")
def synthetic_data():
    """Generate synthetic data once for all tests in this module."""
    return generate_synthetic_data(DEFAULT_UNIVERSE, n_years=5, seed=42)


@pytest.fixture(scope="module")
def factor_data(synthetic_data):
    """Build all four Carhart factors from synthetic data."""
    stock_returns, market_caps, book_to_market, market_returns, risk_free_rate = synthetic_data

    mkt = construct_mkt_factor(market_returns, risk_free_rate)
    smb = construct_smb_factor(stock_returns, market_caps)
    hml = construct_hml_factor(stock_returns, book_to_market)
    mom = construct_mom_factor(stock_returns)

    # Align all factors to common dates
    factor_df = pd.concat([mkt, smb, hml, mom], axis=1).dropna()
    return factor_df


@pytest.fixture(scope="module")
def portfolio_returns(synthetic_data, factor_data):
    """Build a simple equal-weight portfolio from synthetic stock returns."""
    stock_returns = synthetic_data[0]
    risk_free_rate = synthetic_data[4]

    # Equal-weight portfolio
    portfolio_ret = stock_returns.mean(axis=1)
    excess_returns = portfolio_ret - risk_free_rate
    excess_returns.name = "portfolio_excess"

    # Align with factor data
    common_idx = excess_returns.index.intersection(factor_data.index)
    return excess_returns.loc[common_idx]


# ─── generate_synthetic_data ────────────────────────────────────────

class TestGenerateSyntheticData:
    """Behavior: generates all required data components with factor structure."""

    def test_returns_five_elements(self, synthetic_data):
        assert len(synthetic_data) == 5

    def test_stock_returns_shape(self, synthetic_data):
        sr = synthetic_data[0]
        assert isinstance(sr, pd.DataFrame)
        assert sr.shape[1] == len(DEFAULT_UNIVERSE)

    def test_market_returns_not_constant(self, synthetic_data):
        mr = synthetic_data[3]
        assert mr.std() > 0


# ─── construct_mkt_factor ───────────────────────────────────────────

class TestConstructMktFactor:
    """Behavior: MKT = market return - risk-free rate (Sharpe 1964 CAPM)."""

    def test_returns_series(self, factor_data):
        assert isinstance(factor_data["MKT"], pd.Series)

    def test_mkt_not_all_zero(self, factor_data):
        assert factor_data["MKT"].abs().sum() > 0


# ─── Factor Construction ─────────────────────────────────────────────

class TestFactorConstruction:
    """Behavior: all four Carhart factors are constructed and aligned."""

    def test_all_four_factors_present(self, factor_data):
        assert set(factor_data.columns) == {"MKT", "SMB", "HML", "MOM"}

    def test_no_all_nan_columns(self, factor_data):
        for col in factor_data.columns:
            assert factor_data[col].notna().sum() > 0, f"{col} is all NaN"


# ─── run_carhart_regression ─────────────────────────────────────────

class TestRunCarhartRegression:
    """Behavior: OLS regression produces betas, alpha, R² for the window."""

    @pytest.fixture(scope="class")
    def regression_result(self, portfolio_returns, factor_data):
        start = portfolio_returns.index[120]  # skip warmup
        end = portfolio_returns.index[-1]
        return run_carhart_regression(
            portfolio_returns,
            factor_data,
            start.strftime("%Y-%m-%d"),
            end.strftime("%Y-%m-%d"),
        )

    def test_returns_regression_result(self, regression_result):
        assert isinstance(regression_result, RegressionResult)

    def test_has_all_factors(self, regression_result):
        assert set(regression_result.factors.keys()) == {"MKT", "SMB", "HML", "MOM"}

    def test_mkt_beta_significant(self, regression_result):
        """MKT should be significant — synthetic data has strong market factor."""
        assert regression_result.factors["MKT"].significant

    def test_r_squared_positive(self, regression_result):
        assert regression_result.r_squared > 0

    def test_n_observations_sufficient(self, regression_result):
        assert regression_result.n_observations >= 100

    def test_vif_reasonable(self, regression_result):
        """VIF should be low (<10) — factors are designed to be orthogonal."""
        for name, vif in regression_result.vif.items():
            assert vif < 10, f"{name} VIF={vif:.1f} — multicollinearity"

    def test_information_ratio_finite(self, regression_result):
        assert np.isfinite(regression_result.information_ratio)


# ─── Insufficient data handling ──────────────────────────────────────

class TestInsufficientData:
    """Behavior: regression with insufficient data returns empty result."""

    def test_short_window_returns_empty(self, portfolio_returns, factor_data):
        """A 2-day window should be insufficient (< 10 observations)."""
        start = portfolio_returns.index[0]
        end = portfolio_returns.index[1]
        result = run_carhart_regression(
            portfolio_returns, factor_data,
            start.strftime("%Y-%m-%d"),
            end.strftime("%Y-%m-%d"),
        )
        assert result.n_observations < 10
        assert len(result.factors) == 0
