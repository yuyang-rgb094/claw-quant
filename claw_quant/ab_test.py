"""Interface Contract A/B Test — validates the 400 token budget empirically.

Runs backtests with different token budgets for the SFM interface and
compares performance. The goal is to determine whether the 400 token
budget is optimal, or whether a different budget produces better results.

Hypothesis: The 400 token budget balances information density and
attention bias. Too few tokens → lost information; too many → length bias.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

import numpy as np
import pandas as pd

from claw_quant.backtest.data_loader import HistoricalDataLoader
from claw_quant.backtest.engine import BacktestConfig, BacktestEngine
from claw_quant.config import INTERFACE_TOKEN_BUDGET

logger = logging.getLogger("claw_quant.ab_test")


@dataclass
class ABTestResult:
    """Single A/B test result for one token budget."""
    token_budget: int
    sharpe_ratio: float = 0.0
    annualized_return: float = 0.0
    max_drawdown: float = 0.0
    win_rate: float = 0.0
    oos_sharpe: float = 0.0
    factor_selection_count: int = 0  # How many factors were selected on average
    note: str = ""


@dataclass
class ABTestReport:
    """Complete A/B test report."""
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    budgets_tested: list[int] = field(default_factory=list)
    results: list[ABTestResult] = field(default_factory=list)
    best_budget: int = INTERFACE_TOKEN_BUDGET
    baseline_sharpe: float = 0.0
    recommendation: str = ""


class InterfaceABTest:
    """A/B test for the Graham Interface Contract token budget.

    Usage:
        tester = InterfaceABTest(loader)
        report = tester.compare_token_budgets([200, 300, 400, 500, 600])
        print(f"Best budget: {report.best_budget} tokens")
    """

    def __init__(
        self,
        loader: Optional[HistoricalDataLoader] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ):
        self.loader = loader or HistoricalDataLoader()
        self.start_date = start_date
        self.end_date = end_date

    def compare_token_budgets(
        self,
        budgets: Optional[list[int]] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> ABTestReport:
        """Run backtests with different token budgets and compare.

        Args:
            budgets: List of token budgets to test (e.g., [200, 300, 400, 500, 600]).
            start_date: Backtest start date.
            end_date: Backtest end date.

        Returns:
            ABTestReport with results for each budget.
        """
        if budgets is None:
            budgets = [200, 300, 400, 500, 600]

        if start_date is None:
            start_date = self.start_date
        if end_date is None:
            end_date = self.end_date
        if start_date is None or end_date is None:
            start_date, end_date = self.loader.get_date_range()

        report = ABTestReport(budgets_tested=budgets)

        logger.info(
            "A/B test: %d token budgets, period %s → %s",
            len(budgets),
            start_date,
            end_date,
        )

        results = []
        for budget in budgets:
            result = self._test_budget(budget, start_date, end_date)
            if result is not None:
                results.append(result)

        if not results:
            logger.error("No valid A/B test results")
            return report

        # Sort by OOS Sharpe (most important metric for generalization)
        results.sort(key=lambda r: r.oos_sharpe, reverse=True)

        best = results[0]
        report.results = results
        report.best_budget = best.token_budget
        report.baseline_sharpe = next(
            (r.sharpe_ratio for r in results if r.token_budget == INTERFACE_TOKEN_BUDGET),
            results[0].sharpe_ratio,
        )

        # Generate recommendation
        if best.token_budget != INTERFACE_TOKEN_BUDGET:
            improvement = (
                (best.sharpe_ratio - report.baseline_sharpe)
                / abs(report.baseline_sharpe) * 100
                if report.baseline_sharpe != 0
                else 0.0
            )
            if improvement > 5:
                report.recommendation = (
                    f"✅ **Change budget to {best.token_budget} tokens.** "
                    f"Provides {improvement:.0f}% improvement in Sharpe ratio "
                    f"over the current {INTERFACE_TOKEN_BUDGET} token budget."
                )
            elif improvement > 0:
                report.recommendation = (
                    f"⚠️ **Consider {best.token_budget} tokens.** "
                    f"Marginal improvement ({improvement:.0f}%) over current budget. "
                    f"Not urgent."
                )
            else:
                report.recommendation = (
                    f"ℹ️ **Current budget ({INTERFACE_TOKEN_BUDGET}) is optimal.** "
                    f"No change recommended."
                )
        else:
            report.recommendation = (
                f"✅ **Current budget ({INTERFACE_TOKEN_BUDGET} tokens) is optimal.** "
                f"No change needed."
            )

        return report

    def _test_budget(
        self,
        budget: int,
        start_date: str,
        end_date: str,
    ) -> Optional[ABTestResult]:
        """Run a backtest with a specific token budget.

        The token budget affects how the SFM interface compresses its
        key_signal fields. Smaller budgets force more aggressive compression,
        potentially losing nuance but reducing attention bias.
        """
        try:
            # The backtest engine uses the SFM interface indirectly
            # We simulate the effect of token budget by varying how many
            # factors are selected (proxy for information density)

            config = BacktestConfig(
                start_date=start_date,
                end_date=end_date,
                rebalance_frequency="M",
            )

            # Token budget affects top_n_factors:
            # - Smaller budget → fewer factors can be described → fewer selected
            # - Larger budget → more factors can be described → more selected
            n_factors = max(1, min(5, budget // 150))  # ~150 tokens per factor

            config.top_n_factors = n_factors
            engine = BacktestEngine(self.loader, config)
            result = engine.run()

            avg_factors = (
                np.mean([len(sel["preferred_factors"]) for sel in result.factor_selections])
                if result.factor_selections
                else 0
            )

            return ABTestResult(
                token_budget=budget,
                sharpe_ratio=result.metrics.sharpe_ratio,
                annualized_return=result.metrics.annualized_return,
                max_drawdown=result.metrics.max_drawdown,
                win_rate=result.metrics.win_rate,
                oos_sharpe=result.oos_metrics.sharpe_ratio if result.oos_metrics else 0.0,
                factor_selection_count=int(avg_factors),
                note=f"top_n_factors={n_factors} (derived from budget={budget})",
            )
        except Exception as e:
            logger.error("Failed to test budget %d: %s", budget, e)
            return None

    def generate_report(self, report: Optional[ABTestReport] = None) -> str:
        """Generate a Markdown A/B test report."""
        if report is None:
            report = self.compare_token_budgets()

        lines = []
        lines.append("# Graham Interface Contract A/B Test Report")
        lines.append(f"**Generated:** {report.timestamp}")
        lines.append(f"**Current Budget:** {INTERFACE_TOKEN_BUDGET} tokens")
        lines.append("")

        lines.append("## Results by Token Budget")
        lines.append(
            f"| Budget | Sharpe | OOS Sharpe | Return | Max DD | Win Rate | Factors |"
        )
        lines.append(
            f"|--------|--------|------------|--------|--------|----------|---------|"
        )
        for r in report.results:
            marker = " ← CURRENT" if r.token_budget == INTERFACE_TOKEN_BUDGET else ""
            marker = " ← BEST" if r.token_budget == report.best_budget else marker
            lines.append(
                f"| {r.token_budget}{marker} | {r.sharpe_ratio:.3f} | "
                f"{r.oos_sharpe:.3f} | {r.annualized_return:.1%} | "
                f"{r.max_drawdown:.1%} | {r.win_rate:.1%} | {r.factor_selection_count} |"
            )
        lines.append("")

        lines.append("## Analysis")
        lines.append("")

        # Is there a clear trend?
        if len(report.results) >= 3:
            budgets = [r.token_budget for r in report.results]
            sharpes = [r.sharpe_ratio for r in report.results]
            if len(set(budgets)) == len(budgets):
                # Check for monotonic trend
                diffs = np.diff(sharpes)
                if all(d > 0 for d in diffs):
                    lines.append(
                        "📈 **Increasing trend.** Larger token budgets consistently "
                        "improve Sharpe ratio. The 400 token limit may be too restrictive — "
                        "consider increasing to 500-600 tokens."
                    )
                elif all(d < 0 for d in diffs):
                    lines.append(
                        "📉 **Decreasing trend.** Smaller token budgets perform better. "
                        "The 400 token limit may be too generous — consider reducing to "
                        "200-300 tokens to minimize attention bias."
                    )
                else:
                    lines.append(
                        "📊 **No clear trend.** Performance varies non-monotonically "
                        "with token budget. The current 400 token budget is reasonable."
                    )
            lines.append("")

        lines.append("## Recommendation")
        lines.append(report.recommendation)

        return "\n".join(lines)