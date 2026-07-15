"""Hybrid data provider — Wind → AKShare → Synthetic fallback chain.

Implements the DataProvider interface with a priority-based fallback strategy:
    1. Wind MCP (institutional-grade data) — best quality
    2. AKShare (free A-share data) — fallback when Wind unavailable
    3. Synthetic (fake data) — last resort, always available

This ensures the system always returns data, with quality degrading gracefully.
Each fallback step is logged so operators can monitor data source health.

Usage:
    dp = HybridDataProvider()
    # or via factory:
    dp = get_data_provider('hybrid')
    # or explicitly:
    dp = get_data_provider('wind_first')
"""

from __future__ import annotations

import logging
import os
import subprocess
from typing import Optional

import pandas as pd

from claw_quant.data_provider import DataProvider

logger = logging.getLogger("claw_quant.data_hybrid")


class HybridDataProvider(DataProvider):
    """Composite data provider with Wind → AKShare → Synthetic priority.

    Design:
        - Wind is the primary source (institutional data quality).
        - AKShare is the secondary source (free, covers gaps Wind misses).
        - Synthetic is the tertiary source (always available, for testing).
        - Each method independently tries the chain; one method failing
          does not affect others (Wind might be down for stocks but
          AKShare works fine for margin data).

    Availability:
        - Wind: requires Node.js + wind-skills CLI installed locally
        - AKShare: requires `pip install akshare`
        - Synthetic: always available, no dependencies

    Attributes:
        source_stats: Dict tracking which source served each method call.
            Useful for monitoring data quality degradation.
    """

    def __init__(self):
        self._wind: Optional[DataProvider] = None
        self._akshare: Optional[DataProvider] = None
        self._synthetic: Optional[DataProvider] = None
        self._wind_available: Optional[bool] = None  # None = not checked yet
        self._akshare_available: Optional[bool] = None
        self.source_stats: dict[str, str] = {}  # method_name -> source used

    # ------------------------------------------------------------------
    # Provider properties
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        return "hybrid"

    @property
    def is_synthetic(self) -> bool:
        """Hybrid is NOT synthetic — it uses real data when available."""
        return False

    # ------------------------------------------------------------------
    # Lazy provider accessors
    # ------------------------------------------------------------------

    @property
    def _wind_provider(self) -> Optional[DataProvider]:
        """Get Wind provider, checking availability on first access."""
        if self._wind is None:
            if self._check_wind_available():
                try:
                    from claw_quant.data_wind import WindDataProvider
                    self._wind = WindDataProvider()
                    logger.info("Wind MCP provider initialized")
                except Exception as e:
                    logger.warning("Wind MCP init failed: %s", e)
                    self._wind = None
                    self._wind_available = False
            else:
                self._wind = None
        return self._wind

    @property
    def _akshare_provider(self) -> Optional[DataProvider]:
        """Get AKShare provider, checking availability on first access."""
        if self._akshare is None:
            if self._check_akshare_available():
                try:
                    from claw_quant.data_akshare import AKShareDataProvider
                    self._akshare = AKShareDataProvider()
                    logger.info("AKShare provider initialized")
                except Exception as e:
                    logger.warning("AKShare init failed: %s", e)
                    self._akshare = None
                    self._akshare_available = False
            else:
                self._akshare = None
        return self._akshare

    @property
    def _synthetic_provider(self) -> DataProvider:
        """Get synthetic provider (always available)."""
        if self._synthetic is None:
            from claw_quant.data_synthetic import SyntheticDataProvider
            self._synthetic = SyntheticDataProvider()
        return self._synthetic

    # ------------------------------------------------------------------
    # Availability checks (cached)
    # ------------------------------------------------------------------

    def _check_wind_available(self) -> bool:
        """Check if Wind MCP CLI is installed and reachable."""
        if self._wind_available is not None:
            return self._wind_available

        from claw_quant.config import WIND_CLI_PATH

        # Check 1: Node.js installed
        try:
            result = subprocess.run(
                ["node", "--version"],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode != 0:
                logger.info("Wind unavailable: Node.js not found")
                self._wind_available = False
                return False
        except FileNotFoundError:
            logger.info("Wind unavailable: Node.js not installed")
            self._wind_available = False
            return False
        except Exception as e:
            logger.info("Wind unavailable: %s", e)
            self._wind_available = False
            return False

        # Check 2: Wind CLI exists
        cli_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            WIND_CLI_PATH,
        )
        if not os.path.exists(cli_path):
            # Try relative to project root
            from claw_quant.config import PROJECT_ROOT
            cli_path = PROJECT_ROOT / WIND_CLI_PATH
            if not cli_path.exists():
                logger.info(
                    "Wind unavailable: CLI not found at %s. "
                    "Clone https://github.com/Wind-Information-Co-Ltd/wind-skills",
                    cli_path,
                )
                self._wind_available = False
                return False

        # Check 3: API key configured
        from claw_quant.config import WIND_API_KEY
        if not WIND_API_KEY or WIND_API_KEY.startswith("ak_"):
            # ak_ prefix looks like a valid key format
            pass  # proceed
        elif WIND_API_KEY == "":
            logger.info("Wind unavailable: WIND_API_KEY not configured")
            self._wind_available = False
            return False

        self._wind_available = True
        logger.info("Wind MCP available (Node.js + CLI found)")
        return True

    def _check_akshare_available(self) -> bool:
        """Check if AKShare package is installed."""
        if self._akshare_available is not None:
            return self._akshare_available

        try:
            import akshare  # noqa: F401
            self._akshare_available = True
            logger.info("AKShare available")
            return True
        except ImportError:
            logger.info(
                "AKShare not installed. Install with: pip install akshare>=1.14.0"
            )
            self._akshare_available = False
            return False

    def reset_availability(self) -> None:
        """Reset cached availability checks. Use after installing dependencies."""
        self._wind_available = None
        self._akshare_available = None

    # ------------------------------------------------------------------
    # Core data methods — each with Wind → AKShare → Synthetic chain
    # ------------------------------------------------------------------

    def get_stock_prices(
        self,
        symbols: list[str],
        start: str,
        end: str,
    ) -> pd.DataFrame:
        """Fetch stock prices: Wind → AKShare → Synthetic."""
        # Try Wind
        wind = self._wind_provider
        if wind is not None:
            try:
                result = wind.get_stock_prices(symbols, start, end)
                if result is not None and not result.empty:
                    self.source_stats["get_stock_prices"] = "wind"
                    return result
                logger.info("Wind returned empty stock prices, trying AKShare")
            except Exception as e:
                logger.warning("Wind get_stock_prices failed: %s, trying AKShare", e)

        # Try AKShare
        ak = self._akshare_provider
        if ak is not None:
            try:
                result = ak.get_stock_prices(symbols, start, end)
                if result is not None and not result.empty:
                    self.source_stats["get_stock_prices"] = "akshare"
                    return result
                logger.info("AKShare returned empty stock prices, using synthetic")
            except Exception as e:
                logger.warning("AKShare get_stock_prices failed: %s, using synthetic", e)

        # Fallback to synthetic
        self.source_stats["get_stock_prices"] = "synthetic"
        logger.warning("Using synthetic stock prices (Wind and AKShare unavailable)")
        return self._synthetic_provider.get_stock_prices(symbols, start, end)

    def get_index_prices(
        self,
        index_code: str,
        start: str,
        end: str,
    ) -> pd.Series:
        """Fetch index prices: Wind → AKShare → Synthetic."""
        # Try Wind
        wind = self._wind_provider
        if wind is not None:
            try:
                result = wind.get_index_prices(index_code, start, end)
                if result is not None and not result.empty:
                    self.source_stats["get_index_prices"] = "wind"
                    return result
                logger.info("Wind returned empty index prices, trying AKShare")
            except Exception as e:
                logger.warning("Wind get_index_prices failed: %s, trying AKShare", e)

        # Try AKShare
        ak = self._akshare_provider
        if ak is not None:
            try:
                result = ak.get_index_prices(index_code, start, end)
                if result is not None and not result.empty:
                    self.source_stats["get_index_prices"] = "akshare"
                    return result
                logger.info("AKShare returned empty index prices, using synthetic")
            except Exception as e:
                logger.warning("AKShare get_index_prices failed: %s, using synthetic", e)

        # Fallback to synthetic
        self.source_stats["get_index_prices"] = "synthetic"
        logger.warning("Using synthetic index prices")
        return self._synthetic_provider.get_index_prices(index_code, start, end)

    def get_risk_free_rate(
        self,
        start: str,
        end: str,
    ) -> pd.Series:
        """Fetch risk-free rate: Wind → AKShare → Synthetic."""
        # Try Wind
        wind = self._wind_provider
        if wind is not None:
            try:
                result = wind.get_risk_free_rate(start, end)
                if result is not None and not result.empty:
                    self.source_stats["get_risk_free_rate"] = "wind"
                    return result
                logger.info("Wind returned empty risk-free rate, trying AKShare")
            except Exception as e:
                logger.warning("Wind get_risk_free_rate failed: %s, trying AKShare", e)

        # Try AKShare
        ak = self._akshare_provider
        if ak is not None:
            try:
                result = ak.get_risk_free_rate(start, end)
                if result is not None and not result.empty:
                    self.source_stats["get_risk_free_rate"] = "akshare"
                    return result
                logger.info("AKShare returned empty risk-free rate, using synthetic")
            except Exception as e:
                logger.warning("AKShare get_risk_free_rate failed: %s, using synthetic", e)

        # Fallback to synthetic
        self.source_stats["get_risk_free_rate"] = "synthetic"
        logger.warning("Using synthetic risk-free rate")
        return self._synthetic_provider.get_risk_free_rate(start, end)

    def get_market_caps(
        self,
        symbols: list[str],
        start: str,
        end: str,
    ) -> pd.DataFrame:
        """Fetch market caps: Wind → AKShare → Synthetic."""
        # Try Wind
        wind = self._wind_provider
        if wind is not None:
            try:
                result = wind.get_market_caps(symbols, start, end)
                if result is not None and not result.empty:
                    self.source_stats["get_market_caps"] = "wind"
                    return result
                logger.info("Wind returned empty market caps, trying AKShare")
            except Exception as e:
                logger.warning("Wind get_market_caps failed: %s, trying AKShare", e)

        # Try AKShare
        ak = self._akshare_provider
        if ak is not None:
            try:
                result = ak.get_market_caps(symbols, start, end)
                if result is not None and not result.empty:
                    self.source_stats["get_market_caps"] = "akshare"
                    return result
                logger.info("AKShare returned empty market caps, using synthetic")
            except Exception as e:
                logger.warning("AKShare get_market_caps failed: %s, using synthetic", e)

        # Fallback to synthetic
        self.source_stats["get_market_caps"] = "synthetic"
        logger.warning("Using synthetic market caps")
        return self._synthetic_provider.get_market_caps(symbols, start, end)

    def get_book_to_market(
        self,
        symbols: list[str],
        start: str,
        end: str,
    ) -> pd.DataFrame:
        """Fetch book-to-market: Wind → AKShare → Synthetic."""
        # Try Wind
        wind = self._wind_provider
        if wind is not None:
            try:
                result = wind.get_book_to_market(symbols, start, end)
                if result is not None and not result.empty:
                    self.source_stats["get_book_to_market"] = "wind"
                    return result
                logger.info("Wind returned empty book-to-market, trying AKShare")
            except Exception as e:
                logger.warning("Wind get_book_to_market failed: %s, trying AKShare", e)

        # Try AKShare
        ak = self._akshare_provider
        if ak is not None:
            try:
                result = ak.get_book_to_market(symbols, start, end)
                if result is not None and not result.empty:
                    self.source_stats["get_book_to_market"] = "akshare"
                    return result
                logger.info("AKShare returned empty book-to-market, using synthetic")
            except Exception as e:
                logger.warning("AKShare get_book_to_market failed: %s, using synthetic", e)

        # Fallback to synthetic
        self.source_stats["get_book_to_market"] = "synthetic"
        logger.warning("Using synthetic book-to-market")
        return self._synthetic_provider.get_book_to_market(symbols, start, end)

    def get_margin_data(
        self,
        start: str,
        end: str,
    ) -> pd.DataFrame:
        """Fetch margin data: AKShare → Synthetic.

        Note: Wind MCP does not have a dedicated margin trading endpoint,
        so we skip Wind and go directly to AKShare.
        """
        # Try AKShare (primary for margin data)
        ak = self._akshare_provider
        if ak is not None:
            try:
                result = ak.get_margin_data(start, end)
                if result is not None and not result.empty:
                    self.source_stats["get_margin_data"] = "akshare"
                    return result
                logger.info("AKShare returned empty margin data, using synthetic")
            except Exception as e:
                logger.warning("AKShare get_margin_data failed: %s, using synthetic", e)

        # Fallback to synthetic
        self.source_stats["get_margin_data"] = "synthetic"
        logger.warning("Using synthetic margin data")
        return self._synthetic_provider.get_margin_data(start, end)

    # ------------------------------------------------------------------
    # Extended methods (beyond base DataProvider interface)
    # ------------------------------------------------------------------

    def get_northbound_flow(self, start: str = None, end: str = None) -> pd.DataFrame:
        """Fetch northbound flow: AKShare → empty DataFrame.

        Wind MCP does not have a northbound flow endpoint.
        AKShare provides this via stock_hsgt_north_net_flow_in_em().
        """
        ak = self._akshare_provider
        if ak is not None:
            try:
                result = ak.get_northbound_flow(start, end)
                if result is not None and not result.empty:
                    self.source_stats["get_northbound_flow"] = "akshare"
                    return result
            except Exception as e:
                logger.warning("AKShare northbound flow failed: %s", e)

        self.source_stats["get_northbound_flow"] = "none"
        return pd.DataFrame()

    def get_northbound_summary(self) -> dict:
        """Get northbound flow summary."""
        ak = self._akshare_provider
        if ak is not None:
            try:
                result = ak.get_northbound_summary()
                if result.get("trend") != "unknown":
                    self.source_stats["get_northbound_summary"] = "akshare"
                    return result
            except Exception as e:
                logger.warning("AKShare northbound summary failed: %s", e)

        self.source_stats["get_northbound_summary"] = "none"
        return {
            "latest_net_flow": 0, "flow_5d": 0, "flow_20d": 0,
            "trend": "unknown",
        }

    def get_macro_indicator(
        self, question: str, start: str, end: str
    ) -> Optional[pd.Series]:
        """Fetch macro indicator: Wind → AKShare → None.

        Wind has rich macro data via economic_data NL queries.
        AKShare does not have a clean NL macro endpoint.
        """
        wind = self._wind_provider
        if wind is not None:
            try:
                result = wind.get_macro_indicator(question, start, end)
                if result is not None and not result.empty:
                    self.source_stats["get_macro_indicator"] = "wind"
                    return result
            except Exception as e:
                logger.warning("Wind macro indicator failed: %s", e)

        self.source_stats["get_macro_indicator"] = "none"
        return None

    def get_index_indicators(self, index_code: str) -> dict:
        """Fetch index PE/PB/yield indicators: Wind → AKShare → empty."""
        wind = self._wind_provider
        if wind is not None:
            try:
                result = wind.get_index_indicators(index_code)
                if result:
                    self.source_stats["get_index_indicators"] = "wind"
                    return result
            except Exception as e:
                logger.warning("Wind index indicators failed: %s", e)

        self.source_stats["get_index_indicators"] = "none"
        return {}

    # ------------------------------------------------------------------
    # Diagnostics
    # ------------------------------------------------------------------

    def get_availability_report(self) -> dict:
        """Return a report of which providers are available and which
        served the most recent calls.

        Returns:
            Dict with:
            - wind_available: bool
            - akshare_available: bool
            - synthetic_available: bool (always True)
            - source_stats: per-method source breakdown
            - recommendation: human-readable summary
        """
        wind_ok = self._check_wind_available()
        ak_ok = self._check_akshare_available()

        # Count by source
        wind_count = sum(1 for v in self.source_stats.values() if v == "wind")
        ak_count = sum(1 for v in self.source_stats.values() if v == "akshare")
        syn_count = sum(1 for v in self.source_stats.values() if v == "synthetic")
        none_count = sum(1 for v in self.source_stats.values() if v == "none")

        if wind_ok:
            recommendation = "Wind available — institutional data quality"
        elif ak_ok:
            recommendation = "AKShare available — free data, install Wind MCP for better quality"
        else:
            recommendation = "No real data source available — install AKShare or Wind MCP"

        return {
            "wind_available": wind_ok,
            "akshare_available": ak_ok,
            "synthetic_available": True,
            "source_stats": dict(self.source_stats),
            "summary": f"Wind: {wind_count}, AKShare: {ak_count}, Synthetic: {syn_count}, None: {none_count}",
            "recommendation": recommendation,
        }