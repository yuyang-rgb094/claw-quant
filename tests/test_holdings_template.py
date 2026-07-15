"""Tests for holdings template — ADR-017 Holdings File Schema.

Validates that the holdings template is a pure execution record with NO
belief fields (belief-action separation, ADR-009 Principle 1 / ADR-017 §4).
"""

from __future__ import annotations

import pytest

from helpers import PROJECT_ROOT, parse_md_yaml

HOLDINGS_TEMPLATE = PROJECT_ROOT / "templates" / "holdings_template.yaml"


class TestHoldingsTemplateExists:

    def test_file_exists(self):
        assert HOLDINGS_TEMPLATE.exists()


class TestHoldingsSchema:
    """Behavior: holdings file records execution, not beliefs (ADR-017 §4)."""

    @pytest.fixture(scope="class")
    def data(self):
        return parse_md_yaml(HOLDINGS_TEMPLATE)

    def test_has_holding_id(self, data):
        assert "holding_id" in data

    def test_has_ticker(self, data):
        assert "ticker" in data

    def test_has_thesis_refs(self, data):
        assert isinstance(data["thesis_refs"], list)
        assert len(data["thesis_refs"]) >= 1
        ref = data["thesis_refs"][0]
        assert "thesis" in ref and "role_in_thesis" in ref

    def test_has_entry_fields(self, data):
        assert "entry_date" in data
        assert "entry_price" in data
        assert "entry_quantity" in data

    def test_has_position_state(self, data):
        assert data["position_state"] in ("open", "reduced", "closed")

    def test_has_execution_log(self, data):
        assert isinstance(data["execution_log"], list)

    def test_has_risk_budget_fields(self, data):
        assert "risk_budget_assigned" in data
        assert "risk_budget_consumed" in data
        assert "risk_budget_remaining" in data


class TestNoBeliefFields:
    """Behavior: holdings file contains NO belief fields (ADR-017 §4).

    Conviction, key_assumptions, disconfirmation_signals, expectation_gap,
    consensus_catalyst all live in the thesis file Graham Region.
    """

    @pytest.fixture(scope="class")
    def data(self):
        return parse_md_yaml(HOLDINGS_TEMPLATE)

    BELIEF_FIELDS = [
        "conviction_level", "key_assumptions", "disconfirmation_signals",
        "expectation_gap", "consensus_catalyst", "market_consensus",
        "belief_statement",
    ]

    @pytest.mark.parametrize("field", BELIEF_FIELDS)
    def test_no_belief_field(self, data, field):
        assert field not in data, (
            f"{field} is a belief field — must live in thesis file Graham Region, "
            f"not in holdings file (ADR-017 §4 belief-action separation)"
        )
