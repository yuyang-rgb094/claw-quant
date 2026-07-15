"""Markdown report generation for Claw Quant backtesting results.

Generates a comprehensive performance report that can be reviewed by
the AI Agent or a human analyst.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from claw_quant.backtest.engine import BacktestResult
from claw_quant.backtest.performance import PerformanceMetrics


def generate_report(
    result: BacktestResult,
    benchmark_name: str = "CSI 300",
    output_path: Optional[str] = None,
) -> str:
    """Generate a Markdown backtest report.

    Args:
        result: BacktestResult from BacktestEngine.run().
        benchmark_name: Name of the benchmark index for comparison.
        output_path: Optional file path to write the report. If None,
            returns the report as a string.

    Returns:
        Markdown report string.
    """
    m = result.metrics
    config = result.config

    lines = []
    lines.append("# Claw Quant Backtest Report")
    lines.append(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("")

    # --- Configuration ---
    lines.append("## Configuration")
    lines.append("")
    lines.append(f"| Parameter | Value |")
    lines.append(f"|-----------|-------|")
    lines.append(f"| Period | {m.start_date} to {m.end_date} |")
    lines.append(f"| Trading Days | {m.n_trading_days} |")
    lines.append(f"| Fisher State | {config.fisher_stock_vs_cash} |")
    lines.append(f"| Fisher Max Equity | {config.fisher_max_equity:.0%} |")
    lines.append(f"| Initial Capital | ¥{config.initial_capital:,.0f} |")
    lines.append(f"| Rebalance Frequency | {config.rebalance_frequency} |")
    lines.append(f"| Min IC Threshold | {config.min_ic_threshold} |")
    lines.append(f"| Max Crowding Threshold | {config.max_crowding_threshold} |")
    lines.append(f"| Top N Factors | {config.top_n_factors} |")
    lines.append("")

    # --- Performance Summary ---
    lines.append("## Performance Summary")
    lines.append("")
    lines.append(f"| Metric | Value |")
    lines.append(f"|--------|-------|")
    lines.append(f"| Total Return | {m.total_return:.2%} |")
    lines.append(f"| Annualized Return | {m.annualized_return:.2%} |")
    lines.append(f"| Annualized Volatility | {m.annualized_volatility:.2%} |")
    lines.append(f"| Sharpe Ratio | {m.sharpe_ratio:.2f} |")
    lines.append(f"| Max Drawdown | {m.max_drawdown:.2%} |")
    lines.append(f"| Calmar Ratio | {m.calmar_ratio:.2f} |")
    lines.append(f"| Sortino Ratio | {m.sortino_ratio:.2f} |")
    lines.append(f"| Information Ratio | {m.information_ratio:.2f} |")
    lines.append(f"| Daily VaR (95%) | {m.daily_var_95:.2%} |")
    lines.append("")

    # --- Trading Statistics ---
    lines.append("## Trading Statistics")
    lines.append("")
    lines.append(f"| Metric | Value |")
    lines.append(f"|--------|-------|")
    lines.append(f"| Win Rate | {m.win_rate:.2%} |")
    lines.append(f"| Profit Factor | {m.profit_factor:.2f} |")
    lines.append(f"| Average Win | {m.avg_win:.4%} |")
    lines.append(f"| Average Loss | {m.avg_loss:.4%} |")
    lines.append(f"| Max Consecutive Wins | {m.max_consecutive_wins} |")
    lines.append(f"| Max Consecutive Losses | {m.max_consecutive_losses} |")
    lines.append(f"| Omega Ratio | {m.omega_ratio:.2f} |")
    lines.append("")

    # --- Walk-Forward Analysis ---
    if result.is_metrics and result.oos_metrics:
        lines.append("## Walk-Forward Analysis")
        lines.append("")
        lines.append(f"| Metric | In-Sample | Out-of-Sample | Δ |")
        lines.append(f"|--------|-----------|---------------|-----|")
        is_m = result.is_metrics
        oos_m = result.oos_metrics
        lines.append(f"| Sharpe Ratio | {is_m.sharpe_ratio:.2f} | {oos_m.sharpe_ratio:.2f} | {oos_m.sharpe_ratio - is_m.sharpe_ratio:+.2f} |")
        lines.append(f"| Annualized Return | {is_m.annualized_return:.2%} | {oos_m.annualized_return:.2%} | {oos_m.annualized_return - is_m.annualized_return:+.2%} |")
        lines.append(f"| Max Drawdown | {is_m.max_drawdown:.2%} | {oos_m.max_drawdown:.2%} | {oos_m.max_drawdown - is_m.max_drawdown:+.2%} |")
        lines.append(f"| Win Rate | {is_m.win_rate:.2%} | {oos_m.win_rate:.2%} | {oos_m.win_rate - is_m.win_rate:+.2%} |")
        lines.append(f"| Trading Days | {is_m.n_trading_days} | {oos_m.n_trading_days} | — |")
        lines.append("")

    # --- Factor Selection Analysis ---
    if result.factor_selections:
        lines.append("## Factor Selection Analysis")
        lines.append("")
        # Count factor appearances
        factor_counts: dict[str, int] = {}
        for sel in result.factor_selections:
            for f in sel["preferred_factors"]:
                factor_counts[f] = factor_counts.get(f, 0) + 1

        total_rebalances = len(result.factor_selections)
        if total_rebalances > 0:
            lines.append(f"| Factor | Selections | Frequency |")
            lines.append(f"|--------|------------|-----------|")
            for factor, count in sorted(factor_counts.items(), key=lambda x: x[1], reverse=True):
                freq = count / total_rebalances
                lines.append(f"| {factor} | {count} | {freq:.1%} |")
            lines.append("")

        # Latest selection
        latest = result.factor_selections[-1] if result.factor_selections else {}
        lines.append(f"**Latest Factor Selection ({latest.get('date', 'N/A')}):**")
        lines.append(f"- Preferred: {', '.join(latest.get('preferred_factors', []))}")
        lines.append(f"- Avoided: {', '.join(latest.get('avoided_factors', []))}")
        lines.append("")

    # --- Assessment ---
    lines.append("## Assessment")
    lines.append("")
    if m.sharpe_ratio > 1.0:
        lines.append("✅ **Strong performance.** Sharpe ratio > 1.0 indicates significant risk-adjusted alpha.")
    elif m.sharpe_ratio > 0.5:
        lines.append("⚠️ **Moderate performance.** Sharpe ratio between 0.5-1.0 — acceptable but room for improvement.")
    elif m.sharpe_ratio > 0.0:
        lines.append("⚠️ **Weak performance.** Positive but low Sharpe ratio — may not justify active management.")
    else:
        lines.append("❌ **Negative performance.** Sharpe ratio < 0 — the strategy is underperforming risk-free.")

    if m.max_drawdown < -0.20:
        lines.append("⚠️ **High drawdown risk.** Max drawdown > 20% — consider reducing risk budget or adding stop-loss.")
    if m.win_rate < 0.45:
        lines.append("⚠️ **Low win rate.** Win rate < 45% — strategy relies on large wins to offset frequent losses.")
    if m.profit_factor < 1.5:
        lines.append("⚠️ **Low profit factor.** Profit factor < 1.5 — gross profits barely exceed gross losses.")

    # OOS assessment
    if result.is_metrics and result.oos_metrics:
        oos_sharpe = result.oos_metrics.sharpe_ratio
        is_sharpe = result.is_metrics.sharpe_ratio
        sharpe_drop = is_sharpe - oos_sharpe
        if sharpe_drop > 0.5:
            lines.append("❌ **Significant overfitting.** OOS Sharpe is substantially lower than IS, suggesting the strategy does not generalize.")
        elif sharpe_drop > 0.2:
            lines.append("⚠️ **Possible overfitting.** OOS Sharpe is lower than IS — review strategy parameters.")
        else:
            lines.append("✅ **Good generalization.** OOS performance is consistent with IS, suggesting the strategy is robust.")

    lines.append("")

    report = "\n".join(lines)

    if output_path:
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(report)

    return report


def generate_summary(result: BacktestResult) -> str:
    """Generate a brief one-line summary of backtest results."""
    m = result.metrics
    return (
        f"Backtest {m.start_date}→{m.end_date}: "
        f"Return={m.annualized_return:.1%} "
        f"Sharpe={m.sharpe_ratio:.2f} "
        f"MaxDD={m.max_drawdown:.1%} "
        f"WinRate={m.win_rate:.1%} "
        f"(n={m.n_trading_days}d)"
    )