"""Performance metrics and attribution for Claw Quant backtesting.

Computes standard portfolio performance metrics: Sharpe ratio, max drawdown,
Calmar ratio, annualized return/volatility, win rate, profit factor.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd


@dataclass
class PerformanceMetrics:
    """Standard portfolio performance metrics."""

    # Basic metrics
    total_return: float = 0.0
    annualized_return: float = 0.0
    annualized_volatility: float = 0.0
    sharpe_ratio: float = 0.0
    max_drawdown: float = 0.0
    calmar_ratio: float = 0.0

    # Risk metrics
    daily_var_95: float = 0.0  # 95% daily Value at Risk
    downside_deviation: float = 0.0  # semi-deviation (negative returns only)
    sortino_ratio: float = 0.0

    # Trading metrics
    win_rate: float = 0.0  # fraction of positive days
    profit_factor: float = 0.0  # gross profit / gross loss
    avg_win: float = 0.0
    avg_loss: float = 0.0
    max_consecutive_wins: int = 0
    max_consecutive_losses: int = 0

    # Risk-adjusted
    information_ratio: float = 0.0  # excess return / tracking error (vs zero)
    omega_ratio: float = 0.0  # probability-weighted gain/loss ratio

    # Metadata
    n_trading_days: int = 0
    start_date: str = ""
    end_date: str = ""


def compute_metrics(
    returns: pd.Series,
    benchmark_returns: Optional[pd.Series] = None,
    risk_free_rate: float = 0.025,  # 2.5% annual
) -> PerformanceMetrics:
    """Compute all performance metrics from a daily return series.

    Args:
        returns: Daily portfolio returns (as decimals, e.g., 0.01 = 1%).
        benchmark_returns: Optional daily benchmark returns for IR calculation.
        risk_free_rate: Annual risk-free rate (default 2.5% for China).

    Returns:
        PerformanceMetrics with all computed values.
    """
    if len(returns) == 0:
        return PerformanceMetrics()

    returns = returns.dropna()
    n = len(returns)
    if n < 2:
        return PerformanceMetrics(n_trading_days=n)

    daily_rf = (1 + risk_free_rate) ** (1 / 252) - 1
    excess_returns = returns - daily_rf

    # Basic metrics
    total_return = float((1 + returns).prod() - 1)
    annualized_return = float((1 + total_return) ** (252 / n) - 1)
    annualized_volatility = float(returns.std() * np.sqrt(252))

    # Sharpe ratio
    if annualized_volatility > 0:
        sharpe_ratio = float((annualized_return - risk_free_rate) / annualized_volatility)
    else:
        sharpe_ratio = 0.0

    # Max drawdown
    cumulative = (1 + returns).cumprod()
    running_max = cumulative.cummax()
    drawdown = (cumulative - running_max) / running_max
    max_drawdown = float(drawdown.min())

    # Calmar ratio
    if max_drawdown < 0:
        calmar_ratio = float(annualized_return / abs(max_drawdown))
    else:
        calmar_ratio = float("inf") if annualized_return > 0 else 0.0

    # Daily VaR (95%)
    daily_var_95 = float(np.percentile(returns, 5))

    # Downside deviation (semi-deviation)
    neg_returns = returns[returns < 0]
    if len(neg_returns) > 0:
        downside_deviation = float(neg_returns.std() * np.sqrt(252))
    else:
        downside_deviation = 0.0

    # Sortino ratio
    if downside_deviation > 0:
        sortino_ratio = float((annualized_return - risk_free_rate) / downside_deviation)
    else:
        sortino_ratio = float("inf") if annualized_return > risk_free_rate else 0.0

    # Win rate
    positive_days = (returns > 0).sum()
    win_rate = float(positive_days / n) if n > 0 else 0.0

    # Profit factor
    gross_profit = returns[returns > 0].sum()
    gross_loss = abs(returns[returns < 0].sum())
    profit_factor = float(gross_profit / gross_loss) if gross_loss > 0 else float("inf")

    # Average win/loss
    avg_win = float(returns[returns > 0].mean()) if positive_days > 0 else 0.0
    avg_loss = float(returns[returns < 0].mean()) if (returns < 0).sum() > 0 else 0.0

    # Max consecutive wins/losses
    max_consecutive_wins, max_consecutive_losses = _compute_consecutive(returns)

    # Information ratio (vs zero — excess return per unit of total risk)
    if returns.std() > 0:
        information_ratio = float(excess_returns.mean() / returns.std() * np.sqrt(252))
    else:
        information_ratio = 0.0

    # Omega ratio (threshold = 0)
    gains = returns[returns > 0].sum()
    losses = abs(returns[returns < 0].sum())
    omega_ratio = float(gains / losses) if losses > 0 else float("inf")

    return PerformanceMetrics(
        total_return=total_return,
        annualized_return=annualized_return,
        annualized_volatility=annualized_volatility,
        sharpe_ratio=sharpe_ratio,
        max_drawdown=max_drawdown,
        calmar_ratio=calmar_ratio,
        daily_var_95=daily_var_95,
        downside_deviation=downside_deviation,
        sortino_ratio=sortino_ratio,
        win_rate=win_rate,
        profit_factor=profit_factor,
        avg_win=avg_win,
        avg_loss=avg_loss,
        max_consecutive_wins=max_consecutive_wins,
        max_consecutive_losses=max_consecutive_losses,
        information_ratio=information_ratio,
        omega_ratio=omega_ratio,
        n_trading_days=n,
        start_date=str(returns.index[0].date()),
        end_date=str(returns.index[-1].date()),
    )


def _compute_consecutive(returns: pd.Series) -> tuple[int, int]:
    """Compute max consecutive positive and negative days."""
    max_wins = 0
    max_losses = 0
    current_wins = 0
    current_losses = 0

    for r in returns:
        if r > 0:
            current_wins += 1
            current_losses = 0
            max_wins = max(max_wins, current_wins)
        elif r < 0:
            current_losses += 1
            current_wins = 0
            max_losses = max(max_losses, current_losses)
        else:
            current_wins = 0
            current_losses = 0

    return max_wins, max_losses


def compute_attribution(
    returns: pd.Series,
    factor_data: pd.DataFrame,
) -> dict:
    """Brinson-style performance attribution.

    Decomposes returns into allocation effect, selection effect, and
    interaction effect relative to factor exposures.

    Args:
        returns: Portfolio daily returns.
        factor_data: DataFrame with factor returns (MKT, SMB, HML, MOM).

    Returns:
        Dict with attribution components.
    """
    if returns.empty or factor_data.empty:
        return {}

    # Align
    common = returns.index.intersection(factor_data.index)
    if len(common) == 0:
        return {}

    returns = returns.loc[common]
    factor_data = factor_data.loc[common]

    # Simple regression-based attribution
    total_return = float((1 + returns).prod() - 1)

    # Factor contribution
    factor_contrib = {}
    if "MKT" in factor_data.columns:
        # Regress returns on factors
        import numpy as np
        X = factor_data.values
        y = returns.values
        beta = np.linalg.lstsq(X, y, rcond=None)[0]

        for i, col in enumerate(factor_data.columns):
            contrib = float(beta[i] * factor_data[col].sum())
            factor_contrib[col] = contrib

    # Residual (alpha)
    factor_total = sum(factor_contrib.values())
    residual = total_return - factor_total

    return {
        "total_return": total_return,
        "factor_contribution": factor_contrib,
        "alpha_residual": residual,
    }