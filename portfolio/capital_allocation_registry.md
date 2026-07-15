# Capital Allocation Registry — Cross-Thesis Capital State Tracker
<!-- Schema: ADR-017 §3 -->
<!-- This file does NOT make allocation decisions — it tracks state only. -->
<!-- When capital is released, it re-enters the framework as available_capital -->
<!-- and the framework re-runs normally (capital is fungible). -->
<!-- Last updated: 2026-07-14 -->

total_capital: 0                        # total investable capital (CNY)
fisher_max_aggregate_equity: 0.60       # Fisher layer current constraint (from fisher_state.md)

active_theses: []

available_capital: 0                    # released capital awaiting reallocation
aggregate_equity_exposure: 0.0         # fraction deployed to equity (≤ fisher_max)
aggregate_cash_exposure: 0.0           # fraction in cash (including defensive thesis)

# When available_capital > 0, the framework re-runs normally:
# Fisher provides environment → SFM provides factors →
# Graham forms/revises beliefs → Markowitz allocates.
# No special reallocation decision tree needed.
