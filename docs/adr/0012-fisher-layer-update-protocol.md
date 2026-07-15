# ADR-012: Fisher Layer Update Protocol — Three-Tier Structure

**Status:** Accepted

**Date:** 2026-07-07

## Context

The Fisher Layer (ADR-011) defines a four-layer schema for tracking the global monetary environment. However, the schema's fields have vastly different update frequencies and risk profiles:

- UST yield changes daily but doesn't change the framework
- A Securities Law revision happens rarely but fundamentally changes the framework
- Mixing these two update types causes either over-reaction (treating noise as structural change) or under-reaction (missing genuine regime shifts)

The update protocol must distinguish between **data refresh** (updating values within the existing framework) and **regime surveillance** (detecting whether the framework's assumptions still hold).

## Decision

Implement a three-tier update protocol:

### Tier 1: Data Refresh (High-Frequency, Automated)

Routine data updates that change field VALUES but never change the framework STRUCTURE.

| Data Item | Source | Frequency | Field Updated |
|-----------|--------|-----------|---------------|
| Fed balance sheet | H.4.1 | Weekly (Thursday) | `fed_balance_sheet` |
| CME FedWatch | Market | Daily | `fed_rate.market_implied_path` |
| Northbound flows | Stock Connect | Daily (close) | `cross_border_portfolio` |
| UST 10Y / VIX | Market data | Daily | `risk_discount` |
| M2 China | Wind/PBoC | Monthly | `fx_reserves.pboc_balance_sheet` |
| CPI / PCE | NBS / BLS | Monthly | P_trend |
| GDP | NBS / BEA | Quarterly | Y_trend |
| USD Index | Market data | Daily | transmission_channels |

**Processing:** Automated data pull, field update. Does NOT change `stock_vs_cash_baseline`.

**Baseline re-evaluation trigger:** Only when data refresh causes a DIRECTIONAL reversal of M_trend or P_trend (not just numerical change). Direction = expanding/contracting/stable.

### Tier 2: Event-Driven Re-evaluation (Medium-Frequency, Semi-Automated)

Significant events that may change the assessment of specific dimensions.

| Event Type | Trigger | Processing |
|------------|---------|------------|
| FOMC meeting | Every 6 weeks | Re-evaluate `fed_cycle_phase`, recalculate expectation_gap |
| CPI/PCE release | Monthly | Check if P_trend direction changed; if so, re-evaluate |
| Northbound anomaly | 5 consecutive days net outflow >¥10B | Trigger fast_check for structural capital flight |
| USD index anomaly | Single week change >3% | Check PBoC policy space impact |
| Data revision | Revision magnitude >0.5pp | Tag `[REVISION_IMPACT]`, re-evaluate if direction changes |

**Processing:** Re-evaluate affected fields. MAY change `stock_vs_cash_baseline`, but only for dimensions directly impacted by the event.

### Tier 3: Regime Surveillance (Low-Frequency, Human Judgment)

Detection of whether the framework's ASSUMPTIONS still hold. This is where structural change is monitored.

Seven monitoring points:

#### 3.1 Capital Account Openness (World Structure Change)
**What:** Changes in cross-border investment channels — Stock Connect quotas, QFII reforms, Bond Connect expansion, wealth management connect.
**Why:** Changes the "capital account openness" parameter in Rey's dilemma framework. Increased openness → Fed spillover amplifies; decreased openness → PBoC independence increases.
**Frequency:** Quarterly review + event-triggered
**Trigger:** Any capital account policy change

#### 3.2 PBoC Transmission Pathway (Liquidity Framework Change)
**What:** New monetary policy tools, interest rate transmission reform, bank equity investment limit changes, structural monetary tools expanding to equity channels.
**Why:** Directly determines `equity_transmission_efficiency`. If a new tool pushes equity transmission from <10% to >20%, the entire weight structure recalibrates.
**Frequency:** Quarterly review + event-triggered
**Key metric:** `equity_transmission_efficiency` direction of change (low → medium → high)

#### 3.3 Contribution Weight Drift (Marginal Contribution Tracking)
**What:** Periodic regression validation of the three transmission channels' contribution percentages.
**Why:** The quantified contributions (northbound 35-40%, FX reserves 8-10%, risk discount 12-15%) are empirically derived from historical data. Market structure changes cause coefficient drift.
**Frequency:** Quarterly
**Method:** Rolling 2-year window regression. Chow structural break test or CUSUM test.
**Trigger:** Any channel's contribution changes >5 percentage points

#### 3.4 Regulatory Framework Definition (CSRC Functional Positioning)
**What:** Changes in how the government defines the stock market's function and status.
**Two levels of change:**
- **Legislative level** (Securities Law revision, Commercial Bank Law revision): Immediately triggers regime re-evaluation. Hard constraint change.
- **Regulatory level** (IPO rhythm, delisting enforcement, trading system reform): Recorded as structural change, incorporated in next quarterly regression validation.
- **Verbal level** (leadership speeches, window guidance): Recorded as `[SIGNAL]`, no update triggered.

**Why:** The regulatory framework is exogenous to monetary policy but directly affects:
- IPO drainage (liquidity extraction)
- Delisting regime (supply-side structure)
- Trading microstructure (T+0 reform, limit rules)
- Long-term capital introduction (pension, insurance allocation rules)

**Frequency:** Continuous monitoring + event-triggered

#### 3.5 Geopolitical Risk Premium (Orthogonal Factor)
**What:** Taiwan Strait tension, US-China tech war escalation, financial sanctions (SWIFT exclusion threats).
**Why:** These factors are orthogonal to monetary policy but affect the SAME transmission channels — specifically the risk discount channel's ERP component. A geopolitical event can spike ERP independent of Fed policy.
**Frequency:** Continuous monitoring
**Trigger:** Risk level jump (e.g., from "elevated" to "crisis")

#### 3.6 FOMC Communication Paradigm (Connects to ADR-008)
**What:** Fed chair succession, forward guidance mode changes, dot plot signal value changes.
**Why:** Changes the expectation gap calculation framework itself. If a new chair abandons forward guidance, the entire expectation_gap.md methodology changes.
**Frequency:** Event-driven (chair succession, statement language pattern break)
**Trigger:** Governance Paradigm Master Switch file change (ADR-008)

#### 3.7 Trade Settlement Currency Structure (RMB Internationalization)
**What:** RMB settlement in oil trade, bilateral currency swaps, RMB clearing bank expansion.
**Why:** Changes the Mundell-Fleming framework's currency regime parameter. If RMB internationalization progresses significantly, PBoC gains policy independence from Fed — partially exiting Rey's dilemma.
**Frequency:** Semi-annual review
**Trigger:** Significant change in RMB settlement share in major commodity trade

### Tier 3 Processing Protocol — Bidirectional Feynman Method

When a regime surveillance trigger fires, processing follows a three-round bidirectional Feynman protocol (AI-first, not human-first). This replaces the original "human assessment required" step.

**Rationale:** Pure human judgment has information breadth and timeliness blind spots. AI can aggregate more sources, scan broader context, and produce initial analysis faster. Human's value is in domain judgment and contextual correction, not in data gathering. The bidirectional process leverages both strengths.

**Round 1: AI Initial Analysis**
- Agent detects structural change signal (via intelligence retrieval system, ADR-013)
- AI aggregates relevant information sources: official announcement + market reaction + academic literature + historical precedents
- AI outputs structured analysis:
  - Change description (what happened, when, source)
  - Framework impact judgment (which assumptions are affected)
  - Affected Fisher Layer fields (specific fields needing update)
  - Recommended action (weight recalculation / regression revalidation / baseline re-evaluation)
  - AI confidence level (self-assessed: high/medium/low)

**Round 2: Human Review**
- Human reads AI's Round 1 analysis
- Human confirms / corrects / supplements:
  - Confirms AI's factual accuracy
  - Corrects misinterpretations (especially: historical analogies, institutional details, political context)
  - Supplements with domain knowledge AI may lack
- Human outputs: `agree` / `disagree` / `partial_agree` + specific feedback

**Round 3: AI Re-examination**
- AI incorporates human feedback:
  - If `agree`: Execute AI's recommended action
  - If `disagree`: AI re-analyzes incorporating human corrections, produces revised assessment
  - If `partial_agree`: Execute agreed parts; tag disputed parts as `[DISPUTED]`, do not execute
- Final output: Framework impact assessment + downstream impact judgment
- All three rounds logged in `regime_surveillance_log`

**Critical design:** The three rounds are ALL logged, forming a complete reasoning chain. Even if the final judgment is wrong, the user can trace which round introduced the error.

### Tier 3 Log Structure

```yaml
regime_surveillance_log:
  - date: YYYY-MM-DD
    type: structural_change_detected
    monitor_point: capital_account_openness  # or pboc_transmission / contribution_drift / regulatory_framework / geopolitical / fomc_paradigm / trade_settlement
    detection:
      event: "Description of detected change"
      source: "Authoritative source"
      level: legislative  # legislative / regulatory / verbal

    round_1_ai_analysis:
      author: agent
      change_description: "What happened"
      framework_impact:
        assumptions_affected: ["List of framework assumptions impacted"]
        requires_weight_recalculation: true/false
        requires_regression_revalidation: true/false
      affected_fields: ["fisher_state.md fields needing update"]
      recommended_action: "Specific updates"
      ai_confidence: medium  # high / medium / low

    round_2_human_review:
      author: human
      verdict: partial_agree  # agree / disagree / partial_agree
      corrections: "What AI got wrong"
      supplements: "What AI missed"
      key_insight: "Human's domain-specific judgment"

    round_3_ai_revised:
      author: agent
      incorporated_feedback: true
      final_framework_impact:
        assumptions_changed: ["Final list"]
        stock_vs_cash_baseline_changed: false
      action_executed: "What was actually done"
      disputed_items: ["Items tagged [DISPUTED], not executed"]
      downstream_impact: "Impact on thesis files and holdings"
```

## Data Revision Risk Handling

GDP, CPI, and employment data are subject to revision. Protocol:

1. **7-day check:** After each major data release, check for significant revision within 7 days (magnitude >0.5pp)
2. **Directional impact check:** If revision changes the direction of `purchasing_power_trend` or `stock_vs_cash_baseline`, tag as `[REVISION_IMPACT]`
3. **Downstream cascade:** `[REVISION_IMPACT]` tags trigger re-evaluation of affected thesis files

## What This Does NOT Do

- Does NOT attempt to predict regime changes — only to detect them after they occur
- Does NOT automate Tier 3 (regime surveillance) — human judgment is required because structural change detection involves interpreting whether a change is noise or signal
- Does NOT change `stock_vs_cash_baseline` on routine data refresh — only directional reversals or structural changes trigger baseline re-evaluation

## Rationale

The three-tier structure prevents two failure modes:

1. **Over-reaction:** Treating daily data noise as structural change (would cause constant baseline flipping — the exact "anchor drift" problem this framework is designed to prevent)
2. **Under-reaction:** Missing genuine regime shifts because they're buried in routine data updates (would cause the framework to operate on stale assumptions — the "agar drift" problem at the framework level)

Tier 1 handles volume (high frequency, low risk). Tier 2 handles events (medium frequency, medium risk). Tier 3 handles structural change (low frequency, high risk). The separation ensures that each type of update gets the appropriate level of scrutiny.

## References

- ADR-011: Fisher Layer Mundell-Fleming framework (this ADR defines its update protocol)
- ADR-008: CBC Simulator Governance Paradigm (Tier 3.6 connects to this)
- ADR-004: Fact-Opinion-Inference Tagging (legislative/regulatory/verbal levels map to fact/signal tagging)
- Grilling session (2026-07-07): Five monitoring points proposed by domain expert, supplemented with geopolitical, FOMC paradigm, trade settlement, and regression validation
