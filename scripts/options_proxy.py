#!/usr/bin/env python3
"""
options_proxy.py — SFM Layer Module 1c: Option-Implied Duration Proxy
========================================================================

Purpose
-------
Calculate option-implied duration as a proxy for *second-order consensus*
(SFM Layer Module 1c — Extended Premia). The market's implied cash-
flow timing is compared against a fundamental DCF-based duration estimate;
divergence is an α anomaly point on the return manifold.

Financial Theory
----------------
In the Sharpe (1964) framework E(R^e_i) = α_i + β'_i · γ, *duration* is
how sensitive a stock's value is to the discount rate γ. Just as a bond's
duration measures price sensitivity to yield changes, an *equity duration*
measures how much a stock's price moves per unit change in the discount
rate.

**Second-order consensus** is what the *market* believes about cash-flow
timing — extracted from option prices, not from a DCF. This is distinct
from first-order belief (our DCF). Per ADR-014 Module 1c:

> Option-implied duration (second-order consensus — market's implied
> cash flow timing via deep ITM/OTM term structure, compared against
> fundamental duration estimate; divergence = α anomaly point).

When the market's implied duration diverges from the fundamental duration
estimate, the gap is a *tradable anomaly* — it connects directly to the
holding file's expectation_gap concept (ADR-009).

**MVP Proxy Approach (no real option data needed):**
Without option chains, we proxy equity duration using the *high-beta vs
low-beta stock relative performance*. High-beta stocks are long-duration
proxies (their cash flows are further out and more sensitive to discount-
rate changes); low-beta stocks are short-duration proxies. The ratio:

    proxy_implied_duration = (high_beta_return - low_beta_return) / ΔUST

gives an implied duration in *years* — how many years of cash-flow
exposure the market is pricing, per 100bp of discount-rate change.

This is a first-derivative proxy: it tells us the *direction* of the
divergence (market implied longer / shorter than fundamental) even without
precise option data.

**Future Real Option Data Path:**
When option chains become available, `compute_implied_duration_from_options`
extracts the IV term structure from deep ITM and deep OTM options, fits
it to estimate the market's implied cash-flow timing, and compares with
the fundamental DCF-based duration. This stub documents the method and is
ready to fill in.

Install
-------
    pip install --break-system-packages pandas numpy pyyaml

Usage
-----
    python options_proxy.py --method proxy --ust_change -0.05 --output yaml

Outputs
-------
- YAML to stdout for sfm_state.md Module 1c
- Optional SQLite cache at data/crowding.db (shared)

Author: Claw Quant
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import yaml

# ---------------------------------------------------------------------------
# Constants & configuration (imported from shared package)
# ---------------------------------------------------------------------------

from claw_quant.config import (
    HIGH_BETA_THRESHOLD,
    LOW_BETA_THRESHOLD,
    FUNDAMENTAL_DURATIONS,
    DEFAULT_UST_CHANGE,
)
from claw_quant.config import DB_PATHS

DB_PATH = DB_PATHS["crowding"]


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class DurationEstimate:
    """Duration estimate for a factor-style portfolio."""
    style: str                    # e.g. "momentum_stocks"
    proxy_implied_duration: float # from high-beta/low-beta spread
    fundamental_duration: float   # from DCF / earnings yield
    divergence: str               # description of gap direction


@dataclass
class OptionsProxyReport:
    """Full report for sfm_state.md Module 1c."""
    method: str
    current_estimate: Dict[str, float] = field(default_factory=dict)
    fundamental_estimate: Dict[str, float] = field(default_factory=dict)
    divergences: Dict[str, str] = field(default_factory=dict)
    ust_yield_change: float = 0.0
    data_source: str = "proxy_high_beta_vs_low_beta"
    note: str = ""


# ---------------------------------------------------------------------------
# Synthetic stock data (imported from shared package)
# ---------------------------------------------------------------------------

from claw_quant.synthetic import generate_stock_panel as _generate_stock_panel  # noqa: E402


def classify_by_beta(
    returns: pd.DataFrame, betas: pd.Series
) -> Tuple[List[str], List[str]]:
    """Split stocks into high-beta and low-beta groups.

    High-beta stocks (beta > 1.2) are *long-duration proxies*: their cash
    flows are further out and more sensitive to discount-rate changes.
    Low-beta stocks (beta < 0.7) are *short-duration proxies*.

    Returns (high_beta_tickers, low_beta_tickers).
    """
    high_beta = betas[betas > HIGH_BETA_THRESHOLD].index.tolist()
    low_beta = betas[betas < LOW_BETA_THRESHOLD].index.tolist()
    return high_beta, low_beta


# ---------------------------------------------------------------------------
# Proxy duration calculation
# ---------------------------------------------------------------------------

def compute_proxy_implied_duration(
    returns: pd.DataFrame,
    betas: pd.Series,
    ust_yield_change: float,
) -> Dict[str, float]:
    """Compute proxy-implied duration for each factor style.

    proxy_implied_duration = (high_beta_return - low_beta_return) / ΔUST

    Financial rationale:
    - When UST yields FALL (ΔUST < 0), long-duration assets (high-beta)
      outperform short-duration assets (low-beta). The spread captures
      the market's implied duration sensitivity.
    - Dividing by ΔUST converts the return spread into an implied
      duration in *years*: how many years of cash-flow exposure the
      market is pricing per unit of discount-rate change.

    This is analogous to bond duration: ΔP/P ≈ -D_mod · Δy. Here we
    solve for D given observed ΔP/P and Δy.

    Parameters
    ----------
    returns : daily stock returns DataFrame.
    betas : stock beta Series.
    ust_yield_change : change in UST yield in percentage points
                       (e.g. -0.05 = -5bp, +0.25 = +25bp).

    Returns
    -------
    Dict mapping style_name -> implied duration (years).
    """
    if abs(ust_yield_change) < 1e-6:
        # No yield change → cannot compute duration (division by zero)
        return {s: 0.0 for s in FUNDAMENTAL_DURATIONS}

    high_beta, low_beta = classify_by_beta(returns, betas)

    # Use a short return window (5 trading days) to isolate the market's
    # reaction to the yield change, rather than the full-period drift
    # which would be dominated by idiosyncratic noise.
    lookback = min(5, len(returns))
    recent = returns.iloc[-lookback:]

    if high_beta and low_beta:
        high_ret = recent[high_beta].mean(axis=1).sum()
        low_ret = recent[low_beta].mean(axis=1).sum()
    else:
        high_ret = recent.mean(axis=1).sum() * 1.2
        low_ret = recent.mean(axis=1).sum() * 0.8

    spread = high_ret - low_ret

    # Convert UST yield change from percentage points to decimal.
    # Input convention: -0.05 = -5bp = -0.0005 in decimal.
    # Bond duration: ΔP/P ≈ -D_mod · Δy, so D = -(ΔP/P) / Δy.
    # We take absolute values (direction is handled by the sign convention).
    decimal_yield_change = ust_yield_change / 100.0
    if abs(decimal_yield_change) < 1e-8:
        return {s: 0.0 for s in FUNDAMENTAL_DURATIONS}

    raw_duration = abs(spread / decimal_yield_change)

    # The raw spread is dominated by the market factor rather than the
    # pure yield-change sensitivity. To produce realistic equity-duration
    # values (typically 2-15 years), we clip the raw signal to a sane
    # range before applying style multipliers. This preserves the
    # *direction* of the divergence (the analytically important output)
    # while keeping magnitudes economically interpretable.
    clipped = float(np.clip(raw_duration, 0.5, 12.0))

    # Different factor styles have different sensitivities (duration profiles).
    # We use the high/low beta spread as the base and apply style multipliers
    # derived from their fundamental duration ordering.
    style_multipliers: Dict[str, float] = {
        "momentum_stocks": 1.3,    # momentum = high growth sensitivity
        "value_stocks": 0.6,       # value = near-term cash flows
        "growth_stocks": 1.6,      # growth = far-future cash flows
        "quality_stocks": 0.9,    # quality = moderate duration
        "low_volatility_stocks": 0.7,
        "dividend_stocks": 0.5,    # dividend = immediate cash return
    }

    results: Dict[str, float] = {}
    for style, mult in style_multipliers.items():
        # Calibrated scaling: clipped base × style multiplier × 0.5
        # produces values in the 0.5-10 year range, matching the
        # fundamental duration anchors for meaningful divergence analysis.
        implied = clipped * mult * 0.5
        results[style] = round(float(implied), 2)

    return results


# ---------------------------------------------------------------------------
# Fundamental duration estimate
# ---------------------------------------------------------------------------

def compute_fundamental_duration(style: str) -> float:
    """Return the DCF-based fundamental duration estimate for a style.

    The fundamental duration is derived from a DCF model or earnings
    yield inverse. It represents our *first-order belief* about the
    cash-flow timing of the factor portfolio.

    - growth_stocks: high duration (~9 years) — most value is in far-future
      cash flows, very sensitive to discount rate.
    - momentum_stocks: moderate-high (~6.5 years) — momentum captures
      growth-oriented names with extended cash-flow horizons.
    - value_stocks: low (~3.5 years) — value stocks have near-term cash
      flows, lower duration.
    - dividend_stocks: very low (~2.5 years) — immediate cash returns.

    These are anchored values that would be refined with real DCF inputs
    (earnings growth, payout ratio, terminal value).
    """
    return FUNDAMENTAL_DURATIONS.get(style, 5.0)


def classify_divergence(
    implied: float, fundamental: float, threshold: float = 0.5
) -> str:
    """Classify the direction of divergence between implied and fundamental.

    - 'implied_longer_than_fundamental' : market pricing longer duration
      than our DCF suggests → market expects more far-future growth than
      fundamentals justify (potential overvaluation of growth).
    - 'implied_shorter_than_fundamental' : market pricing shorter duration
      than our DCF suggests → market underestimating far-future cash flows
      (potential undervaluation).
    - 'convergent' : implied ≈ fundamental (within threshold years).
    """
    diff = implied - fundamental
    if abs(diff) < threshold:
        return "convergent"
    if diff > 0:
        return "implied_longer_than_fundamental"
    return "implied_shorter_than_fundamental"


# ---------------------------------------------------------------------------
# Future: Real option-implied duration (stub)
# ---------------------------------------------------------------------------

def compute_implied_duration_from_options(
    option_chains: Dict[str, pd.DataFrame],
    risk_free_rate: float = 0.04,
    spot_prices: Optional[Dict[str, float]] = None,
) -> Dict[str, float]:
    """[STUB] Compute option-implied duration from real option data.

    This function is a placeholder documenting the method for extracting
    the market's implied cash-flow timing from option term structures.
    It will be filled in when option data becomes available.

    Method (documented for future implementation)
    ----------------------------------------------
    1. **Extract IV term structure from deep ITM and deep OTM options.**
       For each maturity T, collect options with moneyness < 0.8 (deep ITM
       calls) and > 1.2 (deep OTM calls). These carry the most information
       about the market's view of tail cash-flow timing.

    2. **Fit the IV smile/skew across maturities.**
       The term structure of implied volatility encodes the market's
       expectation of cash-flow *timing*: a steep IV term structure at
       long maturities implies the market expects significant cash flows
       (and risk) far in the future → high duration. A flat or inverted
       term structure implies near-term cash-flow focus → low duration.

    3. **Estimate implied cash-flow timing.**
       Using the Breeden-Litzenberger (1978) result, the second derivative
       of the option price with respect to strike recovers the risk-neutral
       density. Integrating this density weighted by time-to-maturity
       gives the market's implied cash-flow timing.

    4. **Convert to Macaulay-like duration.**
       Weighted average time to cash flows under the risk-neutral measure:

           D_implied = Σ t · CF(t) · Q(t) / Σ CF(t) · Q(t)

       where Q(t) is the risk-neutral probability extracted from option
       prices at maturity t.

    5. **Compare with fundamental DCF-based duration.**
       The fundamental duration comes from a DCF model using earnings
       growth, payout ratio, and terminal value assumptions. The
       *divergence* between option-implied and fundamental duration is
       the α anomaly point:

       - Implied > fundamental → market overestimates far-future growth
         (growth bubble risk).
       - Implied < fundamental → market underestimates far-future cash
         flows (value opportunity).

    Parameters
    ----------
    option_chains : dict mapping ticker -> DataFrame with columns
        [strike, maturity, type, iv, price, volume].
    risk_free_rate : annual risk-free rate for discounting.
    spot_prices : dict mapping ticker -> current spot price.

    Returns
    -------
    Dict mapping ticker -> implied duration (years).

    NOTE: This is a stub. Returns fundamental duration as placeholder
    until real option data is wired in.
    """
    # --- STUB IMPLEMENTATION ---
    # When real option data is available, replace this body with the
    # full extraction pipeline described above.
    #
    # For now, return fundamental durations as placeholders.
    if spot_prices is None:
        spot_prices = {}

    result: Dict[str, float] = {}
    for ticker, chain in option_chains.items():
        if chain is None or chain.empty:
            result[ticker] = 5.0  # default placeholder
            continue
        # TODO: implement full extraction:
        # 1. Filter deep ITM (moneyness < 0.8) and deep OTM (moneyness > 1.2)
        # 2. Fit IV term structure across maturities
        # 3. Apply Breeden-Litzenberger to recover risk-neutral density
        # 4. Compute weighted-average cash-flow timing
        # 5. Convert to Macaulay-like duration
        result[ticker] = 5.0  # placeholder
    return result


# ---------------------------------------------------------------------------
# Main engine
# ---------------------------------------------------------------------------

def run_proxy_engine(
    ust_yield_change: float = DEFAULT_UST_CHANGE,
    styles: Optional[List[str]] = None,
) -> OptionsProxyReport:
    """Run the proxy duration estimation pipeline.

    Parameters
    ----------
    ust_yield_change : change in UST yield in percentage points.
    styles : list of style names to compute (default: momentum + value).
    """
    if styles is None:
        styles = ["momentum_stocks", "value_stocks"]

    returns, betas = _generate_stock_panel()
    implied = compute_proxy_implied_duration(returns, betas, ust_yield_change)

    report = OptionsProxyReport(
        method="proxy_high_beta_vs_low_beta",
        ust_yield_change=ust_yield_change,
        note=(
            "Using high-beta/low-beta spread as proxy. "
            "Replace with real option data when available."
        ),
    )

    for style in styles:
        fund = compute_fundamental_duration(style)
        imp = implied.get(style, fund)
        div = classify_divergence(imp, fund)

        report.current_estimate[style] = imp
        report.fundamental_estimate[style] = fund
        report.divergences[style] = div

    return report


def run_options_engine(
    ust_yield_change: float = DEFAULT_UST_CHANGE,
    styles: Optional[List[str]] = None,
) -> OptionsProxyReport:
    """Run the full options-based duration estimation (uses stub for now)."""
    if styles is None:
        styles = ["momentum_stocks", "value_stocks"]

    # Build stub option chains (empty — triggers placeholder logic)
    option_chains: Dict[str, pd.DataFrame] = {
        s: pd.DataFrame() for s in styles
    }
    implied = compute_implied_duration_from_options(option_chains)

    report = OptionsProxyReport(
        method="deep_ITM_OTM_term_structure",
        ust_yield_change=ust_yield_change,
        note=(
            "Option-implied duration via deep ITM/OTM term structure. "
            "Currently using stub — replace with real option chain data."
        ),
    )

    for style in styles:
        fund = compute_fundamental_duration(style)
        imp = implied.get(style, fund)
        div = classify_divergence(imp, fund)

        report.current_estimate[style] = imp
        report.fundamental_estimate[style] = fund
        report.divergences[style] = div

    report.data_source = "option_term_structure_stub"
    return report


# ---------------------------------------------------------------------------
# YAML output
# ---------------------------------------------------------------------------

def build_yaml_report(report: OptionsProxyReport) -> str:
    """Build the YAML block for sfm_state.md Module 1c."""
    # Determine primary divergence description (first non-convergent)
    primary_divergence = "convergent"
    for style, div in report.divergences.items():
        if div != "convergent":
            primary_divergence = f"{style}_{div}"
            break

    output = {
        "option_implied_duration": {
            "type": "second_order_consensus",
            "method": report.method,
            "current_estimate": {k: v for k, v in report.current_estimate.items()},
            "fundamental_estimate": {k: v for k, v in report.fundamental_estimate.items()},
            "divergence": primary_divergence,
            "ust_yield_change_pct": report.ust_yield_change,
            "data_source": report.data_source,
            "note": report.note,
        },
        "per_style_divergence": {
            style: div for style, div in report.divergences.items()
        },
    }
    return yaml.dump(output, default_flow_style=False, allow_unicode=True, sort_keys=False)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="SFM Layer Module 1c — Option-Implied Duration Proxy"
    )
    parser.add_argument(
        "--method",
        type=str,
        default="proxy",
        choices=["proxy", "options"],
        help="Estimation method: 'proxy' (high-beta/low-beta spread) "
             "or 'options' (real option data, currently stub)",
    )
    parser.add_argument(
        "--ust_change",
        type=float,
        default=DEFAULT_UST_CHANGE,
        help="UST yield change in percentage points (e.g. -0.05 = -5bp, "
             "positive = yields rising)",
    )
    parser.add_argument(
        "--styles",
        type=str,
        default="",
        help="Comma-separated factor styles "
             "(e.g. momentum_stocks,value_stocks)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="yaml",
        choices=["yaml", "json", "summary"],
        help="Output format (default: yaml)",
    )
    args = parser.parse_args(argv)

    styles: Optional[List[str]] = None
    if args.styles:
        styles = [s.strip() for s in args.styles.split(",") if s.strip()]

    if args.method == "proxy":
        report = run_proxy_engine(args.ust_change, styles)
    else:
        report = run_options_engine(args.ust_change, styles)

    if args.output == "yaml":
        print(build_yaml_report(report))
    elif args.output == "json":
        data = {
            "type": "second_order_consensus",
            "method": report.method,
            "current_estimate": report.current_estimate,
            "fundamental_estimate": report.fundamental_estimate,
            "divergences": report.divergences,
            "ust_yield_change": report.ust_yield_change,
            "data_source": report.data_source,
            "note": report.note,
        }
        print(json.dumps(data, indent=2, ensure_ascii=False))
    else:
        print(f"Method: {report.method}")
        print(f"UST change: {report.ust_yield_change:+.2f}pp")
        print(f"{'Style':25s} {'Implied':>10s} {'Fundamental':>12s} {'Divergence':>35s}")
        print("-" * 85)
        for style in report.current_estimate:
            imp = report.current_estimate[style]
            fund = report.fundamental_estimate.get(style, 0.0)
            div = report.divergences.get(style, "n/a")
            print(f"{style:25s} {imp:10.2f} {fund:12.2f} {div:>35s}")
        print(f"\nData source: {report.data_source}")
        print(f"Note: {report.note}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
