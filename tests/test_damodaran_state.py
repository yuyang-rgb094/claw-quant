"""Tests for damodaran_state — ADR-018 Cross-Section Supervisor.

Validates the cross-section state file: belief pool, holdings pool,
7 constraints, and forward-looking valuation.
"""

from __future__ import annotations

import pytest

from helpers import PROJECT_ROOT, parse_md_yaml

DAMODARAN_TEMPLATE = PROJECT_ROOT / "templates" / "damodaran_state_template.md"


class TestTemplateExists:

    def test_file_exists(self):
        assert DAMODARAN_TEMPLATE.exists()


class TestBeliefPool:
    """Behavior: belief pool tracks total active theses (ADR-018 §3a)."""

    @pytest.fixture(scope="class")
    def bp(self):
        data = parse_md_yaml(DAMODARAN_TEMPLATE)
        return data["belief_pool"]

    def test_has_total_active_theses(self, bp):
        assert "total_active_theses" in bp

    def test_has_max_recommended(self, bp):
        assert bp["max_recommended"] == 5


class TestHoldingsPool:
    """Behavior: holdings pool tracks unique tickers (ADR-018 §3b)."""

    @pytest.fixture(scope="class")
    def hp(self):
        data = parse_md_yaml(DAMODARAN_TEMPLATE)
        return data["holdings_pool"]

    def test_has_total_unique_tickers(self, hp):
        assert "total_unique_tickers" in hp

    def test_has_max_recommended(self, hp):
        assert hp["max_recommended"] == 15


class TestConstraints:
    """Behavior: 7 portfolio constraints defined (ADR-018 §3c)."""

    @pytest.fixture(scope="class")
    def constraints(self):
        data = parse_md_yaml(DAMODARAN_TEMPLATE)
        return data["constraints"]

    def test_has_seven_constraints(self, constraints):
        assert len(constraints) == 7

    EXPECTED_NAMES = {
        "max_active_theses", "max_unique_tickers", "max_single_thesis_weight",
        "max_single_ticker_weight", "max_single_duration_bucket",
        "max_single_sector", "fisher_max_aggregate_equity",
    }

    def test_constraint_names_match(self, constraints):
        names = {c["name"] for c in constraints}
        assert names == self.EXPECTED_NAMES


class TestForwardValuation:
    """Behavior: forward-looking valuation exists (ADR-018 §3d)."""

    def test_has_forward_valuation(self):
        data = parse_md_yaml(DAMODARAN_TEMPLATE)
        assert "forward_valuation" in data
