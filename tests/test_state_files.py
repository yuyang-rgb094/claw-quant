"""Tests for fisher_state.md and sfm_state.md interface outputs.

Validates that both state files include the ADR-016 Graham Interface Contract
output sections (fisher_interface and sfm_interface), each with 6 fields
and ≤400 token budget.
"""

from __future__ import annotations

import pytest

from helpers import PROJECT_ROOT, parse_md_yaml

FISHER_STATE = PROJECT_ROOT / "fisher_state.md"
SFM_STATE = PROJECT_ROOT / "sfm_state.md"


class TestFisherInterface:
    """Behavior: fisher_state.md outputs fisher_interface (ADR-016 contract)."""

    @pytest.fixture(scope="class")
    def fi(self):
        return parse_md_yaml(FISHER_STATE)["fisher_interface"]

    def test_has_phase(self, fi):
        assert fi["phase"] in ("easing", "tightening", "peak", "trough")

    def test_has_stock_vs_cash(self, fi):
        assert fi["stock_vs_cash"] in ("stocks_favored", "cash_favored", "neutral")

    def test_has_key_signal_1(self, fi):
        assert isinstance(fi["key_signal_1"], str)
        assert len(fi["key_signal_1"]) > 0

    def test_has_key_signal_2(self, fi):
        assert isinstance(fi["key_signal_2"], str)
        assert len(fi["key_signal_2"]) > 0

    def test_has_position_constraint(self, fi):
        assert isinstance(fi["position_constraint"], str)

    def test_has_confidence(self, fi):
        assert 0 <= fi["confidence"] <= 1


class TestSFMInterface:
    """Behavior: sfm_state.md outputs sfm_interface (ADR-016 contract)."""

    @pytest.fixture(scope="class")
    def si(self):
        return parse_md_yaml(SFM_STATE)["sfm_interface"]

    def test_has_phase(self, si):
        assert si["phase"] in ("short_favored", "medium_favored", "long_favored", "neutral")

    def test_has_preferred_factors(self, si):
        assert isinstance(si["preferred_factors"], list)
        assert len(si["preferred_factors"]) <= 3

    def test_has_key_signal_1(self, si):
        assert isinstance(si["key_signal_1"], str)
        assert len(si["key_signal_1"]) > 0

    def test_has_key_signal_2(self, si):
        assert isinstance(si["key_signal_2"], str)
        assert len(si["key_signal_2"]) > 0

    def test_has_gradient_direction(self, si):
        assert isinstance(si["gradient_direction"], str)

    def test_has_confidence(self, si):
        assert 0 <= si["confidence"] <= 1


class TestSFMStateFullModules:
    """Behavior: sfm_state.md has all 4 ADR-014 modules."""

    @pytest.fixture(scope="class")
    def data(self):
        return parse_md_yaml(SFM_STATE)

    def test_has_module_1a_carhart(self, data):
        assert "carhart_baseline" in data

    def test_has_module_1b_duration(self, data):
        assert "factor_duration_spectrum" in data
        assert "short_term" in data["factor_duration_spectrum"]
        assert "medium_term" in data["factor_duration_spectrum"]
        assert "long_term" in data["factor_duration_spectrum"]

    def test_has_module_1c_extended(self, data):
        assert "extended_premia" in data

    def test_has_module_2a_crowding(self, data):
        assert "crowding_by_duration" in data

    def test_has_module_2b_institutional(self, data):
        assert "institutional_constraints" in data

    def test_has_module_2c_transient(self, data):
        assert "transient_anomaly" in data

    def test_has_module_3a_duration_regime(self, data):
        assert "duration_regime" in data

    def test_has_module_3b_forced_movement(self, data):
        assert "forced_movement" in data

    def test_has_module_3c_rotation(self, data):
        assert "rotation_path" in data

    def test_has_module_4_composite(self, data):
        assert "composite_output" in data


class TestPortfolioStateFiles:
    """Behavior: portfolio/ directory has instantiated state files."""

    def test_capital_allocation_registry_exists(self):
        assert (PROJECT_ROOT / "portfolio" / "capital_allocation_registry.md").exists()

    def test_damodaran_state_exists(self):
        assert (PROJECT_ROOT / "portfolio" / "damodaran_state.md").exists()

    def test_car_has_total_capital(self):
        data = parse_md_yaml(PROJECT_ROOT / "portfolio" / "capital_allocation_registry.md")
        assert "total_capital" in data

    def test_damodaran_has_belief_pool(self):
        data = parse_md_yaml(PROJECT_ROOT / "portfolio" / "damodaran_state.md")
        assert "belief_pool" in data

    def test_damodaran_has_7_constraints(self):
        data = parse_md_yaml(PROJECT_ROOT / "portfolio" / "damodaran_state.md")
        assert len(data["constraints"]) == 7


class TestDirectoryStructure:
    """Behavior: project has theses/ and holdings/ directories for runtime files."""

    def test_theses_dir_exists(self):
        assert (PROJECT_ROOT / "theses").is_dir()

    def test_holdings_dir_exists(self):
        assert (PROJECT_ROOT / "holdings").is_dir()

    def test_portfolio_dir_exists(self):
        assert (PROJECT_ROOT / "portfolio").is_dir()


class TestCLAUDEmd:
    """Behavior: CLAUDE.md exists for Agent configuration."""

    def test_exists(self):
        assert (PROJECT_ROOT / "CLAUDE.md").exists()
