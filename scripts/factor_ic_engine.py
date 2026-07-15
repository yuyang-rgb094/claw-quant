#!/usr/bin/env python3
"""
factor_ic_engine.py — SFM Layer Module 1b: Factor Duration Spectrum
======================================================================

Purpose
-------
Calculate Information Coefficient (IC) and factor half-life for the SFM
Layer (ADR-014, Module 1b — Factor Duration Spectrum).

Financial Theory
----------------
The Sharpe (1964) equation E(R^e_i) = α_i + β'_i · γ decomposes expected
returns into systematic risk premia (β·γ — the *shape* of the return
manifold) and anomaly (α — the *position* on the manifold).

**Information Coefficient (IC)** is the cross-sectional Spearman rank
correlation between a factor's value and the subsequent forward return.
A persistent positive IC means the factor carries predictive content for
the systematic topology (β·γ). IC is the standard single-period metric
for factor quality in both academic (Fama-MacBeth) and practitioner
(Grinold's Fundamental Law: IR ≈ IC · √N) frameworks.

**Factor half-life** is the time for IC to decay by half, modelled as an
exponential decay:

    IC(t) = IC_0 · exp(-t / τ)

where half-life = τ · ln(2). This is the *duration* dimension added on
top of Carhart's static four-factor attribution. Per Daniel & Moskowitz
(2016, JFE 122(2):221-247), 12-month momentum exhibits a half-life of
approximately 70.9 trading days — the anchor for the medium-term bucket.

**Decay status** classifies the temporal trajectory of the factor's signal:
  - stable        : half-life roughly constant over rolling windows
  - accelerating  : half-life decreasing (signal dying faster — crowding risk)
  - reversing     : IC sign flipping (signal broken / regime change)

Half-life is the *generalisation axis* of the SFM layer: it lets the
same tracking logic work in any market state — only the signal strengths
across the three duration buckets (short / medium / long) change.

Install
-------
    pip install --break-system-packages pandas numpy scipy pyyaml

Usage
-----
    python factor_ic_engine.py --factor momentum,value,quality \
        --period 2024-01-01:2026-07-01 --output yaml

Outputs
-------
- SQLite database at data/factor_ic.db (IC series, half-life estimates)
- YAML to stdout (or file) for sfm_state.md Module 1b

Author: Claw Quant
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import yaml
from scipy.optimize import curve_fit
from scipy.stats import spearmanr

# ---------------------------------------------------------------------------
# Constants & configuration (imported from shared package)
# ---------------------------------------------------------------------------

from claw_quant.config import (
    FORWARD_PERIODS,
    DURATION_BUCKETS,
    FACTOR_TO_BUCKET,
    FACTOR_ALIASES,
    MONTHLY_WINDOW,
    DECAY_TREND_MONTHS,
    resolve_factor_name,
)
from claw_quant.config import DB_PATHS

DB_PATH = DB_PATHS["factor_ic"]


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class ICResult:
    """Single factor IC result for one forward period."""
    factor: str
    forward_days: int
    ic_mean: float
    ic_std: float
    ic_tstat: float
    hit_rate: float  # fraction of periods with IC > 0


@dataclass
class HalfLifeResult:
    """Exponential decay fit result for a single factor."""
    factor: str
    ic_0: float          # estimated initial IC
    tau: float           # decay time constant (days)
    half_life_days: float  # = tau * ln(2)
    r_squared: float
    decay_status: str    # stable / accelerating / reversing


@dataclass
class FactorReport:
    """Aggregated report for one factor across all forward periods."""
    factor: str
    duration_bucket: str
    ic_results: List[ICResult] = field(default_factory=list)
    half_life: Optional[HalfLifeResult] = None

    @property
    def current_ic_mean(self) -> float:
        """Mean IC averaged across all forward periods."""
        if not self.ic_results:
            return 0.0
        return float(np.mean([r.ic_mean for r in self.ic_results]))

    @property
    def current_ic_std(self) -> float:
        """Std IC averaged across all forward periods."""
        if not self.ic_results:
            return 0.0
        return float(np.mean([r.ic_std for r in self.ic_results]))


# ---------------------------------------------------------------------------
# Database layer
# ---------------------------------------------------------------------------

def init_db(db_path: Path = DB_PATH) -> sqlite3.Connection:
    """Create SQLite tables for IC series and half-life estimates."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS ic_series (
            factor     TEXT NOT NULL,
            date       TEXT NOT NULL,
            forward_days INTEGER NOT NULL,
            ic         REAL,
            PRIMARY KEY (factor, date, forward_days)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS half_life (
            factor          TEXT PRIMARY KEY,
            ic_0            REAL,
            tau             REAL,
            half_life_days  REAL,
            r_squared       REAL,
            decay_status    TEXT,
            updated_at      TEXT
        )
        """
    )
    conn.commit()
    return conn


def save_ic_series(
    conn: sqlite3.Connection,
    factor: str,
    ic_df: pd.DataFrame,
) -> None:
    """Persist rolling IC time series to SQLite."""
    rows: List[Tuple] = []
    for col in ic_df.columns:
        if not col.startswith("ic_"):
            continue
        forward_days = int(col.split("_")[1])
        for date, val in ic_df[col].items():
            if np.isnan(val):
                continue
            rows.append((factor, date.strftime("%Y-%m-%d"), forward_days, float(val)))
    conn.executemany(
        "INSERT OR REPLACE INTO ic_series VALUES (?, ?, ?, ?)", rows
    )
    conn.commit()


def save_half_life(
    conn: sqlite3.Connection, result: HalfLifeResult
) -> None:
    """Persist half-life estimate to SQLite."""
    from datetime import datetime

    conn.execute(
        """
        INSERT OR REPLACE INTO half_life
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            result.factor,
            result.ic_0,
            result.tau,
            result.half_life_days,
            result.r_squared,
            result.decay_status,
            datetime.utcnow().isoformat(),
        ),
    )
    conn.commit()


# ---------------------------------------------------------------------------
# Factor definitions (built-in)
# ---------------------------------------------------------------------------
#
# Each function receives a price DataFrame indexed by date with columns
# per stock (ticker) and returns a DataFrame of the same shape containing
# the factor *cross-sectional rank* (so IC can be computed directly).
# When real data is unavailable, a synthetic surrogate is generated so the
# pipeline is fully runnable end-to-end.

# ---------------------------------------------------------------------------
# Synthetic data (imported from shared package)
# ---------------------------------------------------------------------------

from claw_quant.synthetic import generate_synthetic_prices, compute_factor_values  # noqa: E402


# ---------------------------------------------------------------------------
# IC calculation
# ---------------------------------------------------------------------------

def compute_forward_returns(prices: pd.DataFrame) -> Dict[int, pd.DataFrame]:
    """Compute forward returns for each horizon in FORWARD_PERIODS.

    forward_return[t] = price[t+h] / price[t] - 1, aligned to date t.
    """
    fwd: Dict[int, pd.DataFrame] = {}
    for h in FORWARD_PERIODS:
        fwd[h] = prices.shift(-h) / prices - 1
    return fwd


def compute_ic_series(
    factor_values: pd.DataFrame,
    forward_returns: Dict[int, pd.DataFrame],
) -> pd.DataFrame:
    """Compute rolling IC (Spearman rank correlation) for each horizon.

    For each date t we cross-sectionally rank stocks by factor value and
    by forward return, then compute Spearman correlation. This produces a
    time series of IC per horizon, which feeds both the IC summary stats
    and the half-life decay curve (IC as a function of horizon).

    Financial note: Grinold's Fundamental Law says IR ≈ IC · √N · √BR.
    A factor with mean IC = 0.05 and breadth N = 200 gives IR ≈ 0.7,
    economically meaningful per ADR-001 thresholds.
    """
    dates = factor_values.index
    # Align forward return columns with factor value columns
    common_tickers = factor_values.columns
    ic_rows: Dict[int, List[float]] = {h: [] for h in FORWARD_PERIODS}

    for date in dates:
        fv = factor_values.loc[date]
        for h in FORWARD_PERIODS:
            if date not in forward_returns[h].index:
                ic_rows[h].append(np.nan)
                continue
            fr = forward_returns[h].loc[date].reindex(common_tickers)
            mask = fv.notna() & fr.notna()
            if mask.sum() < 10:  # need enough stocks for meaningful correlation
                ic_rows[h].append(np.nan)
                continue
            corr, _ = spearmanr(fv[mask], fr[mask])
            ic_rows[h].append(float(corr) if not np.isnan(corr) else np.nan)

    ic_df = pd.DataFrame(
        {f"ic_{h}": ic_rows[h] for h in FORWARD_PERIODS}, index=dates
    )
    return ic_df


def summarize_ic(ic_df: pd.DataFrame, factor: str) -> List[ICResult]:
    """Summarise rolling IC series into per-horizon statistics."""
    results: List[ICResult] = []
    for h in FORWARD_PERIODS:
        col = f"ic_{h}"
        if col not in ic_df.columns:
            continue
        series = ic_df[col].dropna()
        if len(series) < 2:
            results.append(ICResult(factor, h, 0.0, 0.0, 0.0, 0.0))
            continue
        ic_mean = float(series.mean())
        ic_std = float(series.std(ddof=1))
        ic_tstat = ic_mean / ic_std * np.sqrt(len(series)) if ic_std > 0 else 0.0
        hit_rate = float((series > 0).mean())
        results.append(ICResult(factor, h, ic_mean, ic_std, float(ic_tstat), hit_rate))
    return results


# ---------------------------------------------------------------------------
# Half-life estimation
# ---------------------------------------------------------------------------

def _exponential_decay(t: np.ndarray, ic_0: float, tau: float) -> np.ndarray:
    """Exponential decay model: IC(t) = IC_0 * exp(-t / τ)."""
    return ic_0 * np.exp(-t / tau)


def estimate_half_life(
    ic_df: pd.DataFrame,
    factor: str,
    rolling_half_lives: Optional[List[float]] = None,
) -> HalfLifeResult:
    """Fit exponential decay to the IC-vs-horizon curve.

    We treat the mean IC at each forward horizon as a point on the decay
    curve IC(t) and fit IC(t) = IC_0 · exp(-t / τ) via non-linear least
    squares (scipy.optimize.curve_fit). Half-life = τ · ln(2).

    Parameters
    ----------
    ic_df : DataFrame with columns ic_1, ic_5, ... ic_120.
    factor : factor name.
    rolling_half_lives : optional list of historical half-life estimates
        (from sub-windows) used to classify decay_status.
    """
    horizons = np.array(FORWARD_PERIODS, dtype=float)
    ic_means = np.array(
        [ic_df[f"ic_{h}"].dropna().mean() if f"ic_{h}" in ic_df.columns else 0.0
         for h in FORWARD_PERIODS]
    )

    # Guard against all-zero / all-NaN
    if np.all(np.isnan(ic_means)) or np.nanmax(np.abs(ic_means)) < 1e-8:
        return HalfLifeResult(factor, 0.0, 0.0, 0.0, 0.0, "stable")

    # Replace any NaN with 0 for the fit
    ic_means_clean = np.nan_to_num(ic_means, nan=0.0)

    # Initial guess: IC_0 = first horizon IC, τ = 30 days
    p0 = [ic_means_clean[0], 30.0]
    bounds = ([0.0, 0.1], [1.0, 10000.0])

    try:
        # We need IC to be positive for a standard decay fit; if IC is
        # negative (reversal factor like 5d_reversal), flip sign for fitting.
        sign = 1.0
        if ic_means_clean[0] < 0:
            sign = -1.0
            ic_means_fit = -ic_means_clean
        else:
            ic_means_fit = ic_means_clean.copy()

        popt, _ = curve_fit(
            _exponential_decay, horizons, ic_means_fit,
            p0=[abs(p0[0]), p0[1]], bounds=bounds, maxfev=10000,
        )
        ic_0 = sign * popt[0]
        tau = float(popt[1])
        half_life = tau * np.log(2)

        # R²
        pred = _exponential_decay(horizons, popt[0], popt[1])
        ss_res = np.sum((ic_means_fit - pred) ** 2)
        ss_tot = np.sum((ic_means_fit - ic_means_fit.mean()) ** 2)
        r_sq = 1 - ss_res / ss_tot if ss_tot > 0 else 0.0

    except (RuntimeError, ValueError):
        # Fallback: linear regression on log|IC| vs horizon
        valid = ic_means_clean != 0
        if valid.sum() >= 2:
            log_ic = np.log(np.abs(ic_means_clean[valid]))
            slope, _ = np.polyfit(horizons[valid], log_ic, 1)
            if slope < 0:
                tau = -1.0 / slope
                half_life = tau * np.log(2)
                ic_0 = ic_means_clean[0]
                r_sq = 0.0
            else:
                return HalfLifeResult(factor, float(ic_means_clean[0]), 0.0, 0.0, 0.0, "reversing")
        else:
            return HalfLifeResult(factor, 0.0, 0.0, 0.0, 0.0, "stable")

    decay_status = _classify_decay_status(ic_means_clean, rolling_half_lives)
    return HalfLifeResult(factor, float(ic_0), float(tau), float(half_life), float(max(r_sq, 0.0)), decay_status)


def _classify_decay_status(
    ic_means: np.ndarray,
    rolling_half_lives: Optional[List[float]],
) -> str:
    """Classify the temporal trajectory of a factor's signal.

    - 'reversing'    : IC sign flips across horizons (signal broken).
    - 'accelerating' : half-life decreasing over recent windows (dying faster).
    - 'stable'       : otherwise.
    """
    # Sign flip check
    signs = np.sign(ic_means[ic_means != 0])
    if len(signs) >= 2 and np.any(signs[:-1] != signs[1:]):
        return "reversing"

    if rolling_half_lives and len(rolling_half_lives) >= 2:
        recent = rolling_half_lives[-(DECAY_TREND_MONTHS // 2):]
        older = rolling_half_lives[:len(rolling_half_lives) - (DECAY_TREND_MONTHS // 2)]
        if recent and older:
            if np.mean(recent) < np.mean(older) * 0.7:
                return "accelerating"

    return "stable"


def compute_rolling_half_lives(
    factor_values: pd.DataFrame,
    forward_returns: Dict[int, pd.DataFrame],
    window: int = MONTHLY_WINDOW,
) -> List[float]:
    """Compute half-life over rolling sub-windows for decay_status trend."""
    ic_df = compute_ic_series(factor_values, forward_returns)
    half_lives: List[float] = []
    n = len(ic_df)
    step = window
    for start in range(0, n - window, step):
        sub = ic_df.iloc[start: start + window]
        if sub.dropna().empty:
            continue
        result = estimate_half_life(sub, "rolling")
        if result.half_life_days > 0:
            half_lives.append(result.half_life_days)
    return half_lives


# ---------------------------------------------------------------------------
# Signal strength classification
# ---------------------------------------------------------------------------

def classify_signal_strength(
    half_life: float,
    ic_mean: float,
    ic_std: float,
    decay_status: str,
) -> str:
    """Map IC quality + half-life + decay status into a signal-strength label.

    This mirrors the ADR-014 Module 1b 'current_signal_strength' field.
    """
    if decay_status == "reversing":
        return "broken"
    # IR proxy = |IC_mean| / IC_std (Grinold: IR ≈ IC / σ(IC))
    ir_proxy = abs(ic_mean) / ic_std if ic_std > 0 else 0.0

    if decay_status == "accelerating" and ir_proxy > 0.3:
        return "strong_but_decay_accelerating"
    if ir_proxy > 0.5:
        return "strong"
    if ir_proxy > 0.3:
        return "moderate"
    if ir_proxy > 0.15:
        return "weak"
    return "negligible"


# ---------------------------------------------------------------------------
# YAML output
# ---------------------------------------------------------------------------

def build_yaml_report(reports: List[FactorReport]) -> str:
    """Build the YAML block for sfm_state.md Module 1b."""
    spectrum: Dict[str, Dict] = {}
    for bucket in ["short_term", "medium_term", "long_term"]:
        bucket_reports = [r for r in reports if r.duration_bucket == bucket]
        if not bucket_reports:
            continue
        half_lives = [r.half_life.half_life_days for r in bucket_reports if r.half_life]
        typical_hl = float(np.median(half_lives)) if half_lives else 0.0
        ic_means = [r.current_ic_mean for r in bucket_reports]
        ic_stds = [r.current_ic_std for r in bucket_reports]

        # Determine bucket-level signal strength from the strongest factor
        strengths = []
        for r in bucket_reports:
            if r.half_life:
                strengths.append(
                    classify_signal_strength(
                        r.half_life.half_life_days,
                        r.current_ic_mean,
                        r.current_ic_std,
                        r.half_life.decay_status,
                    )
                )
        # Pick the most informative (non-negligible) strength
        priority = ["strong", "strong_but_decay_accelerating", "moderate", "weak", "broken", "negligible"]
        bucket_strength = "negligible"
        for p in priority:
            if p in strengths:
                bucket_strength = p
                break

        spectrum[bucket] = {
            "factors": [r.factor for r in bucket_reports],
            "typical_half_life_days": round(typical_hl, 1),
            "current_ic": {
                "mean": round(float(np.mean(ic_means)), 4) if ic_means else 0.0,
                "std": round(float(np.mean(ic_stds)), 4) if ic_stds else 0.0,
            },
            "current_signal_strength": bucket_strength,
        }

    output = {"factor_duration_spectrum": spectrum}

    # Also include per-factor detail
    per_factor = []
    for r in reports:
        entry: Dict = {
            "factor": r.factor,
            "duration_bucket": r.duration_bucket,
        }
        if r.half_life:
            entry["half_life_days"] = round(r.half_life.half_life_days, 1)
            entry["decay_status"] = r.half_life.decay_status
            entry["signal_strength"] = classify_signal_strength(
                r.half_life.half_life_days,
                r.current_ic_mean,
                r.current_ic_std,
                r.half_life.decay_status,
            )
        per_factor.append(entry)

    full_output = {
        "factor_duration_spectrum": spectrum,
        "per_factor_detail": per_factor,
    }
    return yaml.dump(full_output, default_flow_style=False, allow_unicode=True, sort_keys=False)


# ---------------------------------------------------------------------------
# Main engine
# ---------------------------------------------------------------------------

def run_engine(
    factors: List[str],
    period: Optional[Tuple[str, str]] = None,
    prices: Optional[pd.DataFrame] = None,
) -> List[FactorReport]:
    """Run the full IC + half-life pipeline for the requested factors.

    Parameters
    ----------
    factors : list of factor names to compute.
    period  : optional (start, end) date strings to filter.
    prices  : optional pre-loaded price DataFrame; if None, synthetic data
              is generated so the pipeline is runnable without Wind.
    """
    if prices is None:
        prices = _generate_synthetic_prices()

    if period:
        start, end = period
        prices = prices.loc[start:end]

    # Resolve aliases (e.g. "momentum" → "12m_momentum")
    factors = [resolve_factor_name(f) for f in factors]

    # Validate requested factors
    valid = set(FACTOR_TO_BUCKET.keys())
    unknown = [f for f in factors if f not in valid]
    if unknown:
        print(f"[WARN] Unknown factors ignored: {unknown}", file=sys.stderr)

    factor_values_all = compute_factor_values(prices)
    forward_returns = compute_forward_returns(prices)
    conn = init_db()

    reports: List[FactorReport] = []
    for factor in factors:
        if factor not in factor_values_all:
            continue
        fv = factor_values_all[factor]
        bucket = FACTOR_TO_BUCKET.get(factor, "medium_term")

        ic_df = compute_ic_series(fv, forward_returns)
        ic_results = summarize_ic(ic_df, factor)

        # Rolling half-lives for decay_status trend
        rolling_half_lives = compute_rolling_half_lives(fv, forward_returns)
        hl = estimate_half_life(ic_df, factor, rolling_half_lives)

        save_ic_series(conn, factor, ic_df)
        save_half_life(conn, hl)

        reports.append(FactorReport(
            factor=factor,
            duration_bucket=bucket,
            ic_results=ic_results,
            half_life=hl,
        ))

    conn.close()
    return reports


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_factor_list(raw: str) -> List[str]:
    """Parse comma-separated factor list from CLI."""
    return [f.strip() for f in raw.split(",") if f.strip()]


def parse_period(raw: str) -> Optional[Tuple[str, str]]:
    """Parse 'YYYY-MM-DD:YYYY-MM-DD' period string."""
    if not raw:
        return None
    parts = raw.split(":")
    if len(parts) != 2:
        raise ValueError(f"Invalid period '{raw}'. Expected START:END.")
    return parts[0], parts[1]


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="SFM Layer Module 1b — Factor IC & Half-Life Engine"
    )
    parser.add_argument(
        "--factor",
        type=str,
        default="12m_momentum,value,quality",
        help="Comma-separated factor names "
             "(e.g. momentum,value,quality). "
             f"Available: {', '.join(FACTOR_TO_BUCKET.keys())}",
    )
    parser.add_argument(
        "--period",
        type=str,
        default="",
        help="Date range START:END in YYYY-MM-DD format (e.g. 2024-01-01:2026-07-01)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="yaml",
        choices=["yaml", "json", "summary"],
        help="Output format (default: yaml)",
    )
    args = parser.parse_args(argv)

    factors = parse_factor_list(args.factor)
    period = parse_period(args.period)

    reports = run_engine(factors, period)

    if args.output == "yaml":
        print(build_yaml_report(reports))
    elif args.output == "json":
        import json
        data = []
        for r in reports:
            entry = {
                "factor": r.factor,
                "duration_bucket": r.duration_bucket,
                "current_ic": {"mean": r.current_ic_mean, "std": r.current_ic_std},
            }
            if r.half_life:
                entry["half_life_days"] = round(r.half_life.half_life_days, 2)
                entry["decay_status"] = r.half_life.decay_status
            data.append(entry)
        print(json.dumps(data, indent=2, ensure_ascii=False))
    else:
        # Human-readable summary
        for r in reports:
            hl = r.half_life.half_life_days if r.half_life else 0
            status = r.half_life.decay_status if r.half_life else "n/a"
            strength = classify_signal_strength(
                hl, r.current_ic_mean, r.current_ic_std, status
            ) if r.half_life else "n/a"
            print(f"{r.factor:20s} bucket={r.duration_bucket:12s} "
                  f"half_life={hl:7.1f}d  IC={r.current_ic_mean:+.4f}  "
                  f"status={status:12s} strength={strength}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
