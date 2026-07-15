# Thesis Template — [Thesis Name]
<!-- Schema: ADR-016 (Graham Layer) + ADR-017 (Markowitz Layer) -->
<!-- Copy to theses/<name>.md and populate with real analysis -->
<!-- Last updated: YYYY-MM-DD -->

# ─── Graham Region (Belief) ────────────────────────────────────────
<!-- Only fundamental signals update this region (ADR-016 Principle 3) -->
graham_region:

  thesis_type: growth                 # growth / value / defensive
  duration_bucket: long_term         # short_term / medium_term / long_term (from SFM Module 1b)

  # Principle 1: Belief-Action Separation
  belief_statement: >
    "[Describe the core investment belief — what is the market missing?]"

  # Principle 2: Falsificationism
  key_assumptions:
    - id: A1
      assumption: "[Testable assumption 1]"
      status: monitoring              # confirmed / monitoring / refuted
      verified_date: null
    - id: A2
      assumption: "[Testable assumption 2]"
      status: monitoring
      verified_date: null

  disconfirmation_signals:
    - id: D1
      signal: "[What would prove this thesis wrong?]"
      type: quantitative              # quantitative / event
      source: "[data source]"
      status: not_triggered           # not_triggered / triggered

  # Principle 3: Bayesian Updating
  # Quantitative Floor (ADR-009): 0.3×Evidence + 0.5×IR + 0.2×GMM
  # Bayesian Adjustment (ADR-016): fundamental signals, Feynman-gated
  conviction_level:
    current: 0.50                     # 0-1
    derivation: "[How was this computed?]"
    last_update: YYYY-MM-DD
    last_update_reason: "[What fundamental signal changed?]"
    last_update_type: fundamental     # ONLY fundamental signals update conviction

  # Principle 6: Second-Order Consensus
  market_consensus:
    current_pricing: >
      "[What does the market currently believe/priced in?]"

  expectation_gap:
    direction: divergent              # convergent / divergent / stale
    my_view: "[Your view]"
    market_view: "[Market consensus]"
    gap_type: catalyst_pending        # catalyst_pending / catalyst_active / closing
    gap_magnitude: 0.15               # estimated alpha if gap closes

  consensus_catalyst:
    event: "[What event will close the gap?]"
    expected_date: YYYY-MM-DD
    type: earnings_release            # earnings_release / policy_event / industry_data
    market_reprice_direction: upward  # upward / downward
    confidence: 0.7                   # 0-1

  # Fisher Layer Alignment (from fisher_interface, ≤400 tokens, ADR-016 Interface Contract)
  fisher_alignment:
    stock_vs_cash_baseline: neutral  # from fisher_interface.stock_vs_cash
    ust_direction: stable             # from fisher_interface.key_signal_2
    position_constraint: 0.60         # from fisher_interface.position_constraint
    alignment: neutral                # aligned / misaligned / neutral
    fisher_confidence: 0.70           # from fisher_interface.confidence

  # SFM Layer Alignment (from sfm_interface, ≤400 tokens, ADR-016 Interface Contract)
  sfm_alignment:
    duration_regime: long_term_favored   # from sfm_interface.phase
    preferred_factors: [value, quality]   # from sfm_interface
    crowding_in_target_factors: low       # from sfm_interface.key_signal_2
    gradient_direction: flowing_to_long_duration  # from sfm_interface.gradient_direction
    sfm_confidence: 0.62                  # from sfm_interface.confidence
    alignment: aligned                    # aligned / misaligned / neutral


# ─── Markowitz Region (Portfolio Construction) ─────────────────────
<!-- Driven by conviction changes (from Graham) + risk rules (ADR-010) -->
<!-- Portfolio construction IS trade meta-plan generation (ADR-017) -->
markowitz_region:

  total_allocation: 0                 # CNY allocated to this thesis

  # Component 1: Portfolio Composition
  portfolio_composition:
    - ticker: "[TICKER.SH]"
      name: "[Company Name]"
      target_weight: 0.50             # fraction of total_allocation
      role: core                       # core / satellite / hedge
      duration_bucket: long_term
      entry_logic_ref: "thesis:#belief_statement"
      entry_price: null               # recorded in holdings file
      current_position_state: pending # held / pending / closed

  # Component 2: Risk Budget (ADR-010 Belief-Anchored Risk System)
  risk_budget:
    conviction_tier: medium           # from conviction_level: high(>0.7)/medium(0.4-0.7)/low(<0.4)
    base_risk_budget: 0.01            # 1% of allocation for medium conviction
    market_momentum_regulator: neutral # from sfm_state.md
    momentum_multiplier: 1.0          # bull×1.5 / neutral×1.0 / bear×0.5
    effective_risk_budget: 0.01       # base × multiplier
    tail_circuit_breaker:             # ADR-010 hard exit triggers
      main_board_threshold: 0.10      # >=10% drawdown
      star_chinext_threshold: 0.15    # >=15% for STAR/ChiNext
      consecutive_limit_down: 2
      five_day_decline_threshold: 0.30

  # Component 3: Precommitment Rules (ADR-016, ADR-010 verification)
  # ABNORMAL paths — what happens when thesis deviates
  precommitment_rules:
    - condition: "conviction_level change > 0.15"
      action: "recalculate risk_budget and rebalance"
      source: graham_region
      verification: "ADR-010 Fast Check"
    - condition: "sfm_alignment changes from aligned to misaligned"
      action: "flag for review, reduce position if conviction also drops"
      source: sfm_layer
      verification: "ADR-010 Full Check"

  # Component 4: Alpha Capture Schedule (ADR-017 — normal profit-taking path)
  # Kelly Dynamic: as alpha is captured, remaining edge shrinks, position shrinks
  # ORTHOGONAL to conviction — thesis can be 100% correct while position shrinks
  alpha_capture_schedule:
    initial_gap_magnitude: 0.15       # snapshot at thesis creation, not dynamic

    milestones:
      - stage: "alpha_emerging"
        trigger: "alpha_captured_ratio >= 0.30"
        action: "review_position_sizing"
        weight_adjustment: 0.0
        rationale: "early confirmation, let it run"

      - stage: "alpha_accelerating"
        trigger: "alpha_captured_ratio >= 0.50"
        action: "first_profit_taking"
        weight_adjustment: -0.25
        rationale: "de-risk, recover initial cost basis"

      - stage: "alpha_maturing"
        trigger: "alpha_captured_ratio >= 0.75"
        action: "second_profit_taking"
        weight_adjustment: -0.25
        rationale: "conviction intact, risk-reward deteriorating"

      - stage: "alpha_exhausted"
        trigger: "alpha_captured_ratio >= 0.90"
        action: "reduce_to_residual"
        weight_adjustment: -0.40
        rationale: "remaining alpha marginal, retain small optionality"

    residual_position:
      weight: 0.10
      rationale: "Optionality — thesis could be more right than estimated"
      exit_trigger: "gap fully closed OR conviction < 0.5 OR SFM gradient reverses"

    conviction_interaction: >
      "Alpha Capture is ORTHOGONAL to conviction.
       Conviction measures 'is the thesis correct?'
       Alpha capture measures 'how much alpha is left?'"


# ─── Update Log (Append-only, never deleted) ────────────────────────
<!-- Three-layer structure: narrative / conviction / position -->
update_log:
  narrative_log: []
  conviction_log: []
  position_log: []
