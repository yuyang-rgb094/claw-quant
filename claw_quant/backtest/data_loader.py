"""Historical data loader for the Claw Quant backtesting engine.

Reads all 4 SQLite databases and returns time-aligned DataFrames.
Provides `get_daily_state(date)` — a composite snapshot of all available
signals for a single trading day, used by the BacktestEngine to replay
historical decision-making.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

import numpy as np
import pandas as pd

from claw_quant.database import get_connection, DBName


@dataclass
class DailyState:
    """Composite snapshot of all available signals for a single date.

    This is the historical equivalent of what the AI Agent would read
    from fisher_state.md and sfm_state.md at that point in time.
    """
    date: str  # YYYY-MM-DD

    # Carhart regression (from the most recent window ending on this date)
    carhart_alpha: float = 0.0
    carhart_alpha_t_stat: float = 0.0
    carhart_r_squared: float = 0.0
    carhart_information_ratio: float = 0.0
    carhart_betas: dict[str, float] = field(default_factory=dict)  # MKT/SMB/HML/MOM

    # Factor IC (most recent daily IC per factor)
    factor_ic: dict[str, float] = field(default_factory=dict)  # factor -> latest IC

    # Factor half-life (most recent per factor)
    factor_half_life: dict[str, float] = field(default_factory=dict)  # factor -> days
    factor_decay_status: dict[str, str] = field(default_factory=dict)  # factor -> stable/accelerating/reversing

    # Crowding (most recent per factor)
    crowding_score: dict[str, float] = field(default_factory=dict)  # factor -> 0-1
    crowding_trend: dict[str, str] = field(default_factory=dict)  # factor -> increasing/stable/decreasing

    # CFFEX signals (most recent per symbol)
    cffex_signals: dict[str, float] = field(default_factory=dict)  # symbol -> net_position_signal

    # Margin data (most recent)
    margin_balance: float = 0.0
    margin_sell_rate: float = 0.0

    # Fisher state (config override, not from historical data)
    fisher_stock_vs_cash: str = "neutral"  # stocks_favored / cash_favored / neutral
    fisher_max_equity: float = 0.8


class HistoricalDataLoader:
    """Loads and aligns time-series data from all 4 SQLite databases.

    Usage:
        loader = HistoricalDataLoader()
        state = loader.get_daily_state("2025-06-15")
        print(state.carhart_alpha, state.factor_ic)
    """

    def __init__(self):
        self._carhart_cache: Optional[pd.DataFrame] = None
        self._ic_cache: Optional[pd.DataFrame] = None
        self._crowding_cache: Optional[pd.DataFrame] = None
        self._cffex_cache: Optional[pd.DataFrame] = None
        self._margin_cache: Optional[pd.DataFrame] = None

    # ------------------------------------------------------------------
    # Carhart regression data
    # ------------------------------------------------------------------

    def load_carhart_history(self) -> pd.DataFrame:
        """Load rolling Carhart regression results, indexed by window_end.

        Returns a DataFrame with columns: alpha, alpha_t_stat, r_squared,
        information_ratio, and per-factor beta columns (beta_MKT, beta_SMB,
        beta_HML, beta_MOM).
        """
        if self._carhart_cache is not None:
            return self._carhart_cache

        conn = get_connection(DBName.CARHART)
        try:
            # Load regressions
            regs = pd.read_sql(
                "SELECT window_end, alpha, alpha_t_stat, r_squared, "
                "information_ratio, n_observations FROM regressions "
                "ORDER BY window_end",
                conn,
            )
            if regs.empty:
                self._carhart_cache = pd.DataFrame()
                return self._carhart_cache

            regs["window_end"] = pd.to_datetime(regs["window_end"])
            regs = regs.set_index("window_end")

            # Load factor betas
            factors = pd.read_sql(
                "SELECT window_end, factor_name, beta FROM factor_details "
                "ORDER BY window_end",
                conn,
            )
            if not factors.empty:
                factors["window_end"] = pd.to_datetime(factors["window_end"])
                # Pivot: factor_name -> columns, aggregating duplicates
                beta_pivot = factors.pivot_table(
                    index="window_end",
                    columns="factor_name",
                    values="beta",
                    aggfunc="mean",  # handle duplicates by averaging
                )
                beta_pivot.columns = [f"beta_{c}" for c in beta_pivot.columns]
                regs = regs.join(beta_pivot, how="left")

            self._carhart_cache = regs
            return regs
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Factor IC data
    # ------------------------------------------------------------------

    def load_factor_ic_history(self) -> pd.DataFrame:
        """Load IC series, indexed by date.

        Returns a DataFrame with multi-level columns (factor, forward_days)
        containing daily IC values.
        """
        if self._ic_cache is not None:
            return self._ic_cache

        conn = get_connection(DBName.FACTOR_IC)
        try:
            ic_data = pd.read_sql(
                "SELECT date, factor, forward_days, ic FROM ic_series "
                "ORDER BY date, factor, forward_days",
                conn,
            )
            if ic_data.empty:
                self._ic_cache = pd.DataFrame()
                return self._ic_cache

            ic_data["date"] = pd.to_datetime(ic_data["date"])
            # Pivot to multi-index columns
            ic_pivot = ic_data.pivot_table(
                index="date",
                columns=["factor", "forward_days"],
                values="ic",
            )
            self._ic_cache = ic_pivot
            return ic_pivot
        finally:
            conn.close()

    def load_half_life_data(self) -> pd.DataFrame:
        """Load latest half-life estimates per factor."""
        conn = get_connection(DBName.FACTOR_IC)
        try:
            hl = pd.read_sql(
                "SELECT factor, half_life_days, decay_status, updated_at "
                "FROM half_life",
                conn,
            )
            if hl.empty:
                return pd.DataFrame()
            return hl.set_index("factor")
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Crowding data
    # ------------------------------------------------------------------

    def load_crowding_history(self) -> pd.DataFrame:
        """Load crowding history, indexed by date.

        Returns a DataFrame with multi-level columns (factor, metric).
        """
        if self._crowding_cache is not None:
            return self._crowding_cache

        conn = get_connection(DBName.CROWDING)
        try:
            crowding = pd.read_sql(
                "SELECT date, factor, crowding_score FROM crowding_history "
                "ORDER BY date, factor",
                conn,
            )
            if crowding.empty:
                self._crowding_cache = pd.DataFrame()
                return self._crowding_cache

            crowding["date"] = pd.to_datetime(crowding["date"])
            crowding_pivot = crowding.pivot_table(
                index="date", columns="factor", values="crowding_score", aggfunc="mean"
            )
            self._crowding_cache = crowding_pivot
            return crowding_pivot
        finally:
            conn.close()

    def load_crowding_latest(self) -> pd.DataFrame:
        """Load latest crowding metrics per factor."""
        conn = get_connection(DBName.CROWDING)
        try:
            crowd = pd.read_sql(
                "SELECT factor, duration_bucket, crowding_score, trend, "
                "long_short_cost_bps, concentration, corr_distortion "
                "FROM crowding",
                conn,
            )
            if crowd.empty:
                return pd.DataFrame()
            return crowd.set_index("factor")
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # CFFEX signals
    # ------------------------------------------------------------------

    def load_cffex_signals(self) -> pd.DataFrame:
        """Load CFFEX futures position signals, indexed by trading_day.

        Returns a DataFrame with columns per symbol (IF/IC/IM/IH)
        containing net_position_signal values.
        """
        if self._cffex_cache is not None:
            return self._cffex_cache

        conn = get_connection(DBName.CFFEX)
        try:
            signals = pd.read_sql(
                "SELECT trading_day, symbol, net_position_signal "
                "FROM signals ORDER BY trading_day, symbol",
                conn,
            )
            if signals.empty:
                self._cffex_cache = pd.DataFrame()
                return self._cffex_cache

            signals["trading_day"] = pd.to_datetime(signals["trading_day"])
            signals_pivot = signals.pivot_table(
                index="trading_day", columns="symbol", values="net_position_signal", aggfunc="mean"
            )
            self._cffex_cache = signals_pivot
            return signals_pivot
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Margin data
    # ------------------------------------------------------------------

    def load_margin_data(self) -> pd.DataFrame:
        """Load margin trading data, indexed by date."""
        if self._margin_cache is not None:
            return self._margin_cache

        conn = get_connection(DBName.CROWDING)
        try:
            margin = pd.read_sql(
                "SELECT date, margin_balance, margin_sell_balance, "
                "margin_buy_balance, margin_sell_rate FROM margin_data "
                "ORDER BY date",
                conn,
            )
            if margin.empty:
                self._margin_cache = pd.DataFrame()
                return self._margin_cache

            margin["date"] = pd.to_datetime(margin["date"])
            self._margin_cache = margin.set_index("date")
            return self._margin_cache
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Composite daily state
    # ------------------------------------------------------------------

    def get_daily_state(
        self,
        date: str,
        fisher_config: Optional[dict] = None,
    ) -> DailyState:
        """Return a composite snapshot of all available signals for a date.

        For each data source, uses the most recent data point available
        on or before the given date (no look-ahead bias).

        Args:
            date: The target date in YYYY-MM-DD format.
            fisher_config: Optional dict with keys 'stock_vs_cash' and
                'max_equity' to override the Fisher state.

        Returns:
            DailyState with all available signals populated.
        """
        target_date = pd.Timestamp(date)
        state = DailyState(date=date)

        # Fisher config override
        if fisher_config:
            state.fisher_stock_vs_cash = fisher_config.get("stock_vs_cash", "neutral")
            state.fisher_max_equity = fisher_config.get("max_equity", 0.8)

        # Carhart: most recent regression window ending on or before date
        carhart = self.load_carhart_history()
        if not carhart.empty:
            carhart_before = carhart[carhart.index <= target_date]
            if not carhart_before.empty:
                latest = carhart_before.iloc[-1]
                state.carhart_alpha = float(latest.get("alpha", 0.0))
                state.carhart_alpha_t_stat = float(latest.get("alpha_t_stat", 0.0))
                state.carhart_r_squared = float(latest.get("r_squared", 0.0))
                state.carhart_information_ratio = float(
                    latest.get("information_ratio", 0.0)
                )
                for col in latest.index:
                    if col.startswith("beta_"):
                        factor = col.replace("beta_", "")
                        val = latest[col]
                        if not pd.isna(val):
                            state.carhart_betas[factor] = float(val)

        # Factor IC: most recent IC per factor
        ic_data = self.load_factor_ic_history()
        if not ic_data.empty:
            ic_before = ic_data[ic_data.index <= target_date]
            if not ic_before.empty:
                latest_ic = ic_before.iloc[-1]
                for col in latest_ic.index:
                    if isinstance(col, tuple) and len(col) == 2:
                        factor, fwd_days = col
                        val = latest_ic[col]
                        if not pd.isna(val):
                            # Store the IC for the 20-day forward horizon
                            # as the representative value
                            if fwd_days == 20:
                                state.factor_ic[factor] = float(val)

        # Half-life
        hl_data = self.load_half_life_data()
        if not hl_data.empty:
            for factor, row in hl_data.iterrows():
                state.factor_half_life[factor] = float(row.get("half_life_days", 0))
                state.factor_decay_status[factor] = str(row.get("decay_status", "stable"))

        # Crowding
        crowding = self.load_crowding_history()
        if not crowding.empty:
            crowd_before = crowding[crowding.index <= target_date]
            if not crowd_before.empty:
                latest_crowd = crowd_before.iloc[-1]
                for factor in latest_crowd.index:
                    val = latest_crowd[factor]
                    if not pd.isna(val):
                        state.crowding_score[factor] = float(val)

        # Crowding trends from latest
        crowd_latest = self.load_crowding_latest()
        if not crowd_latest.empty:
            for factor, row in crowd_latest.iterrows():
                state.crowding_trend[factor] = str(row.get("trend", "stable"))

        # CFFEX signals
        cffex = self.load_cffex_signals()
        if not cffex.empty:
            cffex_before = cffex[cffex.index <= target_date]
            if not cffex_before.empty:
                latest_cffex = cffex_before.iloc[-1]
                for symbol in latest_cffex.index:
                    val = latest_cffex[symbol]
                    if not pd.isna(val):
                        state.cffex_signals[symbol] = float(val)

        # Margin data
        margin = self.load_margin_data()
        if not margin.empty:
            margin_before = margin[margin.index <= target_date]
            if not margin_before.empty:
                latest_margin = margin_before.iloc[-1]
                state.margin_balance = float(latest_margin.get("margin_balance", 0))
                state.margin_sell_rate = float(latest_margin.get("margin_sell_rate", 0))

        return state

    def get_date_range(self) -> tuple[str, str]:
        """Return the earliest and latest dates available across all databases.

        Returns:
            Tuple of (earliest_date, latest_date) in YYYY-MM-DD format.
        """
        earliest = None
        latest = None

        carhart = self.load_carhart_history()
        if not carhart.empty:
            earliest = carhart.index.min()
            latest = carhart.index.max()

        ic_data = self.load_factor_ic_history()
        if not ic_data.empty:
            ic_min = ic_data.index.min()
            ic_max = ic_data.index.max()
            if earliest is None or ic_min < earliest:
                earliest = ic_min
            if latest is None or ic_max > latest:
                latest = ic_max

        crowding = self.load_crowding_history()
        if not crowding.empty:
            c_min = crowding.index.min()
            c_max = crowding.index.max()
            if earliest is None or c_min < earliest:
                earliest = c_min
            if latest is None or c_max > latest:
                latest = c_max

        cffex = self.load_cffex_signals()
        if not cffex.empty:
            cf_min = cffex.index.min()
            cf_max = cffex.index.max()
            if earliest is None or cf_min < earliest:
                earliest = cf_min
            if latest is None or cf_max > latest:
                latest = cf_max

        if earliest is None:
            return ("2024-01-01", "2025-12-31")

        return (
            earliest.strftime("%Y-%m-%d"),
            latest.strftime("%Y-%m-%d"),
        )