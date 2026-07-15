"""AKShare data provider — free A-share market data.

Implements the DataProvider interface using AKShare, a free Python library
for Chinese financial data. Covers: stock daily prices, index prices,
margin trading data, and risk-free rate proxies.

AKShare is completely free and requires no API key. Installation:
    pip install akshare>=1.14.0

Data sources used:
- stock_zh_a_hist: A-share daily K-line (price, volume, turnover)
- index_zh_a_hist: Index daily K-line
- stock_margin_detail_sse/szse: Margin trading detail (SSE/SZSE)
- bond_china_yield: China government bond yields (risk-free rate proxy)
"""

from __future__ import annotations

import logging
from typing import Optional

import numpy as np
import pandas as pd

from claw_quant.data_provider import DataProvider

logger = logging.getLogger("claw_quant.data_akshare")

# Map Wind-style exchange suffixes to AKShare exchange codes
# AKShare uses 'sh'/'sz' prefix in some functions, suffix in others
EXCHANGE_SUFFIX_MAP = {
    ".SH": "sh",
    ".SZ": "sz",
    ".BJ": "bj",
}


class AKShareDataProvider(DataProvider):
    """Real A-share data provider backed by AKShare.

    Usage:
        dp = AKShareDataProvider()
        prices = dp.get_stock_prices(['600519.SH'], '2024-01-01', '2024-12-31')
        margin = dp.get_margin_data('2024-01-01', '2024-12-31')
    """

    def __init__(self):
        self._ak = None  # Lazy import

    @property
    def name(self) -> str:
        return "akshare"

    @property
    def is_synthetic(self) -> bool:
        return False

    @property
    def _akshare(self):
        """Lazy import of akshare to avoid import errors when not installed."""
        if self._ak is None:
            try:
                import akshare as ak
                self._ak = ak
            except ImportError:
                raise ImportError(
                    "AKShare is not installed. Install it with:\n"
                    "    pip install akshare>=1.14.0\n"
                    "Or use the synthetic data provider instead."
                )
        return self._ak

    # ------------------------------------------------------------------
    # Stock prices
    # ------------------------------------------------------------------

    def get_stock_prices(
        self,
        symbols: list[str],
        start: str,
        end: str,
    ) -> pd.DataFrame:
        """Fetch A-share daily K-line data from AKShare.

        Uses ak.stock_zh_a_hist() which returns OHLCV data for a single
        stock. We fetch each stock and combine into a multi-column DataFrame.
        """
        all_prices = {}
        for symbol in symbols:
            try:
                native = self._to_akshare_code(symbol)
                df = self._akshare.stock_zh_a_hist(
                    symbol=native,
                    period="daily",
                    start_date=start.replace("-", ""),
                    end_date=end.replace("-", ""),
                    adjust="qfq",  # 前复权
                )
                if df.empty:
                    logger.warning("No data for %s (%s)", symbol, native)
                    continue

                # Standardize: date index, close prices
                df["日期"] = pd.to_datetime(df["日期"])
                close_col = "收盘" if "收盘" in df.columns else df.columns[4]
                prices = df.set_index("日期")[close_col]
                prices.name = symbol
                all_prices[symbol] = prices
            except Exception as e:
                logger.error("Failed to fetch %s: %s", symbol, e)

        if not all_prices:
            logger.warning("AKShare returned no stock data, falling back to synthetic")
            from claw_quant.data_synthetic import SyntheticDataProvider
            return SyntheticDataProvider().get_stock_prices(symbols, start, end)

        # Combine into a single DataFrame
        result = pd.DataFrame(all_prices)
        result = result.sort_index()
        return result

    # ------------------------------------------------------------------
    # Index prices
    # ------------------------------------------------------------------

    def get_index_prices(
        self,
        index_code: str,
        start: str,
        end: str,
    ) -> pd.Series:
        """Fetch index daily K-line from AKShare.

        Supported indices: CSI 300 (000300.SH), CSI 500 (000905.SH),
        SSE Composite (000001.SH), SZSE Component (399001.SZ).
        """
        try:
            native = self._to_akshare_code(index_code)
            df = self._akshare.index_zh_a_hist(
                symbol=native,
                period="daily",
                start_date=start.replace("-", ""),
                end_date=end.replace("-", ""),
            )
            if df.empty:
                logger.warning("No index data for %s", index_code)
                return pd.Series(dtype=float)

            df["日期"] = pd.to_datetime(df["日期"])
            close_col = "收盘" if "收盘" in df.columns else df.columns[3]
            return df.set_index("日期")[close_col]
        except Exception as e:
            logger.error("Failed to fetch index %s: %s", index_code, e)
            return pd.Series(dtype=float)

    # ------------------------------------------------------------------
    # Risk-free rate
    # ------------------------------------------------------------------

    def get_risk_free_rate(
        self,
        start: str,
        end: str,
    ) -> pd.Series:
        """Fetch China 10-year government bond yield as risk-free rate proxy.

        Uses ak.bond_china_yield() and converts annual yield to daily rate.
        """
        try:
            df = self._akshare.bond_china_yield(
                start_date=start.replace("-", ""),
                end_date=end.replace("-", ""),
            )
            if df.empty:
                logger.warning("No bond yield data, using default 2.5%")
                return self._default_risk_free_rate(start, end)

            # Find the 10Y column
            df["日期"] = pd.to_datetime(df["日期"])
            df = df.set_index("日期")

            # AKShare bond_china_yield columns vary by version
            # Look for a column with '10' in the name
            yield_col = None
            for col in df.columns:
                if "10" in str(col):
                    yield_col = col
                    break
            if yield_col is None:
                yield_col = df.columns[0]

            annual_yield = df[yield_col] / 100.0  # Convert % to decimal
            daily_rf = (1 + annual_yield) ** (1 / 252) - 1
            return daily_rf.dropna()
        except Exception as e:
            logger.error("Failed to fetch bond yield: %s, using default", e)
            return self._default_risk_free_rate(start, end)

    def _default_risk_free_rate(self, start: str, end: str) -> pd.Series:
        """Return a default 2.5% annual risk-free rate."""
        dates = pd.bdate_range(start=start, end=end)
        daily_rf = (1 + 0.025) ** (1 / 252) - 1
        return pd.Series(daily_rf, index=dates, name="rf")

    # ------------------------------------------------------------------
    # Market caps and book-to-market
    # ------------------------------------------------------------------

    def get_market_caps(
        self,
        symbols: list[str],
        start: str,
        end: str,
    ) -> pd.DataFrame:
        """Fetch market capitalization from AKShare.

        Uses ak.stock_zh_a_spot_em() for latest market cap, then
        estimates historical values from price changes.
        """
        try:
            # Get latest market caps
            spot = self._akshare.stock_zh_a_spot_em()
            spot["代码"] = spot["代码"].astype(str)

            # Build a mapping from our symbols to market caps
            cap_map = {}
            for _, row in spot.iterrows():
                code = str(row["代码"])
                cap_map[code] = float(row.get("总市值", 0))

            # Get prices for historical estimation
            prices = self.get_stock_prices(symbols, start, end)

            # Estimate historical market caps from price changes
            result = pd.DataFrame(index=prices.index, columns=symbols, dtype=float)
            for symbol in symbols:
                native = self.convert_symbol(symbol)
                latest_cap = cap_map.get(native, 1e10)
                if prices[symbol].notna().any():
                    last_price = prices[symbol].dropna().iloc[-1]
                    result[symbol] = latest_cap * (prices[symbol] / last_price)
                else:
                    result[symbol] = latest_cap

            return result
        except Exception as e:
            logger.error("Failed to fetch market caps: %s", e)
            from claw_quant.data_synthetic import SyntheticDataProvider
            return SyntheticDataProvider().get_market_caps(symbols, start, end)

    def get_book_to_market(
        self,
        symbols: list[str],
        start: str,
        end: str,
    ) -> pd.DataFrame:
        """Estimate book-to-market from market cap and estimated book value.

        Uses inverse of price-to-book ratio when available.
        """
        try:
            spot = self._akshare.stock_zh_a_spot_em()
            spot["代码"] = spot["代码"].astype(str)

            pb_map = {}
            for _, row in spot.iterrows():
                code = str(row["代码"])
                pb = float(row.get("市净率", 2.0))
                if pb > 0:
                    pb_map[code] = 1.0 / pb  # B/M = 1/PB

            prices = self.get_stock_prices(symbols, start, end)
            result = pd.DataFrame(index=prices.index, columns=symbols, dtype=float)
            for symbol in symbols:
                native = self.convert_symbol(symbol)
                bm = pb_map.get(native, 0.5)
                result[symbol] = bm

            return result
        except Exception as e:
            logger.error("Failed to fetch book-to-market: %s", e)
            from claw_quant.data_synthetic import SyntheticDataProvider
            return SyntheticDataProvider().get_book_to_market(symbols, start, end)

    # ------------------------------------------------------------------
    # Margin trading data
    # ------------------------------------------------------------------

    def get_margin_data(
        self,
        start: str,
        end: str,
    ) -> pd.DataFrame:
        """Fetch margin trading data (融资融券) from AKShare.

        Combines SSE and SZSE margin detail data.
        """
        try:
            # SSE margin data
            sse = self._akshare.stock_margin_detail_sse(
                start_date=start.replace("-", ""),
                end_date=end.replace("-", ""),
            )
            # SZSE margin data
            szse = self._akshare.stock_margin_detail_szse(
                start_date=start.replace("-", ""),
                end_date=end.replace("-", ""),
            )

            # Combine
            sse["日期"] = pd.to_datetime(sse["日期"])
            szse["日期"] = pd.to_datetime(szse["日期"])

            sse = sse.set_index("日期")
            szse = szse.set_index("日期")

            # Find the right columns (AKShare column names vary by version)
            def find_col(df, keywords):
                for col in df.columns:
                    if all(kw in str(col) for kw in keywords):
                        return col
                return df.columns[0] if len(df.columns) > 1 else None

            # Combine SSE and SZSE
            margin_balance = sse.get(find_col(sse, ["融资余额"]), sse.iloc[:, 0] if len(sse.columns) > 0 else 0)
            margin_sell = sse.get(find_col(sse, ["融券余额"]), 0)

            # Add SZSE data
            szse_margin = szse.get(find_col(szse, ["融资余额"]), szse.iloc[:, 0] if len(szse.columns) > 0 else 0)

            result = pd.DataFrame({
                "margin_balance": margin_balance + szse_margin,
                "margin_sell_balance": margin_sell,
                "margin_buy_balance": margin_balance * 0.5,  # estimate
                "margin_sell_rate": 0.00002,  # default ~72 bps annual
            }, index=margin_balance.index)

            return result.dropna()
        except Exception as e:
            logger.error("Failed to fetch margin data: %s", e)
            from claw_quant.data_synthetic import SyntheticDataProvider
            return SyntheticDataProvider().get_margin_data(start, end)

    # ------------------------------------------------------------------
    # Northbound flow (北向资金)
    # ------------------------------------------------------------------

    def get_northbound_flow(
        self,
        start: Optional[str] = None,
        end: Optional[str] = None,
    ) -> pd.DataFrame:
        """Fetch northbound net flow data (北向资金净流入) from AKShare.

        Uses ak.stock_hsgt_north_net_flow_in_em() which returns the full
        historical series of daily northbound net inflows.

        Args:
            start: Optional start date filter (YYYY-MM-DD).
            end: Optional end date filter (YYYY-MM-DD).

        Returns:
            DataFrame indexed by date with columns:
            - net_flow: 当日净流入 (in 亿元)
            - cumulative_flow: 累计净流入 (in 亿元)
        """
        try:
            df = self._akshare.stock_hsgt_north_net_flow_in_em()

            if df.empty:
                logger.warning("No northbound flow data")
                return pd.DataFrame()

            # Standardize columns
            col_map = {}
            for col in df.columns:
                col_str = str(col)
                if "日期" in col_str or "date" in col_str.lower():
                    col_map[col] = "date"
                elif "净流入" in col_str and "累计" not in col_str:
                    col_map[col] = "net_flow"
                elif "累计" in col_str:
                    col_map[col] = "cumulative_flow"

            df = df.rename(columns=col_map)

            if "date" in df.columns:
                df["date"] = pd.to_datetime(df["date"])
                df = df.set_index("date").sort_index()

            # Filter by date range if provided
            if start:
                df = df[df.index >= start]
            if end:
                df = df[df.index <= end]

            return df
        except Exception as e:
            logger.error("Failed to fetch northbound flow: %s", e)
            return pd.DataFrame()

    def get_northbound_summary(self) -> dict:
        """Get a summary of recent northbound flow activity.

        Returns:
            Dict with: latest_net_flow, flow_5d, flow_20d, trend, anomaly.
        """
        try:
            df = self.get_northbound_flow()
            if df.empty or "net_flow" not in df.columns:
                return {"latest_net_flow": 0, "flow_5d": 0, "flow_20d": 0, "trend": "unknown"}

            recent = df.tail(20)
            if len(recent) < 5:
                return {"latest_net_flow": 0, "flow_5d": 0, "flow_20d": 0, "trend": "unknown"}

            latest = float(recent["net_flow"].iloc[-1])
            flow_5d = float(recent["net_flow"].tail(5).sum())
            flow_20d = float(recent["net_flow"].sum())

            # Trend: 5-day average vs 20-day average
            avg_5d = flow_5d / 5
            avg_20d = flow_20d / 20
            if avg_5d > avg_20d * 1.5:
                trend = "increasing"
            elif avg_5d < avg_20d * 0.5:
                trend = "decreasing"
            else:
                trend = "stable"

            # Anomaly: 5 consecutive days of net outflow > 10B
            recent_5 = recent["net_flow"].tail(5)
            anomaly = (
                (recent_5 < -10).all()  # All 5 days have net outflow > 10B
            )

            return {
                "latest_net_flow": latest,
                "flow_5d": flow_5d,
                "flow_20d": flow_20d,
                "trend": trend,
                "anomaly": anomaly,
            }
        except Exception as e:
            logger.error("Failed to summarize northbound flow: %s", e)
            return {"latest_net_flow": 0, "flow_5d": 0, "flow_20d": 0, "trend": "unknown"}

    # ------------------------------------------------------------------
    # Symbol conversion
    # ------------------------------------------------------------------

    def _to_akshare_code(self, symbol: str) -> str:
        """Convert Wind-style code to AKShare format.

        '600519.SH' -> '600519'
        '000858.SZ' -> '000858'
        """
        return self.convert_symbol(symbol)