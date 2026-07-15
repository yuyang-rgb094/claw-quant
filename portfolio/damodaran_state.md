# Damodaran State — Cross-Section Supervisor
<!-- Schema: ADR-018 -->
<!-- Adjudicator, NOT Allocator — monitors and flags, does not decide. -->
<!-- Last updated: 2026-07-14 -->

# ─── Belief Pool (ADR-018 §3a) ──────────────────────────────────────
belief_pool:
  total_active_theses: 0
  max_recommended: 5

  theses_summary: []

  belief_diversity:
    by_type: {}
    by_duration: {}
    by_factor_exposure: {}


# ─── Holdings Pool (ADR-018 §3b) ───────────────────────────────────
holdings_pool:
  total_unique_tickers: 0
  max_recommended: 15

  ticker_overlap: []

  aggregate_exposure:
    total_equity: 0.0
    total_cash: 0.0
    total_by_sector: {}


# ─── Constraint Suite (ADR-018 §3c) — 7 Constraints ──────────────────
constraints:
  - name: max_active_theses
    limit: 5
    rationale: "Beyond 5 active theses, the portfolio becomes an index"
    current: 0
    status: within_limit

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
forward_valuation:
  per_thesis_forward: []
  aggregate_forward_return: 0.0
  index_threshold: 0.05
