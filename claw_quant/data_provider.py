"""Data Provider abstract base class for Claw Quant.

Defines the interface that all data providers must implement. This allows
switching between synthetic data (for testing) and real data sources
(AKShare, Wind, Tushare, etc.) without changing any downstream code.

Each method returns a DataFrame or Series with clearly defined columns.
All methods accept a date range (start, end) and return data for that range.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

import pandas as pd


class DataProvider(ABC):
    """Abstract base class for all data providers.

    Usage:
        dp = get_data_provider('akshare')
        prices = dp.get_stock_prices(['600519.SH'], '2024-01-01', '2024-12-31')
        index = dp.get_index_prices('000300.SH', '2024-01-01', '2024-12-31')
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable provider name (e.g., 'akshare', 'synthetic')."""
        ...

    @property
    @abstractmethod
    def is_synthetic(self) -> bool:
        """Whether this provider returns synthetic (fake) data.

        Downstream code checks this to decide whether to:
        - Tag results with [SYNTHETIC] in reports
        - Cap conviction at 0.5 (per ADR-009 hard cap for code-unavailable)
        - Warn the user that results are not based on real market data
        """
        ...

    # ------------------------------------------------------------------
    # Core data methods
    # ------------------------------------------------------------------

    @abstractmethod
    def get_stock_prices(
        self,
        symbols: list[str],
        start: str,
        end: str,
    ) -> pd.DataFrame:
        """Return daily closing prices for a list of stock symbols.

        Args:
            symbols: List of Wind-style stock codes (e.g., ['600519.SH', '000858.SZ']).
            start: Start date in YYYY-MM-DD format.
            end: End date in YYYY-MM-DD format.

        Returns:
            DataFrame indexed by date, columns = stock symbols, values = adjusted close prices.
        """
        ...

    @abstractmethod
    def get_index_prices(
        self,
        index_code: str,
        start: str,
        end: str,
    ) -> pd.Series:
        """Return daily closing prices for a market index.

        Args:
            index_code: Wind-style index code (e.g., '000300.SH' for CSI 300).
            start: Start date in YYYY-MM-DD format.
            end: End date in YYYY-MM-DD format.

        Returns:
            Series indexed by date, values = closing prices.
        """
        ...

    @abstractmethod
    def get_risk_free_rate(
        self,
        start: str,
        end: str,
    ) -> pd.Series:
        """Return daily risk-free rate.

        For China, this is typically the China 10-year government bond yield
        converted to a daily rate: daily_rf = (1 + annual_yield)^(1/252) - 1.

        Args:
            start: Start date in YYYY-MM-DD format.
            end: End date in YYYY-MM-DD format.

        Returns:
            Series indexed by date, values = daily risk-free rate as decimal.
        """
        ...

    @abstractmethod
    def get_market_caps(
        self,
        symbols: list[str],
        start: str,
        end: str,
    ) -> pd.DataFrame:
        """Return market capitalization for each stock over time.

        Args:
            symbols: List of Wind-style stock codes.
            start: Start date in YYYY-MM-DD format.
            end: End date in YYYY-MM-DD format.

        Returns:
            DataFrame indexed by date, columns = stock symbols, values = market cap in CNY.
        """
        ...

    @abstractmethod
    def get_book_to_market(
        self,
        symbols: list[str],
        start: str,
        end: str,
    ) -> pd.DataFrame:
        """Return book-to-market ratio for each stock over time.

        Args:
            symbols: List of Wind-style stock codes.
            start: Start date in YYYY-MM-DD format.
            end: End date in YYYY-MM-DD format.

        Returns:
            DataFrame indexed by date, columns = stock symbols, values = B/M ratio.
        """
        ...

    @abstractmethod
    def get_margin_data(
        self,
        start: str,
        end: str,
    ) -> pd.DataFrame:
        """Return margin trading data (融资融券).

        Args:
            start: Start date in YYYY-MM-DD format.
            end: End date in YYYY-MM-DD format.

        Returns:
            DataFrame indexed by date with columns:
            - margin_balance: 融资余额 (total margin balance)
            - margin_sell_balance: 融券余额 (margin selling balance)
            - margin_buy_balance: 融资买入额 (margin buying amount)
            - margin_sell_rate: 融券卖出费率 (margin selling rate, daily fraction)
        """
        ...

    # ------------------------------------------------------------------
    # Utility methods
    # ------------------------------------------------------------------

    def convert_symbol(self, symbol: str) -> str:
        """Convert a Wind-style symbol to the provider's native format.

        Override in subclasses if the provider uses a different format.
        Default: strip the exchange suffix (e.g., '600519.SH' -> '600519').

        Args:
            symbol: Wind-style symbol (e.g., '600519.SH').

        Returns:
            Provider-native symbol.
        """
        return symbol.split(".")[0] if "." in symbol else symbol

    def convert_symbols(self, symbols: list[str]) -> list[str]:
        """Convert a list of Wind-style symbols to native format."""
        return [self.convert_symbol(s) for s in symbols]