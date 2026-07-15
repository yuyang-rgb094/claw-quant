"""Centralized configuration for Claw Quant.

All hardcoded paths, constants, and parameters extracted from the 5 scripts
into a single source of truth. Scripts import from here instead of defining
their own local copies.
"""

from __future__ import annotations

from pathlib import Path

# ---------------------------------------------------------------------------
# Project paths
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
TESTS_DIR = PROJECT_ROOT / "tests"

# ---------------------------------------------------------------------------
# Database paths
# ---------------------------------------------------------------------------

DB_PATHS = {
    "carhart": DATA_DIR / "carhart_results.db",
    "factor_ic": DATA_DIR / "factor_ic.db",
    "crowding": DATA_DIR / "crowding.db",
    "cffex": DATA_DIR / "cffex_positions.db",
    "validation": DATA_DIR / "validation_metrics.db",
}

# ---------------------------------------------------------------------------
# State file paths
# ---------------------------------------------------------------------------

FISHER_STATE_PATH = PROJECT_ROOT / "fisher_state.md"
SFM_STATE_PATH = PROJECT_ROOT / "sfm_state.md"
DAMODARAN_STATE_PATH = PROJECT_ROOT / "portfolio" / "damodaran_state.md"
CAPITAL_ALLOCATION_REGISTRY_PATH = PROJECT_ROOT / "portfolio" / "capital_allocation_registry.md"

# ---------------------------------------------------------------------------
# Default stock universe (CSI 300 + CSI 500 representative subset)
# ---------------------------------------------------------------------------

DEFAULT_UNIVERSE: list[str] = [
    "600519.SH",  # 贵州茅台
    "000858.SZ",  # 五粮液
    "601318.SH",  # 中国平安
    "600036.SH",  # 招商银行
    "000333.SZ",  # 美的集团
    "600276.SH",  # 恒瑞医药
    "601012.SH",  # 隆基绿能
    "600900.SH",  # 长江电力
    "000725.SZ",  # 京东方A
    "002415.SZ",  # 海康威视
]

# ---------------------------------------------------------------------------
# Wind API (optional)
# ---------------------------------------------------------------------------

WIND_CLI_PATH = "node scripts/cli.mjs"
RISK_FREE_WIND_CODE = "G1009419"  # 中债国债到期收益率:10年

# ---------------------------------------------------------------------------
# Factor IC engine constants
# ---------------------------------------------------------------------------

FORWARD_PERIODS: list[int] = [1, 5, 10, 20, 60, 120]

DURATION_BUCKETS: dict[str, list[str]] = {
    "short_term": ["5d_reversal", "overnight_gap", "volume_shock"],
    "medium_term": ["12m_momentum", "200d_trend", "earnings_revision"],
    "long_term": ["value", "quality", "low_volatility", "dividend_yield"],
}

FACTOR_TO_BUCKET: dict[str, str] = {
    f: bucket for bucket, factors in DURATION_BUCKETS.items() for f in factors
}

FACTOR_ALIASES: dict[str, str] = {
    "reversal": "5d_reversal",
    "momentum": "12m_momentum",
    "trend": "200d_trend",
    "lowvol": "low_volatility",
    "divyield": "dividend_yield",
    "earnings": "earnings_revision",
    "gap": "overnight_gap",
    "shock": "volume_shock",
}

MONTHLY_WINDOW: int = 21
DECAY_TREND_MONTHS: int = 6

# ---------------------------------------------------------------------------
# Crowding (long/short cost) constants
# ---------------------------------------------------------------------------

WEIGHT_COST: float = 0.40
WEIGHT_CONCENTRATION: float = 0.35
WEIGHT_CORR_DISTORTION: float = 0.25

ANNUALISATION_DAYS: int = 360
CORR_WINDOW: int = 60
HIST_BASELINE_WINDOW: int = 252

# ---------------------------------------------------------------------------
# Options proxy constants
# ---------------------------------------------------------------------------

HIGH_BETA_THRESHOLD: float = 1.2
LOW_BETA_THRESHOLD: float = 0.7

FUNDAMENTAL_DURATIONS: dict[str, float] = {
    "momentum_stocks": 6.5,
    "value_stocks": 3.5,
    "growth_stocks": 9.0,
    "quality_stocks": 5.0,
    "low_volatility_stocks": 4.0,
    "dividend_stocks": 2.5,
}

DEFAULT_UST_CHANGE: float = -0.05

# ---------------------------------------------------------------------------
# CFFEX scraper constants
# ---------------------------------------------------------------------------

CFFEX_BASE_URL = "http://www.cffex.com.cn/sj/ccpm"
CFFEX_SYMBOLS = ("IF", "IC", "IM", "IH")
CFFEX_RETRY_COUNT = 3
CFFEX_RETRY_DELAY = 2.0  # seconds
CFFEX_INTER_SYMBOL_DELAY = 1.0  # seconds

# ---------------------------------------------------------------------------
# Data provider
# ---------------------------------------------------------------------------

DATA_PROVIDER = "hybrid"  # 'hybrid' (Wind→AKShare→Synthetic) | 'wind' | 'akshare' | 'synthetic'

# Wind MCP API key (https://github.com/Wind-Information-Co-Ltd/wind-skills)
# Set via environment variable: export WIND_API_KEY="your_key_here"
import os
WIND_API_KEY = os.environ.get("WIND_API_KEY", "")
WIND_CLI_PATH = "node scripts/cli.mjs"

# ---------------------------------------------------------------------------
# Conviction formula
# ---------------------------------------------------------------------------

CONVICTION_WEIGHTS = (0.3, 0.5, 0.2)  # (w_evidence, w_ir, w_gmm), must sum to 1.0
CONVICTION_CAPS = {
    "ir_low": 0.3,   # IR below this → cap conviction
    "ir_cap": 0.4,   # max conviction when IR is low
    "gmm_low": 1.0,  # alpha t-stat below this → cap conviction
    "gmm_cap": 0.5,  # max conviction when GMM is low
    "synthetic_cap": 0.5,  # max conviction when using synthetic data
}

# ---------------------------------------------------------------------------
# Graham Interface Contract
# ---------------------------------------------------------------------------

INTERFACE_TOKEN_BUDGET = 400  # Target token budget per interface


def resolve_factor_name(name: str) -> str:
    """Resolve a CLI factor alias to its canonical name."""
    return FACTOR_ALIASES.get(name.lower(), name)