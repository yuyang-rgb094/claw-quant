"""Backtesting engine for Claw Quant.

Replay-based historical simulation using existing SQLite time-series data.
The engine simulates the SFM → Graham → Markowitz decision chain day-by-day,
using a rule-based Graham surrogate (not an LLM) for reproducibility and speed.
"""

from claw_quant.backtest.data_loader import HistoricalDataLoader
from claw_quant.backtest.engine import BacktestEngine

__all__ = ["HistoricalDataLoader", "BacktestEngine"]