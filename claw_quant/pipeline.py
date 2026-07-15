"""Pipeline Runner — orchestrates the full SFM → Graham → Markowitz flow.

The main entry point for both live operation and backtesting. Coordinates
the three engines and produces a complete portfolio allocation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from claw_quant.backtest.data_loader import HistoricalDataLoader
from claw_quant.sfm_engine import SFMEngine, SFMInterface
from claw_quant.graham_engine import GrahamEngine, GrahamDecision
from claw_quant.markowitz_engine import MarkowitzEngine, PortfolioAllocation
from claw_quant.walkthrough import WalkThroughEngine, WalkThroughResult


@dataclass
class PipelineOutput:
    """Complete pipeline output for a single date."""
    date: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    # SFM layer
    sfm_interface: Optional[SFMInterface] = None

    # Graham layer
    graham_decision: Optional[GrahamDecision] = None

    # Walk-Through layer (ADR-019) — hard gate between Graham and Markowitz
    walkthrough_result: Optional[WalkThroughResult] = None

    # Markowitz layer
    portfolio: Optional[PortfolioAllocation] = None

    # Summary
    summary: str = ""


class PipelineRunner:
    """Orchestrates the full SFM → Graham → Markowitz pipeline.

    Usage:
        runner = PipelineRunner()
        output = runner.run("2025-06-30")
        print(output.portfolio.factor_weights)
    """

    def __init__(
        self,
        loader: Optional[HistoricalDataLoader] = None,
        min_ic_threshold: float = 0.02,
        max_crowding_threshold: float = 0.60,
        top_n_factors: int = 3,
    ):
        self.loader = loader or HistoricalDataLoader()
        self.sfm = SFMEngine(self.loader)
        self.graham = GrahamEngine(
            min_ic_threshold=min_ic_threshold,
            max_crowding_threshold=max_crowding_threshold,
            top_n_factors=top_n_factors,
        )
        self.markowitz = MarkowitzEngine()
        self.walkthrough = WalkThroughEngine()

    def run(
        self,
        date: str,
        fisher_stock_vs_cash: str = "neutral",
        fisher_max_equity: float = 0.8,
        total_capital: float = 1_000_000.0,
        market_momentum: str = "neutral",
        force_refresh: bool = False,
        thesis_path: Optional[str] = None,
    ) -> PipelineOutput:
        """Run the full pipeline for a single date.

        Args:
            date: Date string in YYYY-MM-DD format.
            fisher_stock_vs_cash: Fisher layer stock vs cash baseline.
            fisher_max_equity: Fisher layer max equity constraint.
            total_capital: Total available capital in CNY.
            market_momentum: Market momentum state (bull / neutral / bear).
            force_refresh: If True, refresh all upstream layers before running.
            thesis_path: Optional path to thesis file for walk-through audit.

        Returns:
            PipelineOutput with all layer outputs.
        """
        if force_refresh:
            from claw_quant.refresh import RefreshManager
            rm = RefreshManager()
            rm.refresh_all()

        output = PipelineOutput(date=date)

        # Step 1: SFM — compute factor manifold state
        output.sfm_interface = self.sfm.get_sfm_interface(
            date,
            fisher_config={
                "stock_vs_cash": fisher_stock_vs_cash,
                "max_equity": fisher_max_equity,
            },
        )

        # Step 2: Graham — form investment beliefs
        state = self.loader.get_daily_state(
            date,
            fisher_config={
                "stock_vs_cash": fisher_stock_vs_cash,
                "max_equity": fisher_max_equity,
            },
        )
        output.graham_decision = self.graham.form_belief(
            output.sfm_interface,
            fisher_stock_vs_cash=fisher_stock_vs_cash,
            fisher_max_equity=fisher_max_equity,
            carhart_ir=state.carhart_information_ratio,
            carhart_alpha_t=state.carhart_alpha_t_stat,
        )

        # Step 3: Walk-Through — audit thesis integrity (hard gate)
        if thesis_path:
            try:
                output.walkthrough_result = self.walkthrough.audit(thesis_path)
                if not output.walkthrough_result.passed:
                    output.summary = self._generate_walkthrough_failure_summary(output)
                    return output
            except FileNotFoundError:
                pass  # Thesis doesn't exist yet, skip audit

        # Step 4: Markowitz — construct portfolio
        output.portfolio = self.markowitz.construct_portfolio(
            output.graham_decision,
            total_capital=total_capital,
            market_momentum=market_momentum,
        )

        # Step 5: Generate summary
        output.summary = self._generate_summary(output)

        return output

    def _generate_summary(self, output: PipelineOutput) -> str:
        """Generate a human-readable summary of the pipeline output."""
        sfm = output.sfm_interface
        graham = output.graham_decision
        portfolio = output.portfolio

        if not sfm or not graham or not portfolio:
            return "Pipeline output incomplete"

        lines = []
        lines.append(f"## Pipeline Summary — {output.date}")
        lines.append("")
        lines.append(f"**SFM Phase:** {sfm.phase} (confidence: {sfm.confidence})")
        lines.append(f"**Preferred Factors:** {', '.join(sfm.preferred_factors) if sfm.preferred_factors else 'none'}")
        lines.append(f"**Gradient:** {sfm.gradient_direction}")
        lines.append("")
        lines.append(f"**Conviction:** {graham.conviction} ({graham.conviction_tier})")
        lines.append(f"**Duration Regime:** {graham.duration_regime}")
        lines.append(f"**Fisher Alignment:** {graham.fisher_alignment}")
        lines.append(f"**SFM Alignment:** {graham.sfm_alignment}")
        lines.append(f"**Defensive Mode:** {'YES' if graham.is_defensive else 'no'}")
        lines.append("")
        if portfolio.factor_weights:
            lines.append("**Factor Weights:**")
            for factor, weight in portfolio.factor_weights.items():
                lines.append(f"  - {factor}: {weight:.1%}")
        else:
            lines.append("**Factor Weights:** none (cash position)")
        lines.append(f"**Risk Budget:** {portfolio.effective_risk_budget:.1%} "
                     f"(base: {portfolio.base_risk_budget:.1%} × "
                     f"momentum: {portfolio.momentum_multiplier}x)")
        lines.append(f"**Equity Exposure:** {portfolio.total_equity_exposure:.1%}")

        if portfolio.constraint_violations:
            lines.append("")
            lines.append("**⚠️ Constraint Violations:**")
            for v in portfolio.constraint_violations:
                lines.append(f"  - {v.name}: {v.message}")

        lines.append(f"**Valid:** {'✅' if portfolio.is_valid else '❌'}")

        return "\n".join(lines)

    def _generate_walkthrough_failure_summary(self, output: PipelineOutput) -> str:
        """Generate summary when walk-through audit fails."""
        wr = output.walkthrough_result
        if not wr:
            return "Walk-through audit skipped"

        lines = []
        lines.append(f"## Pipeline Blocked — Walk-Through Audit Failed — {output.date}")
        lines.append("")
        lines.append(f"**Thesis:** {wr.thesis_name}")
        lines.append(f"**Status:** ❌ FAILED — {len(wr.violations)} BLOCKING violations")
        lines.append("")

        if wr.violations:
            lines.append("### BLOCKING Violations (must fix before proceeding)")
            for v in wr.violations:
                lines.append(f"  - **[{v.dimension}]** {v.description}")
                if v.fix_suggestion:
                    lines.append(f"    → Fix: {v.fix_suggestion}")

        if wr.warnings:
            lines.append("")
            lines.append("### Warnings")
            for w in wr.warnings:
                lines.append(f"  - {w}")

        lines.append("")
        lines.append("**Action:** Fix all BLOCKING violations and re-run the pipeline.")
        lines.append(f"*Full audit trail available in walk-through report.*")

        return "\n".join(lines)