"""Metrics tracker — time-series storage of key pipeline metrics.

Tracks key metrics over time in a dedicated SQLite database
(data/validation_metrics.db). Enables trend analysis and threshold monitoring.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime
from typing import Optional

import pandas as pd

from claw_quant.database import get_connection, DBName


class MetricsTracker:
    """Tracks key pipeline metrics over time.

    Usage:
        tracker = MetricsTracker()
        tracker.track("pipeline_sharpe", 0.85)
        tracker.track("max_drawdown", -0.12)
        ts = tracker.get_timeseries("pipeline_sharpe")
    """

    def __init__(self):
        self._init_db()

    def _init_db(self) -> None:
        """Create metrics table if it doesn't exist."""
        conn = get_connection(DBName.VALIDATION)
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    value REAL NOT NULL,
                    date TEXT NOT NULL,
                    recorded_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_metrics_name_date
                ON metrics(name, date)
            """)
            conn.commit()
        finally:
            conn.close()

    def track(self, name: str, value: float, date: Optional[str] = None) -> None:
        """Record a metric value.

        Args:
            name: Metric name (e.g., 'pipeline_sharpe', 'max_drawdown').
            value: Numeric value.
            date: Optional date string. Defaults to today.
        """
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")

        conn = get_connection(DBName.VALIDATION)
        try:
            conn.execute(
                "INSERT INTO metrics (name, value, date) VALUES (?, ?, ?)",
                (name, value, date),
            )
            conn.commit()
        finally:
            conn.close()

    def get_timeseries(self, name: str) -> pd.Series:
        """Retrieve historical values for a metric.

        Returns:
            pd.Series indexed by date.
        """
        conn = get_connection(DBName.VALIDATION)
        try:
            df = pd.read_sql(
                "SELECT date, value FROM metrics WHERE name = ? ORDER BY date",
                conn,
                params=(name,),
            )
            if df.empty:
                return pd.Series(dtype=float)
            df["date"] = pd.to_datetime(df["date"])
            return df.set_index("date")["value"]
        finally:
            conn.close()

    def get_latest(self, name: str) -> Optional[float]:
        """Get the most recent value for a metric."""
        conn = get_connection(DBName.VALIDATION)
        try:
            row = conn.execute(
                "SELECT value FROM metrics WHERE name = ? ORDER BY date DESC LIMIT 1",
                (name,),
            ).fetchone()
            return float(row["value"]) if row else None
        finally:
            conn.close()

    def check_threshold(
        self, name: str, threshold: float, direction: str = "above"
    ) -> bool:
        """Check if the latest metric value crosses a threshold.

        Args:
            name: Metric name.
            threshold: Threshold value.
            direction: 'above' (alert if value > threshold) or
                       'below' (alert if value < threshold).

        Returns:
            True if the threshold is crossed.
        """
        latest = self.get_latest(name)
        if latest is None:
            return False

        if direction == "above":
            return latest > threshold
        else:
            return latest < threshold

    def track_pipeline_metrics(
        self,
        sharpe: float,
        max_dd: float,
        annualized_return: float,
        annualized_vol: float,
        win_rate: float,
        date: Optional[str] = None,
    ) -> None:
        """Record all pipeline performance metrics at once."""
        metrics = {
            "pipeline_sharpe": sharpe,
            "pipeline_max_dd": max_dd,
            "pipeline_annualized_return": annualized_return,
            "pipeline_annualized_vol": annualized_vol,
            "pipeline_win_rate": win_rate,
        }
        for name, value in metrics.items():
            self.track(name, value, date)

    def track_factor_metrics(
        self,
        ic_mean: float,
        crowding_avg: float,
        alpha_t_stat: float,
        date: Optional[str] = None,
    ) -> None:
        """Record factor-level metrics."""
        metrics = {
            "factor_ic_mean": ic_mean,
            "factor_crowding_avg": crowding_avg,
            "alpha_t_stat": alpha_t_stat,
        }
        for name, value in metrics.items():
            self.track(name, value, date)

    def get_summary(self) -> dict:
        """Get a summary of latest values for all tracked metrics."""
        conn = get_connection(DBName.VALIDATION)
        try:
            rows = conn.execute("""
                SELECT name, value, date FROM metrics
                WHERE (name, date) IN (
                    SELECT name, MAX(date) FROM metrics GROUP BY name
                )
            """).fetchall()
            return {row["name"]: {"value": row["value"], "date": row["date"]} for row in rows}
        finally:
            conn.close()