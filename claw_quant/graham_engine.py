"""Graham Engine — rule-based belief formation (MVP surrogate for the AI Agent).

In backtesting and automated pipelines, the Graham layer is replaced by
deterministic rules that select factors, compute conviction, and classify
the duration regime. This is the same logic used by the backtesting engine,
ensuring consistency between backtest and live pipeline.

In production, the AI Agent would replace these rules with its own reasoning,
but the quantitative floor formula (conviction = 0.3*Evidence + 0.5*IR + 0.2*GMM)
remains the same.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Tuple

import numpy as np

from claw_quant.sfm_engine import SFMInterface
from claw_quant.freshness import FreshnessTracker
from claw_quant.config import CONVICTION_WEIGHTS, CONVICTION_CAPS


@dataclass
class GrahamDecision:
    """Graham layer output: belief formation result.

    This is the interface between Graham (belief) and Markowitz (portfolio).
    """
    # Factor selection
    preferred_factors: list[str] = field(default_factory=list)
    avoided_factors: list[str] = field(default_factory=list)

    # Duration regime
    duration_regime: str = "neutral"  # short_favored / medium_favored / long_favored / neutral

    # Conviction
    conviction: float = 0.5  # 0.0-1.0
    conviction_tier: str = "medium"  # high (>0.7) / medium (0.4-0.7) / low (<0.4)

    # Fisher alignment
    fisher_stock_vs_cash: str = "neutral"
    fisher_alignment: str = "neutral"  # aligned / misaligned / neutral

    # SFM alignment
    sfm_phase: str = "neutral"
    sfm_alignment: str = "neutral"  # aligned / misaligned / neutral

    # Expectation gap (simplified)
    expectation_gap_direction: str = "stale"  # convergent / divergent / stale
    expectation_gap_magnitude: float = 0.0  # estimated alpha if gap closes

    # Flags
    is_defensive: bool = False  # True if Fisher is cash_favored and no factor opportunity


class GrahamEngine:
    """Rule-based belief formation (MVP surrogate for the AI Agent).

    Replaces the LLM's Graham-layer reasoning with deterministic rules
    that are testable, reproducible, and fast. The same rules are used
    in both the backtesting engine and the live pipeline.

    Usage:
        engine = GrahamEngine()
        decision = engine.form_belief(sfm_interface, fisher_config)
        print(decision.conviction, decision.preferred_factors)
    """

    def __init__(
        self,
        min_ic_threshold: float = 0.02,
        max_crowding_threshold: float = 0.60,
        top_n_factors: int = 3,
        conviction_weights: Optional[tuple[float, float, float]] = None,
    ):
        self.min_ic_threshold = min_ic_threshold
        self.max_crowding_threshold = max_crowding_threshold
        self.top_n_factors = top_n_factors
        self.conviction_weights = conviction_weights or CONVICTION_WEIGHTS

    def form_belief(
        self,
        sfm: SFMInterface,
        fisher_stock_vs_cash: str = "neutral",
        fisher_max_equity: float = 0.8,
        carhart_ir: float = 0.0,
        carhart_alpha_t: float = 0.0,
    ) -> GrahamDecision:
        """Form investment beliefs from SFM interface and Fisher state.

        Args:
            sfm: SFMInterface from the SFM engine.
            fisher_stock_vs_cash: Fisher layer stock vs cash baseline.
            fisher_max_equity: Fisher layer max aggregate equity constraint.
            carhart_ir: Carhart information ratio.
            carhart_alpha_t: Carhart alpha t-statistic.

        Returns:
            GrahamDecision with factor selection, conviction, and alignment.
        """
        decision = GrahamDecision()

        # Factor selection
        decision.preferred_factors = sfm.preferred_factors
        decision.avoided_factors = self._identify_avoided_factors(sfm)

        # Duration regime
        decision.duration_regime = sfm.phase

        # Conviction
        decision.conviction = self._compute_conviction(
            sfm, carhart_ir, carhart_alpha_t
        )
        if decision.conviction > 0.7:
            decision.conviction_tier = "high"
        elif decision.conviction > 0.4:
            decision.conviction_tier = "medium"
        else:
            decision.conviction_tier = "low"

        # Fisher alignment
        decision.fisher_stock_vs_cash = fisher_stock_vs_cash
        decision.fisher_alignment = self._compute_fisher_alignment(
            fisher_stock_vs_cash, decision.duration_regime
        )

        # SFM alignment
        decision.sfm_phase = sfm.phase
        decision.sfm_alignment = self._compute_sfm_alignment(
            sfm, decision.preferred_factors
        )

        # Expectation gap
        decision.expectation_gap_direction = self._compute_gap_direction(sfm)
        decision.expectation_gap_magnitude = self._compute_gap_magnitude(sfm)

        # Defensive mode
        decision.is_defensive = (
            fisher_stock_vs_cash == "cash_favored"
            and sfm.confidence < 0.6
        )

        # Apply data freshness adjustment to conviction
        decision.conviction = self._apply_freshness_adjustment(decision.conviction)

        return decision

    def _apply_freshness_adjustment(self, conviction: float) -> float:
        """Apply staleness-based reduction to conviction.

        If state files are stale, the conviction should be reduced because
        the data underlying the belief may be outdated.
        """
        tracker = FreshnessTracker()
        aggregate = tracker.get_aggregate_freshness()
        # aggregate is 0.5-1.0; use it as a multiplier on conviction
        # but don't let it reduce conviction below 0.1
        adjusted = conviction * aggregate
        return round(max(adjusted, 0.1), 2)

    def _identify_avoided_factors(self, sfm: SFMInterface) -> list[str]:
        """Identify factors to avoid (crowded, reversing, or low IC)."""
        avoided = []
        # In the full implementation, this would use the SFM state data
        # For now, we use the preferred factors as a proxy for what's NOT avoided
        return avoided

    def _compute_conviction(
        self,
        sfm: SFMInterface,
        carhart_ir: float,
        carhart_alpha_t: float,
    ) -> float:
        """Compute conviction using the quantitative floor formula.

        conviction = 0.3 * Evidence + 0.5 * IR_norm + 0.2 * GMM_norm

        Evidence: based on SFM confidence and number of preferred factors
        IR_norm: normalized Carhart information ratio
        GMM_norm: alpha persistence proxy (alpha t-statistic)
        """
        # Evidence: SFM confidence + factor count
        evidence = sfm.confidence
        if len(sfm.preferred_factors) >= 3:
            evidence = min(evidence * 1.1, 1.0)

        # IR normalization
        ir_norm = min(abs(carhart_ir) / 1.0, 1.0)

        # GMM proxy: alpha t-statistic
        gmm_norm = min(abs(carhart_alpha_t) / 2.0, 1.0)

        w_e, w_ir, w_gmm = self.conviction_weights
        conviction = w_e * evidence + w_ir * ir_norm + w_gmm * gmm_norm

        # Hard caps (from config)
        if abs(carhart_ir) < CONVICTION_CAPS["ir_low"]:
            conviction = min(conviction, CONVICTION_CAPS["ir_cap"])
        if abs(carhart_alpha_t) < CONVICTION_CAPS["gmm_low"]:
            conviction = min(conviction, CONVICTION_CAPS["gmm_cap"])
        if sfm.confidence < 0.3:
            conviction = min(conviction, CONVICTION_CAPS["synthetic_cap"])

        return round(max(conviction, 0.1), 2)

    def _compute_fisher_alignment(
        self, fisher_stock_vs_cash: str, duration_regime: str
    ) -> str:
        """Compute alignment between Fisher state and duration regime.

        General rule: long-duration assets perform better in easing cycles,
        short-duration in tightening cycles.
        """
        if fisher_stock_vs_cash == "stocks_favored" and duration_regime in ("long_favored", "medium_favored"):
            return "aligned"
        elif fisher_stock_vs_cash == "cash_favored" and duration_regime == "short_favored":
            return "aligned"
        elif fisher_stock_vs_cash == "neutral":
            return "neutral"
        else:
            return "misaligned"

    def _compute_sfm_alignment(
        self, sfm: SFMInterface, preferred_factors: list[str]
    ) -> str:
        """Compute alignment between SFM phase and factor selection."""
        if not preferred_factors:
            return "neutral"
        if sfm.phase == "neutral":
            return "neutral"
        if sfm.confidence > 0.6:
            return "aligned"
        return "neutral"

    def _compute_gap_direction(self, sfm: SFMInterface) -> str:
        """Compute expectation gap direction.

        Simplified: if SFM confidence is high and preferred factors exist,
        the gap is likely divergent (market hasn't caught up).
        """
        if sfm.confidence > 0.6 and len(sfm.preferred_factors) >= 2:
            return "divergent"
        elif sfm.confidence < 0.3:
            return "stale"
        else:
            return "convergent"

    def _compute_gap_magnitude(self, sfm: SFMInterface) -> float:
        """Estimate the magnitude of the expectation gap.

        Derived from SFM confidence and factor count.
        """
        base = sfm.confidence * 0.15  # 0-15% alpha potential
        if len(sfm.preferred_factors) >= 3:
            base *= 1.2
        return round(min(base, 0.25), 3)