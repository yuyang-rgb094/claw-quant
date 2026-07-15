"""Backtesting engine for Claw Quant.

Replays the SFM → Graham → Markowitz decision chain day-by-day using
historical data from the SQLite databases. The Graham layer uses a
deterministic rule-based surrogate (not an LLM) for reproducibility.

Key design decisions:
- No LLM in backtesting — Graham is a factor-timing rule
- Fisher is a config parameter, not reconstructed from history
- Walk-forward split: IS (first 60%) vs OOS (last 40%)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

import numpy as np
import pandas as pd

from claw_quant.backtest.data_loader import DailyState, HistoricalDataLoader
from claw_quant.backtest.performance import PerformanceMetrics, compute_metrics


@dataclass
class BacktestConfig:
    """Configuration for a backtest run."""

    start_date: str  # YYYY-MM-DD
    end_date: str  # YYYY-MM-DD
    fisher_stock_vs_cash: str = "neutral"  # stocks_favored / cash_favored / neutral
    fisher_max_equity: float = 0.8
    initial_capital: float = 1_000_000.0
    max_positions: int = 10
    rebalance_frequency: str = "W"  # W=weekly, M=monthly, D=daily
    # Factor selection parameters
    min_ic_threshold: float = 0.02  # minimum IC to consider a factor
    max_crowding_threshold: float = 0.6  # maximum crowding to select a factor
    top_n_factors: int = 2  # number of preferred factors to select
    conviction_base: float = 0.5  # base conviction when signal is moderate


@dataclass
class BacktestResult:
    """Complete backtest result."""

    config: BacktestConfig
    daily_returns: pd.Series  # daily portfolio returns
    daily_positions: pd.DataFrame  # daily position weights (date x ticker)
    daily_turnover: pd.Series  # daily turnover
    metrics: PerformanceMetrics
    factor_selections: list[dict]  # selected factors at each rebalance
    is_metrics: Optional[PerformanceMetrics] = None  # in-sample metrics
    oos_metrics: Optional[PerformanceMetrics] = None  # out-of-sample metrics


class BacktestEngine:
    """Replay-based backtesting engine.

    Usage:
        loader = HistoricalDataLoader()
        config = BacktestConfig(start_date="2024-06-01", end_date="2025-06-01")
        engine = BacktestEngine(loader, config)
        result = engine.run()
        print(result.metrics.sharpe_ratio)
    """

    def __init__(
        self,
        loader: HistoricalDataLoader,
        config: BacktestConfig,
    ):
        self.loader = loader
        self.config = config
        self._preferred_factors: list[str] = []
        self._target_weights: dict[str, float] = {}

    def run(self) -> BacktestResult:
        """Execute the backtest and return results."""
        # Get all trading dates in range
        dates = self._get_trading_dates()
        if len(dates) == 0:
            raise ValueError(
                f"No trading dates in range {self.config.start_date} to {self.config.end_date}"
            )

        # Initialize tracking
        daily_returns = pd.Series(0.0, index=dates, name="portfolio_return")
        daily_positions_data: dict = {}
        daily_turnover = pd.Series(0.0, index=dates, name="turnover")
        factor_selections: list[dict] = []

        prev_weights: dict[str, float] = {}
        capital = self.config.initial_capital
        rebalance_dates = self._get_rebalance_dates(dates)

        for i, date in enumerate(dates):
            date_str = date.strftime("%Y-%m-%d")

            # Get daily state
            state = self.loader.get_daily_state(
                date_str,
                fisher_config={
                    "stock_vs_cash": self.config.fisher_stock_vs_cash,
                    "max_equity": self.config.fisher_max_equity,
                },
            )

            # Rebalance on rebalance dates
            if date_str in rebalance_dates:
                preferred = self._select_factors(state)
                self._preferred_factors = preferred
                factor_selections.append({
                    "date": date_str,
                    "preferred_factors": preferred,
                    "avoided_factors": self._get_avoided_factors(state),
                })

                # Build target weights from factor preferences
                self._target_weights = self._build_target_weights(state)

            # Apply weights (simulate holding from previous rebalance)
            current_weights = self._target_weights if self._target_weights else prev_weights

            # Compute daily return (simplified: assume equal-weight among holdings)
            if current_weights:
                # In a real backtest, we'd use actual price data
                # For now, estimate return from factor exposures
                daily_ret = self._estimate_daily_return(state, current_weights)
            else:
                daily_ret = 0.0

            daily_returns[date] = daily_ret
            daily_positions_data[date_str] = current_weights.copy()

            # Compute turnover
            if prev_weights:
                turnover = self._compute_turnover(prev_weights, current_weights)
                daily_turnover[date] = turnover

            prev_weights = current_weights.copy()

        # Build positions DataFrame
        daily_positions = pd.DataFrame.from_dict(daily_positions_data, orient="index")
        daily_positions.index = pd.to_datetime(daily_positions.index)

        # Compute performance metrics
        metrics = compute_metrics(daily_returns)

        # Walk-forward split
        split_idx = int(len(dates) * 0.6)
        is_returns = daily_returns.iloc[:split_idx]
        oos_returns = daily_returns.iloc[split_idx:]
        is_metrics = compute_metrics(is_returns) if len(is_returns) > 0 else None
        oos_metrics = compute_metrics(oos_returns) if len(oos_returns) > 0 else None

        return BacktestResult(
            config=self.config,
            daily_returns=daily_returns,
            daily_positions=daily_positions,
            daily_turnover=daily_turnover,
            metrics=metrics,
            factor_selections=factor_selections,
            is_metrics=is_metrics,
            oos_metrics=oos_metrics,
        )

    # ------------------------------------------------------------------
    # Factor selection (Graham surrogate)
    # ------------------------------------------------------------------

    def _select_factors(self, state: DailyState) -> list[str]:
        """Select preferred factors based on IC strength and crowding.

        This is the rule-based Graham surrogate. It picks the top-N factors
        by IC strength that are not in "reversing" decay status and have
        crowding score below the threshold.

        Returns:
            List of preferred factor names.
        """
        candidates = []
        for factor, ic in state.factor_ic.items():
            if abs(ic) < self.config.min_ic_threshold:
                continue
            decay = state.factor_decay_status.get(factor, "stable")
            if decay == "reversing":
                continue
            crowding = state.crowding_score.get(factor, 0.5)
            if crowding > self.config.max_crowding_threshold:
                continue
            candidates.append((factor, abs(ic)))

        # Sort by IC strength descending
        candidates.sort(key=lambda x: x[1], reverse=True)
        return [f for f, _ in candidates[: self.config.top_n_factors]]

    def _get_avoided_factors(self, state: DailyState) -> list[str]:
        """Return factors to avoid (crowded or reversing)."""
        avoided = []
        for factor, crowding in state.crowding_score.items():
            if crowding > self.config.max_crowding_threshold:
                avoided.append(factor)
        for factor, decay in state.factor_decay_status.items():
            if decay == "reversing" and factor not in avoided:
                avoided.append(factor)
        return avoided

    # ------------------------------------------------------------------
    # Portfolio construction (Markowitz surrogate)
    # ------------------------------------------------------------------

    def _build_target_weights(self, state: DailyState) -> dict[str, float]:
        """Build target portfolio weights from factor preferences.

        Simplified portfolio construction: assign equal weight to all
        factors, then derive tilt toward stocks with high exposure to
        preferred factors and away from avoided factors.

        Since we don't have individual stock data in the backtest
        (only factor-level data), we return factor-level weights.
        In a real deployment, these would be translated to stock weights.
        """
        if not self._preferred_factors:
            return {}

        n_factors = len(self._preferred_factors)
        base_weight = 1.0 / n_factors

        weights = {}
        for factor in self._preferred_factors:
            # Adjust weight by conviction
            ic = state.factor_ic.get(factor, 0.0)
            conviction = self._compute_conviction(state, factor)
            weights[factor] = base_weight * conviction

        # Normalize
        total = sum(weights.values())
        if total > 0:
            weights = {k: v / total for k, v in weights.items()}

        return weights

    def _compute_conviction(self, state: DailyState, factor: str) -> float:
        """Compute conviction for a factor using the quantitative floor formula.

        conviction = 0.3 * Evidence + 0.5 * IR_norm + 0.2 * GMM_norm

        In backtesting, we use simplified proxies:
        - Evidence: based on IC significance (|IC| > 0.03 => high)
        - IR_norm: normalized information ratio from Carhart regression
        - GMM_norm: alpha persistence proxy (if alpha t-stat > 1.5 => high)
        """
        ic = abs(state.factor_ic.get(factor, 0.0))
        evidence = min(ic / 0.05, 1.0)  # normalize to 0-1

        ir_raw = state.carhart_information_ratio
        ir_norm = min(abs(ir_raw) / 1.0, 1.0)  # IR=1.0 => full

        gmm_norm = min(abs(state.carhart_alpha_t_stat) / 2.0, 1.0)  # t=2 => full

        conviction = 0.3 * evidence + 0.5 * ir_norm + 0.2 * gmm_norm

        # Hard caps
        if abs(ir_raw) < 0.3:
            conviction = min(conviction, 0.4)
        if abs(state.carhart_alpha_t_stat) < 1.0:
            conviction = min(conviction, 0.5)

        return max(conviction, 0.1)  # floor

    # ------------------------------------------------------------------
    # Return estimation
    # ------------------------------------------------------------------

    def _estimate_daily_return(
        self, state: DailyState, weights: dict[str, float]
    ) -> float:
        """Estimate daily portfolio return from factor exposures.

        Simplified: use Carhart alpha + factor exposure * factor premia.
        In a real backtest, this would use actual stock price returns.
        """
        if not weights:
            return 0.0

        # Base return from alpha
        daily_alpha = state.carhart_alpha / 252  # annualize

        # Factor contribution
        factor_contrib = 0.0
        for factor, weight in weights.items():
            ic = state.factor_ic.get(factor, 0.0)
            factor_contrib += weight * ic * 0.01  # IC contribution to daily return

        return daily_alpha + factor_contrib

    def _compute_turnover(
        self, prev: dict[str, float], curr: dict[str, float]
    ) -> float:
        """Compute turnover between two weight vectors."""
        all_keys = set(prev.keys()) | set(curr.keys())
        turnover = 0.0
        for k in all_keys:
            w1 = prev.get(k, 0.0)
            w2 = curr.get(k, 0.0)
            turnover += abs(w2 - w1)
        return turnover / 2  # one-way turnover

    # ------------------------------------------------------------------
    # Date utilities
    # ------------------------------------------------------------------

    def _get_trading_dates(self) -> pd.DatetimeIndex:
        """Get all trading dates in the backtest range."""
        start = pd.Timestamp(self.config.start_date)
        end = pd.Timestamp(self.config.end_date)
        all_dates = pd.bdate_range(start=start, end=end)

        # Filter to dates that have at least some data
        carhart = self.loader.load_carhart_history()
        if not carhart.empty:
            min_date = carhart.index.min()
            all_dates = all_dates[all_dates >= min_date]

        return all_dates

    def _get_rebalance_dates(self, dates: pd.DatetimeIndex) -> set[str]:
        """Get rebalance dates based on frequency."""
        rebalance_dates = set()
        freq_map = {"D": "B", "W": "W-FRI", "M": "BME"}

        freq = freq_map.get(self.config.rebalance_frequency, "W-FRI")
        if self.config.rebalance_frequency == "D":
            # Every day is a rebalance
            return {d.strftime("%Y-%m-%d") for d in dates}

        rebalance_range = pd.date_range(
            start=dates[0], end=dates[-1], freq=freq
        )
        for rd in rebalance_range:
            # Find the nearest actual trading date
            valid_dates = dates[dates >= rd]
            if len(valid_dates) > 0:
                rebalance_dates.add(valid_dates[0].strftime("%Y-%m-%d"))

        return rebalance_dates