# fisher_state.md — Fisher Layer State (Mundell-Fleming / Rey Framework)
<!-- Schema: ADR-011 | Update Protocol: ADR-012 -->
<!-- Template — populate with real data from Wind/H.4.1/CME FedWatch/etc. -->
<!-- Last updated: 2026-07-14 -->

# ─── Layer 1: Global Financial Cycle (Fed-Driven) ──────────────────
global_financial_cycle:

  fed_balance_sheet:
    m_trend: stable                    # expanding / contracting / stable
    m_trend_direction: stable          # last directional reversal date
    weekly_change_b: -5.0             # B in billions (QT pace)
    notes: "Fed balance sheet stable; QT continues at measured pace"

  fed_rate:
    current_rate: 5.25                # upper bound of target range (%)
    market_implied_path:
      next_meeting: "2026-09-18"
      implied_cut_probability: 0.65
      implied_path: [5.25, 5.00, 4.75, 4.50]   # next 4 meetings upper bound
    v_influence: moderate             # high / moderate / low

  usd_purchasing_power:
    p_trend: stable                   # rising / falling / stable
    cpi_latest: 3.2                   # YoY %
    pce_latest: 2.8                   # YoY %
    fisher_equation_output: "real rates positive — purchasing power stable"


# ─── Layer 2: Three Transmission Channels (Independent) ─────────────
transmission_channels:

  cross_border_portfolio:
    signal_strength: moderate         # strong / moderate / weak
    northbound_flow_today: 0           # net CNY millions (Stock Connect)
    northbound_flow_5d_avg: 0
    marginal_contribution: 0.37       # 35-40% of marginal volatility
    status: normal                     # normal / anomaly / structural_break

  fx_reserves:
    signal_strength: weak             # slow, indirect
    pboc_balance_sheet:
      m2_latest: 300                  # Tn CNY
      m2_yoy: 0.072                   # 7.2%
    marginal_contribution: 0.09       # 8-10%
    status: normal

  risk_discount:
    signal_strength: moderate
    ust_10y: 4.25                     # percent
    vix: 15.3
    a_share_discount_rate_impact: -0.08   # -12% growth stocks per 100bp UST rise
    marginal_contribution: 0.13       # 12-15%
    status: normal


# ─── Layer 3: A-share Marginal Liquidity (Direct Price Determinant) ─
a_share_marginal_liquidity:

  composite_signal: neutral           # positive / negative / neutral
  composite_score: 0.0               # -1 to +1

  pboc_modifier:
    coordination_with_fed: diverging   # coordinating / diverging / neutral
    equity_transmission_efficiency: low # low / medium / high (<10% reaches equities)
    contribution: 0.22                  # 20-25% of marginal volatility

  endogenous_factors:
    retail_flow: neutral               # positive / negative / neutral
    margin_balance: stable             # expanding / stable / contracting
    ipo_drainage: moderate             # low / moderate / high

  tail_risk_tools:
    sfisf:
      market_impact: liquidity_backstop    # liquidity_backstop / trend_driver
      tail_risk_reduction: 0.60           # ~60% reduction in >3% drop days
      trend_impact: none                  # does not change medium-term direction


# ─── Layer 4: Composite Assessment (Final Output) ───────────────────
# Downstream: thesis files reference these via fisher_alignment (ADR-016)
composite_assessment:

  fed_cycle_phase: peak               # easing / tightening / peak / trough
  bull_market_conditions_met: false    # requires Fed easing + domestic coordination
  stock_vs_cash_baseline: neutral     # stocks_favored / cash_favored / neutral
  position_constraint:
    max_aggregate_equity: 0.60       # below 0.8 Fisher cap, adjusted for current phase
  confidence: 0.70                    # 0-1, signal consistency and data quality


# ─── Fisher Interface (ADR-016 Graham Interface Contract, ≤400 tokens) ─
# Compressed output for Graham Layer thesis fisher_alignment
fisher_interface:
  phase: "peak"                                # easing / tightening / peak / trough
  stock_vs_cash: "neutral"                    # stocks_favored / cash_favored / neutral
  key_signal_1: "Fed balance sheet stable, QT -5B/wk"  # ≤ 20 tokens, factual
  key_signal_2: "UST 10Y stable at 4.25%"     # ≤ 20 tokens, factual
  position_constraint: "max_equity: 0.60"       # ≤ 10 tokens
  confidence: 0.70                              # 0-1 scalar


# ─── Regime Surveillance Log (ADR-012 Tier 3) ───────────────────────
# Append-only log of structural change detections (bidirectional Feynman protocol)
regime_surveillance_log: []
