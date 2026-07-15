# Damodaran State Template — Cross-Section Supervisor
<!-- Schema: ADR-018 -->
<!-- Adjudicator, NOT Allocator — monitors and flags, does not decide. -->
<!-- Copy to portfolio/damodaran_state.md -->

# ─── Belief Pool (ADR-018 §3a) ──────────────────────────────────────
belief_pool:
  total_active_theses: 0
  max_recommended: 5                    # beyond this → "you're an index fund"

  theses_summary: []
    # - thesis: "theses/[name].md"
    #   conviction: 0.0
    #   alpha_captured: null
    #   belief_type: growth             # growth / value / defensive
    #   duration_bucket: long          # short / medium / long / null
    #   status: active

  belief_diversity:
    by_type: {}
    by_duration: {}
    by_factor_exposure: {}
    # If any single factor > 0.6 → flag: over-concentrated


# ─── Holdings Pool (ADR-018 §3b) ───────────────────────────────────
holdings_pool:
  total_unique_tickers: 0
  max_recommended: 15                   # beyond this → complexity without edge

  ticker_overlap: []
    # - ticker: "[TICKER.SH]"
    #   theses: ["thesis_a", "thesis_b"]
    #   total_weight: 0.0
    #   max_single_ticker: 0.15
    #   risk_budget_combined: 0         # weighted average, NOT additive

  aggregate_exposure:
    total_equity: 0.0                   # within Fisher cap
    total_cash: 0.0
    total_by_sector: {}
    # If any sector > 0.50 → flag: sector concentration risk


# ─── Constraint Suite (ADR-018 §3c) — 7 Constraints ──────────────────
constraints:
  - name: max_active_theses
    limit: 5
    rationale: "Beyond 5 active theses, the portfolio becomes an index"
    current: 0
    status: within_limit                # within_limit / at_limit / breached

  - name: max_unique_tickers
    limit: 15
    rationale: "Too many tickers = complexity without diversification benefit"
    current: 0
    status: within_limit

  - name: max_single_thesis_weight
    limit: 0.40
    rationale: "No single thesis > 40% of total capital"
    current: 0.0
    status: within_limit

  - name: max_single_ticker_weight
    limit: 0.15
    rationale: "No single ticker > 15% of total capital across all theses"
    current: 0.0
    status: within_limit

  - name: max_single_duration_bucket
    limit: 0.60
    rationale: "No single duration bucket > 60% of equity exposure"
    current: 0.0
    status: within_limit

  - name: max_single_sector
    limit: 0.50
    rationale: "No single sector > 50% of total capital"
    current: 0.0
    status: within_limit

  - name: fisher_max_aggregate_equity
    limit: 0.80
    rationale: "Fisher layer hard constraint — macro environment ceiling"
    current: 0.0
    status: within_limit


# ─── Forward-Looking Aggregate Valuation (ADR-018 §3d) ──────────────
# Damodaran's "look forward" — value by what it will earn, not what it has earned
# If forward return < 5% vs market value → flag as "index化"
forward_valuation:
  per_thesis_forward: []
    # - thesis: "theses/[name].md"
    #   current_market_value: 0
    #   forward_intrinsic_value: 0
    #   forward_return: 0.0
  aggregate_forward_return: 0.0
  index_threshold: 0.05                 # < 5% → flag "指数化"
