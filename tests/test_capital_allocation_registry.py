"""Tests for capital_allocation_registry — ADR-017 §3.

Validates the cross-thesis capital state tracker. This is a state tracker,
NOT a decision maker — capital is fungible and re-enters the framework
normally when released.
"""

from __future__ import annotations

import pytest

from helpers import PROJECT_ROOT, parse_md_yaml

CAR_TEMPLATE = PROJECT_ROOT / "templates" / "capital_allocation_registry_template.md"


class TestTemplateExists:

    def test_file_exists(self):
        assert CAR_TEMPLATE.exists()


class TestRegistrySchema:
    """Behavior: registry tracks aggregate capital state across all theses."""

    @pytest.fixture(scope="class")
    def data(self):
        return parse_md_yaml(CAR_TEMPLATE)

    def test_has_total_capital(self, data):
        assert "total_capital" in data

    def test_has_fisher_max_equity(self, data):
        assert "fisher_max_aggregate_equity" in data

    def test_has_active_theses(self, data):
        assert isinstance(data["active_theses"], list)

    def test_has_available_capital(self, data):
        assert "available_capital" in data

    def test_has_aggregate_equity_exposure(self, data):
        assert "aggregate_equity_exposure" in data

    def test_has_aggregate_cash_exposure(self, data):
        assert "aggregate_cash_exposure" in data
