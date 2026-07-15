# ADR-017: Markowitz Layer — Portfolio Construction & Holdings Schema

**Status:** Accepted

**Date:** 2026-07-13

## Context

ADR-016 defined the thesis file with two coexisting regions: Graham Region (belief) and Markowitz Region (portfolio). The Markowitz Region was partially specified with `portfolio_composition`, `risk_budget`, and `precommitment_rules`. However, three critical gaps remained:

1. **No normal profit-taking path.** The architecture had complete mechanisms for loss scenarios (risk budget breach → re-verification, tail breaker → hard reduction, conviction collapse → thesis invalidation) but no mechanism for the success scenario — when the thesis is correct and alpha is being captured, how and when should positions be reduced?

2. **No cross-thesis capital coordination.** Each thesis independently manages its own `total_allocation`, but when profit-taking releases capital, there is no mechanism to track aggregate exposure across all active theses or enforce Fisher's `max_aggregate_equity` constraint at the portfolio level.

3. **Holdings file schema pre-dates the four-layer architecture.** ADR-009 defined holding files with belief fields (`conviction_level`, `key_assumptions`, `disconfirmation_signals`) because at that time, thesis and holding were separate concepts. Now that thesis files contain the Graham Region (belief), these fields are redundant and create synchronization risk.

Additionally, grilling sessions (2026-07-12, 2026-07-13) revealed a key insight: **portfolio construction is trade meta-plan generation.** When Markowitz says "澜起科技 50%", it simultaneously defines the entry plan, rebalancing plan, profit-taking plan, and exit plan. The trade meta-plan is not a separate function — it is the portfolio construction process viewed across time dimensions.

A second insight: **capital is fungible.** Realized profit is indistinguishable from new deposits. There is no "special path" for profit-taking capital — it re-enters the framework as available capital and is allocated wherever the current opportunity landscape dictates. This eliminates the need for a complex reallocation decision tree.

## Decision

### 1. Markowitz Region — Complete Schema

The Markowitz Region in the thesis file is expanded to four components:

```yaml
# ─── Markowitz Region (Portfolio Construction) ──────────────
markowitz_region:
  
  # Component 1: Portfolio Composition (ADR-016, unchanged)
  total_allocation: 1000000
  portfolio_composition:
    - ticker: "688008.SH"       # 澜起科技
      name: "Montage Technology"
      target_weight: 0.50
      role: core                # core / satellite / hedge
    - ticker: "301308.SZ"       # 江波龙
      name: "Longsys Electronics"
      target_weight: 0.30
      role: satellite
    - ticker: "688012.SH"       # 中微半导体
      name: "AMEC"
      target_weight: 0.20
      role: satellite
  
  # Component 2: Risk Budget (ADR-010, unchanged)
  risk_budget:
    conviction_tier: high       # derived from Graham Region conviction_level
    base_risk_budget: 0.02      # 2% of NAV for high conviction
    market_momentum_multiplier: 1.5  # bull state
    effective_risk_budget: 0.03 # 3% of NAV
    per_position_allocation:    # split across portfolio
      "688008.SH": 0.015
      "301308.SZ": 0.009
      "688012.SH": 0.006
  
  # Component 3: Precommitment Rules (ADR-016, updated)
  # Covers ABNORMAL paths — what happens when thesis deviates
  # See ADR-016 for full schema (conviction change, alignment shift, 
  # disconfirmation, risk budget breach, tail circuit breaker)
  precommitment_rules: [...]
  
  # Component 4: Alpha Capture Schedule (NEW — normal profit-taking path)
  # Covers NORMAL path — what happens when thesis SUCCEEDS
  alpha_capture_schedule: [...]
```

### 2. Alpha Capture Schedule

The Alpha Capture Schedule defines the normal profit-taking path — what happens when the thesis is correct and alpha is being captured. It is generated at thesis creation time as part of portfolio construction.

**Core principle (Kelly Dynamic):** As alpha is captured, the remaining edge shrinks. The optimal position size shrinks proportionally, even when conviction_level is unchanged. This is orthogonal to conviction — the thesis can be 100% correct while the position should still shrink because the remaining alpha no longer justifies the current exposure.

```yaml
alpha_capture_schedule:
  # Anchor: expectation_gap at thesis creation time
  initial_gap_magnitude: 0.15    # snapshot, not dynamic
  
  # Graham Region updates gap_magnitude over time.
  # alpha_captured_ratio = (initial_gap - current_gap) / initial_gap
  # Markowitz reads this value and executes weight adjustments.
  
  milestones:
    - stage: "alpha_emerging"
      trigger: "alpha_captured_ratio >= 0.30"
      action: "review_position_sizing"
      weight_adjustment: 0.0      # no reduction yet
      rationale: "early confirmation, let it run"
      signal_required:
        gap_type: "catalyst_active"
        consensus_catalyst_triggered: true
    
    - stage: "alpha_accelerating"
      trigger: "alpha_captured_ratio >= 0.50"
      action: "first_profit_taking"
      weight_adjustment: -0.25    # reduce position by 25% of current weight
      rationale: "de-risk — recover initial cost basis on the reduced portion"
      signal_required:
        gap_magnitude_decline: ">50% from initial"
        sfm_crowding: "< 0.6"
    
    - stage: "alpha_maturing"
      trigger: "alpha_captured_ratio >= 0.75"
      action: "second_profit_taking"
      weight_adjustment: -0.25    # reduce another 25%
      rationale: "conviction intact, but risk-reward deteriorating"
      signal_required:
        gap_type: "closing"
        sfm_crowding: "< 0.7"
    
    - stage: "alpha_exhausted"
      trigger: "alpha_captured_ratio >= 0.90"
      action: "reduce_to_residual"
      weight_adjustment: -0.40    # reduce to 10% of original weight
      rationale: "remaining alpha marginal, retain small optionality"
      signal_required:
        gap_magnitude: "< 0.02"
  
  # Residual position — let winners run with minimal exposure
  residual_position:
    weight: 0.10                  # 10% of original weight retained
    rationale: >
      "Optionality — thesis could be more right than initially estimated.
       The super-cycle could extend beyond 2027, or new demand drivers
       could emerge. Small exposure with zero risk budget cost."
    exit_trigger: >
      "gap fully closed (gap_magnitude → 0)
       OR conviction_level drops below 0.5
       OR SFM gradient reverses against thesis factors
       OR tail_circuit_breaker fires"
  
  # Relationship to conviction_level
  conviction_interaction: >
    "Alpha Capture Schedule is ORTHOGONAL to conviction_level.
     Conviction measures 'is the thesis correct?'
     Alpha capture measures 'how much alpha is left?'
     Thesis can be 100% correct (conviction unchanged)
     while alpha is 90% captured → position should still shrink."
```

**Belief-action separation in profit-taking:**
- Graham Region updates `gap_magnitude` (belief: "how much alpha remains?")
- Markowitz Region reads it and executes `weight_adjustment` (action: position reduction)
- Price does NOT trigger profit-taking — alpha capture ratio does, which is derived from expectation_gap, not from price return

### 3. Capital Allocation Registry

A portfolio-level file (not per-thesis) that tracks aggregate capital state across all active theses. It is a **state tracker, NOT a decision maker.**

```yaml
# portfolio/capital_allocation_registry.md
# Markowitz Layer — Cross-Thesis Capital State Tracker
# This file does NOT make allocation decisions.
# When capital is released, it re-enters the framework as available_capital
# and the framework re-runs normally (capital is fungible).

total_capital: 5000000
fisher_max_aggregate_equity: 0.8    # Fisher layer hard constraint

active_theses:
  - thesis: "theses/memory_super_cycle.md"
    allocation: 1000000
    status: active
    alpha_captured_ratio: 0.30
    capital_released: 0              # not yet triggered profit-taking
  
  - thesis: "theses/defensive_cash.md"
    allocation: 2000000
    status: active
    alpha_captured_ratio: null       # defensive thesis, no alpha capture
    capital_released: 0
  
  - thesis: "theses/ai_infra_chokepoint.md"
    allocation: 2000000
    status: active
    alpha_captured_ratio: 0.55
    capital_released: 500000         # triggered first_profit_taking

available_capital: 500000            # released capital awaiting reallocation
aggregate_equity_exposure: 0.60      # 60% deployed to equity, within Fisher 0.8 cap
aggregate_cash_exposure: 0.40       # including defensive thesis

# When available_capital > 0, the framework re-runs normally:
# Fisher provides environment → SFM provides factors → 
# Graham forms/revises beliefs → Markowitz allocates.
# No special reallocation decision tree needed.
```

**Why a registry, not a decision-maker:** Capital released from profit-taking is indistinguishable from new deposits. Building a special "where does profit go" decision tree would duplicate the framework's existing allocation logic. The registry's role is to (1) track aggregate exposure for Fisher constraint enforcement, and (2) record which theses have released capital so the framework knows `available_capital` exists.

### 4. Holdings File Schema (Execution Layer)

The holdings file is **simplified to pure execution record.** All belief fields are removed — they live in the thesis file (Graham Region). The holding file records what actually happened: entry price, current position, P&L, execution log.

```yaml
# holdings/688008_001.yaml
# Execution record — no belief, no strategy, no conviction
# All of those live in the thesis file (Graham Region)

holding_id: 688008_001
ticker: "688008.SH"
name: "Montage Technology"

# Multiple thesis references (for cross-thesis overlap)
thesis_refs:
  - thesis: "theses/memory_super_cycle.md"
    role_in_thesis: core
    target_weight: 0.50
  - thesis: "theses/ai_infra_chokepoint.md"
    role_in_thesis: satellite
    target_weight: 0.30

# ─── Entry ───
entry_date: 2026-07-01
entry_price: 82.50
entry_quantity: 6060
entry_value: 499950

# ─── Current State ───
position_state: open                 # open / reduced / closed
current_quantity: 4545               # reduced after first_profit_taking
current_price: 89.20
current_value: 405474
unrealized_pnl: +55524
realized_pnl: +41288                 # from reduced portion

# ─── Risk Budget Consumption ───
# Derived from thesis risk_budget, split by thesis_refs weights
risk_budget_assigned: 15000           # weighted across theses
risk_budget_consumed: 3200            # max floating loss observed
risk_budget_remaining: 11800

# ─── Execution Log (append-only) ───
execution_log:
  - date: 2026-07-01
    action: buy
    quantity: 6060
    price: 82.50
    reason_ref: "theses/memory_super_cycle.md # initial_entry"
  
  - date: 2026-08-15
    action: sell
    quantity: 1515                    # 25% reduction
    price: 109.50
    reason_ref: "theses/memory_super_cycle.md # alpha_capture_milestone_2"
    realized_pnl: +40905
  
  - date: 2026-08-15
    action: risk_budget_update
    old_budget: 15000
    new_budget: 11250                 # position reduced, risk budget adjusted
    reason_ref: "ADR-010 # position_reduction"
```

**One physical position = one holdings file.** When the same ticker appears in multiple theses, the holdings file records multiple `thesis_refs` entries. The physical position is a single entity — it cannot be split into "these shares belong to thesis A, those to thesis B."

### 5. ADR-009 Partial Supersession

ADR-009's six principles remain valid as **design philosophy.** However, the holding file **field schema** is partially superseded:

| ADR-009 Field | Four-Layer Architecture Location | Status |
|---------------|----------------------------------|--------|
| `entry_logic` | Holdings file → `entry_date`, `entry_price`, `entry_quantity` | Renamed to execution record |
| `position_state` | Holdings file → `position_state`, `current_quantity`, `current_price` | Retained, simplified |
| `conviction_level` | Thesis file → Graham Region | **Moved** — belief field, not execution |
| `key_assumptions` | Thesis file → Graham Region | **Moved** — belief field |
| `disconfirmation_signals` | Thesis file → Graham Region | **Moved** — belief field |
| `market_consensus` | Thesis file → Graham Region | **Moved** — belief field |
| `expectation_gap` | Thesis file → Graham Region | **Moved** — belief field |
| `consensus_catalyst` | Thesis file → Graham Region | **Moved** — belief field |
| `update_log` | Thesis file → Three-Layer Update Log (narrative/conviction/position) | **Moved and expanded** |
| `time_horizon` / `decay_status` | Thesis file → Narrative Log entries | **Moved** — tagged per entry |
| `precommitment_rules` | Thesis file → Markowitz Region | **Moved and expanded** (ADR-010 supersession) |

**Belief Hierarchy mapping:**

| ADR-009 Belief Layer | Four-Layer Architecture Location |
|---------------------|----------------------------------|
| Paradigm ("AI is ten-x revolution") | Thesis file Graham Region — `belief_statement` |
| Industry ("memory super-cycle to 2027") | Thesis file Graham Region — `key_assumptions` |
| Trade ("buy at this price") | Holdings file — `entry_date`, `entry_price`, `entry_quantity` |

ADR-009 is NOT invalidated — its principles are preserved and elevated. The fields are relocated to their structurally correct homes under the four-layer architecture.

### 6. Conviction Level Dual Definition Resolution

ADR-009 defines conviction as a quantitative formula: `conviction = 0.3 × Evidence_norm + 0.5 × IR_norm + 0.2 × GMM_norm`. ADR-016 states "ONLY fundamental signals update conviction." These are unified as:

- **Quantitative Floor (ADR-009):** Offline scripts (Carhart regression, IC engine, GMM) produce a quantitative baseline. This is the conviction anchor — recalculated when scripts run (daily/weekly).
- **Bayesian Adjustment (ADR-016):** Graham layer AI, based on fundamental signals (supply chain verification, penetration rates, order data), proposes Bayesian updates above/below the quantitative floor. Human reviews via bidirectional Feynman protocol before write.

```
Quantitative Floor (machine)     Bayesian Adjustment (AI + human)
     ↓                                    ↓
  Carhart R², IR, GMM           Fundamental signals, catalysts
  Recalculated periodically     Event-driven, Feynman-gated
     ↓                                    ↓
     └─────────── conviction_level ───────────┘
                        ↓
              Markowitz reads → adjusts portfolio
```

### 7. Cross-Thesis Ticker Overlap

When the same ticker appears in multiple active theses:

**7a. Holdings file:** One file per ticker. Multiple `thesis_refs` entries record which theses reference this position.

**7b. Risk budget:** Weighted average across theses, NOT additive. Additive would double-count risk for the same physical position. Weighting is by each thesis's allocation proportion.

**7c. Alpha capture:** Each thesis has an independent `alpha_captured_ratio` (based on its own `expectation_gap`). When theses disagree on profit-taking (A says reduce, B says hold), the Damodaran layer (ADR-018) resolves the conflict by computing a merged action based on combined thesis weights.

**7d. Diversification tracking:** The Damodaran layer tracks total exposure per ticker across all theses and enforces concentration limits.

## What This Does NOT Do

- Does NOT create a special "profit reallocation" decision tree — capital is fungible, framework re-runs normally
- Does NOT store belief fields in holdings files — beliefs live exclusively in thesis file Graham Region
- Does NOT delete ADR-009 — principles preserved, fields relocated
- Does NOT use price-return as profit-taking trigger — alpha_captured_ratio (derived from expectation_gap) is the trigger
- Does NOT eliminate human judgment — conviction updates require bidirectional Feynman review

## Rationale

The Markowitz layer design rests on six insights:

1. **Portfolio construction IS trade meta-plan generation.** Defining "澜起科技 50%" simultaneously defines entry, rebalancing, profit-taking, and exit plans. The trade meta-plan is not a separate function — it is the portfolio construction process viewed across time dimensions.

2. **Capital is fungible.** Realized profit is indistinguishable from new deposits. No special reallocation path is needed — released capital re-enters the framework and is allocated by the normal Fisher → SFM → Graham → Markowitz flow. The Capital Allocation Registry tracks state; the framework makes decisions.

3. **The architecture was asymmetric — it handled loss but not profit.** Complete loss mechanisms (risk budget, re-verification, tail breaker, invalidation) existed, but no normal profit-taking path. The Alpha Capture Schedule fills this gap using Kelly dynamics: as edge shrinks, optimal bet shrinks, even when conviction is unchanged.

4. **Belief fields belong in thesis files, not holdings files.** ADR-009 pre-dated the four-layer architecture. Now that thesis files contain the Graham Region, storing beliefs in both places creates synchronization risk. Holdings files are pure execution records — what actually happened, not what was believed.

5. **Conviction has a quantitative floor and a Bayesian ceiling.** ADR-009's formula and ADR-016's fundamental-signal requirement are complementary, not conflicting. The quantitative floor anchors conviction to statistical evidence; the Bayesian adjustment reflects fundamental judgment. Both are needed — neither alone is sufficient.

6. **Cross-thesis overlap is a physical reality, not a design flaw.** The same ticker will appear in multiple theses. The architecture handles this with one holdings file per ticker, weighted-average risk budgets, and the Damodaran layer's cross-section supervision (ADR-018).

## References

- ADR-009: Holding File Six Principles (partially superseded — fields relocated)
- ADR-010: Belief-Anchored Risk System (risk budget integration)
- ADR-016: Graham Layer Thesis Architecture (Markowitz Region origin, Alpha Capture dependency on expectation_gap)
- Markowitz, H. (1952). Portfolio Selection. Journal of Finance, 7(1):77-91.
- Kelly, J.L. (1956). A New Interpretation of Information Rate. Bell System Technical Journal, 35(4):917-926.
- Grilling session (2026-07-12): Profit-taking归属 analysis, trade meta-plan insight
- Grilling session (2026-07-13): Capital fungibility, cross-thesis overlap, conviction dual definition
