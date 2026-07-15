"""Tests for thesis template — ADR-016 Graham Layer Thesis Architecture.

Validates that the thesis template conforms to ADR-016's two-region structure
(Graham Region for belief + Markowitz Region for portfolio) plus ADR-017's
Alpha Capture Schedule expansion.
"""

from __future__ import annotations

import pytest

from helpers import PROJECT_ROOT, parse_md_yaml

THESIS_TEMPLATE = PROJECT_ROOT / "templates" / "thesis_template.md"


class TestThesisTemplateExists:

    def test_file_exists(self):
        assert THESIS_TEMPLATE.exists(), "thesis_template.md missing in templates/"


class TestGrahamRegion:
    """Behavior: Graham Region contains all belief fields (ADR-016)."""

    @pytest.fixture(scope="class")
    def graham(self):
        data = parse_md_yaml(THESIS_TEMPLATE)
        return data["graham_region"]

    def test_has_thesis_type(self, graham):
        assert graham["thesis_type"] in ("growth", "value", "defensive")

    def test_has_duration_bucket(self, graham):
        assert graham["duration_bucket"] in ("short_term", "medium_term", "long_term")

    def test_has_belief_statement(self, graham):
        assert "belief_statement" in graham

    def test_has_key_assumptions(self, graham):
        assert isinstance(graham["key_assumptions"], list)
        assert len(graham["key_assumptions"]) >= 1
        a = graham["key_assumptions"][0]
        assert "id" in a and "assumption" in a and "status" in a

    def test_has_disconfirmation_signals(self, graham):
        assert isinstance(graham["disconfirmation_signals"], list)
        assert len(graham["disconfirmation_signals"]) >= 1

    def test_has_conviction_level(self, graham):
        cl = graham["conviction_level"]
        assert "current" in cl
        assert 0 <= cl["current"] <= 1

    def test_has_expectation_gap(self, graham):
        eg = graham["expectation_gap"]
        assert "direction" in eg
        assert "gap_magnitude" in eg
        assert "gap_type" in eg

    def test_has_fisher_alignment(self, graham):
        fa = graham["fisher_alignment"]
        assert "stock_vs_cash_baseline" in fa
        assert "alignment" in fa

    def test_has_sfm_alignment(self, graham):
        sa = graham["sfm_alignment"]
        assert "duration_regime" in sa
        assert "alignment" in sa


class TestMarkowitzRegion:
    """Behavior: Markowitz Region contains portfolio + risk + alpha capture (ADR-016/017)."""

    @pytest.fixture(scope="class")
    def markowitz(self):
        data = parse_md_yaml(THESIS_TEMPLATE)
        return data["markowitz_region"]

    def test_has_total_allocation(self, markowitz):
        assert "total_allocation" in markowitz

    def test_has_portfolio_composition(self, markowitz):
        pc = markowitz["portfolio_composition"]
        assert isinstance(pc, list)
        assert len(pc) >= 1
        assert "ticker" in pc[0] and "target_weight" in pc[0]

    def test_has_risk_budget(self, markowitz):
        rb = markowitz["risk_budget"]
        assert "conviction_tier" in rb
        assert "effective_risk_budget" in rb

    def test_has_alpha_capture_schedule(self, markowitz):
        acs = markowitz["alpha_capture_schedule"]
        assert "initial_gap_magnitude" in acs
        assert "milestones" in acs

    def test_alpha_capture_has_four_milestones(self, markowitz):
        milestones = markowitz["alpha_capture_schedule"]["milestones"]
        assert len(milestones) == 4
        stages = [m["stage"] for m in milestones]
        assert "alpha_emerging" in stages
        assert "alpha_exhausted" in stages

    def test_alpha_capture_has_residual_position(self, markowitz):
        rp = markowitz["alpha_capture_schedule"]["residual_position"]
        assert "weight" in rp


class TestUpdateLog:
    """Behavior: Update Log section exists (ADR-016 three-layer structure)."""

    def test_has_update_log(self):
        data = parse_md_yaml(THESIS_TEMPLATE)
        assert "update_log" in data
