"""Tests for fisher_state.md — Fisher Layer state file.

Validates that fisher_state.md conforms to ADR-011 (Mundell-Fleming / Rey
framework) and ADR-012 (Three-Tier Update Protocol) schema requirements.

The Fisher Layer is the pipeline source (Layer 0). Without it, downstream
layers (SFM, Graham, Markowitz) have no monetary environment input.
"""

from __future__ import annotations

import pytest

from helpers import PROJECT_ROOT, parse_md_yaml

FISHER_STATE_PATH = PROJECT_ROOT / "fisher_state.md"


# ─── Tracer Bullet: file exists and parses ──────────────────────────

class TestFisherStateFileExists:
    """Behavior: fisher_state.md exists at project root (P0 blocker)."""

    def test_file_exists(self):
        assert FISHER_STATE_PATH.exists(), (
            "fisher_state.md is missing — this is the P0 pipeline source. "
            "Downstream layers (SFM, Graham, Markowitz) cannot operate without it."
        )


# ─── Four-Layer Structure (ADR-011) ──────────────────────────────────

class TestFisherStateFourLayers:
    """Behavior: fisher_state.md has the 4-layer structure from ADR-011."""

    @pytest.fixture(scope="class")
    def fisher(self):
        return parse_md_yaml(FISHER_STATE_PATH)

    def test_layer1_global_financial_cycle(self, fisher):
        assert "global_financial_cycle" in fisher, "Layer 1 missing"

    def test_layer2_transmission_channels(self, fisher):
        assert "transmission_channels" in fisher, "Layer 2 missing"

    def test_layer3_a_share_marginal_liquidity(self, fisher):
        assert "a_share_marginal_liquidity" in fisher, "Layer 3 missing"

    def test_layer4_composite_assessment(self, fisher):
        assert "composite_assessment" in fisher, "Layer 4 missing"


# ─── Composite Assessment Output (ADR-011 §Composite Assessment) ─────

class TestCompositeAssessment:
    """Behavior: composite_assessment provides the 5 required output fields
    that downstream thesis files reference via fisher_alignment.
    """

    @pytest.fixture(scope="class")
    def ca(self):
        fs = parse_md_yaml(FISHER_STATE_PATH)
        return fs["composite_assessment"]

    def test_fed_cycle_phase(self, ca):
        assert ca["fed_cycle_phase"] in ("easing", "tightening", "peak", "trough")

    def test_bull_market_conditions_met(self, ca):
        assert isinstance(ca["bull_market_conditions_met"], bool)

    def test_stock_vs_cash_baseline(self, ca):
        assert ca["stock_vs_cash_baseline"] in ("stocks_favored", "cash_favored", "neutral")

    def test_position_constraint_max_equity(self, ca):
        pc = ca["position_constraint"]
        assert "max_aggregate_equity" in pc
        assert 0 <= pc["max_aggregate_equity"] <= 1

    def test_confidence(self, ca):
        assert 0 <= ca["confidence"] <= 1


# ─── Transmission Channels (ADR-011 §Three Channels) ─────────────────

class TestTransmissionChannels:
    """Behavior: three transmission channels are tracked independently."""

    @pytest.fixture(scope="class")
    def channels(self):
        fs = parse_md_yaml(FISHER_STATE_PATH)
        return fs["transmission_channels"]

    def test_cross_border_portfolio(self, channels):
        assert "cross_border_portfolio" in channels

    def test_fx_reserves(self, channels):
        assert "fx_reserves" in channels

    def test_risk_discount(self, channels):
        assert "risk_discount" in channels


# ─── PBoC Modifier (ADR-011 §PBoC as Auxiliary Modifier) ─────────────

class TestPBoCModifier:
    """Behavior: PBoC modifier has coordination_with_fed and
    equity_transmission_efficiency (ADR-011 design decision 4).
    """

    @pytest.fixture(scope="class")
    def pboc(self):
        fs = parse_md_yaml(FISHER_STATE_PATH)
        return fs["a_share_marginal_liquidity"]["pboc_modifier"]

    def test_coordination_with_fed(self, pboc):
        assert pboc["coordination_with_fed"] in ("coordinating", "diverging", "neutral")

    def test_equity_transmission_efficiency(self, pboc):
        assert pboc["equity_transmission_efficiency"] in ("low", "medium", "high")


# ─── Update Protocol (ADR-012) ────────────────────────────────────────

class TestRegimeSurveillanceLog:
    """Behavior: regime_surveillance_log exists (may be empty list)."""

    def test_log_exists(self):
        fs = parse_md_yaml(FISHER_STATE_PATH)
        assert "regime_surveillance_log" in fs
        assert isinstance(fs["regime_surveillance_log"], list)
