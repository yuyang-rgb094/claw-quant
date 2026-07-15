# Capital Allocation Registry Template — Cross-Thesis Capital State Tracker
<!-- Schema: ADR-017 §3 -->
<!-- This file does NOT make allocation decisions — it tracks state only. -->
<!-- When capital is released, it re-enters the framework as available_capital -->
<!-- and the framework re-runs normally (capital is fungible). -->
<!-- Copy to portfolio/capital_allocation_registry.md -->

total_capital: 0                        # total investable capital (CNY)
fisher_max_aggregate_equity: 0.80       # Fisher layer hard constraint (ADR-011)

active_theses:
  - thesis: "theses/[thesis_name].md"
    allocation: 0                      # CNY allocated to this thesis
    status: active                      # active / closed
    alpha_captured_ratio: null          # null for defensive theses
    capital_released: 0                # CNY released via profit-taking

available_capital: 0                    # released capital awaiting reallocation
aggregate_equity_exposure: 0.0         # fraction deployed to equity (≤ fisher_max)
aggregate_cash_exposure: 0.0           # fraction in cash (including defensive thesis)

# When available_capital > 0, the framework re-runs normally:
# Fisher provides environment → SFM provides factors →
# Graham forms/revises beliefs → Markowitz allocates.
# No special reallocation decision tree needed.
