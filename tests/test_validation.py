"""Tests for the validation loop and metrics tracker."""

from __future__ import annotations

import pytest

from claw_quant.validation_loop import ValidationLoop, ValidationAlert, ValidationReport
from claw_quant.metrics_tracker import MetricsTracker
from claw_quant.validation import (
    stability_check,
    factor_rotation_frequency,
    compare_to_benchmark,
)


class TestValidationLoop:
    """Behavior: validation loop runs checks without errors."""

    @pytest.fixture(scope="module")
    def loop(self):
        return ValidationLoop()

    def test_run_all_checks_returns_report(self, loop):
        report = loop.run_all_checks()
        assert isinstance(report, ValidationReport)

    def test_report_has_timestamp(self, loop):
        report = loop.run_all_checks()
        assert report.timestamp is not None

    def test_ic_decay_check_returns_list(self, loop):
        alerts = loop.run_ic_decay_check()
        assert isinstance(alerts, list)

    def test_crowding_surge_check_returns_list(self, loop):
        alerts = loop.run_crowding_surge_check()
        assert isinstance(alerts, list)

    def test_alpha_persistence_check_returns_list(self, loop):
        alerts = loop.run_alpha_persistence_check()
        assert isinstance(alerts, list)

    def test_benchmark_comparison_returns_list(self, loop):
        alerts = loop.run_benchmark_comparison()
        assert isinstance(alerts, list)

    def test_generate_report_returns_string(self, loop):
        report = loop.run_all_checks()
        md = loop.generate_markdown_report(report)
        assert isinstance(md, str)
        assert "Claw Quant Validation Report" in md


class TestMetricsTracker:
    """Behavior: metrics tracker stores and retrieves values."""

    @pytest.fixture(scope="function")
    def tracker(self):
        return MetricsTracker()

    def test_track_and_retrieve(self, tracker):
        tracker.track("test_metric_1", 0.85, "2025-01-15")
        ts = tracker.get_timeseries("test_metric_1")
        assert len(ts) > 0
        assert ts.iloc[-1] == 0.85

    def test_get_latest(self, tracker):
        tracker.track("test_metric_2", 0.90, "2025-01-16")
        latest = tracker.get_latest("test_metric_2")
        assert latest == 0.90

    def test_check_threshold_above(self, tracker):
        tracker.track("test_metric_3", 0.95, "2025-01-17")
        assert tracker.check_threshold("test_metric_3", 0.90, "above")
        assert not tracker.check_threshold("test_metric_3", 1.0, "above")

    def test_check_threshold_below(self, tracker):
        tracker.track("test_metric_4", 0.10, "2025-01-18")
        assert tracker.check_threshold("test_metric_4", 0.20, "below")
        assert not tracker.check_threshold("test_metric_4", 0.05, "below")

    def test_track_pipeline_metrics(self, tracker):
        tracker.track_pipeline_metrics(0.85, -0.12, 0.15, 0.20, 0.55)
        assert tracker.get_latest("pipeline_sharpe") == 0.85
        assert tracker.get_latest("pipeline_max_dd") == -0.12

    def test_track_factor_metrics(self, tracker):
        tracker.track_factor_metrics(0.03, 0.35, 2.1)
        assert tracker.get_latest("factor_ic_mean") == 0.03
        assert tracker.get_latest("factor_crowding_avg") == 0.35

    def test_get_summary(self, tracker):
        tracker.track("test_metric_5", 0.50, "2025-01-19")
        summary = tracker.get_summary()
        assert "test_metric_5" in summary


class TestValidationUtilities:
    """Behavior: validation utility functions work correctly."""

    def test_stability_check_no_change(self):
        weights = {"a": 0.5, "b": 0.5}
        prev = {"a": 0.5, "b": 0.5}
        assert stability_check(weights, prev) == 1.0

    def test_stability_check_full_change(self):
        weights = {"a": 1.0}
        prev = {"b": 1.0}
        assert stability_check(weights, prev) == 0.0

    def test_stability_check_partial_change(self):
        weights = {"a": 0.7, "b": 0.3}
        prev = {"a": 0.5, "b": 0.5}
        stability = stability_check(weights, prev)
        assert 0.0 < stability < 1.0

    def test_factor_rotation_frequency_no_change(self):
        selections = [["a", "b"], ["a", "b"], ["a", "b"]]
        assert factor_rotation_frequency(selections) == 0.0

    def test_factor_rotation_frequency_all_change(self):
        selections = [["a"], ["b"], ["c"]]
        assert factor_rotation_frequency(selections) == 1.0

    def test_factor_rotation_frequency_single_period(self):
        selections = [["a", "b"]]
        assert factor_rotation_frequency(selections) == 0.0

    def test_compare_to_benchmark(self):
        import numpy as np
        import pandas as pd

        dates = pd.date_range("2024-01-01", periods=100)
        pr = pd.Series(np.random.normal(0.001, 0.01, 100), index=dates)
        br = pd.Series(np.random.normal(0.0005, 0.008, 100), index=dates)

        comparison = compare_to_benchmark(pr, br)
        assert comparison is not None
        assert comparison.correlation is not None