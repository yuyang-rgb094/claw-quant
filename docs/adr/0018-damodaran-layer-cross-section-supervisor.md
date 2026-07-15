# ADR-018: Damodaran Layer — Cross-Section Supervisor

**Status:** Accepted

**Date:** 2026-07-13

## Context

The four-layer sequential architecture (Fisher → SFM → Graham → Markowitz) handles single-thesis portfolio construction and risk management. However, grilling sessions (2026-07-13) identified structural gaps when multiple theses coexist:

1. **Ticker overlap.** The same ticker appears in multiple theses (e.g., 澜起科技 in both "memory super cycle" and "AI infra chokepoint" theses). Each thesis independently assigns risk budget — additive risk would double-count exposure on the same physical position.

2. **Alpha capture conflict.** Thesis A's alpha capture ratio reaches 50% (trigger reduction), but Thesis B's is only 30% (hold). The physical position cannot be both reduced and held simultaneously.

3. **Portfolio complexity creep.** Too many active theses with too many tickers means the portfolio effectively becomes an index — no edge, no alpha, just diversification without purpose. No mechanism existed to detect or prevent this.

4. **No forward-looking aggregate view.** Each thesis tracks its own expectation_gap and alpha_captured_ratio, but no view exists of the total portfolio's forward-looking intrinsic value vs. current market value. Damodaran's "look forward" philosophy — valuing a company by what it will earn, not what it has earned — was absent from the aggregate level.

The user proposed a Damodaran layer during the grilling session, recognizing that these problems require a **cross-section** supervisor — not a fifth sequential step, but a layer that cuts across all four sequential layers simultaneously.

## Decision

### 1. Cross-Section Architecture

The Damodaran layer is NOT a sequential layer (not "Layer 5"). It is a **cross-section layer** that supervises all four sequential layers simultaneously:

```
Sequential (vertical information flow):
  Fisher → SFM → Graham → Markowitz

Cross-section (horizontal supervision):
  Damodaran ════════════════════════════════════════════
      ║          ║          ║          ║
   Fisher    SFM     Graham     Markowitz
      ║          ║          ║          ║
  Damodaran ════════════════════════════════════════════
```

Damodaran reads all layers' output but does NOT modify any layer's state. It flags violations to the relevant layer for correction. It does not make allocation decisions — the framework re-run handles capital allocation when profit is released.

### 2. Role: Adjudicator, NOT Allocator

The Damodaran layer is a **constraint enforcer and risk monitor**, not a capital allocator. This preserves the belief-action separation:

- Graham owns beliefs
- Markowitz owns portfolio construction
- Damodaran owns **aggregate constraints** — ensuring the collection of theses and holdings does not violate portfolio-level rules

When the Damodaran layer detects a violation (e.g., too many active theses, risk budget stacking on overlapping tickers), it flags the issue to the relevant layer. It does not itself reduce positions or reallocate capital.

### 3. Responsibilities

#### 3a. Belief Pool Management

Track the total population of active investment beliefs:

```yaml
# portfolio/damodaran_state.md — Belief Pool
belief_pool:
  total_active_theses: 3
  max_recommended: 5              # beyond this → "you're an index fund"
  
  theses_summary:
    - thesis: "memory_super_cycle"
      conviction: 0.72
      alpha_captured: 0.30
      belief_type: growth
      duration_bucket: long       # > 90d factor half-life
      status: active
    
    - thesis: "defensive_cash"
      conviction: 0.80
      alpha_captured: null
      belief_type: defensive
      duration_bucket: null
      status: active
    
    - thesis: "ai_infra_chokepoint"
      conviction: 0.65
      alpha_captured: 0.55
      belief_type: growth
      duration_bucket: medium     # 5-90d
      status: active
  
  # Diversification of belief sources
  belief_diversity:
    by_type: {growth: 2, defensive: 1}        # acceptable
    by_duration: {long: 1, medium: 1, null: 1} # acceptable
    by_factor_exposure:                        # derived from SFM alignment
      momentum: 0.3
      value: 0.1
      quality: 0.2
      defensive: 0.4
    # If any single factor > 0.6 → flag: over-concentrated in one factor
```

#### 3b. Holdings Pool Management

Track the total population of physical positions:

```yaml
# portfolio/damodaran_state.md — Holdings Pool
holdings_pool:
  total_unique_tickers: 7
  max_recommended: 15             # beyond this → complexity with no edge
  
  # Cross-thesis overlap detection
  ticker_overlap:
    - ticker: "688008.SH"         # 澜起科技
      theses: ["memory_super_cycle", "ai_infra_chokepoint"]
      total_weight: 0.15          # 15% of total capital across both theses
      max_single_ticker: 0.15     # at limit — flag if increasing
      risk_budget_combined: 15000 # weighted average, NOT additive
    
    - ticker: "688012.SH"         # 中微半导体
      theses: ["memory_super_cycle", "ai_infra_chokepoint"]
      total_weight: 0.08
      max_single_ticker: 0.15     # within limit
      risk_budget_combined: 6000
  
  # Aggregate exposure
  aggregate_exposure:
    total_equity: 0.60            # within Fisher 0.8 cap
    total_cash: 0.40             # includes defensive thesis
    total_by_sector:             # sector concentration check
      semiconductors: 0.35
      memory: 0.15
      cash: 0.40
      other: 0.10
    # If any sector > 0.50 → flag: sector concentration risk
```

#### 3c. Constraint Suite

```yaml
# portfolio/damodaran_state.md — Constraints
constraints:
  # Portfolio structure limits
  - name: max_active_theses
    limit: 5
    rationale: "Beyond 5 active theses, the portfolio becomes an index — no edge"
    current: 3
    status: within_limit
  
  - name: max_unique_tickers
    limit: 15
    rationale: "Too many tickers = complexity without diversification benefit"
    current: 7
    status: within_limit
  
  - name: max_single_thesis_weight
    limit: 0.40
    rationale: "No single thesis > 40% of total capital"
    current: 0.40                 # defensive_cash at exactly 40%
    status: at_limit
  
  - name: max_single_ticker_weight
    limit: 0.15
    rationale: "No single ticker > 15% of total capital (across all theses)"
    current: 0.15                 # 澜起科技 at exactly 15%
    status: at_limit
  
  - name: max_single_duration_bucket
    limit: 0.60
    rationale: "No single duration bucket > 60% of equity exposure"
    current: 0.50                 # long-duration at 50%
    status: within_limit
  
  - name: max_single_sector
    limit: 0.50
    rationale: "No single sector > 50% of total capital"
    current: 0.35                 # semiconductors at 35%
    status: within_limit
  
  - name: fisher_max_aggregate_equity
    limit: 0.80
    rationale: "Fisher layer hard constraint — macro environment ceiling"
    current: 0.60
    status: within_limit
```

When a constraint is breached, Damodaran flags to the responsible layer:
- `max_single_ticker_weight` → flag to Markowitz: "reduce ticker X or stop adding"
- `max_active_theses` → flag to Graham: "do not create new thesis until one is closed"
- `fisher_max_aggregate_equity` → flag to Markowitz: "cannot deploy more capital to equity"

#### 3d. Forward-Looking Aggregate Valuation (Damodaran's "Look Forward")

Inspired by Damodaran's philosophy: value investments by what they will earn, not what they have earned. The aggregate view sums each thesis's forward-looking intrinsic value estimate:

```yaml
# portfolio/damodaran_state.md — Forward-Looking Valuation
forward_valuation:
  # For each thesis, estimate forward intrinsic value
  # based on thesis belief × target price
  per_thesis_forward:
    - thesis: "memory_super_cycle"
      current_market_value: 700000     # sum of holdings market values
      forward_intrinsic_value: 950000   # based on thesis target prices
      forward_return: 0.357              # (950K - 700K) / 700K
      confidence_weighted_return: 0.257  # 0.357 × conviction 0.72
    
    - thesis: "defensive_cash"
      current_market_value: 2000000
      forward_intrinsic_value: 2020000   # modest real return on cash
      forward_return: 0.010
      confidence_weighted_return: 0.008  # 0.010 × 0.80
    
    - thesis: "ai_infra_chokepoint"
      current_market_value: 1300000
      forward_intrinsic_value: 1750000
      forward_return: 0.346
      confidence_weighted_return: 0.225  # 0.346 × 0.65
  
  # Aggregate forward view
  total_current_value: 4000000
  total_forward_intrinsic: 4722000
  aggregate_forward_return: 0.181         # 18.1% forward
  confidence_weighted_aggregate: 0.122   # 12.2% risk-adjusted
  
  # Assessment
  assessment: >
    "Aggregate forward return 18.1% (confidence-weighted 12.2%).
     This portfolio has meaningful edge — not an index.
     If aggregate_forward_return < 5%, flag: portfolio may be
     over-diversified or theses lack sufficient edge."
  
  # Look forward, NOT backward
  backward_pnl:
    realized: +91288
    unrealized: +55524
    note: "Reference only — backward P&L does not drive decisions.
          Forward intrinsic value drives decisions."
```

### 4. Alpha Capture Conflict Resolution

When theses sharing a ticker disagree on profit-taking action:

```yaml
# Damodaran resolves by computing merged action
alpha_capture_conflict:
  ticker: "688008.SH"
  
  thesis_A: "memory_super_cycle"
    alpha_captured_ratio: 0.55      # → should reduce 25%
    weight_in_thesis: 0.50
    thesis_allocation: 1000000
  
  thesis_B: "ai_infra_chokepoint"
    alpha_captured_ratio: 0.30      # → should hold
    weight_in_thesis: 0.30
    thesis_allocation: 2000000
  
  # Merged calculation
  # Thesis A controls: 0.50 × 1000000 = 500000 of the position
  # Thesis B controls: 0.30 × 2000000 = 600000 of the position
  # Total position value: 1100000 (weighted by thesis allocation × weight)
  # Thesis A wants to reduce its portion by 25%: 500000 × 0.25 = 125000 reduction
  # Thesis B wants to hold: no reduction
  # Merged action: reduce 125000 / 1100000 = 11.4% of total position
  
  merged_action:
    reduction_ratio: 0.114          # reduce total position by 11.4%
    rationale: >
      "Thesis A's alpha capture milestone triggers reduction on its
       proportion of the position. Thesis B's alpha is still emerging,
       so its proportion is held. Physical execution is one trade."
    flag_to: "Markowitz layer"
    status: "flagged for execution"
```

### 5. Trigger Mechanism (Mode C: Event-Driven + Periodic)

```yaml
# Damodaran Layer Trigger Protocol
trigger_protocol:
  
  # Event-driven (immediate)
  event_driven:
    - trigger: "alpha_capture_profit_taking"
      action: "update holdings_pool, check constraints, resolve conflicts"
      target: "affected thesis + overlapping tickers"
    
    - trigger: "thesis_creation"
      action: "check max_active_theses, scan ticker overlap, update belief_pool"
      target: "new thesis + all existing theses"
    
    - trigger: "thesis_invalidation"
      action: "update belief_pool, reallocate available_capital tracking"
      target: "invalidated thesis + capital registry"
    
    - trigger: "fisher_regime_change"
      action: "re-check fisher_max_aggregate_equity, flag if exposure exceeds new cap"
      target: "all active theses"
    
    - trigger: "new_holding_entry"
      action: "check max_single_ticker_weight, max_unique_tickers, update holdings_pool"
      target: "new holding + overlapping theses"
  
  # Periodic
  periodic:
    weekly:
      - "ticker overlap scan — detect new overlaps since last scan"
      - "risk budget stacking check — verify weighted average is correct"
      - "constraint suite evaluation — all constraints checked"
      - "available_capital reconciliation — verify registry matches actual"
    
    monthly:
      - "forward-looking aggregate intrinsic value assessment"
      - "portfolio complexity score — is the portfolio becoming an index?"
      - "belief diversity audit — factor exposure distribution"
      - "backward P&L reference update (reference only, not decision input)"
```

### 6. Relationship to Sequential Layers

```
Damodaran reads:
  - fisher_state.md (Fisher output: stock_vs_cash, max_aggregate_equity)
  - sfm_state.md (SFM output: factor preferences, crowding)
  - all thesis files (Graham Region: conviction, beliefs; Markowitz Region: portfolio)
  - all holdings files (execution state, risk budget consumption)
  - capital_allocation_registry.md (aggregate capital state)

Damodaran writes:
  - damodaran_state.md (its own state file)
  - Flags to specific layers (does NOT modify their files)

Damodaran does NOT:
  - Modify any thesis file
  - Modify any holdings file
  - Make capital allocation decisions
  - Override any layer's output
  - Execute trades
```

### 7. Damodaran's "Look Forward" Philosophy

Aswath Damodaran's valuation philosophy emphasizes that intrinsic value is forward-looking — based on what a company will earn, not what it has earned. The Damodaran layer applies this at the portfolio level:

- **Backward P&L** (realized + unrealized) is reference only — it does not drive decisions
- **Forward intrinsic value** (thesis belief × target price, confidence-weighted) drives the aggregate assessment
- If aggregate forward return falls below a threshold, the portfolio is flagged as "index-like" — too diversified to have edge
- This connects to the user's principle: "太杂的投资组合跟买指数没区别"

## What This Does NOT Do

- Does NOT make capital allocation decisions — the framework re-run handles allocation when capital is released
- Does NOT modify any sequential layer's state — it reads and flags, never writes to other layers
- Does NOT use backward P&L as a decision input — forward intrinsic value only
- Does NOT replace Markowitz's portfolio construction — it supervises the aggregate, not individual theses
- Does NOT eliminate cross-thesis ticker overlap — it detects, manages, and constrains it

## Rationale

The Damodaran layer design rests on four insights:

1. **Cross-section supervision is structurally different from sequential processing.** The four sequential layers process information top-down (Fisher → SFM → Graham → Markowitz). Cross-thesis problems — overlap, stacking, complexity — require simultaneous visibility across all theses, which no sequential layer has. A cross-section layer is the structural answer.

2. **Adjudicator role preserves belief-action separation.** If Damodaran made allocation decisions, it would violate the principle that Graham owns beliefs and Markowitz owns portfolios. By limiting Damodaran to constraint enforcement and flagging, the ownership boundaries remain clean.

3. **Capital is fungible — no special reallocation path.** The user's insight that "released profit = new money" eliminates the need for a complex reallocation decision tree. Damodaran tracks state; the framework re-runs normally.

4. **Forward-looking valuation prevents index-ification.** Without an aggregate forward view, the portfolio can accumulate theses and tickers until it becomes an index — diversified but edgeless. Damodaran's "look forward" assessment provides the early warning system.

## References

- ADR-009: Holding File Six Principles (belief-action separation foundation)
- ADR-010: Belief-Anchored Risk System (risk budget per-position allocation source)
- ADR-016: Graham Layer Thesis Architecture (thesis file structure, Markowitz Region origin)
- ADR-017: Markowitz Layer (holdings file schema, capital allocation registry, alpha capture schedule)
- Damodaran, A. (2012). Investment Valuation: Tools and Techniques for Determining the Value of Any Asset. 3rd Edition. Wiley.
- Grilling session (2026-07-13): Cross-section layer proposal, "look forward" philosophy, capital fungibility, portfolio complexity concern
