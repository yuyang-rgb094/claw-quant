"""Wind MCP data provider — institutional-grade A-share and macro data.

Wind (万得) is the gold standard for Chinese financial data. This provider
uses the Wind MCP Skill to fetch stock prices, index data, and macro
economic indicators via the Node.js CLI.

API reference: https://github.com/Wind-Information-Co-Ltd/wind-skills

CLI format (from tool-contracts.md):
    node scripts/cli.mjs call <server_type> <tool_name> '<JSON params>'

Key constraints:
    - windcode must be a SINGLE string, not array or comma-separated
    - Dates are yyyyMMdd format
    - Parameters are a single JSON string, not --key value flags

Available tools:
    stock_data.get_stock_kline          : Daily K-line (OHLCV)
    stock_data.get_stock_fundamentals   : NL-based fundamentals (ROE, revenue, etc.)
    stock_data.get_stock_basicinfo      : Company basic info
    stock_data.get_stock_technicals     : Technical indicators
    stock_data.get_risk_metrics         : Risk metrics (beta, volatility, VaR)
    index_data.get_index_kline          : Index K-line
    index_data.get_index_price_indicators: Index PE/PB, yield, etc.
    economic_data.natural_language_get_edb_data: GDP, CPI, M2, bond yields, etc.

API Key: configured in claw_quant.config.WIND_API_KEY
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
from typing import Optional

import pandas as pd

from claw_quant.data_provider import DataProvider
from claw_quant.config import WIND_CLI_PATH, WIND_API_KEY

logger = logging.getLogger("claw_quant.data_wind")


class WindDataProvider(DataProvider):
    """Real A-share data provider backed by Wind MCP Skill.

    Usage:
        dp = WindDataProvider()
        prices = dp.get_stock_prices(['600519.SH'], '2024-01-01', '2024-12-31')
    """

    def __init__(self, cli_path: Optional[str] = None, api_key: Optional[str] = None):
        self._cli_path = cli_path or WIND_CLI_PATH
        self._api_key = api_key or WIND_API_KEY

    @property
    def name(self) -> str:
        return "wind"

    @property
    def is_synthetic(self) -> bool:
        return False

    # ------------------------------------------------------------------
    # Stock prices — one call per stock (windcode must be single)
    # ------------------------------------------------------------------

    def get_stock_prices(
        self,
        symbols: list[str],
        start: str,
        end: str,
    ) -> pd.DataFrame:
        """Fetch stock daily K-line via Wind MCP.

        Calls stock_data.get_stock_kline once per stock.
        Returns a DataFrame indexed by date, columns = symbols.
        """
        all_prices = {}
        for symbol in symbols:
            df = self._fetch_single_kline(symbol, start, end)
            if df is not None and not df.empty:
                all_prices[symbol] = df["close"]
            else:
                logger.warning("No K-line data for %s", symbol)

        if not all_prices:
            return self._fallback_prices(symbols, start, end)

        result = pd.DataFrame(all_prices).sort_index()
        return result

    def _fetch_single_kline(
        self, symbol: str, start: str, end: str
    ) -> Optional[pd.DataFrame]:
        """Fetch K-line for a single stock."""
        params = {
            "windcode": symbol,
            "begin_date": self._fmt_date(start),
            "end_date": self._fmt_date(end),
            "aftime": "0",  # 前复权
        }
        stdout = self._call_wind("stock_data", "get_stock_kline", params)
        if stdout is None:
            return None

        try:
            data = self._parse_json(stdout)
            if isinstance(data, list):
                df = pd.DataFrame(data)
            elif isinstance(data, dict):
                df = pd.DataFrame([data]) if "date" in data else pd.DataFrame(data.get("data", []))
            else:
                return None

            if df.empty:
                return None

            # Standardize columns
            col_map = {
                "date": "date", "trade_date": "date", "日期": "date",
                "close": "close", "closing_price": "close", "收盘价": "close",
                "open": "open", "opening_price": "open", "开盘价": "open",
                "high": "high", "highest_price": "high", "最高价": "high",
                "low": "low", "lowest_price": "low", "最低价": "low",
                "volume": "volume", "交易量": "volume",
            }
            df = df.rename(columns={k: v for k, v in col_map.items() if k in df.columns})

            if "date" in df.columns:
                df["date"] = pd.to_datetime(df["date"])
                df = df.set_index("date")

            return df
        except Exception as e:
            logger.error("Failed to parse K-line for %s: %s", symbol, e)
            return None

    # ------------------------------------------------------------------
    # Index prices
    # ------------------------------------------------------------------

    def get_index_prices(
        self,
        index_code: str,
        start: str,
        end: str,
    ) -> pd.Series:
        """Fetch index K-line via Wind MCP."""
        params = {
            "windcode": index_code,
            "begin_date": self._fmt_date(start),
            "end_date": self._fmt_date(end),
            "aftime": "0",
        }
        stdout = self._call_wind("index_data", "get_index_kline", params)
        if stdout is None:
            return pd.Series(dtype=float)

        df = self._parse_kline_series(stdout, "close")
        if df is not None and not df.empty:
            return df
        return pd.Series(dtype=float)

    def get_index_indicators(self, index_code: str) -> dict:
        """Fetch index price indicators (PE, PB, yield, etc.).

        Returns a dict with indicator names as keys.
        """
        params = {
            "windcode": index_code,
            "indexes": "最新成交价,涨跌幅,市盈率,市净率,股息率",
        }
        stdout = self._call_wind("index_data", "get_index_price_indicators", params)
        if stdout is None:
            return {}
        return self._parse_json(stdout) or {}

    # ------------------------------------------------------------------
    # Risk-free rate — via economic_data
    # ------------------------------------------------------------------

    def get_risk_free_rate(
        self,
        start: str,
        end: str,
    ) -> pd.Series:
        """Fetch China 10Y government bond yield via Wind MCP.

        Uses economic_data.natural_language_get_edb_data with
        executionMode="searchFetch" to find and fetch the 10Y yield.
        """
        params = {
            "executionMode": "searchFetch",
            "question": "中国10年期国债收益率",
            "beginDate": self._fmt_date(start),
            "endDate": self._fmt_date(end),
        }
        stdout = self._call_wind("economic_data", "natural_language_get_edb_data", params)
        if stdout is None:
            return self._fallback_risk_free_rate(start, end)

        series = self._parse_edb_series(stdout)
        if series is not None and not series.empty:
            # Convert annual yield (%) to daily rate
            daily_rf = (1 + series / 100.0) ** (1 / 252) - 1
            return daily_rf

        return self._fallback_risk_free_rate(start, end)

    def get_macro_indicator(
        self, question: str, start: str, end: str
    ) -> Optional[pd.Series]:
        """Fetch any macro indicator via NL query.

        Examples:
            get_macro_indicator("中国CPI同比", "2024-01-01", "2024-12-31")
            get_macro_indicator("中国M2同比增速", "2024-01-01", "2024-12-31")
            get_macro_indicator("美国联邦基金利率", "2024-01-01", "2024-12-31")
            get_macro_indicator("中国社会融资规模", "2024-01-01", "2024-12-31")
        """
        params = {
            "executionMode": "searchFetch",
            "question": question,
            "beginDate": self._fmt_date(start),
            "endDate": self._fmt_date(end),
        }
        stdout = self._call_wind("economic_data", "natural_language_get_edb_data", params)
        if stdout is None:
            return None
        return self._parse_edb_series(stdout)

    # ------------------------------------------------------------------
    # Market caps and book-to-market — via fundamentals
    # ------------------------------------------------------------------

    def get_market_caps(
        self,
        symbols: list[str],
        start: str,
        end: str,
    ) -> pd.DataFrame:
        """Fetch market cap via Wind MCP fundamentals.

        Uses stock_data.get_stock_fundamentals with NL question.
        Falls back to synthetic if unavailable.
        """
        # Fallback: try AKShare, then synthetic
        try:
            from claw_quant.data_akshare import AKShareDataProvider
            return AKShareDataProvider().get_market_caps(symbols, start, end)
        except Exception:
            from claw_quant.data_synthetic import SyntheticDataProvider
            return SyntheticDataProvider().get_market_caps(symbols, start, end)

    def get_book_to_market(
        self,
        symbols: list[str],
        start: str,
        end: str,
    ) -> pd.DataFrame:
        """Fetch book-to-market via Wind MCP fundamentals.

        Falls back to AKShare, then synthetic.
        """
        # Fallback: try AKShare, then synthetic
        try:
            from claw_quant.data_akshare import AKShareDataProvider
            return AKShareDataProvider().get_book_to_market(symbols, start, end)
        except Exception:
            from claw_quant.data_synthetic import SyntheticDataProvider
            return SyntheticDataProvider().get_book_to_market(symbols, start, end)

    def get_margin_data(
        self,
        start: str,
        end: str,
    ) -> pd.DataFrame:
        """Fetch margin trading data (融资融券).

        Wind MCP does not have a dedicated margin trading endpoint.
        Delegates to AKShare for SSE/SZSE margin data.
        Falls back to synthetic if AKShare is unavailable.
        """
        try:
            from claw_quant.data_akshare import AKShareDataProvider
            ak = AKShareDataProvider()
            return ak.get_margin_data(start, end)
        except Exception:
            from claw_quant.data_synthetic import SyntheticDataProvider
            return SyntheticDataProvider().get_margin_data(start, end)

    def get_northbound_flow(self, start: str = None, end: str = None) -> dict:
        """Fetch northbound flow summary (北向资金).

        Wind MCP does not have a northbound flow endpoint.
        Delegates to AKShare.
        """
        try:
            from claw_quant.data_akshare import AKShareDataProvider
            ak = AKShareDataProvider()
            return ak.get_northbound_summary()
        except Exception:
            return {"latest_net_flow": 0, "flow_5d": 0, "flow_20d": 0, "trend": "unknown"}

    # ------------------------------------------------------------------
    # Wind MCP CLI call
    # ------------------------------------------------------------------

    def _call_wind(
        self,
        server_type: str,
        tool_name: str,
        params: dict,
    ) -> Optional[str]:
        """Call the Wind MCP Skill CLI.

        Format:
            node scripts/cli.mjs call <server_type> <tool_name> '<JSON params>'

        Args:
            server_type: e.g., 'stock_data', 'economic_data', 'index_data'.
            tool_name: e.g., 'get_stock_kline', 'natural_language_get_edb_data'.
            params: Dict of parameter names to values.

        Returns:
            Raw JSON string from stdout, or None on failure.
        """
        json_params = json.dumps(params, ensure_ascii=False)
        cmd = ["node", self._cli_path, "call", server_type, tool_name, json_params]

        logger.info("Wind CLI: %s %s ...", server_type, tool_name)

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120,
                env={**os.environ, "WIND_API_KEY": self._api_key},
            )
            if result.returncode != 0:
                logger.error(
                    "Wind CLI failed (code %d): %s",
                    result.returncode,
                    result.stderr[:500] if result.stderr else "(no stderr)",
                )
                return None
            return result.stdout.strip()
        except FileNotFoundError:
            logger.warning(
                "Wind MCP CLI not found at '%s'. "
                "Clone https://github.com/Wind-Information-Co-Ltd/wind-skills "
                "and run 'npm install' in that directory.",
                self._cli_path,
            )
            return None
        except subprocess.TimeoutExpired:
            logger.error("Wind CLI timed out")
            return None
        except Exception as e:
            logger.error("Wind CLI error: %s", e)
            return None

    # ------------------------------------------------------------------
    # Parsing helpers
    # ------------------------------------------------------------------

    def _parse_json(self, stdout: str) -> Optional[dict | list]:
        """Parse JSON from Wind CLI output."""
        try:
            return json.loads(stdout)
        except json.JSONDecodeError:
            # Sometimes Wind returns NDJSON or extra text
            for line in stdout.strip().split("\n"):
                line = line.strip()
                if line.startswith("{") or line.startswith("["):
                    try:
                        return json.loads(line)
                    except json.JSONDecodeError:
                        continue
            logger.error("Failed to parse Wind JSON: %s", stdout[:200])
            return None

    def _parse_kline_series(
        self, stdout: str, field: str = "close"
    ) -> Optional[pd.Series]:
        """Parse K-line JSON to a Series indexed by date."""
        data = self._parse_json(stdout)
        if data is None:
            return None

        if isinstance(data, list):
            df = pd.DataFrame(data)
        elif isinstance(data, dict):
            df = pd.DataFrame(data.get("data", [data]))
        else:
            return None

        if df.empty:
            return None

        # Find date and value columns
        date_col = None
        val_col = None
        for col in df.columns:
            col_lower = col.lower()
            if "date" in col_lower or "日期" in col:
                date_col = col
            if field in col_lower or field in col:
                val_col = col

        if date_col is None or val_col is None:
            if len(df.columns) >= 2:
                date_col = df.columns[0]
                val_col = df.columns[1]
            else:
                return None

        df[date_col] = pd.to_datetime(df[date_col])
        return df.set_index(date_col)[val_col]

    def _parse_edb_series(self, stdout: str) -> Optional[pd.Series]:
        """Parse economic_data EDB response to a Series."""
        return self._parse_kline_series(stdout, "value")

    def _fallback_prices(
        self, symbols: list[str], start: str, end: str
    ) -> pd.DataFrame:
        """Fallback to AKShare when Wind is unavailable, then synthetic."""
        try:
            from claw_quant.data_akshare import AKShareDataProvider
            result = AKShareDataProvider().get_stock_prices(symbols, start, end)
            if result is not None and not result.empty:
                return result
        except Exception:
            pass
        from claw_quant.data_synthetic import SyntheticDataProvider
        return SyntheticDataProvider().get_stock_prices(symbols, start, end)

    def _fallback_risk_free_rate(self, start: str, end: str) -> pd.Series:
        """Fallback risk-free rate: try AKShare, then default 2.5%."""
        try:
            from claw_quant.data_akshare import AKShareDataProvider
            result = AKShareDataProvider().get_risk_free_rate(start, end)
            if result is not None and not result.empty:
                return result
        except Exception:
            pass
        return self._default_risk_free_rate(start, end)

    def _default_risk_free_rate(self, start: str, end: str) -> pd.Series:
        """Default 2.5% annual risk-free rate."""
        dates = pd.bdate_range(start=start, end=end)
        daily_rf = (1 + 0.025) ** (1 / 252) - 1
        return pd.Series(daily_rf, index=dates, name="rf")

    @staticmethod
    def _fmt_date(date_str: str) -> str:
        """Convert YYYY-MM-DD to yyyyMMdd."""
        return date_str.replace("-", "")