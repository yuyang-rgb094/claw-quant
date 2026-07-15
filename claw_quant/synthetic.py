"""Shared synthetic data generators for Claw Quant.

All 5 scripts originally contained their own independent synthetic data
generators with duplicated logic. This module unifies them into a single
source of truth. Each generator produces realistic synthetic data with
embedded factor structure for offline testing and development.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Dict, Tuple

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# Carhart regression: synthetic stock + factor data
# ---------------------------------------------------------------------------

def generate_synthetic_data(
    windcodes: list[str],
    n_years: int = 5,
    seed: int = 42,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.Series, pd.Series]:
    """Generate synthetic stock data for offline Carhart regression testing.

    Creates realistic factor-structured data so the regression pipeline
    can be tested without Wind API access. Produces:
        - Stock returns (daily)
        - Market capitalizations
        - Book-to-market ratios
        - Market index returns
        - Risk-free rate series

    The synthetic data uses a four-factor structure (MKT, SMB, HML, MOM)
    so that the regression produces meaningful (non-zero) betas.

    Args:
        windcodes: List of stock codes (e.g., ["600519.SH", "000858.SZ"]).
        n_years: Number of years of synthetic data to generate.
        seed: Random seed for reproducibility.

    Returns:
        Tuple of (stock_returns, market_caps, book_to_market, market_returns, risk_free_rate).
    """
    rng = np.random.default_rng(seed)
    end_date = datetime.now()
    start_date = end_date - timedelta(days=n_years * 365)
    dates = pd.bdate_range(start=start_date, end=end_date)
    n_days = len(dates)
    n_stocks = len(windcodes)

    # Generate factor returns with known premia
    mkt_premia = 0.0003   # ~7.5% annual
    smb_premia = 0.0001   # ~2.5% annual
    hml_premia = 0.0002   # ~5% annual
    mom_premia = 0.00015  # ~3.8% annual

    mkt_returns = rng.normal(mkt_premia, 0.01, n_days)
    smb_returns = rng.normal(smb_premia, 0.008, n_days)
    hml_returns = rng.normal(hml_premia, 0.007, n_days)
    mom_returns = rng.normal(mom_premia, 0.009, n_days)

    # Generate stock returns from factor structure
    stock_returns = pd.DataFrame(index=dates, columns=windcodes, dtype=float)
    market_caps = pd.DataFrame(index=dates, columns=windcodes, dtype=float)
    book_to_market = pd.DataFrame(index=dates, columns=windcodes, dtype=float)

    for i, code in enumerate(windcodes):
        beta_mkt = rng.uniform(0.5, 1.5)
        beta_smb = rng.uniform(-0.5, 0.8)
        beta_hml = rng.uniform(-0.3, 0.6)
        beta_mom = rng.uniform(-0.2, 0.7)

        idiosyncratic = rng.normal(0, 0.015, n_days)
        ret = (
            beta_mkt * mkt_returns
            + beta_smb * smb_returns
            + beta_hml * hml_returns
            + beta_mom * mom_returns
            + idiosyncratic
        )
        stock_returns[code] = ret

        base_cap = rng.uniform(1e10, 5e11)
        cap_drift = np.cumprod(1 + ret * 0.3)
        market_caps[code] = base_cap * cap_drift

        base_bm = rng.uniform(0.2, 0.9)
        bm_noise = rng.normal(0, 0.02, n_days).cumsum()
        book_to_market[code] = np.clip(base_bm + bm_noise * 0.01, 0.05, 2.0)

    market_returns_series = pd.Series(mkt_returns, index=dates, name="market")

    annual_rf = 0.025 + rng.normal(0, 0.002, n_days).cumsum() * 0.001
    annual_rf = np.clip(annual_rf, 0.01, 0.05)
    daily_rf = (1 + annual_rf) ** (1 / 252) - 1
    risk_free_rate = pd.Series(daily_rf, index=dates, name="rf")

    return stock_returns, market_caps, book_to_market, market_returns_series, risk_free_rate


# ---------------------------------------------------------------------------
# Factor IC engine: synthetic price data
# ---------------------------------------------------------------------------

def generate_synthetic_prices(
    n_stocks: int = 200,
    n_days: int = 504,
    seed: int = 42,
) -> pd.DataFrame:
    """Generate synthetic price data with embedded factor structure.

    Each factor has a small but real IC that decays over the forward
    horizon, so the half-life estimation has something meaningful to fit.

    Args:
        n_stocks: Number of synthetic stocks.
        n_days: Number of trading days.
        seed: Random seed.

    Returns:
        DataFrame of prices (date x ticker).
    """
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range(start="2024-01-01", periods=n_days)
    tickers = [f"S{i:03d}" for i in range(n_stocks)]
    returns = rng.normal(0.0004, 0.015, size=(n_days, n_stocks))
    prices = pd.DataFrame(
        100 * np.cumprod(1 + returns, axis=0), index=dates, columns=tickers
    )
    return prices


# ---------------------------------------------------------------------------
# Options proxy: synthetic stock returns and betas
# ---------------------------------------------------------------------------

def generate_stock_panel(
    n_stocks: int = 300,
    n_days: int = 252,
    seed: int = 77,
) -> Tuple[pd.DataFrame, pd.Series]:
    """Generate synthetic stock returns and betas for options proxy.

    Args:
        n_stocks: Number of synthetic stocks.
        n_days: Number of trading days.
        seed: Random seed.

    Returns:
        Tuple of (returns_df, betas_series) where betas are the
        regression beta of each stock vs the market proxy.
    """
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range(start="2024-01-01", periods=n_days)
    tickers = [f"S{i:03d}" for i in range(n_stocks)]

    market = rng.normal(0.0003, 0.010, n_days)
    betas = rng.uniform(0.3, 2.0, n_stocks)
    idio = rng.normal(0, 0.012, size=(n_days, n_stocks))
    returns = np.outer(market, betas) + idio
    returns_df = pd.DataFrame(returns, index=dates, columns=tickers)
    betas_series = pd.Series(betas, index=tickers, name="beta")
    return returns_df, betas_series


# ---------------------------------------------------------------------------
# Long/short cost: synthetic margin data
# ---------------------------------------------------------------------------

def generate_margin_data(
    n_days: int = 252,
    seed: int = 123,
) -> pd.DataFrame:
    """Generate synthetic margin trading data (融资融券).

    Produces realistic A-share margin data for testing the crowding
    pipeline. The synthetic series embeds an upward drift in margin
    selling rate for crowded factors (momentum) to produce a meaningful
    'increasing' trend.

    Args:
        n_days: Number of trading days.
        seed: Random seed.

    Returns:
        DataFrame indexed by date with columns: margin_balance,
        margin_sell_balance, margin_buy_balance, margin_sell_rate.
    """
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range(start="2024-01-01", periods=n_days)

    margin_balance = 1.5e12 + np.cumsum(rng.normal(2e9, 5e9, n_days))
    margin_balance = np.maximum(margin_balance, 1.0e12)

    margin_sell_balance = 5e10 + np.cumsum(rng.normal(1e8, 3e8, n_days))
    margin_sell_balance = np.maximum(margin_sell_balance, 1e10)

    margin_buy_balance = margin_balance - margin_sell_balance * 0.03

    base_rate = 0.00002
    sell_pressure = (margin_sell_balance - margin_sell_balance.min()) / (
        margin_sell_balance.max() - margin_sell_balance.min() + 1e-12
    )
    margin_sell_rate = base_rate + sell_pressure * 0.00008 + rng.normal(0, 0.000005, n_days)
    margin_sell_rate = np.maximum(margin_sell_rate, 0.000005)

    return pd.DataFrame(
        {
            "margin_balance": margin_balance,
            "margin_sell_balance": margin_sell_balance,
            "margin_buy_balance": margin_buy_balance,
            "margin_sell_rate": margin_sell_rate,
        },
        index=dates,
    )


# ---------------------------------------------------------------------------
# Factor values (from factor_ic_engine.py)
# ---------------------------------------------------------------------------

def compute_factor_values(prices: pd.DataFrame) -> Dict[str, pd.DataFrame]:
    """Compute raw factor values for all built-in factors.

    Returns a dict mapping factor_name -> DataFrame (date x ticker) of
    raw factor exposures. A real deployment would replace this body with
    Wind/Tushare feeds.

    Args:
        prices: DataFrame of prices (date x ticker).

    Returns:
        Dict mapping factor name to DataFrame of factor values.
    """
    factors: Dict[str, pd.DataFrame] = {}

    # Short-term factors
    ret_5d = prices.pct_change(5)
    factors["5d_reversal"] = -ret_5d

    overnight = prices / prices.shift(1) - 1
    factors["overnight_gap"] = overnight

    volume_proxy = prices.pct_change().abs().rolling(20).mean()
    volume_shock = (prices.pct_change().abs() - volume_proxy) / volume_proxy.replace(0, np.nan)
    factors["volume_shock"] = volume_shock

    # Medium-term factors
    mom_252 = prices.pct_change(252).shift(21)
    factors["12m_momentum"] = mom_252

    ma_200 = prices.rolling(200).mean()
    factors["200d_trend"] = prices / ma_200 - 1

    factors["earnings_revision"] = prices.pct_change(60).shift(5)

    # Long-term factors
    factors["value"] = 1.0 / prices

    ret_vol_120 = prices.pct_change().rolling(120).std()
    factors["quality"] = 1.0 / ret_vol_120.replace(0, np.nan)

    ret_vol_60 = prices.pct_change().rolling(60).std()
    factors["low_volatility"] = 1.0 / ret_vol_60.replace(0, np.nan)

    factors["dividend_yield"] = prices.pct_change(252) / prices

    return factors