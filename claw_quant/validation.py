"""Validation utilities for Claw Quant.

Walk-forward validation, benchmark comparison, and stability checks.
Used to validate the pipeline against historical data and benchmarks.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd

from claw_quant.backtest.data_loader import HistoricalDataLoader
from claw_quant.backtest.engine import BacktestConfig, BacktestEngine, BacktestResult
from claw_quant.backtest.performance import compute_metrics, PerformanceMetrics


@dataclass
class WalkForwardResult:
    """Walk-forward validation result."""
    train_start: str
    train_end: str
    test_start: str
    test_end: str

    is_metrics: Optional[PerformanceMetrics] = None
    oos_metrics: Optional[PerformanceMetrics] = None

    is_sharpe: float = 0.0
    oos_sharpe: float = 0.0
    sharpe_decay: float = 0.0  # IS - OOS (positive = overfitting)

    assessment: str = ""


@dataclass
class BenchmarkComparison:
    """Comparison between pipeline and benchmark."""
    pipeline_return: float = 0.0
    benchmark_return: float = 0.0
    excess_return: float = 0.0
    tracking_error: float = 0.0
    information_ratio: float = 0.0
    alpha: float = 0.0
    beta: float = 0.0
    correlation: float = 0.0


def compute_walk_forward(
    loader: HistoricalDataLoader,
    train_start: str,
    train_end: str,
    test_start: str,
    test_end: str,
    fisher_config: Optional[dict] = None,
) -> WalkForwardResult:
    """Run a walk-forward validation.

    Trains (in-sample) on train_start..train_end, then tests
    (out-of-sample) on test_start..test_end.

    Args:
        loader: HistoricalDataLoader instance.
        train_start, train_end: In-sample period.
        test_start, test_end: Out-of-sample period.
        fisher_config: Optional Fisher state override.

    Returns:
        WalkForwardResult with IS and OOS metrics.
    """
    result = WalkForwardResult(
        train_start=train_start,
        train_end=train_end,
        test_start=test_start,
        test_end=test_end,
    )

    fc = fisher_config or {"stock_vs_cash": "neutral", "max_equity": 0.8}

    # In-sample
    is_config = BacktestConfig(
        start_date=train_start,
        end_date=train_end,
        fisher_stock_vs_cash=fc.get("stock_vs_cash", "neutral"),
        fisher_max_equity=fc.get("max_equity", 0.8),
    )
    is_engine = BacktestEngine(loader, is_config)
    is_result = is_engine.run()
    result.is_metrics = is_result.metrics
    result.is_sharpe = is_result.metrics.sharpe_ratio

    # Out-of-sample
    oos_config = BacktestConfig(
        start_date=test_start,
        end_date=test_end,
        fisher_stock_vs_cash=fc.get("stock_vs_cash", "neutral"),
        fisher_max_equity=fc.get("max_equity", 0.8),
    )
    oos_engine = BacktestEngine(loader, oos_config)
    oos_result = oos_engine.run()
    result.oos_metrics = oos_result.metrics
    result.oos_sharpe = oos_result.metrics.sharpe_ratio

    # Sharpe decay
    result.sharpe_decay = result.is_sharpe - result.oos_sharpe

    # Assessment
    if result.sharpe_decay > 0.5:
        result.assessment = "Significant overfitting detected. OOS Sharpe is substantially lower than IS."
    elif result.sharpe_decay > 0.2:
        result.assessment = "Possible overfitting. OOS performance is lower than IS."
    elif result.oos_sharpe > 0.5:
        result.assessment = "Good generalization. Pipeline shows positive risk-adjusted returns OOS."
    elif result.oos_sharpe > 0.0:
        result.assessment = "Weak but positive OOS performance. Review strategy parameters."
    else:
        result.assessment = "Negative OOS performance. Strategy does not generalize."

    return result


def compare_to_benchmark(
    pipeline_returns: pd.Series,
    benchmark_returns: pd.Series,
) -> BenchmarkComparison:
    """Compare pipeline returns against a benchmark.

    Args:
        pipeline_returns: Daily pipeline returns.
        benchmark_returns: Daily benchmark returns (e.g., CSI 300).

    Returns:
        BenchmarkComparison with excess return, tracking error, IR, alpha, beta.
    """
    comparison = BenchmarkComparison()

    # Align
    common = pipeline_returns.index.intersection(benchmark_returns.index)
    if len(common) < 10:
        return comparison

    pr = pipeline_returns.loc[common]
    br = benchmark_returns.loc[common]

    n = len(pr)

    # Total returns
    comparison.pipeline_return = float((1 + pr).prod() - 1)
    comparison.benchmark_return = float((1 + br).prod() - 1)
    comparison.excess_return = comparison.pipeline_return - comparison.benchmark_return

    # Excess daily returns
    excess = pr - br
    comparison.tracking_error = float(excess.std() * np.sqrt(252))

    # Information ratio
    if comparison.tracking_error > 0:
        comparison.information_ratio = float(
            excess.mean() / excess.std() * np.sqrt(252)
        )

    # Alpha and beta (simple linear regression)
    cov = np.cov(pr.values, br.values)
    if cov[1, 1] > 0:
        comparison.beta = float(cov[0, 1] / cov[1, 1])
        comparison.alpha = float(
            pr.mean() - comparison.beta * br.mean()
        ) * 252  # annualized

    # Correlation
    comparison.correlation = float(pr.corr(br))

    return comparison


def stability_check(
    weights: dict[str, float],
    prev_weights: dict[str, float],
) -> float:
    """Compute weight stability (1 - one-way turnover).

    Returns a value between 0 and 1, where 1 = no change, 0 = complete turnover.
    """
    all_keys = set(weights.keys()) | set(prev_weights.keys())
    if not all_keys:
        return 1.0

    turnover = 0.0
    for k in all_keys:
        w1 = prev_weights.get(k, 0.0)
        w2 = weights.get(k, 0.0)
        turnover += abs(w2 - w1)

    one_way = turnover / 2
    return max(1.0 - one_way, 0.0)


def factor_rotation_frequency(
    selections: list[list[str]],
) -> float:
    """Compute how often factor preferences change (0-1).

    Returns the fraction of rebalance periods where the factor selection
    changed from the previous period.
    """
    if len(selections) < 2:
        return 0.0

    changes = 0
    for i in range(1, len(selections)):
        if set(selections[i]) != set(selections[i - 1]):
            changes += 1

    return changes / (len(selections) - 1)