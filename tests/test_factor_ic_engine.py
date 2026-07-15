"""Tests for factor_ic_engine.py — SFM Layer Module 1b: Factor Duration Spectrum.

Tests the core computational functions through their public interfaces,
using the module's own synthetic data generator for reproducibility.

ADR-014 defines the SFM Layer; this script implements Module 1b
(IC + half-life estimation for factor duration classification).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from factor_ic_engine import (
    HalfLifeResult,
    compute_forward_returns,
    compute_ic_series,
    estimate_half_life,
    summarize_ic,
)
from claw_quant.synthetic import generate_synthetic_prices, compute_factor_values
from claw_quant.config import DURATION_BUCKETS, FORWARD_PERIODS


@pytest.fixture(scope="module")
def synthetic_prices():
    """Generate synthetic prices once for all tests in this module."""
    return generate_synthetic_prices(n_stocks=100, n_days=504, seed=42)


@pytest.fixture(scope="module")
def factor_values(synthetic_prices):
    return compute_factor_values(synthetic_prices)


@pytest.fixture(scope="module")
def forward_returns(synthetic_prices):
    return compute_forward_returns(synthetic_prices)


@pytest.fixture(scope="module")
def ic_df(factor_values, forward_returns):
    return compute_ic_series(
        factor_values["12m_momentum"],
        forward_returns,
    )


# ─── compute_factor_values ──────────────────────────────────────────

class TestComputeFactorValues:
    """Behavior: computes all 10 built-in factors across 3 duration buckets."""

    def test_returns_all_factors(self, factor_values):
        expected = set(DURATION_BUCKETS["short_term"] +
                        DURATION_BUCKETS["medium_term"] +
                        DURATION_BUCKETS["long_term"])
        assert set(factor_values.keys()) == expected

    def test_factor_dataframes_aligned(self, factor_values, synthetic_prices):
        for name, df in factor_values.items():
            assert df.shape == synthetic_prices.shape, f"{name} shape mismatch"

    def test_factor_values_not_all_nan(self, factor_values):
        for name, df in factor_values.items():
            valid_ratio = df.notna().sum().sum() / df.size
            assert valid_ratio > 0.3, f"{name} has too many NaNs ({valid_ratio:.1%})"


# ─── compute_forward_returns ────────────────────────────────────────

class TestComputeForwardReturns:
    """Behavior: computes forward returns for all 6 horizons."""

    def test_returns_all_periods(self, forward_returns):
        assert set(forward_returns.keys()) == set(FORWARD_PERIODS)

    def test_forward_return_shape(self, forward_returns, synthetic_prices):
        for h, df in forward_returns.items():
            assert df.shape == synthetic_prices.shape


# ─── compute_ic_series ──────────────────────────────────────────────

class TestComputeICSeries:
    """Behavior: computes rolling Spearman IC for each forward horizon."""

    def test_returns_dataframe(self, ic_df):
        assert isinstance(ic_df, pd.DataFrame)

    def test_has_ic_columns(self, ic_df):
        expected_cols = {f"ic_{h}" for h in FORWARD_PERIODS}
        assert set(ic_df.columns) == expected_cols

    def test_ic_values_bounded(self, ic_df):
        """IC (Spearman correlation) must be in [-1, 1]."""
        for col in ic_df.columns:
            valid = ic_df[col].dropna()
            if len(valid) > 0:
                assert valid.between(-1, 1).all(), f"{col} has out-of-range IC"


# ─── estimate_half_life ──────────────────────────────────────────────

class TestEstimateHalfLife:
    """Behavior: fits exponential decay and returns half-life estimate."""

    def test_returns_half_life_result(self, ic_df):
        result = estimate_half_life(ic_df, "12m_momentum")
        assert isinstance(result, HalfLifeResult)

    def test_half_life_positive(self, ic_df):
        result = estimate_half_life(ic_df, "12m_momentum")
        assert result.half_life_days >= 0

    def test_decay_status_valid(self, ic_df):
        result = estimate_half_life(ic_df, "12m_momentum")
        assert result.decay_status in ("stable", "accelerating", "reversing")

    def test_r_squared_bounded(self, ic_df):
        result = estimate_half_life(ic_df, "12m_momentum")
        assert 0 <= result.r_squared <= 1


# ─── summarize_ic ───────────────────────────────────────────────────

class TestSummarizeIC:
    """Behavior: summarizes IC series into per-horizon statistics."""

    def test_returns_icresults(self, ic_df):
        results = summarize_ic(ic_df, "12m_momentum")
        assert len(results) == len(FORWARD_PERIODS)

    def test_ic_mean_bounded(self, ic_df):
        results = summarize_ic(ic_df, "12m_momentum")
        for r in results:
            assert -1 <= r.ic_mean <= 1

    def test_hit_rate_bounded(self, ic_df):
        results = summarize_ic(ic_df, "12m_momentum")
        for r in results:
            assert 0 <= r.hit_rate <= 1
