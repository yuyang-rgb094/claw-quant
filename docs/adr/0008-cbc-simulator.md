# ADR-0008: Central Bank Committee Simulator (CBC Simulator)

**Status:** Accepted

**Date:** 2026-07-03

## Context

The investment committee (ADR-007) requires macro-environmental input that the existing Serenity Chokepoint skill cannot provide. The skill only sees micro-industry dynamics (chokepoint, evidence stage, supply chain) — it is blind to macro-liquidity environment, central bank policy trajectory, and expectation gaps.

Empirical testing (DeepSeek dialogue, 2026-06) demonstrated that LLM-based policy simulation can effectively:
1. Estimate FOMC strategy space probability distributions (90% baseline / 10% hawkish / 1.5% black swan)
2. Identify expectation gaps (priced_in vs not_priced vs directional_bias)
3. Simulate internal committee dynamics (Warsh's dovish lean vs hawkish committee)

However, the term "Institution Simulator" was proposed initially, which is ambiguous in financial contexts (where "institution" typically means financial institutions like banks and asset managers, not regulatory bodies).

Additional concern: naive simulation of committee decisions by aggregating individual member attributes (hawkish/dovish labels → majority vote) triggers **aggregation fallacy** — a systematic error documented in four failure modes (judgment aggregation paradox, process omission bias, label granularity distortion, common belief assumption bias).

A further insight emerged during design: a central bank chair's influence has **two orthogonal dimensions** — Policy Stance (rate level preference) and Governance Paradigm (how decisions are made/communicated). The latter is often more impactful: a reformist chair abandoning forward guidance and the dot plot reshapes market pricing more than a simple hawkish/dovish pivot.

## Decision

Add a **Central Bank Committee Simulator (CBC Simulator)** as an independent agent feeding the investment committee.

### Naming

"Central Bank Committee Simulator" — explicitly names the simulation target as the decision committee, not a commercial institution. Abbreviation: CBC Simulator.

### Scope

- **In scope:** Macro environment + committee strategy space + expectation gap assessment
- **Out of scope:** Transmission chain (policy → rate → capital flow → asset), individual stock impact — these are the investment committee's job

### Output Format

1. **Strategy Space:** Probability distribution over possible policy outcomes (e.g., 90% hold / 10% hawkish shift / 1.5% black swan)
2. **Expectation Gap:** Classification of market pricing vs simulated outcomes:
   - `priced_in` — market already expects this outcome
   - `not_priced` — market has not accounted for this
   - `directional_bias` — market expects the opposite
3. **Confidence Level:** Assessment of simulation confidence given data quality and regime stability

### Key Design Decisions

#### 1. Aggregation Fallacy as Design Constraint

Pure member-attribute aggregation (hawkish/dovish labels → majority vote) produces systematic error. Mitigated by:
- **Institutional rules layer** — FOMC procedure, power structure, governance paradigm as explicit constraints
- **Continuous belief vectors** — replace 3-class labels with multi-dimensional continuous values (Phase 1: 2 dimensions; Phase 2: 4+)
- **Multi-round deliberation** (Phase 2+) — simulate the debate process, not just the vote

Academic basis:
- MiniFed (arXiv:2410.18012): Five-stage FOMC simulation, debate > vote aggregation
- FedSight AI (arXiv:2512.15728): Institutional reasoning priority, 93.75% accuracy
- FOMC In Silico (Kazinnik & Sinclair, 2025): Dual-track (LLM + Monte Carlo), debate introduces ~5bp hawkish bias

#### 2. Two Orthogonal Dimensions

| Dimension | Definition | Warsh Example | Powell Example |
|-----------|-----------|---------------|----------------|
| **Policy Stance** | Preference for rate level (hawkish/dovish/neutral) | Hawkish, inflation-first | Neutral-dovish, balanced |
| **Governance Paradigm** | Institutional philosophy: how decisions are made, communicated, framed | Reformist: abandon forward guidance, weaken dot plot, expand discretion, return to ambiguity | Gradualist: strong forward guidance, clear dot plot, predictable path |

These are independent: a reformist chair can shift the governance paradigm without changing rate direction. This shift has larger impact on asset pricing than a rate pivot.

#### 3. Governance Paradigm Master Switch

A single file (`governance_paradigm.md`) stores the current chair's **observable institutional rules**:
- Communication patterns (e.g., "no explicit forward guidance")
- Decision protocols (e.g., "data-dependent, meeting-by-meeting")
- Tool usage norms (e.g., "chair does not submit personal dot plot")

Switching chairs requires only replacing this file — the entire simulation behavior shifts.

**Critical constraint:** This file contains only `[FACT]` (observable rules) and `[INFERENCE]` (motivation analysis, explicitly tagged). It NEVER contains untagged "constant undertone" — deep beliefs about macroeconomic theory (e.g., "MMT failed", "Phillips curve is masked") are interpretations, not observable behaviors. They belong in prompt context as `[INFERENCE]`, not in persistent state as ground truth.

#### 4. Chair-Specific Institutional Preference Fields

The chair's state file includes an `institutional_preference` block (not present for regular members):
- `forward_guidance_attitude`: -2 (abolish) to +2 (strengthen)
- `dot_plot_role`: -2 (cancel) to +2 (strengthen)
- `consensus_norm`: -2 (encourage dissent) to +2 (strong consensus)
- `discretion_vs_rules`: -2 (pure rules) to +2 (full discretion)

Updates require observable signals (e.g., FOMC statement language change, press conference behavior).

#### 5. Market Regime Tracking (Phase 2)

`market_regime.md` tracks whether the market is pricing based on forward guidance (commitment-driven) or data dependence (博弈-driven). This is a slow variable (changes over quarters) that defines the calculation framework for expectation gaps.

Distinct from `expectation_gap.md` (a fast variable, updated each meeting):
- `market_regime.md` = "what rule is the market using to price?"
- `expectation_gap.md` = "what is the gap between market pricing and simulated outcomes?"

#### 6. Phased Implementation

| Phase | Scope | Key Addition |
|-------|-------|-------------|
| **Phase 1 (MVP)** | governance_paradigm.md + simplified member states (2D continuous beliefs) + single-round deliberation + expectation gap (group + market layers) | Governance paradigm as master switch |
| **Phase 2** | Multi-round debate + individual expectation gap + market_regime.md | Deliberation process simulation |
| **Phase 3** | Triple aggregation cross-check (vote / debate / institutional correction) | Academic-grade accuracy |

### Memory Structure

```
world/
├── 1_institutional_rules/
│   ├── fomc_procedure.md        # Meeting procedure, voting rules
│   ├── power_structure.md       # Seat weights, key person influence
│   └── governance_paradigm.md   # Chair's institutional rules (master switch)
├── 2_member_states/
│   └── fomc_members.md         # Continuous belief vectors, not 3-class labels
├── 3_environment_states/
│   ├── macro_snapshot.md       # Objective data snapshot
│   └── expectation_gap.md      # Market vs simulation gap (fast variable)
└── 4_simulation_traces/         # (Phase 2+) Meeting simulation logs
    └── meeting_2026_06.md
```

## Rationale

The CBC Simulator addresses the committee's blind spot: the existing skill only sees micro-industry dynamics, not macro-liquidity environment. The DeepSeek dialogue proved that strategy-space estimation + expectation-gap identification is the correct output format — not precise rate prediction.

The phased approach follows the "minimal viable solution, reserve upgrade path" principle:
- Phase 1's single-round simulation already outperforms pure attribute aggregation (per FOMC In Silico: even single-round behavioral simulation captures ~5bp bias that rule-based voting misses)
- Multi-round debate (Phase 2) is a marginal improvement — MiniFed showed debate adds accuracy but with significantly higher token cost
- Triple aggregation (Phase 3) is academic-grade precision, only needed if Phase 1-2 prove insufficient for investment decisions

The aggregation fallacy mitigation is grounded in three peer-reviewed academic papers that validate the approach. The two-dimension split (Policy Stance vs Governance Paradigm) is a novel contribution beyond existing academic frameworks — none of the three papers model the chair's institutional reform power.

## References

- MiniFed: arXiv:2410.18012 — Five-stage FOMC simulation framework
- FedSight AI: arXiv:2512.15728 — Institutional reasoning priority, 93.75% accuracy
- FOMC In Silico: Kazinnik & Sinclair (2025) — Dual-track simulation, behavioral vs rational baseline
- DeepSeek FOMC dialogue (2026-06): Empirical proof of concept
- ADR-007: Investment Committee Architecture
