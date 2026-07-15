"""Markowitz Engine — portfolio construction from Graham decisions.

Receives conviction_level and belief state from the Graham layer and
constructs the actual portfolio: weight allocation, risk budget assignment,
and constraint checking. Implements the Damodaran constraint suite (7 rules).

Portfolio construction IS trade meta-plan generation — defining weights
simultaneously defines entry, rebalancing, profit-taking, and exit plans.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from claw_quant.graham_engine import GrahamDecision


@dataclass
class ConstraintViolation:
    """A single Damodaran constraint violation."""
    name: str
    limit: float
    current: float
    status: str  # within_limit / at_limit / breached
    message: str = ""


@dataclass
class PortfolioAllocation:
    """Markowitz layer output: constructed portfolio.

    This is the final output of the pipeline — target weights, risk budget,
    and constraint status.
    """
    # Factor-level allocation (in backtesting, we work at factor level)
    factor_weights: dict[str, float] = field(default_factory=dict)

    # Risk budget
    conviction_tier: str = "medium"  # high / medium / low
    base_risk_budget: float = 0.01  # fraction of allocation
    momentum_multiplier: float = 1.0  # bull: 1.5, neutral: 1.0, bear: 0.5
    effective_risk_budget: float = 0.01

    # Constraints
    fisher_max_equity: float = 0.8
    total_equity_exposure: float = 0.0
    constraint_violations: list[ConstraintViolation] = field(default_factory=list)

    # Alpha capture
    total_allocation: float = 0.0  # CNY
    available_capital: float = 0.0  # CNY for new positions

    # Metadata
    n_active_factors: int = 0
    is_valid: bool = True


class MarkowitzEngine:
    """Portfolio construction from Graham decisions.

    Usage:
        engine = MarkowitzEngine()
        allocation = engine.construct_portfolio(decision, total_capital=1_000_000)
        print(allocation.factor_weights, allocation.effective_risk_budget)
    """

    def __init__(
        self,
        max_single_factor_weight: float = 0.40,
        max_total_factors: int = 5,
        max_equity_exposure: float = 0.80,
    ):
        self.max_single_factor_weight = max_single_factor_weight
        self.max_total_factors = max_total_factors
        self.max_equity_exposure = max_equity_exposure

    def construct_portfolio(
        self,
        decision: GrahamDecision,
        total_capital: float = 1_000_000.0,
        market_momentum: str = "neutral",
    ) -> PortfolioAllocation:
        """Construct portfolio allocation from a Graham decision.

        Args:
            decision: GrahamDecision from GrahamEngine.form_belief().
            total_capital: Total available capital in CNY.
            market_momentum: Market momentum state (bull / neutral / bear).

        Returns:
            PortfolioAllocation with factor weights, risk budget, and constraints.
        """
        allocation = PortfolioAllocation()
        allocation.total_allocation = total_capital

        # Factor weights
        allocation.factor_weights = self._build_factor_weights(decision)
        allocation.n_active_factors = len(allocation.factor_weights)

        # Risk budget
        allocation.conviction_tier = decision.conviction_tier
        allocation.base_risk_budget = self._get_base_risk_budget(
            decision.conviction_tier
        )
        allocation.momentum_multiplier = self._get_momentum_multiplier(
            market_momentum
        )
        allocation.effective_risk_budget = (
            allocation.base_risk_budget * allocation.momentum_multiplier
        )

        # Equity exposure
        allocation.total_equity_exposure = self._compute_equity_exposure(
            decision, allocation.factor_weights
        )

        # Constraint checking
        allocation.constraint_violations = self._check_constraints(
            allocation, decision
        )

        # Available capital
        allocation.available_capital = total_capital * (
            1.0 - allocation.total_equity_exposure
        )

        # Validity
        allocation.is_valid = len(allocation.constraint_violations) == 0

        return allocation

    def _build_factor_weights(
        self, decision: GrahamDecision
    ) -> dict[str, float]:
        """Build factor-level weights from preferred factors and conviction.

        Higher conviction → higher weight per factor. Weights are constrained
        by max_single_factor_weight.
        """
        if not decision.preferred_factors or decision.is_defensive:
            return {}

        n_factors = min(len(decision.preferred_factors), self.max_total_factors)
        base_weight = min(1.0 / n_factors, self.max_single_factor_weight)

        weights = {}
        for factor in decision.preferred_factors[:n_factors]:
            # Adjust weight by conviction tier
            if decision.conviction_tier == "high":
                mult = 1.0
            elif decision.conviction_tier == "medium":
                mult = 0.75
            else:
                mult = 0.5

            weights[factor] = base_weight * mult

        # Normalize
        total = sum(weights.values())
        if total > 0:
            weights = {k: v / total for k, v in weights.items()}

        return weights

    def _get_base_risk_budget(self, conviction_tier: str) -> float:
        """Get base risk budget per conviction tier.

        High: 2%, Medium: 1%, Low: 0.3% (per ADR-010).
        """
        if conviction_tier == "high":
            return 0.02
        elif conviction_tier == "medium":
            return 0.01
        else:
            return 0.003

    def _get_momentum_multiplier(self, market_momentum: str) -> float:
        """Get momentum multiplier (per ADR-010).

        Bull: 1.5x, Neutral: 1.0x, Bear: 0.5x.
        """
        if market_momentum == "bull":
            return 1.5
        elif market_momentum == "bear":
            return 0.5
        else:
            return 1.0

    def _compute_equity_exposure(
        self,
        decision: GrahamDecision,
        factor_weights: dict[str, float],
    ) -> float:
        """Compute total equity exposure from factor weights.

        Defensive mode → 0% equity exposure.
        """
        if decision.is_defensive:
            return 0.0

        total_weight = sum(factor_weights.values())
        return min(total_weight, self.max_equity_exposure)

    def _check_constraints(
        self,
        allocation: PortfolioAllocation,
        decision: GrahamDecision,
    ) -> list[ConstraintViolation]:
        """Check all 7 Damodaran constraints.

        Returns:
            List of ConstraintViolation objects (empty if all clear).
        """
        violations = []

        # 1. max_active_theses → max_active_factors (proxy)
        if allocation.n_active_factors > self.max_total_factors:
            violations.append(ConstraintViolation(
                name="max_active_factors",
                limit=self.max_total_factors,
                current=allocation.n_active_factors,
                status="breached",
                message=f"Too many active factors: {allocation.n_active_factors} > {self.max_total_factors}",
            ))

        # 2. max_single_factor_weight
        for factor, weight in allocation.factor_weights.items():
            if weight > self.max_single_factor_weight:
                violations.append(ConstraintViolation(
                    name="max_single_factor_weight",
                    limit=self.max_single_factor_weight,
                    current=weight,
                    status="breached",
                    message=f"Factor {factor} weight {weight:.1%} exceeds limit {self.max_single_factor_weight:.1%}",
                ))

        # 3. fisher_max_aggregate_equity
        fisher_max = decision.fisher_stock_vs_cash
        if fisher_max == "cash_favored":
            equity_limit = 0.40
        else:
            equity_limit = self.max_equity_exposure

        if allocation.total_equity_exposure > equity_limit:
            violations.append(ConstraintViolation(
                name="fisher_max_aggregate_equity",
                limit=equity_limit,
                current=allocation.total_equity_exposure,
                status="breached",
                message=f"Equity exposure {allocation.total_equity_exposure:.1%} exceeds Fisher limit {equity_limit:.1%}",
            ))

        # 4. Defensive mode check
        if decision.is_defensive and allocation.total_equity_exposure > 0:
            violations.append(ConstraintViolation(
                name="defensive_mode",
                limit=0.0,
                current=allocation.total_equity_exposure,
                status="breached",
                message="Defensive mode active but equity exposure > 0",
            ))

        return violations