"""Tests for the MVP pipeline (SFM → Graham → Markowitz)."""

from __future__ import annotations

import pytest

from claw_quant.sfm_engine import SFMEngine, SFMInterface
from claw_quant.graham_engine import GrahamEngine, GrahamDecision
from claw_quant.markowitz_engine import MarkowitzEngine, PortfolioAllocation
from claw_quant.pipeline import PipelineRunner, PipelineOutput


class TestSFMEngine:
    """Behavior: SFM engine produces valid interface."""

    @pytest.fixture(scope="module")
    def engine(self):
        return SFMEngine()

    def test_get_sfm_interface_returns_interface(self, engine):
        interface = engine.get_sfm_interface("2025-01-15")
        assert isinstance(interface, SFMInterface)

    def test_interface_has_6_fields(self, engine):
        interface = engine.get_sfm_interface("2025-01-15")
        # Check all 6 fields exist
        assert interface.phase is not None
        assert isinstance(interface.preferred_factors, list)
        assert isinstance(interface.key_signal_1, str)
        assert isinstance(interface.key_signal_2, str)
        assert isinstance(interface.gradient_direction, str)
        assert isinstance(interface.confidence, float)

    def test_confidence_between_0_and_1(self, engine):
        interface = engine.get_sfm_interface("2025-01-15")
        assert 0.0 <= interface.confidence <= 1.0

    def test_phase_is_valid_enum(self, engine):
        interface = engine.get_sfm_interface("2025-01-15")
        valid_phases = {"short_favored", "medium_favored", "long_favored", "neutral"}
        assert interface.phase in valid_phases


class TestGrahamEngine:
    """Behavior: Graham engine produces valid decision."""

    @pytest.fixture(scope="module")
    def engine(self):
        return GrahamEngine()

    @pytest.fixture(scope="module")
    def sfm_interface(self):
        return SFMInterface(
            phase="long_favored",
            preferred_factors=["12m_momentum", "value"],
            key_signal_1="IC(12m_momentum)=0.035 HL=70d (stable)",
            key_signal_2="crowding 0.30 (low)",
            gradient_direction="flowing_to_long",
            confidence=0.65,
        )

    def test_form_belief_returns_decision(self, engine, sfm_interface):
        decision = engine.form_belief(sfm_interface)
        assert isinstance(decision, GrahamDecision)

    def test_conviction_between_0_and_1(self, engine, sfm_interface):
        decision = engine.form_belief(sfm_interface)
        assert 0.0 <= decision.conviction <= 1.0

    def test_conviction_tier_is_valid(self, engine, sfm_interface):
        decision = engine.form_belief(sfm_interface)
        assert decision.conviction_tier in {"high", "medium", "low"}

    def test_preferred_factors_preserved(self, engine, sfm_interface):
        decision = engine.form_belief(sfm_interface)
        assert decision.preferred_factors == ["12m_momentum", "value"]

    def test_defensive_mode_when_cash_favored(self, engine, sfm_interface):
        decision = engine.form_belief(
            sfm_interface,
            fisher_stock_vs_cash="cash_favored",
        )
        # With cash_favored and SFM confidence < 0.6, should be defensive
        # But our SFM has confidence 0.65, so not defensive
        # Test with low confidence
        low_sfm = SFMInterface(
            phase="neutral",
            preferred_factors=[],
            confidence=0.2,
        )
        decision = engine.form_belief(
            low_sfm,
            fisher_stock_vs_cash="cash_favored",
        )
        assert decision.is_defensive

    def test_fisher_alignment_computed(self, engine, sfm_interface):
        decision = engine.form_belief(
            sfm_interface,
            fisher_stock_vs_cash="stocks_favored",
        )
        assert decision.fisher_alignment in {"aligned", "misaligned", "neutral"}


class TestMarkowitzEngine:
    """Behavior: Markowitz engine produces valid portfolio."""

    @pytest.fixture(scope="module")
    def engine(self):
        return MarkowitzEngine()

    def test_construct_portfolio_returns_allocation(self, engine):
        decision = GrahamDecision(
            preferred_factors=["12m_momentum", "value"],
            conviction_tier="high",
        )
        allocation = engine.construct_portfolio(decision)
        assert isinstance(allocation, PortfolioAllocation)

    def test_high_conviction_gives_larger_risk_budget(self, engine):
        decision_high = GrahamDecision(
            preferred_factors=["12m_momentum"],
            conviction_tier="high",
        )
        decision_low = GrahamDecision(
            preferred_factors=["12m_momentum"],
            conviction_tier="low",
        )
        high_alloc = engine.construct_portfolio(decision_high)
        low_alloc = engine.construct_portfolio(decision_low)
        assert high_alloc.effective_risk_budget > low_alloc.effective_risk_budget

    def test_defensive_mode_zero_equity(self, engine):
        decision = GrahamDecision(
            preferred_factors=[],
            is_defensive=True,
        )
        allocation = engine.construct_portfolio(decision)
        assert allocation.total_equity_exposure == 0.0
        assert len(allocation.factor_weights) == 0

    def test_constraints_checked(self, engine):
        """Weight constraints should be enforced — check via violation list."""
        decision = GrahamDecision(
            preferred_factors=["f1"],
            conviction_tier="high",
        )
        # Use a very low max_single_factor_weight to trigger violation
        engine_strict = MarkowitzEngine(max_single_factor_weight=0.10)
        allocation = engine_strict.construct_portfolio(decision)
        # With max_single=0.10 and 1 factor at 100%, should have violation
        assert not allocation.is_valid

    def test_momentum_multiplier_applied(self, engine):
        decision = GrahamDecision(
            preferred_factors=["12m_momentum"],
            conviction_tier="high",
        )
        bull_alloc = engine.construct_portfolio(decision, market_momentum="bull")
        bear_alloc = engine.construct_portfolio(decision, market_momentum="bear")
        assert bull_alloc.effective_risk_budget > bear_alloc.effective_risk_budget


class TestPipelineRunner:
    """Behavior: pipeline orchestrates all layers correctly."""

    @pytest.fixture(scope="module")
    def runner(self):
        return PipelineRunner()

    def test_run_returns_pipeline_output(self, runner):
        output = runner.run("2025-01-15")
        assert isinstance(output, PipelineOutput)

    def test_output_has_all_layers(self, runner):
        output = runner.run("2025-01-15")
        assert output.sfm_interface is not None
        assert output.graham_decision is not None
        assert output.portfolio is not None

    def test_summary_generated(self, runner):
        output = runner.run("2025-01-15")
        assert output.summary is not None
        assert "Pipeline Summary" in output.summary

    def test_data_flow_sfm_to_graham(self, runner):
        output = runner.run("2025-01-15")
        # Graham decision should reflect SFM interface
        assert output.graham_decision.sfm_phase == output.sfm_interface.phase

    def test_data_flow_graham_to_markowitz(self, runner):
        output = runner.run("2025-01-15")
        # Markowitz portfolio should reflect Graham decision
        assert output.portfolio.conviction_tier == output.graham_decision.conviction_tier