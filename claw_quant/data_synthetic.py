"""Synthetic data provider — wraps synthetic generators for testing.

Implements the DataProvider interface using the synthetic data generators
from claw_quant.synthetic. All data is explicitly tagged as synthetic.
"""

from __future__ import annotations

import pandas as pd

from claw_quant.data_provider import DataProvider
from claw_quant.synthetic import (
    generate_synthetic_data,
    generate_synthetic_prices,
    generate_margin_data,
)


class SyntheticDataProvider(DataProvider):
    """Data provider that returns synthetic (fake) data for testing.

    Usage:
        dp = SyntheticDataProvider(seed=42)
        prices = dp.get_stock_prices(['600519.SH'], '2024-01-01', '2024-12-31')
    """

    def __init__(self, seed: int = 42, n_stocks: int = 200):
        self._seed = seed
        self._n_stocks = n_stocks
        self._cache: dict = {}

    @property
    def name(self) -> str:
        return "synthetic"

    @property
    def is_synthetic(self) -> bool:
        return True

    def get_stock_prices(
        self,
        symbols: list[str],
        start: str,
        end: str,
    ) -> pd.DataFrame:
        """Generate synthetic stock prices from GBM with factor structure."""
        n_days = self._estimate_days(start, end)
        prices = generate_synthetic_prices(
            n_stocks=len(symbols),
            n_days=n_days,
            seed=self._seed,
        )
        # Rename columns to match input symbols
        prices.columns = symbols
        # Filter to date range
        mask = (prices.index >= start) & (prices.index <= end)
        return prices[mask]

    def get_index_prices(
        self,
        index_code: str,
        start: str,
        end: str,
    ) -> pd.Series:
        """Generate synthetic index prices."""
        # Use the full synthetic data generator and extract market returns
        from claw_quant.config import DEFAULT_UNIVERSE

        symbols = DEFAULT_UNIVERSE[:5]  # Use a subset for speed
        _, _, _, market_returns, _ = generate_synthetic_data(
            symbols, n_years=3, seed=self._seed
        )
        # Convert returns to price levels
        prices = 1000 * (1 + market_returns).cumprod()
        mask = (prices.index >= start) & (prices.index <= end)
        return prices[mask]

    def get_risk_free_rate(
        self,
        start: str,
        end: str,
    ) -> pd.Series:
        """Generate synthetic risk-free rate (~2.5% annual)."""
        from claw_quant.config import DEFAULT_UNIVERSE

        symbols = DEFAULT_UNIVERSE[:5]
        _, _, _, _, risk_free_rate = generate_synthetic_data(
            symbols, n_years=3, seed=self._seed
        )
        mask = (risk_free_rate.index >= start) & (risk_free_rate.index <= end)
        return risk_free_rate[mask]

    def get_market_caps(
        self,
        symbols: list[str],
        start: str,
        end: str,
    ) -> pd.DataFrame:
        """Generate synthetic market capitalizations."""
        _, market_caps, _, _, _ = generate_synthetic_data(
            symbols, n_years=3, seed=self._seed
        )
        mask = (market_caps.index >= start) & (market_caps.index <= end)
        return market_caps[mask]

    def get_book_to_market(
        self,
        symbols: list[str],
        start: str,
        end: str,
    ) -> pd.DataFrame:
        """Generate synthetic book-to-market ratios."""
        _, _, book_to_market, _, _ = generate_synthetic_data(
            symbols, n_years=3, seed=self._seed
        )
        mask = (book_to_market.index >= start) & (book_to_market.index <= end)
        return book_to_market[mask]

    def get_margin_data(
        self,
        start: str,
        end: str,
    ) -> pd.DataFrame:
        """Generate synthetic margin trading data."""
        n_days = self._estimate_days(start, end)
        df = generate_margin_data(n_days=n_days, seed=self._seed)
        mask = (df.index >= start) & (df.index <= end)
        return df[mask]

    def _estimate_days(self, start: str, end: str) -> int:
        """Estimate the number of trading days between two dates."""
        try:
            days = (
                pd.Timestamp(end) - pd.Timestamp(start)
            ).days
            return max(int(days * 0.7), 20)  # ~70% of calendar days are trading days
        except Exception:
            return 252