# ADR-011: Fisher Layer — Mundell-Fleming / Rey Framework

**Status:** Accepted

**Date:** 2026-07-07

## Context

ADR-008 introduced the CBC Simulator with a focus on FOMC interest rate decisions. The Fisher Layer was initially designed (in grilling session) as a dual-section file: US Fisher + China Fisher + transmission link.

This design was fundamentally challenged and rewritten based on the Mundell-Fleming model and Rey's (2013) "Dilemma not Trilemma" framework. The key insight: under partially open capital accounts, there are NOT two independent monetary cycles. There is ONE global financial cycle, driven by the Federal Reserve. China's managed float + partial capital account openness + macroprudential controls reduce short-term volatility of spillovers but do NOT eliminate directional transmission.

Three additional clarifications from domain expertise (financial practitioner, graduate-level instructor):

1. **Three liquidity layers** must be distinguished: (1) base money (central bank balance sheet), (2) broad liquidity (M2, social financing), (3) stock market marginal liquidity (incremental trading funds). Conflating these leads to errors — PBoC expanding M2 does NOT mean stock market liquidity is increasing (70% goes to bonds/credit, <10% reaches equities).

2. **Three transmission channels** with quantified contributions: cross-border portfolio investment (35-40% of marginal volatility), FX reserves (8-10% spillover to equities), risk discounting (12-15% valuation impact on growth stocks per 100bp UST move). Total Fed-driven: 40-50% of A-share marginal liquidity volatility.

3. **PBoC is auxiliary modifier, not independent driver**: contributes 20-25% of marginal volatility. Bull market requires Fed easing + domestic coordination; domestic easing alone during Fed tightening produces only bounces, not trends.

## Decision

Replace the dual-section Fisher design with a **single-system, four-layer framework** based on Mundell-Fleming / Rey.

### Structure

```
fisher_state.md
├── Layer 1: Global Financial Cycle (Fed-driven)
│   ├── Fed balance sheet (M trend — Fisher equation core)
│   ├── Fed rate decision (V influence — secondary)
│   └── USD purchasing power trend (Fisher equation output)
├── Layer 2: Three Transmission Channels (independent)
│   ├── Cross-border portfolio (northbound flows — largest marginal contributor)
│   ├── FX reserves (passive base money — slow, indirect)
│   └── Risk discount (UST yield + VIX → A-share discount rate — no capital flow)
├── Layer 3: A-share Marginal Liquidity (direct price determinant)
│   ├── Composite signal (three channels combined)
│   ├── PBoC modifier (auxiliary, with equity_transmission_efficiency)
│   └── Endogenous factors (retail, margin, IPO drainage)
└── Layer 4: Composite Assessment (final output)
    ├── Fed cycle phase
    ├── Bull market conditions met (requires Fed easing)
    ├── Stock-vs-cash baseline
    └── Position constraint (max aggregate equity)
```

### Key Design Decisions

#### 1. Single System, Not Dual Sections
Fed is the gravitational center, not an "external input" to a separate China Fisher. PBoC is an auxiliary modifier within the same system, not a parallel monetary cycle. The `transmission` is not a bridge between two systems — it IS the system structure.

#### 2. Three Liquidity Layers
All analysis strictly distinguishes:
- **Base money**: Central bank balance sheet (Fed H.4.1, PBoC balance sheet). The liquidity source.
- **Broad liquidity**: M2, social financing. Interbank + credit markets.
- **Stock marginal liquidity**: Incremental trading funds. Directly determines stock prices.

Critical: PBoC expanding M2 does NOT directly increase stock liquidity. Empirically, <10% of PBoC liquidity reaches equities. The `equity_transmission_efficiency` field tracks this.

#### 3. Three Transmission Channels (Independent Tracking)
Each channel has its own signal_strength and is tracked separately:

| Channel | Mechanism | Marginal Contribution | Timescale |
|---------|-----------|----------------------|-----------|
| Cross-border portfolio | Fed easing → northbound flows → A-share marginal liquidity | 35-40% of marginal volatility | Direct, fast (daily/weekly) |
| FX reserves | Fed easing → trade surplus → passive M creation | 8-10% spillover to equities | Indirect, slow (monthly/quarterly) |
| Risk discounting | UST yield + VIX → A-share discount rate | -12% growth stocks per 100bp UST rise | No capital flow, pure pricing |

#### 4. PBoC as Auxiliary Modifier
- Contribution: 20-25% of marginal volatility
- Equity transmission efficiency: low (<10% of liquidity reaches stocks)
- Cannot independently drive bull market during Fed tightening
- `coordination_with_fed`: coordinating / diverging / neutral

#### 5. Bull Market Conditions
Per the framework: bull market requires Fed easing cycle + domestic policy coordination. Both conditions must be met. The `bull_market_conditions_met` boolean is the gating check for aggressive equity exposure.

#### 6. SFISF as Tail-Risk Tool (Not Trend Driver)
Tracked separately in `tail_risk_tools`:
- Market impact: liquidity_backstop (not trend_driver)
- Effect on tail risk: reduces extreme decline probability (~60% reduction in >3% drop days)
- Effect on trend: none (does not change medium-term direction)
- Trading implication: deploy only during liquidity panic for bounce; do not hold as trend position

### Composite Assessment Output

The Fisher Layer's final output (`composite_assessment`) provides:

1. **`fed_cycle_phase`**: easing / tightening / peak / trough — the primary anchor for large position decisions
2. **`bull_market_conditions_met`**: boolean — requires Fed easing + domestic coordination
3. **`stock_vs_cash_baseline`**: stocks_favored / cash_favored / neutral — environment-level stance
4. **`position_constraint.max_aggregate_equity`**: hard cap on total equity exposure based on monetary environment
5. **`confidence`**: 0-1 score reflecting signal consistency and data quality

### Downstream Constraints

- All thesis files must reference `fisher_state.md` composite assessment
- If `stock_vs_cash_baseline: cash_favored`, new offensive theses require stronger conviction (conviction_level > 0.7 minimum)
- If `bull_market_conditions_met: false`, no new offensive theses — only defensive thesis or existing position management
- `position_constraint.max_aggregate_equity` constrains total portfolio exposure

## Theoretical Foundation

- **Fisher (1920)**: M·V = P·Y — purchasing power of money is uncertain, determines stock vs cash baseline
- **Mundell-Fleming (1960s)**: Open-economy macro model, capital mobility + monetary policy independence tradeoff
- **Rey (2013)**: "Dilemma not Trilemma" — under partially open capital accounts, Fed policy drives global financial cycle regardless of exchange rate regime. NBER/Jackson Hole.
- **Grossman-Stiglitz (1980)**: Information paradox — referenced in Rey's framework for why markets can't be fully efficient

## References

- Rey, H. (2013). Dilemma not Trilemma: The Global Financial Cycle and Monetary Policy Independence. Jackson Hole Symposium.
- BIS (2024). Cross-border Spillovers of US Monetary Policy on Emerging Market Equities.
- IMF (2023). Monetary Policy Transmission in Emerging Markets. WP/23/198.
- IMF (2024). Monetary Policy Transmission in China. WP/24/126.
- Zhang, Y. & Li, W. (2024). US Monetary Policy Spillovers to China's Stock Market. JIMF, Vol. 148.
- Fisher, I. (1920). Stabilizing the Dollar.
- Grilling session (2026-07-07): Complete framework provided by domain expert with 8 English-language authoritative references

## What This Replaces

- The dual-section Fisher design (US + China + transmission) proposed in the previous grilling session is superseded
- ADR-008's CBC Simulator scope is expanded: it must simulate BOTH interest rate decisions (affecting V) AND balance sheet decisions (affecting M) — the latter is Fisher's primary variable
