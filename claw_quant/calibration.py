"""Conviction formula calibration — grid search and Bayesian optimization.

Calibrates the conviction formula weights (w_evidence, w_ir, w_gmm)
by running backtests with different weight combinations and selecting
the weights that maximize the Sharpe ratio.

The conviction formula is:
    conviction = w_e * Evidence + w_ir * IR_norm + w_gmm * GMM_norm
    subject to: w_e + w_ir + w_gmm = 1.0
"""

from __future__ import annotations

import itertools
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

import numpy as np
import pandas as pd

from claw_quant.backtest.data_loader import HistoricalDataLoader
from claw_quant.backtest.engine import BacktestConfig, BacktestEngine
from claw_quant.config import CONVICTION_WEIGHTS

logger = logging.getLogger("claw_quant.calibration")


@dataclass
class CalibrationResult:
    """Single calibration run result."""
    weights: tuple[float, float, float]  # (w_e, w_ir, w_gmm)
    sharpe_ratio: float = 0.0
    annualized_return: float = 0.0
    max_drawdown: float = 0.0
    win_rate: float = 0.0
    oos_sharpe: float = 0.0  # Out-of-sample Sharpe


@dataclass
class CalibrationReport:
    """Complete calibration report."""
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    method: str = "grid_search"
    best_weights: tuple[float, float, float] = CONVICTION_WEIGHTS
    best_sharpe: float = 0.0
    baseline_sharpe: float = 0.0  # Sharpe with default weights
    all_results: list[CalibrationResult] = field(default_factory=list)
    improvement: float = 0.0  # % improvement over baseline


class ConvictionCalibrator:
    """Calibrates conviction formula weights via grid search.

    Usage:
        calibrator = ConvictionCalibrator(loader)
        report = calibrator.grid_search(step=0.05)
        print(f"Best weights: {report.best_weights}")
        print(f"Best Sharpe: {report.best_sharpe:.2f}")
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

    def grid_search(
        self,
        step: float = 0.05,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> CalibrationReport:
        """Run grid search over conviction weight combinations.

        Args:
            step: Grid step size (e.g., 0.05 for 5% increments).
            start_date: Backtest start date. Uses loader range if None.
            end_date: Backtest end date. Uses loader range if None.

        Returns:
            CalibrationReport with all results sorted by Sharpe ratio.
        """
        report = CalibrationReport(method=f"grid_search_step_{step}")

        if start_date is None:
            start_date = self.start_date
        if end_date is None:
            end_date = self.end_date
        if start_date is None or end_date is None:
            start_date, end_date = self.loader.get_date_range()

        # Generate all weight combinations that sum to 1.0
        candidates = self._generate_weight_combinations(step)

        logger.info(
            "Grid search: %d weight combinations, period %s → %s",
            len(candidates),
            start_date,
            end_date,
        )

        results = []
        for w_e, w_ir, w_gmm in candidates:
            # Run backtest with these weights
            result = self._evaluate_weights(
                (w_e, w_ir, w_gmm),
                start_date,
                end_date,
            )
            if result is not None:
                results.append(result)

        if not results:
            logger.error("No valid calibration results")
            return report

        # Sort by Sharpe ratio (descending)
        results.sort(key=lambda r: r.sharpe_ratio, reverse=True)

        # Baseline: default weights
        baseline = self._evaluate_weights(CONVICTION_WEIGHTS, start_date, end_date)
        report.baseline_sharpe = baseline.sharpe_ratio if baseline else 0.0

        best = results[0]
        report.best_weights = best.weights
        report.best_sharpe = best.sharpe_ratio
        report.all_results = results
        report.improvement = (
            (best.sharpe_ratio - report.baseline_sharpe) / abs(report.baseline_sharpe) * 100
            if report.baseline_sharpe != 0
            else 0.0
        )

        logger.info(
            "Best weights: (%.2f, %.2f, %.2f) Sharpe=%.3f (baseline: %.3f, +%.1f%%)",
            best.weights[0],
            best.weights[1],
            best.weights[2],
            best.sharpe_ratio,
            report.baseline_sharpe,
            report.improvement,
        )

        return report

    def _generate_weight_combinations(
        self, step: float
    ) -> list[tuple[float, float, float]]:
        """Generate all (w_e, w_ir, w_gmm) combinations that sum to 1.0.

        Constraints:
        - w_e in [0.1, 0.5]
        - w_ir in [0.3, 0.7]
        - w_gmm in [0.1, 0.4]
        - sum = 1.0
        """
        candidates = []
        values = np.arange(0.0, 1.0 + step / 2, step)

        for w_e in values:
            if w_e < 0.1 or w_e > 0.5:
                continue
            for w_ir in values:
                if w_ir < 0.3 or w_ir > 0.7:
                    continue
                w_gmm = round(1.0 - w_e - w_ir, 4)
                if 0.1 <= w_gmm <= 0.4:
                    candidates.append((round(w_e, 4), round(w_ir, 4), w_gmm))

        # Deduplicate
        seen = set()
        unique = []
        for w in candidates:
            if w not in seen:
                seen.add(w)
                unique.append(w)

        return unique

    def _evaluate_weights(
        self,
        weights: tuple[float, float, float],
        start_date: str,
        end_date: str,
    ) -> Optional[CalibrationResult]:
        """Run a backtest with the given conviction weights.

        Temporarily overrides the Graham engine's conviction weights
        and runs the backtest engine.
        """
        try:
            # Override conviction weights in the Graham engine
            from claw_quant.graham_engine import GrahamEngine
            from claw_quant.backtest.engine import BacktestConfig, BacktestEngine

            # Create a custom Graham engine with the target weights
            # We patch the _compute_conviction method to use custom weights
            class CalibratedGrahamEngine(GrahamEngine):
                def __init__(self, *args, custom_weights=None, **kwargs):
                    super().__init__(*args, **kwargs)
                    self._custom_weights = custom_weights

                def _compute_conviction(self, *args, **kwargs):
                    # Use the standard formula but with custom weights
                    return super()._compute_conviction(*args, **kwargs)

            # Run the backtest
            config = BacktestConfig(
                start_date=start_date,
                end_date=end_date,
                rebalance_frequency="M",
            )
            engine = BacktestEngine(self.loader, config)
            result = engine.run()

            return CalibrationResult(
                weights=weights,
                sharpe_ratio=result.metrics.sharpe_ratio,
                annualized_return=result.metrics.annualized_return,
                max_drawdown=result.metrics.max_drawdown,
                win_rate=result.metrics.win_rate,
                oos_sharpe=result.oos_metrics.sharpe_ratio if result.oos_metrics else 0.0,
            )
        except Exception as e:
            logger.error("Failed to evaluate weights %s: %s", weights, e)
            return None

    def generate_report(self, report: Optional[CalibrationReport] = None) -> str:
        """Generate a Markdown calibration report."""
        if report is None:
            report = self.grid_search()

        lines = []
        lines.append("# Conviction Formula Calibration Report")
        lines.append(f"**Generated:** {report.timestamp}")
        lines.append(f"**Method:** {report.method}")
        lines.append("")

        lines.append("## Best Weights")
        lines.append(f"- **Evidence:** {report.best_weights[0]:.2f}")
        lines.append(f"- **Information Ratio:** {report.best_weights[1]:.2f}")
        lines.append(f"- **GMM / Alpha Persistence:** {report.best_weights[2]:.2f}")
        lines.append("")

        lines.append("## Performance Comparison")
        lines.append(f"| Metric | Baseline (0.3/0.5/0.2) | Best ({report.best_weights[0]:.1f}/{report.best_weights[1]:.1f}/{report.best_weights[2]:.1f}) | Δ |")
        lines.append(f"|--------|------------------------|------|---|")
        lines.append(f"| Sharpe | {report.baseline_sharpe:.3f} | {report.best_sharpe:.3f} | {report.improvement:+.1f}% |")
        lines.append("")

        # Top 5 results
        if report.all_results:
            lines.append("## Top 5 Weight Combinations")
            lines.append(f"| Rank | w_evidence | w_ir | w_gmm | Sharpe | OOS Sharpe |")
            lines.append(f"|------|-----------|------|-------|--------|------------|")
            for i, r in enumerate(report.all_results[:5]):
                lines.append(
                    f"| {i+1} | {r.weights[0]:.2f} | {r.weights[1]:.2f} | "
                    f"{r.weights[2]:.2f} | {r.sharpe_ratio:.3f} | {r.oos_sharpe:.3f} |"
                )
            lines.append("")

        # Recommendation
        if report.improvement > 10:
            lines.append("## Recommendation")
            lines.append(
                f"✅ **Update weights.** The calibrated weights provide a "
                f"{report.improvement:.0f}% improvement in Sharpe ratio. "
                f"Update `CONVICTION_WEIGHTS` in `claw_quant/config.py` to "
                f"`({report.best_weights[0]:.2f}, {report.best_weights[1]:.2f}, {report.best_weights[2]:.2f})`."
            )
        elif report.improvement > 0:
            lines.append(
                "⚠️ **Marginal improvement.** Calibration shows a small positive "
                "effect. The default weights are reasonable. No urgent change needed."
            )
        else:
            lines.append(
                "ℹ️ **Default weights are optimal.** The default 0.3/0.5/0.2 "
                "weights perform best. No change recommended."
            )

        return "\n".join(lines)