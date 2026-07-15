#!/usr/bin/env python3
"""
Carhart Four-Factor Rolling Regression
======================================

SFM Layer (ADR-014, Module 1a) — Carhart Baseline.

This script computes the Carhart four-factor model (MKT, SMB, HML, MOM) for a
given portfolio or stock universe. It runs offline (daily or weekly), performs
rolling 2-year OLS regressions with monthly rebalancing, and writes the results
to sfm_state.md as static YAML fields for the AI Agent to read.

Financial Theory:
    The Carhart (1997) four-factor model extends the Fama-French (1993)
    three-factor model with a momentum factor:

        R_i - R_f = α + β₁·MKT + β₂·SMB + β₃·HML + β₄·MOM + ε

    where:
        R_i   = return of asset i
        R_f   = risk-free rate
        MKT   = market excess return (Sharpe, 1964 — CAPM)
        SMB   = small minus big (Fama-French, 1993 — size factor)
        HML   = high minus low (Fama-French, 1993 — value factor)
        MOM   = momentum (Carhart, 1997 — past 12-month return, skip 1 month)
        α     = Jensen's alpha (residual / anomaly return)
        β     = factor loadings (systematic risk exposures)
        ε     = idiosyncratic residual

    The β·γ component defines the manifold's shape (systematic risk premia
    topology); the α component defines the position on the manifold (anomaly).
    See ADR-014 for the full design rationale.

Usage:
    python carhart_regression.py --portfolio "600519.SH,000858.SZ"
    python carhart_regression.py --output sfm_state.md --window 2y
    python carhart_regression.py --backfill

References:
    - Sharpe, W. (1964). Capital Asset Prices. Journal of Finance.
    - Fama, E. & French, K. (1993). Common Risk Factors in the Returns on
      Stocks and Bonds. Journal of Financial Economics.
    - Carhart, M. (1997). On Persistence in Mutual Fund Performance. Journal
      of Finance.
    - Daniel, K. & Moskowitz, T. (2016). Momentum Crashes. JFE 122(2):221-247.
"""

from __future__ import annotations

import argparse
import json
import logging
import sqlite3
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
from scipy import stats  # Used for additional t-tests if needed; OLS t-stats come from statsmodels
from statsmodels.api import OLS, add_constant
from statsmodels.stats.outliers_influence import variance_inflation_factor

# ---------------------------------------------------------------------------
# Configuration (imported from shared package)
# ---------------------------------------------------------------------------

from claw_quant.config import (
    PROJECT_ROOT,
    DATA_DIR,
    DEFAULT_UNIVERSE,
    WIND_CLI_PATH,
    RISK_FREE_WIND_CODE,
)
from claw_quant.config import DB_PATHS, SFM_STATE_PATH

DB_PATH = DB_PATHS["carhart"]
KEYNES_STATE_PATH = SFM_STATE_PATH

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("carhart")


# ---------------------------------------------------------------------------
# Data Structures
# ---------------------------------------------------------------------------

@dataclass
class FactorResult:
    """Single factor regression result.

    Attributes:
        beta: Factor loading (systematic risk exposure).
        t_stat: t-statistic for the beta coefficient.
        p_value: p-value for the beta coefficient.
        premia_gamma: Factor risk premium (time-series average of factor returns).
        significant: Whether the factor is statistically significant (p < 0.05).
    """

    beta: float
    t_stat: float
    p_value: float
    premia_gamma: float
    significant: bool


@dataclass
class RegressionResult:
    """Complete Carhart four-factor regression output for one window.

    Attributes:
        window_start: Start date of the rolling window.
        window_end: End date of the rolling window.
        factors: Dictionary of factor_name -> FactorResult.
        alpha: Jensen's alpha (intercept — residual / anomaly return).
        alpha_t_stat: t-statistic for alpha.
        alpha_p_value: p-value for alpha.
        r_squared: R-squared of the regression.
        adj_r_squared: Adjusted R-squared.
        residual_std: Standard deviation of residuals (for IR computation).
        information_ratio: IR = alpha / residual_std.
        n_observations: Number of observations in the window.
        vif: Variance Inflation Factors per factor (multicollinearity check).
    """

    window_start: str
    window_end: str
    factors: dict[str, FactorResult] = field(default_factory=dict)
    alpha: float = 0.0
    alpha_t_stat: float = 0.0
    alpha_p_value: float = 1.0
    r_squared: float = 0.0
    adj_r_squared: float = 0.0
    residual_std: float = 0.0
    information_ratio: float = 0.0
    n_observations: int = 0
    vif: dict[str, float] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Factor Construction
# ---------------------------------------------------------------------------

def construct_mkt_factor(
    market_returns: pd.Series,
    risk_free_rate: pd.Series,
) -> pd.Series:
    """Construct the MKT (Market) factor: market excess return.

    MKT = R_market - R_f

    This is the foundational CAPM factor (Sharpe, 1964). It represents the
    excess return of the market portfolio over the risk-free rate. In the
    Sharpe equation E(R^e_i) = α_i + β'_i · γ, MKT captures the broad
    market risk premium — the single most important systematic risk factor.

    Args:
        market_returns: Time series of market index returns (e.g., CSI 300).
        risk_free_rate: Time series of risk-free rate (e.g., China 10Y Treasury).

    Returns:
        Time series of MKT factor returns (market excess return).
    """
    # Align indices
    aligned = pd.concat(
        [market_returns.rename("market"), risk_free_rate.rename("rf")],
        axis=1,
    ).dropna()
    mkt = aligned["market"] - aligned["rf"]
    mkt.name = "MKT"
    return mkt


def construct_smb_factor(
    stock_returns: pd.DataFrame,
    market_caps: pd.DataFrame,
) -> pd.Series:
    """Construct the SMB (Small Minus Big) factor: size factor.

    SMB = R_small - R_big

    Fama & French (1993) identified that small-cap stocks tend to outperform
    large-cap stocks on a risk-adjusted basis. This "size effect" is attributed
    to: (1) higher systematic risk of small firms, (2) lower liquidity, and
    (3) informational inefficiency. In A-shares, the size effect has been
    historically strong but has shown signs of decay due to institutional
    investor growth and index product proliferation.

    Construction methodology:
        1. Sort all stocks by market capitalization each month.
        2. Split into small-cap (bottom 50%) and large-cap (top 50%).
        3. Compute value-weighted returns for each group.
        4. SMB = small-cap return - large-cap return.

    Args:
        stock_returns: DataFrame of stock returns (date x stock).
        market_caps: DataFrame of market caps (date x stock), aligned with
            stock_returns.

    Returns:
        Time series of SMB factor returns.
    """
    # Median market cap for each date as the split threshold
    median_cap = market_caps.median(axis=1)

    smb_data: dict = {}
    for date in stock_returns.index:
        if date not in market_caps.index:
            continue
        caps = market_caps.loc[date].dropna()
        rets = stock_returns.loc[date].reindex(caps.index)

        median = median_cap.loc[date]
        small_mask = caps < median
        big_mask = caps >= median

        small_caps = caps[small_mask]
        big_caps = caps[big_mask]

        if len(small_caps) == 0 or len(big_caps) == 0:
            continue

        # Value-weighted returns (use boolean indexing to select only the
        # relevant stocks, not all stocks in the universe)
        small_weights = small_caps / small_caps.sum()
        big_weights = big_caps / big_caps.sum()

        small_ret = (rets.reindex(small_caps.index).fillna(0) * small_weights).sum()
        big_ret = (rets.reindex(big_caps.index).fillna(0) * big_weights).sum()

        smb_data[date] = small_ret - big_ret

    smb = pd.Series(smb_data)
    smb.name = "SMB"
    return smb


def construct_hml_factor(
    stock_returns: pd.DataFrame,
    book_to_market: pd.DataFrame,
) -> pd.Series:
    """Construct the HML (High Minus Low) factor: value factor.

    HML = R_high_bm - R_low_bm

    Fama & French (1993) found that high book-to-market (value) stocks tend
    to outperform low book-to-market (growth) stocks. The theoretical basis
    is that value stocks are "distressed" — they carry higher fundamental
    risk and investors demand a premium for bearing that risk. Alternatively,
    Lakonishok, Shleifer & Vishny (1994) argue it's a behavioral phenomenon:
    investors extrapolate past growth too far, creating mean-reversion.

    Construction methodology:
        1. Sort all stocks by book-to-market (B/M) ratio each month.
        2. Split into high B/M (top 30% = value) and low B/M (bottom 30% = growth).
        3. Compute value-weighted returns for each group.
        4. HML = value return - growth return.

    Args:
        stock_returns: DataFrame of stock returns (date x stock).
        book_to_market: DataFrame of B/M ratios (date x stock).

    Returns:
        Time series of HML factor returns.
    """
    hml_data: dict = {}
    for date in stock_returns.index:
        if date not in book_to_market.index:
            continue
        bm = book_to_market.loc[date].dropna()
        rets = stock_returns.loc[date].reindex(bm.index)

        # Top 30% = high B/M (value), bottom 30% = low B/M (growth)
        bm_30 = bm.quantile(0.30)
        bm_70 = bm.quantile(0.70)

        high_stocks = bm[bm >= bm_70]
        low_stocks = bm[bm <= bm_30]

        if len(high_stocks) == 0 or len(low_stocks) == 0:
            continue

        # Equal-weighted returns for HML (simplified; FF use value-weighted)
        # Use reindex to select only value/growth stocks
        high_ret = rets.reindex(high_stocks.index).mean()
        low_ret = rets.reindex(low_stocks.index).mean()

        hml_data[date] = high_ret - low_ret

    hml = pd.Series(hml_data)
    hml.name = "HML"
    return hml


def construct_mom_factor(
    stock_returns: pd.DataFrame,
    lookback_months: int = 12,
    skip_months: int = 1,
) -> pd.Series:
    """Construct the MOM (Momentum) factor: past-return continuation.

    MOM = R_winners - R_losers

    Carhart (1997) extended the Fama-French three-factor model with a
    momentum factor based on Jegadeesh & Titman (1993). The factor captures
    the tendency of stocks that have performed well (poorly) over the past
    year to continue performing well (poorly) in the near future.

    Key construction detail — the "skip month":
        To avoid contamination from the short-term reversal effect (1-month
        mean reversion), the momentum signal uses returns from t-12 to t-2
        (12 months of history, skipping the most recent month). The skip is
        critical: without it, the short-term reversal and medium-term
        momentum signals partially cancel each other.

    Daniel & Moskowitz (2016) document that momentum half-life is ~70.9
    trading days, placing it firmly in the medium-term duration bucket
    (5-90 days). Momentum crashes occur in panic states following market
    declines with high volatility and contemporaneous market rebounds —
    these preconditions are tracked in SFM Module 3b.

    Construction methodology:
        1. For each month t, compute cumulative return from t-12-skip to t-skip.
        2. Rank stocks by past return.
        3. Winners = top 30%, Losers = bottom 30%.
        4. MOM = winner return - loser return in month t.

    Args:
        stock_returns: DataFrame of stock returns (date x stock).
        lookback_months: Number of months of past returns to use (default 12).
        skip_months: Months to skip before measuring momentum (default 1).

    Returns:
        Time series of MOM factor returns, forward-filled to daily frequency
        to align with other factors.
    """
    # Resample to monthly if daily data is provided
    monthly_returns = stock_returns.resample("ME").apply(
        lambda x: (1 + x).prod() - 1 if len(x) > 0 else np.nan
    )

    # Compute cumulative past returns for momentum signal
    past_returns = monthly_returns.rolling(
        window=lookback_months + skip_months
    ).apply(
        lambda x: (1 + x[skip_months:]).prod() - 1, raw=False
    )

    mom_data: dict = {}
    dates = monthly_returns.index
    for i in range(lookback_months + skip_months, len(dates)):
        date = dates[i]
        past = past_returns.loc[date].dropna()
        current_ret = monthly_returns.loc[date].reindex(past.index)

        # Require at least 2 stocks to form winner/loser portfolios
        if len(past) < 2:
            continue

        # Top 30% = winners, bottom 30% = losers
        p70 = past.quantile(0.70)
        p30 = past.quantile(0.30)

        winner_stocks = past[past >= p70]
        loser_stocks = past[past <= p30]

        if len(winner_stocks) == 0 or len(loser_stocks) == 0:
            continue

        # Use reindex to select only winner/loser stocks
        winner_ret = current_ret.reindex(winner_stocks.index).mean()
        loser_ret = current_ret.reindex(loser_stocks.index).mean()

        mom_data[date] = winner_ret - loser_ret

    if not mom_data:
        logger.warning("MOM factor construction produced no valid data points")
        return pd.Series(dtype=float, name="MOM")

    mom = pd.Series(mom_data)
    mom.name = "MOM"

    # Forward-fill from monthly to daily frequency to align with other factors.
    # MOM is a monthly signal that persists until the next rebalance; forward-
    # filling captures this persistence at the daily level.
    mom = mom.resample("B").ffill()
    return mom


def compute_factor_premia(factor_returns: pd.Series) -> float:
    """Compute factor risk premium (γ): time-series average of factor returns.

    In the Sharpe (1964) framework, E(R^e_i) = α_i + β'_i · γ, the γ vector
    represents the factor risk premia — the compensation per unit of factor
    exposure. Each γ_j is estimated as the time-series mean of the j-th
    factor portfolio's return.

    This is the "time-series approach" to estimating factor premia, as
    distinguished from the Fama-MacBeth cross-sectional approach. For traded
    factor portfolios (which all four Carhart factors are), the time-series
    mean is the efficient estimator (Fama, 1976).

    Args:
        factor_returns: Time series of a single factor's returns.

    Returns:
        Factor risk premium (mean of the factor return series).
    """
    return float(factor_returns.mean())


# ---------------------------------------------------------------------------
# Multicollinearity Check
# ---------------------------------------------------------------------------

def compute_vif(factor_matrix: pd.DataFrame) -> dict[str, float]:
    """Compute Variance Inflation Factor (VIF) for each factor.

    VIF measures how much the variance of an estimated regression coefficient
    increases due to multicollinearity. A VIF of 1 means no correlation with
    other factors. Rules of thumb:
        - VIF < 5:  Low multicollinearity (acceptable)
        - VIF 5-10: Moderate multicollinearity (review needed)
        - VIF > 10: Severe multicollinearity (problematic)

    In the Carhart model, MKT and HML can exhibit moderate correlation (both
    are related to the broad market), and MOM can show time-varying correlation
    with MKT during momentum crash periods. High VIF inflates standard errors,
    making it harder to detect statistically significant factors.

    Args:
        factor_matrix: DataFrame where each column is a factor return series.

    Returns:
        Dictionary mapping factor names to their VIF values.
    """
    vif_results: dict[str, float] = {}
    factor_matrix = factor_matrix.dropna()

    if len(factor_matrix) < 3 or factor_matrix.shape[1] < 2:
        return {col: float("nan") for col in factor_matrix.columns}

    X = add_constant(factor_matrix.values, has_constant="add")
    for i, col in enumerate(factor_matrix.columns):
        try:
            vif_val = variance_inflation_factor(X, i + 1)  # +1 for const column
            vif_results[col] = float(vif_val) if not np.isinf(vif_val) else float("inf")
        except Exception:
            vif_results[col] = float("nan")

    return vif_results


# ---------------------------------------------------------------------------
# Rolling Regression
# ---------------------------------------------------------------------------

def run_carhart_regression(
    portfolio_returns: pd.Series,
    factor_data: pd.DataFrame,
    window_start: str,
    window_end: str,
) -> RegressionResult:
    """Run a single Carhart four-factor OLS regression over a specified window.

    The regression model:
        R_p - R_f = α + β₁·MKT + β₂·SMB + β₃·HML + β₄·MOM + ε

    This is the core of Module 1a (Carhart Baseline). The β vector captures
    the portfolio's systematic risk exposures — the "shape" of the return
    manifold. The α (Jensen's alpha) captures the residual anomaly — the
    "position" on the manifold. These feed into Module 2 (Anomaly Map) for
    crowding and institutional constraint analysis.

    Args:
        portfolio_returns: Excess returns of the portfolio (R_p - R_f).
        factor_data: DataFrame with columns MKT, SMB, HML, MOM.
        window_start: Start date string for the regression window.
        window_end: End date string for the regression window.

    Returns:
        RegressionResult with betas, alpha, R², t-stats, and VIF.
    """
    # Align data within the window
    mask = (portfolio_returns.index >= window_start) & (
        portfolio_returns.index <= window_end
    )
    y = portfolio_returns[mask].dropna()
    X = factor_data.loc[y.index, ["MKT", "SMB", "HML", "MOM"]].dropna()

    # Re-align after dropping NAs
    common_idx = y.index.intersection(X.index)
    y = y.loc[common_idx]
    X = X.loc[common_idx]

    if len(y) < 10:
        logger.warning(
            "Insufficient data for regression: %d observations in %s..%s",
            len(y),
            window_start,
            window_end,
        )
        return RegressionResult(
            window_start=window_start,
            window_end=window_end,
            n_observations=len(y),
        )

    # OLS regression with intercept (alpha)
    X_with_const = add_constant(X.values, has_constant="add")
    model = OLS(y.values, X_with_const).fit()

    # Extract results
    alpha = float(model.params[0])
    alpha_t_stat = float(model.tvalues[0])
    alpha_p_value = float(model.pvalues[0])

    factor_names = ["MKT", "SMB", "HML", "MOM"]
    factors: dict[str, FactorResult] = {}
    for i, name in enumerate(factor_names):
        premia = compute_factor_premia(X[name])
        factors[name] = FactorResult(
            beta=float(model.params[i + 1]),
            t_stat=float(model.tvalues[i + 1]),
            p_value=float(model.pvalues[i + 1]),
            premia_gamma=premia,
            significant=bool(model.pvalues[i + 1] < 0.05),
        )

    # Residual standard deviation and Information Ratio
    residual_std = float(np.std(model.resid, ddof=X.shape[1] + 1))
    ir = alpha / residual_std if residual_std > 0 else 0.0

    # VIF check
    vif = compute_vif(X)

    return RegressionResult(
        window_start=window_start,
        window_end=window_end,
        factors=factors,
        alpha=alpha,
        alpha_t_stat=alpha_t_stat,
        alpha_p_value=alpha_p_value,
        r_squared=float(model.rsquared),
        adj_r_squared=float(model.rsquared_adj),
        residual_std=residual_std,
        information_ratio=ir,
        n_observations=len(y),
        vif=vif,
    )


def run_rolling_regression(
    portfolio_returns: pd.Series,
    factor_data: pd.DataFrame,
    window_years: int = 2,
    rebalance_freq: str = "ME",
) -> list[RegressionResult]:
    """Run rolling Carhart regression with periodic rebalancing.

    For each rebalance date, the regression uses the trailing `window_years`
    of data. The most recent window's result is what gets written to
    sfm_state.md as the current Carhart baseline.

    The rolling approach captures time-varying factor exposures — a portfolio's
    loading on MOM may shift from positive to negative during a momentum crash
    (Daniel & Moskowitz, 2016), and its HML exposure may change as a company
    transitions from growth to value. Static single-window regressions miss
    these dynamics.

    Args:
        portfolio_returns: Excess returns of the portfolio (R_p - R_f).
        factor_data: DataFrame with columns MKT, SMB, HML, MOM.
        window_years: Length of the rolling window in years (default 2).
        rebalance_freq: Rebalancing frequency (pandas offset alias, default "ME" = month-end).

    Returns:
        List of RegressionResult objects, one per rebalance window.
    """
    # Align data
    common_idx = portfolio_returns.index.intersection(factor_data.index)
    portfolio_returns = portfolio_returns.loc[common_idx]
    factor_data = factor_data.loc[common_idx]

    if len(common_idx) == 0:
        logger.error(
            "No overlapping dates between portfolio returns and factor data. "
            "Check date alignment — MOM (monthly) must be forward-filled to daily."
        )
        return []

    # Generate rebalance dates
    rebalance_dates = pd.date_range(
        start=portfolio_returns.index.min(),
        end=portfolio_returns.index.max(),
        freq=rebalance_freq,
    )

    window_days = window_years * 252  # Approximate trading days per year

    results: list[RegressionResult] = []
    for rebalance_date in rebalance_dates:
        window_start = rebalance_date - timedelta(days=window_days)

        if window_start < portfolio_returns.index.min():
            continue

        result = run_carhart_regression(
            portfolio_returns=portfolio_returns,
            factor_data=factor_data,
            window_start=window_start.strftime("%Y-%m-%d"),
            window_end=rebalance_date.strftime("%Y-%m-%d"),
        )
        results.append(result)
        logger.info(
            "Window %s..%s: α=%.6f, R²=%.4f, n=%d",
            result.window_start,
            result.window_end,
            result.alpha,
            result.r_squared,
            result.n_observations,
        )

    if not results:
        logger.warning("No valid regression windows produced results")

    return results


# ---------------------------------------------------------------------------
# Wind API Data Fetching (Reference Implementation)
# ---------------------------------------------------------------------------

def fetch_data_from_wind(
    windcodes: list[str],
    start_date: str,
    end_date: str,
    indicator: str = "close",
) -> pd.DataFrame:
    """Fetch stock K-line data from Wind MCP Skill.

    Wind MCP constraints:
        - windcode must be a SINGLE string per call (no arrays)
        - Parameters are a single JSON string
        - Dates are yyyyMMdd format

    Calls stock_data.get_stock_kline once per stock and combines results.

    Args:
        windcodes: List of Wind stock codes (e.g., ["600519.SH", "000858.SZ"]).
        start_date: Start date in YYYY-MM-DD format.
        end_date: End date in YYYY-MM-DD format.
        indicator: Which price indicator to fetch ("close", "open", etc.).

    Returns:
        DataFrame indexed by date with stock columns.
    """
    fmt_start = start_date.replace("-", "")
    fmt_end = end_date.replace("-", "")

    all_prices = {}
    for wc in windcodes:
        params = json.dumps({
            "windcode": wc,
            "begin_date": fmt_start,
            "end_date": fmt_end,
            "aftime": "0",  # 前复权
        }, ensure_ascii=False)
        cmd = ["node", "scripts/cli.mjs", "call", "stock_data", "get_stock_kline", params]

        logger.info("Wind K-line: %s", wc)

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            if result.returncode != 0 or not result.stdout.strip():
                logger.warning("Wind K-line failed for %s: %s", wc, result.stderr[:200])
                continue
            data = json.loads(result.stdout)
            if isinstance(data, list):
                df = pd.DataFrame(data)
            elif isinstance(data, dict) and "data" in data:
                df = pd.DataFrame(data["data"])
            else:
                continue
            if "date" in df.columns or "trade_date" in df.columns:
                date_col = "date" if "date" in df.columns else "trade_date"
                df[date_col] = pd.to_datetime(df[date_col])
                close_col = indicator if indicator in df.columns else df.columns[-1]
                all_prices[wc] = df.set_index(date_col)[close_col]
        except FileNotFoundError:
            raise RuntimeError(
                "Wind CLI not found. Clone https://github.com/Wind-Information-Co-Ltd/wind-skills "
                "and run 'npm install'. For testing, use generate_synthetic_data()."
            )
        except (subprocess.TimeoutExpired, json.JSONDecodeError) as e:
            logger.warning("Wind K-line error for %s: %s", wc, e)

    if not all_prices:
        raise RuntimeError("Wind API returned no data for any stock")

    return pd.DataFrame(all_prices).sort_index()


def fetch_risk_free_rate(start_date: str, end_date: str) -> pd.Series:
    """Fetch China 10-year Treasury yield from Wind as risk-free rate proxy.

    Uses economic_data.natural_language_get_edb_data with executionMode="searchFetch".

    Args:
        start_date: Start date in YYYY-MM-DD format.
        end_date: End date in YYYY-MM-DD format.

    Returns:
        Daily risk-free rate series (as decimal, e.g., 0.0001 for ~2.5% annual).
    """
    params = json.dumps({
        "executionMode": "searchFetch",
        "question": "中国10年期国债收益率",
        "beginDate": start_date.replace("-", ""),
        "endDate": end_date.replace("-", ""),
    }, ensure_ascii=False)
    cmd = ["node", "scripts/cli.mjs", "call", "economic_data", "natural_language_get_edb_data", params]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode != 0 or not result.stdout.strip():
            raise RuntimeError(f"Wind CLI failed: {result.stderr[:200]}")
        data = json.loads(result.stdout)
        if isinstance(data, list):
            df = pd.DataFrame(data)
        elif isinstance(data, dict) and "data" in data:
            df = pd.DataFrame(data["data"])
        else:
            raise RuntimeError("Unexpected Wind response format")
        if df.empty:
            raise RuntimeError("Wind returned empty data")
        # Find date and value columns
        date_col = next((c for c in df.columns if "date" in c.lower() or "日期" in c), df.columns[0])
        val_col = next((c for c in df.columns if "value" in c.lower() or "close" in c.lower()), df.columns[-1])
        df[date_col] = pd.to_datetime(df[date_col])
        df = df.set_index(date_col).sort_index()
        annual_yield = df[val_col] / 100.0
        daily_rf = (1 + annual_yield) ** (1 / 252) - 1
        return daily_rf
    except (FileNotFoundError, RuntimeError, json.JSONDecodeError) as e:
        logger.warning("Could not fetch risk-free rate from Wind: %s. Using synthetic 2.5%% annual rate.", e)
        dates = pd.bdate_range(start=start_date, end=end_date)
        annual_yield = 0.025
        daily_rf = (1 + annual_yield) ** (1 / 252) - 1
        return pd.Series(daily_rf, index=dates, name="rf")


# ---------------------------------------------------------------------------
# Synthetic Data Generator (for offline testing without Wind)
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Synthetic Data (imported from shared package)
# ---------------------------------------------------------------------------

from claw_quant.synthetic import generate_synthetic_data  # noqa: E402


# ---------------------------------------------------------------------------
# Output: YAML and SQLite
# ---------------------------------------------------------------------------

def results_to_yaml(
    result: RegressionResult,
    portfolio_name: str = "portfolio",
) -> str:
    """Convert a RegressionResult to YAML string for sfm_state.md.

    The YAML output follows the ADR-014 Module 1a format:

        carhart_baseline:
          portfolio: <name>
          regression_window: rolling_2y
          factors:
            MKT: { beta: ..., premia_gamma: ..., significant: true }
            SMB: { beta: ..., premia_gamma: ..., significant: false }
            HML: { beta: ..., premia_gamma: ..., significant: true }
            MOM: { beta: ..., premia_gamma: ..., significant: true }
          residual_alpha: 0.003
          alpha_t_stat: 2.15
          r_squared: 0.72
          information_ratio: 0.85
          vif_check:
            MKT: 1.2
            SMB: 1.5
            HML: 2.1
            MOM: 1.8
          computed_at: 2026-07-09T12:00:00

    This format is designed for the AI Agent to read as pre-computed static
    fields. The agent does NOT compute regressions itself — it reads these
    values and uses them in its manifold state analysis.

    Args:
        result: RegressionResult to convert.
        portfolio_name: Name of the portfolio for labeling.

    Returns:
        YAML string suitable for embedding in sfm_state.md.
    """
    lines: list[str] = []
    lines.append("carhart_baseline:")
    lines.append(f"  portfolio: {portfolio_name}")
    lines.append(f"  regression_window: {result.window_start}..{result.window_end}")
    lines.append("  factors:")
    for name in ["MKT", "SMB", "HML", "MOM"]:
        f = result.factors.get(name)
        if f is None:
            lines.append(f"    {name}: {{ beta: null, premia_gamma: null, significant: false }}")
        else:
            lines.append(
                f"    {name}: {{ beta: {f.beta:.4f}, "
                f"premia_gamma: {f.premia_gamma:.6f}, "
                f"significant: {str(f.significant).lower()} }}"
            )
    lines.append(f"  residual_alpha: {result.alpha:.6f}")
    lines.append(f"  alpha_t_stat: {result.alpha_t_stat:.4f}")
    lines.append(f"  alpha_p_value: {result.alpha_p_value:.4f}")
    lines.append(f"  r_squared: {result.r_squared:.4f}")
    lines.append(f"  adj_r_squared: {result.adj_r_squared:.4f}")
    lines.append(f"  information_ratio: {result.information_ratio:.4f}")
    lines.append(f"  n_observations: {result.n_observations}")
    lines.append("  vif_check:")
    for name in ["MKT", "SMB", "HML", "MOM"]:
        vif_val = result.vif.get(name, float("nan"))
        if np.isinf(vif_val):
            lines.append(f"    {name}: inf")
        elif np.isnan(vif_val):
            lines.append(f"    {name}: null")
        else:
            lines.append(f"    {name}: {vif_val:.4f}")
    lines.append(f"  computed_at: {datetime.now().isoformat()}")

    return "\n".join(lines)


def append_to_keynes_state(
    yaml_output: str,
    output_path: Path,
) -> None:
    """Append Carhart baseline YAML to sfm_state.md.

    This writes the pre-computed regression results to the Module 1a section
    of sfm_state.md. The AI Agent reads these values during its manifold
    state analysis — it does not compute regressions itself.

    If the file doesn't exist, it creates it with a header. If a previous
    carhart_baseline section exists, it replaces the block.

    Args:
        yaml_output: YAML string from results_to_yaml().
        output_path: Path to sfm_state.md (or custom output file).
    """
    content = yaml_output + "\n"

    if not output_path.exists():
        # Create new file with header
        header = (
            f"# sfm_state.md — SFM Layer Manifold State\n\n"
            f"<!-- Auto-generated by carhart_regression.py — Module 1a: Carhart Baseline -->\n"
            f"<!-- Last updated: {datetime.now().isoformat()} -->\n\n"
        )
        output_path.write_text(header + content, encoding="utf-8")
        logger.info("Created %s with Carhart baseline", output_path)
    else:
        existing = output_path.read_text(encoding="utf-8")

        # Check if carhart_baseline block already exists
        if "carhart_baseline:" in existing:
            # Replace existing block
            import re
            pattern = r"carhart_baseline:.*?(?=\n[a-zA-Z#]|\Z)"
            replacement = yaml_output
            new_content = re.sub(
                pattern, replacement, existing, flags=re.DOTALL
            )
            output_path.write_text(new_content, encoding="utf-8")
            logger.info("Updated carhart_baseline in %s", output_path)
        else:
            # Append new block
            with open(output_path, "a", encoding="utf-8") as f:
                f.write("\n" + content)
            logger.info("Appended carhart_baseline to %s", output_path)


def save_to_sqlite(
    results: list[RegressionResult],
    db_path: Path,
    portfolio_name: str = "portfolio",
) -> None:
    """Save full regression results to SQLite database.

    The SQLite database stores complete regression details for historical
    analysis, backtesting, and audit trails. The AI Agent does not read this
    directly — it reads the YAML in sfm_state.md. The SQLite database is
    for quantitative verification and historical comparison.

    Schema:
        - regressions: One row per window with all aggregate metrics.
        - factor_details: One row per factor per window (betas, t-stats, etc.).

    Args:
        results: List of RegressionResult objects from rolling regression.
        db_path: Path to the SQLite database file.
        portfolio_name: Name of the portfolio for labeling.
    """
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    # Create tables
    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS regressions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            portfolio TEXT NOT NULL,
            window_start TEXT NOT NULL,
            window_end TEXT NOT NULL,
            alpha REAL,
            alpha_t_stat REAL,
            alpha_p_value REAL,
            r_squared REAL,
            adj_r_squared REAL,
            residual_std REAL,
            information_ratio REAL,
            n_observations INTEGER,
            computed_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS factor_details (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            regression_id INTEGER NOT NULL,
            portfolio TEXT NOT NULL,
            window_start TEXT NOT NULL,
            window_end TEXT NOT NULL,
            factor_name TEXT NOT NULL,
            beta REAL,
            t_stat REAL,
            p_value REAL,
            premia_gamma REAL,
            significant INTEGER,
            vif REAL,
            FOREIGN KEY (regression_id) REFERENCES regressions(id)
        );

        CREATE INDEX IF NOT EXISTS idx_regressions_window
            ON regressions(portfolio, window_start, window_end);
        CREATE INDEX IF NOT EXISTS idx_factor_details
            ON factor_details(regression_id, factor_name);
    """)

    now = datetime.now().isoformat()

    for result in results:
        # Insert regression record
        cursor.execute(
            """
            INSERT INTO regressions (
                portfolio, window_start, window_end, alpha, alpha_t_stat,
                alpha_p_value, r_squared, adj_r_squared, residual_std,
                information_ratio, n_observations, computed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                portfolio_name,
                result.window_start,
                result.window_end,
                result.alpha,
                result.alpha_t_stat,
                result.alpha_p_value,
                result.r_squared,
                result.adj_r_squared,
                result.residual_std,
                result.information_ratio,
                result.n_observations,
                now,
            ),
        )
        regression_id = cursor.lastrowid

        # Insert factor detail records
        for factor_name in ["MKT", "SMB", "HML", "MOM"]:
            f = result.factors.get(factor_name)
            if f is None:
                continue
            cursor.execute(
                """
                INSERT INTO factor_details (
                    regression_id, portfolio, window_start, window_end,
                    factor_name, beta, t_stat, p_value, premia_gamma,
                    significant, vif
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    regression_id,
                    portfolio_name,
                    result.window_start,
                    result.window_end,
                    factor_name,
                    f.beta,
                    f.t_stat,
                    f.p_value,
                    f.premia_gamma,
                    int(f.significant),
                    result.vif.get(factor_name),
                ),
            )

    conn.commit()
    conn.close()
    logger.info("Saved %d regression results to %s", len(results), db_path)


# ---------------------------------------------------------------------------
# Portfolio Construction
# ---------------------------------------------------------------------------

def build_portfolio_returns(
    stock_returns: pd.DataFrame,
    market_caps: pd.DataFrame,
    windcodes: list[str],
) -> pd.Series:
    """Build value-weighted portfolio returns from individual stock returns.

    The portfolio is constructed as a value-weighted basket of the input
    stocks. Value weighting ensures that larger stocks have proportionally
    larger impact on portfolio returns — this matches how actual index
    and fund portfolios are constructed in practice.

    Args:
        stock_returns: DataFrame of individual stock returns (date x stock).
        market_caps: DataFrame of market caps (date x stock).
        windcodes: List of stock codes in the portfolio.

    Returns:
        Time series of portfolio returns.
    """
    available = [c for c in windcodes if c in stock_returns.columns]
    if not available:
        raise ValueError("No valid stock codes found in return data")

    rets = stock_returns[available]
    # Filter to only stocks that also have market cap data
    cap_cols = [c for c in available if c in market_caps.columns]
    caps = market_caps[cap_cols] if cap_cols else None

    if caps is not None:
        # Value-weighted returns
        weights = caps.div(caps.sum(axis=1), axis=0).fillna(0)
        portfolio = (rets * weights).sum(axis=1)
    else:
        # Equal-weighted fallback
        portfolio = rets.mean(axis=1)

    portfolio.name = "portfolio"
    return portfolio


# ---------------------------------------------------------------------------
# Main Pipeline
# ---------------------------------------------------------------------------

def run_carhart_pipeline(
    windcodes: list[str],
    window_years: int = 2,
    output_file: Optional[Path] = None,
    use_synthetic: bool = True,
    backfill: bool = False,
) -> list[RegressionResult]:
    """Run the complete Carhart four-factor regression pipeline.

    This is the main entry point that orchestrates:
        1. Data fetching (Wind API or synthetic).
        2. Factor construction (MKT, SMB, HML, MOM).
        3. Portfolio return computation.
        4. Rolling regression.
        5. Output (YAML to sfm_state.md + SQLite).

    The pipeline is designed to run offline (daily or weekly). Results are
    written as static fields that the AI Agent reads — the agent does NOT
    compute regressions itself. This separation ensures that quantitative
    computation is done by proper statistical tools (statsmodels, scipy),
    not by LLM estimation.

    Args:
        windcodes: List of stock Wind codes.
        window_years: Rolling window length in years.
        output_file: Path to output file (sfm_state.md). If None, print YAML.
        use_synthetic: If True, use synthetic data (for testing without Wind).
        backfill: If True, run full historical backfill instead of latest only.

    Returns:
        List of RegressionResult objects.
    """
    logger.info("=== Carhart Four-Factor Regression Pipeline ===")
    logger.info("Universe: %d stocks", len(windcodes))
    logger.info("Window: %dy rolling", window_years)
    logger.info("Mode: %s", "backfill (full history)" if backfill else "latest window")

    # Step 1: Fetch data
    if use_synthetic:
        logger.info("Using synthetic data (no Wind API connection)")
        stock_returns, market_caps, book_to_market, market_returns, rf = (
            generate_synthetic_data(windcodes, n_years=max(window_years + 1, 5))
        )
    else:
        end_date = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=(window_years + 1) * 365)).strftime("%Y-%m-%d")
        logger.info("Fetching data from Wind: %s to %s", start_date, end_date)

        # These calls require wind-mcp-skill to be installed
        stock_data = fetch_data_from_wind(windcodes, start_date, end_date)
        market_returns = fetch_data_from_wind(
            ["000300.SH"], start_date, end_date, indicator="close"
        ).iloc[:, 0]
        rf = fetch_risk_free_rate(start_date, end_date)
        # market_caps and book_to_market would also be fetched here
        # For now, generate synthetic for missing pieces
        _, market_caps, book_to_market, _, _ = generate_synthetic_data(windcodes, n_years=window_years + 1)

    # Step 2: Construct factors
    logger.info("Constructing Carhart factors...")

    mkt = construct_mkt_factor(market_returns, rf)

    smb = construct_smb_factor(stock_returns, market_caps)

    hml = construct_hml_factor(stock_returns, book_to_market)

    mom = construct_mom_factor(stock_returns)

    # Combine into factor matrix
    factor_data = pd.concat([mkt, smb, hml, mom], axis=1).dropna()
    logger.info(
        "Factor matrix: %d observations, columns: %s",
        len(factor_data),
        list(factor_data.columns),
    )

    if len(factor_data) == 0:
        logger.error(
            "Factor matrix is empty after construction. Check data alignment "
            "and ensure MOM factor has sufficient lookback period."
        )
        return []

    # Step 3: Build portfolio returns
    portfolio_returns = build_portfolio_returns(stock_returns, market_caps, windcodes)
    portfolio_excess = portfolio_returns - rf.reindex(portfolio_returns.index).fillna(0)

    # Step 4: Run rolling regression
    logger.info("Running rolling %dy regression...", window_years)
    results = run_rolling_regression(
        portfolio_returns=portfolio_excess,
        factor_data=factor_data,
        window_years=window_years,
    )

    if not results:
        logger.error("No regression results produced. Check data availability.")
        return []

    # Step 5: Output results
    if backfill:
        # Save all windows to SQLite
        save_to_sqlite(results, DB_PATH, portfolio_name=",".join(windcodes[:3]) + "...")
        # Write latest to YAML
        latest = results[-1]
    else:
        # Only process the latest window
        latest = results[-1]
        save_to_sqlite([latest], DB_PATH, portfolio_name=",".join(windcodes[:3]) + "...")

    yaml_output = results_to_yaml(latest, portfolio_name=",".join(windcodes[:3]) + "...")

    if output_file:
        append_to_keynes_state(yaml_output, output_file)
    else:
        print("\n" + "=" * 70)
        print("Carhart Baseline (Module 1a) — Latest Window")
        print("=" * 70)
        print(yaml_output)
        print("=" * 70 + "\n")

    # Log summary
    logger.info("=== Regression Summary ===")
    logger.info("Window: %s .. %s", latest.window_start, latest.window_end)
    logger.info("Alpha (Jensen's): %.6f (t=%.2f, p=%.4f)", latest.alpha, latest.alpha_t_stat, latest.alpha_p_value)
    logger.info("R-squared: %.4f | Adjusted R-squared: %.4f", latest.r_squared, latest.adj_r_squared)
    logger.info("Information Ratio: %.4f", latest.information_ratio)
    for name in ["MKT", "SMB", "HML", "MOM"]:
        f = latest.factors.get(name)
        if f:
            logger.info(
                "  %s: β=%.4f (t=%.2f, p=%.4f, γ=%.6f, sig=%s, VIF=%.2f)",
                name, f.beta, f.t_stat, f.p_value, f.premia_gamma, f.significant,
                latest.vif.get(name, float("nan")),
            )

    return results


# ---------------------------------------------------------------------------
# CLI Interface
# ---------------------------------------------------------------------------

def parse_window(window_str: str) -> int:
    """Parse a window string like '2y' into years.

    Args:
        window_str: Window string (e.g., '1y', '2y', '3y').

    Returns:
        Number of years as integer.

    Raises:
        ValueError: If the format is not recognized.
    """
    window_str = window_str.strip().lower()
    if window_str.endswith("y"):
        years = int(window_str[:-1])
        if years < 1 or years > 10:
            raise ValueError(f"Window must be between 1y and 10y, got {window_str}")
        return years
    raise ValueError(f"Invalid window format: '{window_str}'. Use format like '2y'")


def main() -> None:
    """CLI entry point for the Carhart four-factor regression script.

    This script is designed to be run offline (daily or weekly) via cron or
    manual invocation. It does NOT run in real-time — the AI Agent reads the
    pre-computed static values from sfm_state.md.

    Examples:
        # Run with default CSI 300 + CSI 500 subset, synthetic data
        python carhart_regression.py

        # Run with specific portfolio
        python carhart_regression.py --portfolio "600519.SH,000858.SZ,601318.SH"

        # Write results to sfm_state.md
        python carhart_regression.py --output sfm_state.md

        # Custom window
        python carhart_regression.py --window 3y

        # Full historical backfill
        python carhart_regression.py --backfill

        # Use real Wind API data (requires wind-mcp-skill)
        python carhart_regression.py --use-wind
    """
    parser = argparse.ArgumentParser(
        description="Carhart Four-Factor Rolling Regression (SFM Layer Module 1a)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Financial Theory:
  The Carhart (1997) four-factor model extends Fama-French (1993) with momentum:
    R_i - R_f = α + β₁·MKT + β₂·SMB + β₃·HML + β₄·MOM + ε

  MKT: Market excess return (Sharpe, 1964)
  SMB: Small Minus Big (Fama-French, 1993 — size factor)
  HML: High Minus Low (Fama-French, 1993 — value factor)
  MOM: Momentum (Carhart, 1997 — past 12 months, skip 1 month)

Output:
  - YAML written to sfm_state.md (Module 1a section)
  - Full details saved to SQLite at data/carhart_results.db

Dependencies (install with --break-system-packages on externally managed Python):
  pip install --break-system-packages pandas numpy scipy statsmodels pyyaml

References:
  - ADR-014: SFM Layer Manifold State Tracking
  - Sharpe (1964), Fama-French (1993), Carhart (1997), Daniel & Moskowitz (2016)
        """,
    )

    parser.add_argument(
        "--portfolio",
        type=str,
        default=None,
        help="Comma-separated Wind stock codes (e.g., '600519.SH,000858.SZ'). "
        "If not provided, uses default CSI 300 + CSI 500 subset.",
    )

    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output file path (e.g., 'sfm_state.md'). "
        "If not provided, prints YAML to stdout.",
    )

    parser.add_argument(
        "--window",
        type=str,
        default="2y",
        help="Regression window (e.g., '1y', '2y', '3y'). Default: 2y",
    )

    parser.add_argument(
        "--backfill",
        action="store_true",
        help="Historical backfill mode. Runs regression for all available "
        "windows and saves all to SQLite.",
    )

    parser.add_argument(
        "--use-wind",
        action="store_true",
        help="Use real Wind API data via wind-mcp-skill CLI. "
        "If not set, uses synthetic data for testing.",
    )

    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose (DEBUG) logging.",
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Parse portfolio
    if args.portfolio:
        windcodes = [c.strip() for c in args.portfolio.split(",") if c.strip()]
    else:
        windcodes = DEFAULT_UNIVERSE
        logger.info("Using default universe: %d stocks", len(windcodes))

    # Parse window
    window_years = parse_window(args.window)

    # Parse output file
    output_file: Optional[Path] = None
    if args.output:
        output_file = Path(args.output)
        if not output_file.is_absolute():
            output_file = PROJECT_ROOT / args.output

    # Run pipeline
    try:
        run_carhart_pipeline(
            windcodes=windcodes,
            window_years=window_years,
            output_file=output_file,
            use_synthetic=not args.use_wind,
            backfill=args.backfill,
        )
    except Exception as e:
        logger.error("Pipeline failed: %s", e, exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
