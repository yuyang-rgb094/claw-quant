# ADR-016: Graham Layer — Thesis Architecture

**Status:** Accepted

**Date:** 2026-07-09

## Context

Layer 0 (Fisher) defines the monetary environment. Layer 1 (Sharpe-Fama-Merton) tracks the return manifold's state — factor landscape, anomaly map, and gradient direction. Layer 2 (Graham) must now define how investment beliefs are formed, falsified, and translated into portfolio action — bridging the manifold state to actual capital allocation.

ADR-009 defined six first principles for holding files, including: Belief-Action Separation (Principle 1), Falsificationism (Principle 2), Bayesian Updating (Principle 3), and Second-Order Consensus & Expectation Gap (Principle 6). These principles need a concrete file structure — the thesis file — that operationalizes them.

The design challenge: a thesis is not merely a belief record. It is a **portfolio container** that manages a group of holdings. One thesis ("memory super-cycle") drives multiple positions (澜起科技 50%, 江波龙 30%, 中微 20%) with a shared capital allocation. The thesis file must bridge Graham (belief) and Markowitz (portfolio construction) without conflating them.

## Decision

### Naming

**Graham** — after Benjamin Graham (1934, Security Analysis). Graham's core contribution: intrinsic value vs. market price separation, the "margin of safety" concept, and the "Mr. Market" metaphor. The Graham layer operationalizes these: thesis beliefs are formed from fundamental analysis independent of market price; the market consensus is tracked separately (Mr. Market's mood); the expectation gap between the two is where alpha lives.

### Thesis File Structure

One thesis = one portfolio = one group of holdings. A thesis file has two regions coexisting in a single document:

```
theses/
└── memory_super_cycle.md
    ├── Graham Region (Belief)     ← Only fundamental signals update this
    ├── Markowitz Region (Portfolio) ← Belief changes + risk rules drive this
    └── Update Log (Append-only)   ← Three-layer structure, never deleted
```

### Graham Region (Belief)

```yaml
# ─── Graham Region (Belief) ──────────────────────────────────
thesis_type: growth          # growth / value / defensive
duration_bucket: long_term   # from SFM Module 1b

# Principle 1: Belief-Action Separation
belief_statement: >
  "LLM/Agent engineering is driving memory demand growth, 
   creating a memory super-cycle peaking in 2027."

# Principle 2: Falsificationism
key_assumptions:
  - id: A1
    assumption: "DDR5 penetration rate exceeds 40% by Q2 2026"
    status: confirmed
    verified_date: 2026-06-15
  - id: A2
    assumption: "HBM demand pulls advanced process node capacity"
    status: confirmed
    verified_date: 2026-07-01
  - id: A3
    assumption: "Memory prices continue upward through 2027"
    status: monitoring
    verified_date: null

disconfirmation_signals:
  - id: D1
    signal: "DDR5 penetration rate below 30% by Q3 2026"
    type: quantitative
    source: industry_data
    status: not_triggered
  - id: D2
    signal: "Memory prices decline for 2 consecutive months MoM"
    type: quantitative
    source: market_data
    status: not_triggered
  - id: D3
    signal: "Key customer (hyperscaler) reduces orders >20%"
    type: event
    source: supply_chain
    status: not_triggered

# Principle 3: Bayesian Updating
conviction_level:
  current: 0.72
  derivation: "0.3 × Evidence_norm(0.85) + 0.5 × IR_norm(0.68) + 0.2 × GMM_norm(0.65)"
  # Evidence Level: assumptions A1/A2 confirmed, A3 monitoring
  # IR: rolling 4-quarter information ratio of thesis-driven positions
  # GMM: Gaussian Mixture Model persistence of factor returns
  last_update: 2026-07-05
  last_update_reason: "HBM demand exceeded expectations, Samsung expanded advanced node"
  last_update_type: fundamental   # ONLY fundamental signals update conviction

# Principle 6: Second-Order Consensus
market_consensus:
  current_pricing: >
    "Market prices in a mild memory recovery, not a super-cycle.
     Sector PE at 45th percentile vs 5-year range."
  
expectation_gap:
  direction: divergent          # convergent / divergent / stale
  my_view: "Super-cycle driven by AI/Agent demand"
  market_view: "Cyclical recovery, moderate growth"
  gap_type: catalyst_pending     # catalyst_pending / catalyst_active / closing
  gap_magnitude: 0.15            # estimated alpha if gap closes

consensus_catalyst:
  event: "Q2 2026 earnings season: DDR5 penetration disclosure + HBM revenue breakdown"
  expected_date: 2026-08-15
  type: earnings_release
  market_reprice_direction: upward
  confidence: 0.7

# Fisher Layer Alignment
# NOTE: fisher_alignment is the PROCESSED alignment assessment stored in the thesis.
# It is derived from the fisher_interface (Graham Interface Contract, ≤400 tokens)
# which is the COMPRESSED INPUT from fisher_state.md. The relationship:
#   fisher_state.md (full) → fisher_interface (≤400 tokens, schema-compressed)
#   → fisher_alignment (thesis file, processed assessment: aligned/misaligned/neutral)
# The thesis file does NOT store the raw fisher_state.md — only the processed alignment.
fisher_alignment:
  stock_vs_cash_baseline: stocks_favored   # from fisher_interface.stock_vs_cash
  ust_direction: declining                  # from fisher_interface.key_signal_2
  position_constraint: 0.8                   # from fisher_interface.position_constraint
  alignment: aligned                         # derived: thesis duration vs Fisher cycle phase
  fisher_confidence: 0.75                    # from fisher_interface.confidence

# SFM Layer Alignment
# NOTE: sfm_alignment is the PROCESSED alignment assessment stored in the thesis.
# Derived from sfm_interface (Graham Interface Contract, ≤400 tokens).
# The thesis file does NOT store the raw sfm_state.md — only the processed alignment.
sfm_alignment:
  duration_regime: long_term_favored        # from sfm_interface.phase
  preferred_factors: [residual_momentum, quality, earnings_revision]  # from sfm_interface
  crowding_in_target_factors: low            # from sfm_interface.key_signal_2
  gradient_direction: flowing_to_long_duration  # from sfm_interface.gradient_direction
  sfm_confidence: 0.62                    # from sfm_interface.confidence
  alignment: aligned                         # derived: thesis factors vs SFM factor preference
```

### Markowitz Region (Portfolio)

```yaml
# ─── Markowitz Region (Portfolio) ────────────────────────────
# Driven by conviction changes (from Graham) + risk rules (ADR-010)

total_allocation: 1000000      # CNY allocated to this thesis

portfolio_composition:
  - ticker: "688008.SH"
    name: "Montage Tech (澜起科技)"
    weight: 0.50
    role: "DDR5 interface chip — primary beneficiary"
    duration_bucket: long_term
    entry_logic_ref: "thesis:memory_super_cycle.md#belief_statement"
    entry_price: null          # recorded in holdings/688008.md
    current_position_state: held
    
  - ticker: "301308.SZ"
    name: "Longsys Electronics (江波龙)"
    weight: 0.30
    role: "Memory module — volume play"
    duration_bucket: medium_term
    entry_logic_ref: "thesis:memory_super_cycle.md#belief_statement"
    entry_price: null
    current_position_state: held
    
  - ticker: "688012.SH"
    name: "AMEC (中微半导体)"
    weight: 0.20
    role: "Equipment — capacity expansion beneficiary"
    duration_bucket: long_term
    entry_logic_ref: "thesis:memory_super_cycle.md#belief_statement"
    entry_price: null
    current_position_state: held

# Risk Budget (ADR-010 Belief-Anchored Risk System)
risk_budget:
  conviction_tier: high                    # from conviction_level: 0.72 → high
  base_risk_budget: 0.02                   # high conviction = 2% of allocation
  market_momentum_regulator: bull           # from sfm_state.md
  momentum_multiplier: 1.5                 # bull ×1.5
  effective_risk_budget: 0.03              # 2% × 1.5 = 3% = ¥30,000
  tail_circuit_breaker:                    # only hard trigger
    main_board_threshold: 0.10             # ≥10% drawdown → hard exit
    star_chinext_threshold: 0.15           # ≥15% for STAR/ChiNext
    consecutive_limit_down: 2              # 2 consecutive limit-down → exit
    five_day_decline_threshold: 0.30       # 5-day ≥30% decline → exit

# Precommitment Rules (ADR-009 Principle 4 — Time Inconsistency Constraint)
# These rules are committed in a CALM state and executed in an EMOTIONAL state.
# They are the thesis file's precommitment_rules field, superseding ADR-009's
# original dual-layer design per ADR-010.
# Re-verification protocol follows ADR-010's two-tier system:
#   - Fast Check (5 min): scan public negatives, check disconfirmation signals,
#     check cross-validation → clear / suspicious / confirmed_break
#   - Full Check (30 min): re-run complete Skill analysis, update Evidence/IR/GMM,
#     recompute conviction_level
precommitment_rules:
  - condition: "conviction_level change > 0.15"
    action: "recalculate risk_budget and rebalance"
    source: graham_region
    verification: "ADR-010 Fast Check — confirm fundamental basis for conviction change"
  - condition: "sfm_alignment changes from aligned to misaligned"
    action: "flag for review, reduce position if conviction also drops"
    source: sfm_layer
    verification: "ADR-010 Fast Check — check if factor rotation invalidates thesis assumptions"
  - condition: "fisher_alignment changes from stocks_favored to cash_favored"
    action: "activate defensive posture, reduce gross exposure"
    source: fisher_layer
    verification: "ADR-010 Fast Check — if Tier 2/3 Fisher event, run Full Check before action"
  - condition: "disconfirmation_signal triggered"
    action: "immediate conviction re-evaluation"
    source: graham_region
    verification: "ADR-010 Full Check (30 min) — disconfirmation signal is fundamental, requires complete re-assessment"
  - condition: "risk_budget breached (floating loss reaches effective_risk_budget)"
    action: "trigger belief re-verification, NOT automatic sale"
    source: markowitz_region
    verification: "ADR-010 two-tier: Fast Check first; if suspicious, Full Check; if confirmed_break, reduce per conviction rules"
  - condition: "tail_circuit_breaker triggered (≥10% single-day / ≥15% STAR / 2 consecutive limit-down / 5-day ≥30%)"
    action: "immediate reduction to 30% of position, then emergency re-verification"
    source: markowitz_region
    verification: "ADR-010 Layer 3 — only unconditional hard trigger; fires on information asymmetry assumption"
```

### Update Log (Append-Only, Three-Layer)

```yaml
# ─── Update Log (Never Deleted, Append-Only) ─────────────────
# Three layers map to ADR-009's belief hierarchy and information flow

update_log:
  
  # Layer 1: Narrative Log — human insight, events, AI verification
  # Each entry tagged with time_horizon and decay_status (ADR-009 Principle 5)
  # time_horizon: short (1-3d) / medium (1-4Q) / long (1-5y)
  # decay_status: fresh / aging / expired — expired info must be re-verified before use
  narrative_log:
    - timestamp: "2026-07-01T14:30:00+08:00"
      author: human
      type: insight
      time_horizon: medium            # Samsung capex = industry-level, quarterly relevance
      decay_status: fresh            # recent, not yet aging
      content: >
        "Samsung announced expansion of HBM advanced node capacity.
         This validates assumption A2. HBM demand pulling advanced 
         process is now confirmed by supply-side action."
      action_taken: "flagged for AI verification"
    
    - timestamp: "2026-07-02T09:00:00+08:00"
      author: agent
      type: verification
      time_horizon: medium            # supply chain verification = quarterly relevance
      decay_status: fresh
      content: >
        "Verified: Samsung Q2 capex guidance increased 35% YoY.
         HBM3E qualification confirmed at TSMC. 
         Supply chain cross-check: 3/3 equipment vendors 
         confirm advanced node orders."
      verification_result: confirmed
      source_reliability: tier_a
    
    - timestamp: "2026-07-05T10:15:00+08:00"
      author: human
      type: insight
      time_horizon: short             # DDR5 penetration data = monthly, decays fast
      decay_status: fresh
      content: >
        "DDR5 penetration data from industry research suggests 
         >40% by Q2, ahead of schedule. Memory prices 
         continued upward in June."
      action_taken: "flagged for conviction update"
  
  # Layer 2: Conviction Log — Bayesian updates
  conviction_log:
    - timestamp: "2026-07-05T10:30:00+08:00"
      trigger: narrative_log_entry_above
      prior_conviction: 0.68
      evidence:
        type: fundamental
        description: "HBM demand exceeded expectations + DDR5 penetration ahead"
        evidence_level: strong        # weak/moderate/strong
      posterior_conviction: 0.72
      update_magnitude: 0.04
      bayesian_reasoning: >
        "Prior 0.68 reflected A1 confirmed, A2 monitoring. 
         Now A2 confirmed via Samsung capex + supply chain cross-check. 
         Evidence level upgraded to strong. 
         Posterior = prior + weighted_evidence_update = 0.72."
      conviction_tier_change: null    # still in 'high' tier (0.6-0.8)
      position_action_triggered: null  # no position change needed
    
    - timestamp: "2026-06-15T16:00:00+08:00"
      trigger: assumption_verification
      prior_conviction: 0.62
      evidence:
        type: fundamental
        description: "A1 confirmed: DDR5 penetration at 42% in May data"
        evidence_level: moderate
      posterior_conviction: 0.68
      update_magnitude: 0.06
      bayesian_reasoning: >
        "A1 moved from monitoring to confirmed. Evidence moderate 
         (single data point, needs Q2 confirmation). 
         Standard Bayesian update applied."
      conviction_tier_change: "medium → high"  # crossed 0.6 threshold
      position_action_triggered: "risk_budget recalculated: base 1% → 2%"
  
  # Layer 3: Position Log — quantifiable portfolio changes
  position_log:
    - timestamp: "2026-06-15T16:05:00+08:00"
      trigger: conviction_tier_change
      conviction_tier: high
      action: "risk_budget_update"
      old_risk_budget: 0.01          # medium = 1%
      new_risk_budget: 0.02          # high = 2%
      momentum_multiplier: 1.5      # bull market
      effective_risk_budget: 0.03   # 3%
      total_allocation: 1000000
      max_risk_amount: 30000        # ¥30,000 = 3% of ¥1M
      position_changes: null        # no holdings added/removed
      rebalancing_note: >
        "Risk budget increased due to conviction tier upgrade.
         Existing positions within new risk budget — no rebalance needed."
    
    - timestamp: "2026-07-05T10:35:00+08:00"
      trigger: conviction_update
      conviction_change: 0.04       # 0.68 → 0.72
      action: "no_action"
      reason: "change < 0.15 threshold, conviction tier unchanged"
      positions_status:
        688008.SH: { weight: 0.50, unrealized_pnl: 0.08, within_risk_budget: true }
        301308.SZ: { weight: 0.30, unrealized_pnl: 0.03, within_risk_budget: true }
        688012.SH: { weight: 0.20, unrealized_pnl: -0.02, within_risk_budget: true }
```

### Defensive Thesis (Special Case)

A Defensive Thesis represents the belief that "current manifold state does not support high-conviction offensive positions." It is NOT "doing nothing" — it is an active conviction position grounded in Fisher (1920).

```yaml
# theses/defensive_cash.md
thesis_type: defensive
duration_bucket: none              # no factor exposure

belief_statement: >
  "Current Fisher layer stock_vs_cash_baseline = cash_favored.
   Sharpe-Fama-Merton Layer factor preference confidence < 0.6.
   The manifold state does not support high-conviction positions.
   Cash is the optimal risk-adjusted position."

# No standard key_assumptions — defensive thesis has different structure
key_assumptions:
  - id: DA1
    assumption: "Fisher layer stock_vs_cash_baseline remains cash_favored"
    status: monitoring
  - id: DA2
    assumption: "No factor in Sharpe-Fama-Merton Layer achieves confidence > 0.6"
    status: monitoring

disconfirmation_signals:
  - id: DD1
    signal: "Fisher layer stock_vs_cash_baseline changes to stocks_favored"
    type: structural
    source: fisher_layer
    status: not_triggered
  - id: DD2
    signal: "Sharpe-Fama-Merton Layer factor_preference confidence > 0.6 with crowding < 0.5"
    type: structural
    source: sfm_layer
    status: not_triggered
  - id: DD3
    signal: "Both DD1 and DD2 satisfied simultaneously"
    type: combined
    source: fisher_sfm_joint
    status: not_triggered
    note: "Disconfirmation requires both macro improvement AND factor opportunity"

conviction_level:
  current: 0.80
  derivation: "Based on Fisher stock_vs_cash_baseline strength + SFM gradient unreliability"
  last_update: 2026-07-09

# Markowitz Region
total_allocation: 0              # no capital deployed in offensive positions
portfolio_composition:
  - ticker: "CASH"
    name: "Cash / Money Market"
    weight: 1.0
    role: "Defensive position"
    entry_logic_ref: "thesis:defensive_cash.md#belief_statement"

risk_budget:
  conviction_tier: high           # high conviction in the defensive stance
  base_risk_budget: 0.0           # no risk budget — no positions to risk
  effective_risk_budget: 0.0

# Exit logic: Logic B + prompt-level calibration (NOT code-level gate)
exit_protocol:
  method: "context_window_full_access"
  description: >
    "All Fisher and Sharpe-Fama-Merton Layer context is presented to the Graham Transformer.
     No code-level gate filters information. The attention mechanism determines
     weighting between macro risk and factor opportunity.
     Prompt-level calibration provides a prior, not a hard gate."
  calibration_rule: >
    "When Fisher says cash_favored:
      - Default: maintain Defensive Thesis
      - Override (create new offensive thesis) requires:
        1. SFM factor_preference confidence > 0.6
        2. Specific consensus_catalyst identified
        3. Target factor duration bucket crowding < 0.5
      - Override reasoning must be explicitly documented in narrative_log"
  rationale: >
    "Modern multi-head attention models can balance conflicting signals 
     from Fisher (macro risk) and SFM (factor opportunity). 
     Hard gating (Logic A) would zero out valid factor signals — 
     equivalent to forcing attention weight = 0. 
     Full context access (Logic B) lets the Transformer's attention 
     mechanism perform the weighting naturally. 
     Prompt calibration prevents overconfidence without blocking information."
```

### Thesis Invalidation Protocol

A thesis is not immortal. It must be falsifiable (ADR-009 Principle 2) — which means there must be a defined process for declaring it dead and winding down its portfolio. Without this, the system degenerates into "the thesis is never wrong, the market is just temporarily irrational."

#### Invalidation Triggers

A thesis enters invalidation review when ANY of the following conditions is met:

| Trigger | Condition | Severity |
|---------|-----------|----------|
| **Conviction Collapse** | `conviction_level.current < 0.3` | Automatic — conviction tier "none" |
| **Disconfirmation Cascade** | ≥ 50% of `disconfirmation_signals` have `status: triggered` | Automatic — falsification criteria met |
| **Core Assumption Collapse** | Any `key_assumptions` item with `id` tagged as `critical: true` changes to `status: refuted` | Automatic — foundational belief broken |
| **Fisher Regime Shift** | Fisher layer undergoes Tier 3 regime change (ADR-012) that changes `stock_vs_cash_baseline` from `stocks_favored` to `cash_favored` for > 2 consecutive assessment cycles | Review-required — environment no longer supports equity theses |
| **SFM Gradient Reversal** | Sharpe-Fama-Merton Layer gradient direction reverses against the thesis's factor exposure for > 2 consecutive assessment cycles | Review-required — the manifold's gradient is flowing against the thesis |

#### Invalidation Process

```
Step 1: Trigger Detection
  → Automatic triggers (conviction < 0.3, disconfirmation cascade, core assumption collapse):
    Proceed immediately to Step 2
  → Review-required triggers (Fisher regime, SFM gradient):
    Require ADR-010 Full Check (30 min) before proceeding

Step 2: Invalidation Assessment (ADR-010 Full Check)
  → Re-run complete Skill analysis on all holdings in the thesis portfolio
  → Check: has the fundamental basis changed, or is this a price-driven panic?
  → Price signals alone CANNOT invalidate a thesis (reflexive feedback loop guard)
  → Output: confirmed_invalidated / thesis_intact_review_needed / partial_invalidation

Step 3: Confirmed Invalidation → Winding Down
  → conviction_level.current → 0.0, status → "invalidated"
  → thesis file status: active → invalidated
  → Holdings wind-down protocol (see below)
  → Thesis file archived (NOT deleted — append-only history preserved)

Step 4: Partial Invalidation (if applicable)
  → Some assumptions invalidated but core thesis holds
  → Reduce conviction to reflect weakened basis
  → Remove affected holdings from portfolio_composition
  → Rebalance remaining holdings
```

#### Holdings Wind-Down Protocol

When a thesis is confirmed invalidated, its holdings must be wound down. The wind-down respects the belief-action separation principle — the action (selling) is driven by the belief change (invalidation), not by price.

```yaml
wind_down_protocol:
  # Thesis status: active → invalidated
  thesis_status: invalidated
  invalidation_date: "2026-XX-XX"
  invalidation_reason: "conviction_below_0.3 / disconfirmation_cascade / assumption_refuted"
  
  # Graduated exit — NOT fire sale
  exit_schedule:
    - phase: immediate
      action: "reduce all positions to 50% of current weight"
      timing: "next trading session"
      rationale: "conviction gone, but respect T+1 and liquidity constraints"
    
    - phase: orderly
      action: "reduce remaining 50% over 5-10 trading days"
      timing: "within 2 weeks"
      rationale: "avoid market impact from concentrated selling"
      exception: "if tail_circuit_breaker fires during wind-down, accelerate to immediate full exit"
    
    - phase: final
      action: "close all positions, return capital to cash"
      timing: "within 3 weeks of invalidation"
  
  # Capital reallocation
  capital_reallocation:
    - option_a: "return to cash — await new thesis"
    - option_b: "redeploy to Defensive Thesis if Fisher is cash_favored"
    - option_c: "redeploy to new offensive thesis if Fisher+SFM support it"
    decision_required: "human review — AI proposes, human approves reallocation"
  
  # Archival — thesis file is NEVER deleted
  archival:
    new_status: archived_invalidated
    retention: permanent
    reason: >
      "Invalidated theses are valuable negative examples.
       They calibrate future conviction assessments — 
       a thesis that was invalidated at conviction 0.72 
       provides data on what evidence was insufficient."
```

#### What Invalidation Does NOT Do

- Does NOT delete the thesis file — archived, not removed. The update log, conviction history, and disconfirmation record are preserved for future calibration.
- Does NOT trigger automatic new thesis creation — capital returns to cash or Defensive Thesis. New thesis requires the full Graham belief formation process.
- Does NOT allow price-only invalidation — only fundamental signals (assumption refutation, disconfirmation cascade) can invalidate. Price drops trigger ADR-010 re-verification, not invalidation.
- Does NOT skip the Full Check — even automatic triggers (conviction < 0.3) require a Full Check to confirm the conviction drop was fundamental, not a transient panic.

### Cross-Layer Information Flow

The thesis file is the nexus where all three layers converge:

```
Fisher Layer → fisher_alignment (stock_vs_cash_baseline, ΔUST)
                ↓
Sharpe-Fama-Merton Layer → sfm_alignment (duration_regime, factor_preference, crowding)
                ↓
Graham Layer → belief formation (conviction, assumptions, catalyst)
                ↓ conviction_level as interface
Markowitz Layer → portfolio expression (weights, risk_budget, rebalancing)
```

**Critical design rule:** Information flows DOWN only. Graham layer never changes Fisher or SFM state. Markowitz region never changes Graham beliefs. Price signals (unrealized P&L, drawdown) can trigger risk actions in Markowitz region but CANNOT update conviction in Graham region (reflexive feedback loop guard, ADR-009).

### Prompt-Level Calibration (Not Code-Level Gate)

The decision between Logic A (hard gate) and Logic B (full context) resolves as follows:

**Modern multi-head attention models can naturally balance conflicting signals** from Fisher (macro risk) and SFM (factor opportunity). Different attention heads focus on different information sources; the FFN layer combines them. Hard gating would artificially zero out valid signals, equivalent to forcing attention weights — the very "gradient vanishing" problem.

However, attention mechanisms have structural biases:
- **Length bias**: Longer outputs naturally receive more attention
- **Position bias**: Recent context gets higher attention (recency)
- **Semantic strength bias**: Dramatic macro narrative ("crisis", "crash") gets more attention than numerical factor data

These biases mean Logic B alone is insufficient — the prompt must provide calibration. The calibration is a **prior**, not a filter:

```
When Fisher layer says stock_vs_cash_baseline = cash_favored:
  - Default: maintain Defensive Thesis
  - Override requires elevated evidence:
    1. SFM factor_preference confidence > 0.6
    2. consensus_catalyst identified
    3. Target factor crowding < 0.5
  - Document override reasoning explicitly
```

This gives the Transformer full context (Logic B) while preventing overconfidence in hostile macro environments (soft Logic A). The attention mechanism does the actual weighting; the prompt ensures the calibration prior is present.

### Graham Interface Contract

Prompt-level calibration defines the *semantic* prior (what the Transformer should weigh more carefully). The Graham Interface Contract defines the *structural* prior — a fixed-schema, fixed-token-budget output contract that each upstream layer must satisfy before its context enters Graham's attention window.

#### Problem Statement

Multi-head attention resolves *what* signals get attended to (head specialization), but does not resolve *how much* total weight each source receives. Three structural biases persist regardless of head count:

| Bias | Mechanism | Consequence |
|------|-----------|-------------|
| **Length bias** | Softmax normalizes over all tokens; a 2000-token Fisher output naturally receives ~4x the total weight of a 500-token SFM output | Macro narrative over-dominates factor data |
| **Position bias** | Autoregressive decoding gives higher attention to recent tokens (recency effect) | Signal ordering within context window affects weight allocation |
| **Semantic strength bias** | Emotionally charged language ("crisis", "crash") attracts more attention than numerical data ("IC=0.03") | Narrative intensity distorts quantitative signal weighting |

These biases are properties of the input distribution, not the attention architecture. Adding heads does not fix them — softmax normalization is global.

#### Design: Symmetric Schema + Token Budget

Each upstream layer outputs a **compressed interface object** — a fixed YAML schema with equal field count, equal token budget, and parallel structure. The schema enforces information density parity at the source.

**Token budget:** Each interface ≤ 400 tokens. This is a prompt-level constraint, not a code-level truncation — the upstream layer's system prompt instructs it to produce output conforming to the schema.

```yaml
# ─── Graham Interface Contract (each layer ≤ 400 tokens) ──────

# Fisher Layer → Graham Interface
fisher_interface:
  phase: "easing"                              # enum: easing / tightening / peak / trough
  stock_vs_cash: "stocks_favored"              # enum: stocks_favored / cash_favored / neutral
  key_signal_1: "Fed balance sheet M↑ 2.1%"    # ≤ 20 tokens, factual
  key_signal_2: "UST 10Y declining 15bp"      # ≤ 20 tokens, factual
  position_constraint: "max_equity: 0.8"        # ≤ 10 tokens
  confidence: 0.75                              # 0-1 scalar

# Sharpe-Fama-Merton Layer → Graham Interface
sfm_interface:
  phase: "long_duration_favored"               # enum: short_favored / medium_favored / long_favored / neutral
  preferred_factors: ["residual_momentum"]      # ≤ 3 items
  key_signal_1: "IC half-life 70.9d (stable)"  # ≤ 20 tokens, factual
  key_signal_2: "crowding 0.36 (low)"           # ≤ 20 tokens, factual
  gradient_direction: "flowing_to_long"         # ≤ 10 tokens
  confidence: 0.62                              # 0-1 scalar
```

**Symmetry rules:**
1. **Equal field count**: both interfaces have exactly 6 fields (phase, primary classification, two key signals, one directional output, confidence)
2. **Parallel structure**: both use enum + factual signals + scalar confidence — no narrative paragraphs
3. **Equal token budget**: both ≤ 400 tokens — eliminates length bias at the source
4. **Factual expression only**: `key_signal_N` must be factual statements with numbers, not emotional narratives — mitigates semantic strength bias
5. **Confidence scalar**: both provide a 0-1 confidence value, allowing the attention mechanism to weight by self-assessed signal quality

#### Distillation Gate (Fallback)

When an upstream layer's raw state exceeds the token budget (e.g., Fisher layer during a major policy regime shift with >2000 tokens of analysis), a **distillation step** compresses the full state into the interface schema before it enters Graham's context window.

```
Normal flow:
  fisher_state.md (full) → fisher_interface (≤400 tokens) → Graham context window

Distillation flow (when raw state is unusually complex):
  fisher_state.md (full) → distillation_prompt → fisher_interface (≤400 tokens) → Graham context window
```

**Distillation prompt** (lightweight, single LLM call):
```
Given the following fisher_state.md (or sfm_state.md) content,
extract the 6 fields defined in the Graham Interface Contract schema.
Prioritize: phase classification, the two most decision-relevant factual signals,
and confidence assessment. Output YAML only, ≤ 400 tokens.
Discard narrative context — Graham's attention will operate on the compressed interface.
```

**When to trigger distillation:**
- After Tier 2/3 Fisher update protocol events (ADR-012) — regime shifts produce dense analysis
- After SFM Module 3 gradient reversal detection — factor rotation events produce extended reasoning
- Manual trigger: when the upstream layer's system prompt reports token count > 400 in self-check

Distillation is **not** a filter — it does not decide what Graham should attend to. It normalizes the input distribution so the attention mechanism can operate without structural bias. The full upstream state remains accessible via file reference (`fisher_state.md`, `sfm_state.md`) if Graham's reasoning needs to drill down.

#### Relationship to Prompt-Level Calibration

The two mechanisms are complementary, not redundant:

| Mechanism | Addresses | Layer | Type |
|----------|-----------|-------|------|
| **Graham Interface Contract** | Length bias, semantic strength bias | Input structure | Schema constraint |
| **Prompt-Level Calibration** | Overconfidence in hostile environments | Attention prior | Semantic instruction |

The interface contract ensures the *input distribution* is balanced (Fisher and SFM arrive with equal structural weight). The prompt calibration ensures the *attention allocation* is calibrated (when Fisher says `cash_favored`, SFM override needs elevated evidence). Together they cover both the structural and semantic dimensions of the bias problem.

Position bias (recency) is partially mitigated by the symmetric schema — since both interfaces have parallel structure, the recency advantage of whichever was output last is structurally bounded. Full elimination of position bias would require interleaving Fisher and SFM fields, which sacrifices schema clarity for marginal bias reduction — not worth the complexity.

## What This Does NOT Do

- Does NOT use price signals to update conviction — only fundamental signals (reflexive feedback loop guard)
- Does NOT hard-code exit triggers based on price — risk management is in Markowitz region via ADR-010
- Does NOT filter information between layers — all context presented to the Transformer (Logic B)
- Does NOT allow Markowitz region to modify Graham beliefs — information flows DOWN only
- Does NOT require every holding to have its own thesis — one thesis drives a portfolio of holdings
- Does NOT use code-level gates between Fisher and Graham — calibration is prompt-level, preserving attention mechanism's weighting ability
- Does NOT truncate upstream layer output — the Graham Interface Contract is a schema constraint on upstream system prompts, not a code-level truncation of existing state files
- Does NOT filter information through distillation — distillation normalizes the input distribution; the full upstream state remains accessible via file reference
- Does NOT require model weight access — the interface contract works with API-based LLMs, no embedding-level projection or KV cache compression needed
- Does NOT allow price-only thesis invalidation — only fundamental signals can invalidate; price drops trigger re-verification, not invalidation
- Does NOT delete invalidated thesis files — archived permanently as negative examples for future conviction calibration

## Rationale

The thesis file design rests on six insights:

1. **Belief-Action Separation requires structural enforcement.** Graham region (belief) and Markowitz region (portfolio) coexist in one file but are updated by different signals. The interface is `conviction_level` — belief changes trigger portfolio adjustments, never the reverse.

2. **Falsificationism requires both pre-commitment and a termination protocol.** Disconfirmation signals are defined in a calm state and cannot be redefined in panic (ADR-009 Principle 2). But falsification is meaningless without a defined invalidation process — the Thesis Invalidation Protocol ensures that when falsification criteria are met, the system acts rather than rationalizes.

3. **Second-Order Consensus is the alpha source.** `market_consensus` + `expectation_gap` + `consensus_catalyst` — being right is not enough; being right before the market corrects is where alpha lives. Without a catalyst, being right but early is indistinguishable from being wrong.

4. **Modern attention mechanisms handle multi-source context, but not multi-source bias.** The choice between hard gating (Logic A) and full context access (Logic B) resolves in favor of Logic B + prompt calibration. The Transformer's multi-head attention can balance conflicting signals from Fisher and SFM layers, but structural biases (length, position, semantic strength) persist regardless of head count. The Graham Interface Contract addresses these biases at the input distribution level — a structural prior that complements the semantic prior of prompt-level calibration.

5. **Time Inconsistency and Information Decay require persistent enforcement.** Precommitment rules (ADR-009 Principle 4) are defined when calm and executed when emotional — the thesis file persists them. Information decay tags (ADR-009 Principle 5) on narrative log entries prevent stale evidence from masquerading as fresh conviction support.

## References

- Graham, B. & Dodd, D. (1934). Security Analysis.
- Fisher, I. (1930). The Theory of Interest. (Defensive Thesis grounding)
- ADR-009: Holding File Six Principles (Principles 1, 2, 3, 6 operationalized)
- ADR-010: Belief-Anchored Risk System (risk_budget fields in Markowitz region)
- ADR-011: Fisher Layer (fisher_alignment input)
- ADR-014: Sharpe-Fama-Merton Layer (sfm_alignment input)
- Grilling session (2026-07-09): One-to-many thesis→holdings structure, Logic B + prompt calibration decision
- Grilling session (2026-07-11): Graham Interface Contract — symmetric schema + token budget, mHC convergence analysis, distillation gate fallback
