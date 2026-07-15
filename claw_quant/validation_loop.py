"""Validation loop — periodic checks on factor signal quality and pipeline health.

Runs scheduled checks on IC decay, crowding surges, alpha persistence,
and benchmark comparison. Generates actionable alerts when signals degrade.
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
from claw_quant.backtest.performance import compute_metrics

logger = logging.getLogger("claw_quant.validation_loop")


@dataclass
class ValidationAlert:
    """A single validation alert."""
    check_name: str
    severity: str  # info / warning / critical
    message: str
    metric_value: float = 0.0
    threshold: float = 0.0
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class ValidationReport:
    """Complete validation report."""
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    alerts: list[ValidationAlert] = field(default_factory=list)
    metrics: dict = field(default_factory=dict)
    is_healthy: bool = True


class ValidationLoop:
    """Periodic validation checks for the Claw Quant pipeline.

    Usage:
        loop = ValidationLoop()
        report = loop.run_all_checks()
        if not report.is_healthy:
            for alert in report.alerts:
                print(f"[{alert.severity}] {alert.message}")
    """

    def __init__(self, loader: Optional[HistoricalDataLoader] = None):
        self.loader = loader or HistoricalDataLoader()

    def run_all_checks(self) -> ValidationReport:
        """Run all validation checks and return a report."""
        report = ValidationReport()

        # IC decay check
        ic_alerts = self.run_ic_decay_check()
        report.alerts.extend(ic_alerts)

        # Crowding surge check
        crowding_alerts = self.run_crowding_surge_check()
        report.alerts.extend(crowding_alerts)

        # Alpha persistence check
        alpha_alerts = self.run_alpha_persistence_check()
        report.alerts.extend(alpha_alerts)

        # Benchmark comparison
        benchmark_alerts = self.run_benchmark_comparison()
        report.alerts.extend(benchmark_alerts)

        # Health assessment
        critical_count = sum(1 for a in report.alerts if a.severity == "critical")
        warning_count = sum(1 for a in report.alerts if a.severity == "warning")
        report.is_healthy = critical_count == 0
        report.metrics = {
            "total_alerts": len(report.alerts),
            "critical": critical_count,
            "warning": warning_count,
            "info": sum(1 for a in report.alerts if a.severity == "info"),
        }

        return report

    def run_ic_decay_check(self) -> list[ValidationAlert]:
        """Check if any factor's IC has significantly declined.

        Detects factors with "accelerating" or "reversing" decay status.
        """
        alerts = []
        hl_data = self.loader.load_half_life_data()

        if hl_data.empty:
            return alerts

        for factor, row in hl_data.iterrows():
            decay = str(row.get("decay_status", "stable"))
            half_life = float(row.get("half_life_days", 0))

            if decay == "reversing":
                alerts.append(ValidationAlert(
                    check_name="ic_decay",
                    severity="critical",
                    message=f"Factor '{factor}' IC is reversing — signal may be broken",
                    metric_value=half_life,
                    threshold=0,
                ))
            elif decay == "accelerating":
                if half_life < 10:
                    severity = "critical"
                elif half_life < 30:
                    severity = "warning"
                else:
                    severity = "info"
                alerts.append(ValidationAlert(
                    check_name="ic_decay",
                    severity=severity,
                    message=f"Factor '{factor}' IC decay accelerating (half-life: {half_life:.0f}d)",
                    metric_value=half_life,
                    threshold=30,
                ))

        return alerts

    def run_crowding_surge_check(self) -> list[ValidationAlert]:
        """Check if any factor's crowding score has crossed above threshold."""
        alerts = []
        crowd_data = self.loader.load_crowding_latest()

        if crowd_data.empty:
            return alerts

        for factor, row in crowd_data.iterrows():
            score = float(row.get("crowding_score", 0))
            trend = str(row.get("trend", "stable"))

            if score > 0.70:
                alerts.append(ValidationAlert(
                    check_name="crowding_surge",
                    severity="critical",
                    message=f"Factor '{factor}' is severely crowded ({score:.2f}) — high forced-deleveraging risk",
                    metric_value=score,
                    threshold=0.70,
                ))
            elif score > 0.55 and trend == "increasing":
                alerts.append(ValidationAlert(
                    check_name="crowding_surge",
                    severity="warning",
                    message=f"Factor '{factor}' crowding increasing ({score:.2f}) — monitor closely",
                    metric_value=score,
                    threshold=0.55,
                ))

        return alerts

    def run_alpha_persistence_check(self) -> list[ValidationAlert]:
        """Check if Carhart alpha has been consistently positive.

        Looks at the rolling 12-month alpha trend from the regression history.
        """
        alerts = []
        carhart = self.loader.load_carhart_history()

        if carhart.empty:
            return alerts

        # Get the most recent 12 windows
        recent = carhart.tail(12)
        if len(recent) < 6:
            return alerts

        avg_alpha = float(recent["alpha"].mean())
        avg_ir = float(recent.get("information_ratio", pd.Series([0])).mean())
        alpha_trend = float(recent["alpha"].diff().mean())  # positive = improving

        if avg_alpha < 0 and alpha_trend < 0:
            alerts.append(ValidationAlert(
                check_name="alpha_persistence",
                severity="critical",
                message=f"Carhart alpha negative and declining (avg: {avg_alpha:.4f}, trend: {alpha_trend:.4f})",
                metric_value=avg_alpha,
                threshold=0,
            ))
        elif avg_alpha < 0:
            alerts.append(ValidationAlert(
                check_name="alpha_persistence",
                severity="warning",
                message=f"Carhart alpha negative (avg: {avg_alpha:.4f})",
                metric_value=avg_alpha,
                threshold=0,
            ))
        elif avg_ir < 0.3:
            alerts.append(ValidationAlert(
                check_name="alpha_persistence",
                severity="info",
                message=f"Carhart IR below economic significance threshold (avg IR: {avg_ir:.2f})",
                metric_value=avg_ir,
                threshold=0.3,
            ))

        return alerts

    def run_benchmark_comparison(self) -> list[ValidationAlert]:
        """Compare pipeline performance against benchmark.

        Runs a quick backtest and compares to a zero-excess-return benchmark.
        """
        alerts = []

        start, end = self.loader.get_date_range()
        config = BacktestConfig(
            start_date=start,
            end_date=end,
            fisher_stock_vs_cash="neutral",
        )
        engine = BacktestEngine(self.loader, config)
        result = engine.run()

        if result.metrics.sharpe_ratio < 0:
            alerts.append(ValidationAlert(
                check_name="benchmark_comparison",
                severity="critical",
                message=f"Pipeline Sharpe ratio is negative ({result.metrics.sharpe_ratio:.2f})",
                metric_value=result.metrics.sharpe_ratio,
                threshold=0,
            ))
        elif result.metrics.sharpe_ratio < 0.3:
            alerts.append(ValidationAlert(
                check_name="benchmark_comparison",
                severity="warning",
                message=f"Pipeline Sharpe ratio is low ({result.metrics.sharpe_ratio:.2f})",
                metric_value=result.metrics.sharpe_ratio,
                threshold=0.3,
            ))

        return alerts

    def generate_markdown_report(self, report: Optional[ValidationReport] = None) -> str:
        """Generate a Markdown validation report."""
        if report is None:
            report = self.run_all_checks()

        lines = []
        lines.append("# Claw Quant Validation Report")
        lines.append(f"**Generated:** {report.timestamp}")
        lines.append(f"**Status:** {'✅ Healthy' if report.is_healthy else '❌ Issues Detected'}")
        lines.append("")

        lines.append(f"| Severity | Count |")
        lines.append(f"|----------|-------|")
        for sev in ["critical", "warning", "info"]:
            count = report.metrics.get(sev, 0)
            lines.append(f"| {sev} | {count} |")
        lines.append("")

        if report.alerts:
            lines.append("## Alerts")
            lines.append("")
            for alert in report.alerts:
                icon = {"critical": "🔴", "warning": "🟡", "info": "🔵"}.get(alert.severity, "⚪")
                lines.append(f"- {icon} **[{alert.severity.upper()}]** {alert.check_name}: {alert.message}")
            lines.append("")

        return "\n".join(lines)