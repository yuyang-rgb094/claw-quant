"""Agent Interface — single point of contact between AI Agent and computation.

The AI Agent NEVER calls scripts directly. It always goes through this
interface. The interface handles all computation (factor computation,
state updates, backtesting); the Agent handles belief formation (Graham layer).

This directly addresses the "agent cognitive overload" issue by:
- Reducing Fisher + SFM to a combined ≤800 token compressed interface
- Automating all script execution behind a single method call
- Providing pre-computed factor recommendations and constraint checks
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from claw_quant.config import PROJECT_ROOT
from claw_quant.backtest.data_loader import HistoricalDataLoader
from claw_quant.backtest.engine import BacktestConfig, BacktestEngine
from claw_quant.backtest.report import generate_report, generate_summary
from claw_quant.sfm_engine import SFMEngine, SFMInterface
from claw_quant.graham_engine import GrahamEngine, GrahamDecision
from claw_quant.markowitz_engine import MarkowitzEngine, PortfolioAllocation
from claw_quant.pipeline import PipelineRunner, PipelineOutput
from claw_quant.walkthrough import WalkThroughEngine, WalkThroughResult
from claw_quant.fisher_automation import FisherStateUpdater
from claw_quant.scheduler import Scheduler
from claw_quant.refresh import RefreshManager

logger = logging.getLogger("claw_quant.agent_interface")


class AgentInterface:
    """Single entry point for the AI Agent to interact with the computation layer.

    The Agent should:
    1. Read fisher_summary and sfm_summary (each ≤400 tokens, 6 fields)
    2. Read factor_recommendations for pre-computed factor preferences
    3. Form investment beliefs (Graham layer — Agent's job)
    4. Call constraint_check to validate any proposed thesis
    5. Call run_weekly_update to refresh all state files

    The Agent should NOT:
    - Run any Python scripts directly
    - Compute factors or Carhart regressions
    - Look at raw SQLite data
    - Update state files manually

    Usage:
        ai = AgentInterface()
        print(ai.get_fisher_summary())
        print(ai.get_sfm_summary())
        print(ai.get_factor_recommendations())
        ai.run_weekly_update()
    """

    def __init__(self):
        self.loader = HistoricalDataLoader()
        self.sfm = SFMEngine(self.loader)
        self.graham = GrahamEngine()
        self.markowitz = MarkowitzEngine()
        self.pipeline = PipelineRunner(self.loader)
        self.fisher = FisherStateUpdater()
        self.scheduler = Scheduler()
        self.refresh_mgr = RefreshManager()
        self.walkthrough = WalkThroughEngine()

    # ------------------------------------------------------------------
    # Read-only summaries (what the Agent reads)
    # ------------------------------------------------------------------

    def get_fisher_summary(self, auto_refresh: bool = True) -> dict:
        """Return the Fisher interface (6 fields, ≤400 tokens).

        The Agent reads this to understand the monetary environment.

        Args:
            auto_refresh: If True (default), checks and refreshes stale
                layers before returning data.
        """
        if auto_refresh:
            self.refresh_mgr.check_and_refresh()
        return self.fisher.get_fisher_interface()

    def get_sfm_summary(self, date: Optional[str] = None) -> dict:
        """Return the SFM interface (6 fields, ≤400 tokens).

        The Agent reads this to understand the factor manifold state.

        Args:
            date: Optional date override. Defaults to today.
        """
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")

        interface = self.sfm.get_sfm_interface(date)
        return {
            "phase": interface.phase,
            "preferred_factors": interface.preferred_factors,
            "key_signal_1": interface.key_signal_1,
            "key_signal_2": interface.key_signal_2,
            "gradient_direction": interface.gradient_direction,
            "confidence": interface.confidence,
        }

    def get_factor_recommendations(self) -> dict:
        """Return pre-computed factor recommendations.

        Includes preferred factors, avoided factors, crowding warnings,
        and duration regime assessment. The Agent uses this to form
        investment beliefs.
        """
        date = datetime.now().strftime("%Y-%m-%d")
        state = self.loader.get_daily_state(date)
        interface = self.sfm.get_sfm_interface(date)

        # Preferred factors
        preferred = interface.preferred_factors

        # Avoided factors (crowded or reversing)
        avoided = []
        for factor, crowding in state.crowding_score.items():
            if crowding > 0.6:
                avoided.append({
                    "factor": factor,
                    "reason": f"crowded ({crowding:.2f})",
                })
        for factor, decay in state.factor_decay_status.items():
            if decay == "reversing" and factor not in [a["factor"] for a in avoided]:
                avoided.append({
                    "factor": factor,
                    "reason": "IC reversing",
                })

        # Duration regime
        regime = interface.phase

        # Carhart baseline summary
        carhart = {
            "alpha": state.carhart_alpha,
            "alpha_t_stat": state.carhart_alpha_t_stat,
            "r_squared": state.carhart_r_squared,
            "information_ratio": state.carhart_information_ratio,
            "betas": state.carhart_betas,
        }

        return {
            "date": date,
            "preferred_factors": preferred,
            "avoided_factors": avoided,
            "duration_regime": regime,
            "sfm_confidence": interface.confidence,
            "gradient_direction": interface.gradient_direction,
            "carhart_baseline": carhart,
            "crowding_alerts": [
                {"factor": f, "score": s}
                for f, s in state.crowding_score.items()
                if s > 0.5
            ],
        }

    def get_constraint_check(
        self,
        preferred_factors: list[str],
        conviction_tier: str = "medium",
        fisher_stock_vs_cash: str = "neutral",
        total_capital: float = 1_000_000.0,
    ) -> dict:
        """Check Damodaran constraints for a proposed thesis.

        The Agent calls this before finalizing any investment decision.

        Args:
            preferred_factors: List of factors the thesis targets.
            conviction_tier: high / medium / low.
            fisher_stock_vs_cash: Fisher layer baseline.
            total_capital: Total capital in CNY.

        Returns:
            Dict with constraint status and any violations.
        """
        decision = GrahamDecision(
            preferred_factors=preferred_factors,
            conviction_tier=conviction_tier,
            fisher_stock_vs_cash=fisher_stock_vs_cash,
        )
        allocation = self.markowitz.construct_portfolio(
            decision, total_capital=total_capital
        )

        return {
            "is_valid": allocation.is_valid,
            "n_active_factors": allocation.n_active_factors,
            "equity_exposure": allocation.total_equity_exposure,
            "effective_risk_budget": allocation.effective_risk_budget,
            "violations": [
                {
                    "name": v.name,
                    "limit": v.limit,
                    "current": v.current,
                    "message": v.message,
                }
                for v in allocation.constraint_violations
            ],
        }

    # ------------------------------------------------------------------
    # Walk-Through Audit (ADR-019) — hallucination prevention gate
    # ------------------------------------------------------------------

    def walkthrough_check(self, thesis_path: str) -> dict:
        """Run the walk-through audit on a thesis file.

        This is a HARD GATE — if the audit fails, the thesis CANNOT
        proceed to Markowitz. The Agent MUST call this before executing
        any thesis.

        The walk-through layer checks 7 dimensions:
            A. Factor Provenance — factors match SFM output
            B. Conviction Audit — Bayesian adjustment cap enforced
            C. Claim Verification — quantitative claims sanity-checked
            D. Disconfirmation Testability — signals must be falsifiable
            E. Ticker & Universe Validity — tickers exist in universe
            F. Cross-Reference Consistency — no internal contradictions
            G. Source Traceability — [FACT] tags traceable to sources

        Args:
            thesis_path: Path to the thesis .md file.

        Returns:
            Dict with pass/fail status, violations, and full audit trail.
        """
        result = self.walkthrough.audit(thesis_path)
        return {
            "passed": result.passed,
            "thesis_name": result.thesis_name,
            "thesis_hash": result.thesis_hash,
            "violations": [
                {
                    "dimension": v.dimension,
                    "severity": v.severity,
                    "check_name": v.check_name,
                    "description": v.description,
                    "fix_suggestion": v.fix_suggestion,
                }
                for v in result.violations
            ],
            "warnings": result.warnings,
            "audit_trail": result.audit_trail,
            "dimensions": {
                "factor_provenance": result.factor_provenance.passed,
                "conviction_audit": result.conviction_audit.passed,
                "claim_verification": result.claim_verification.passed,
                "disconfirmation_testability": result.disconfirmation_testability.passed,
                "ticker_validity": result.ticker_validity.passed,
                "cross_reference": result.cross_reference.passed,
                "source_traceability": result.source_traceability.passed,
            },
        }

    # ------------------------------------------------------------------
    # Actions (what the Agent triggers)
    # ------------------------------------------------------------------

    def run_weekly_update(self) -> dict:
        """Run all weekly computation tasks and update state files.

        This is the main automation entry point. The Agent calls this
        once per week (or when needed) to refresh all state.

        Returns:
            Dict with results for each task.
        """
        logger.info("Agent triggered weekly update")
        return self.scheduler.run_weekly()

    def run_daily_update(self) -> dict:
        """Run daily computation tasks."""
        logger.info("Agent triggered daily update")
        return self.scheduler.run_daily()

    def run_pipeline(
        self,
        date: Optional[str] = None,
        fisher_stock_vs_cash: str = "neutral",
        total_capital: float = 1_000_000.0,
    ) -> dict:
        """Run the full pipeline for a single date.

        Args:
            date: Date string. Defaults to today.
            fisher_stock_vs_cash: Fisher baseline.
            total_capital: Total capital.

        Returns:
            Pipeline output as a dict.
        """
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")

        output = self.pipeline.run(
            date,
            fisher_stock_vs_cash=fisher_stock_vs_cash,
            total_capital=total_capital,
        )

        return {
            "date": output.date,
            "sfm_phase": output.sfm_interface.phase if output.sfm_interface else "unknown",
            "preferred_factors": output.sfm_interface.preferred_factors if output.sfm_interface else [],
            "conviction": output.graham_decision.conviction if output.graham_decision else 0.0,
            "conviction_tier": output.graham_decision.conviction_tier if output.graham_decision else "low",
            "factor_weights": output.portfolio.factor_weights if output.portfolio else {},
            "risk_budget": output.portfolio.effective_risk_budget if output.portfolio else 0.0,
            "is_valid": output.portfolio.is_valid if output.portfolio else False,
            "summary": output.summary,
        }

    def run_backtest(
        self,
        start_date: str,
        end_date: str,
        fisher_stock_vs_cash: str = "neutral",
        output_path: Optional[str] = None,
    ) -> dict:
        """Run a backtest and return the summary.

        Args:
            start_date: Backtest start date (YYYY-MM-DD).
            end_date: Backtest end date (YYYY-MM-DD).
            fisher_stock_vs_cash: Fisher baseline for the backtest period.
            output_path: Optional path for the full report.

        Returns:
            Dict with key metrics and report path.
        """
        config = BacktestConfig(
            start_date=start_date,
            end_date=end_date,
            fisher_stock_vs_cash=fisher_stock_vs_cash,
        )
        engine = BacktestEngine(self.loader, config)
        result = engine.run()

        if output_path is None:
            output_path = str(
                PROJECT_ROOT / "data" / f"backtest_{start_date}_{end_date}.md"
            )

        report = generate_report(result, output_path=output_path)
        summary = generate_summary(result)

        return {
            "summary": summary,
            "report_path": output_path,
            "sharpe_ratio": result.metrics.sharpe_ratio,
            "annualized_return": result.metrics.annualized_return,
            "max_drawdown": result.metrics.max_drawdown,
            "win_rate": result.metrics.win_rate,
            "calmar_ratio": result.metrics.calmar_ratio,
            "n_trading_days": result.metrics.n_trading_days,
            "oos_sharpe": result.oos_metrics.sharpe_ratio if result.oos_metrics else None,
        }

    def snapshot_fisher(self) -> str:
        """Create a Fisher state snapshot for historical record.

        Returns:
            Path to the snapshot file.
        """
        path = self.fisher.snapshot()
        return str(path)

    # ------------------------------------------------------------------
    # Refresh management
    # ------------------------------------------------------------------

    def get_refresh_status(self) -> dict:
        """Get the refresh status of all layers.

        Returns:
            Dict mapping layer name to status info.
        """
        statuses = self.refresh_mgr.get_all_status()
        return {
            layer: {
                "freshness": s.freshness,
                "last_refreshed": s.last_refreshed.isoformat() if s.last_refreshed else None,
                "pending_cascade": s.pending_cascade,
                "cascade_from": s.cascade_from,
                "refresh_count": s.refresh_count,
            }
            for layer, s in statuses.items()
        }

    def refresh_layer(self, layer: str) -> dict:
        """Manually trigger a refresh of a specific layer.

        The cascade rules will automatically trigger downstream layers
        if the refresh causes a direction change.

        Args:
            layer: Layer name (fisher/sfm/graham/markowitz/damodaran).

        Returns:
            Dict with refresh result.
        """
        result = self.refresh_mgr.refresh(layer, trigger="manual")
        return {
            "layer": result.layer,
            "success": result.success,
            "trigger": result.trigger,
            "direction_changed": result.direction_changed,
            "cascade_triggered": result.cascade_triggered,
            "message": result.message,
        }

    def refresh_all(self) -> dict:
        """Force-refresh all layers in order.

        Returns:
            Dict mapping layer name to success status.
        """
        results = self.refresh_mgr.refresh_all()
        return {
            layer: {"success": r.success, "message": r.message}
            for layer, r in results.items()
        }

    def check_and_refresh(self) -> dict:
        """Auto-check and refresh stale layers.

        Returns:
            Dict with refresh results.
        """
        results = self.refresh_mgr.check_and_refresh()
        return {
            layer: {"success": r.success, "message": r.message}
            for layer, r in results.items()
        }