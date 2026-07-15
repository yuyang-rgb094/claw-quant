# ADR-009: Holding File Schema — Six First Principles

**Status:** Accepted

**Date:** 2026-07-03

## Context

The investment committee (ADR-007) requires a persistent holding file to prevent anchor drift. Before defining specific fields, the schema's meta-design must be grounded in explicit financial engineering and economic theory. Each field must answer: **why does this need to exist? What failure mode does it prevent?**

Six independent first-principles were identified during the grilling session. Each principle maps to a group of fields. Together they define the holding file's complete schema.

## The Six Principles

### Principle 1: Belief-Action Separation (信念-行动分离)

**Theory:** Savage (1954) expected utility theory; Kahneman-Tversky prospect theory.

**Problem:** Investors conflate "what I believe" (probability judgment) with "what I should do" (optimal action given that belief). The most common error is jumping from "I believe this company is good" to "I should hold a full position" without considering position sizing, risk, and alternatives. Conversely, panic selling is an action change without belief change.

**Fields:** `entry_logic` (belief record) + `position_state` (action record). The adjudicator can check: is the action consistent with the belief? If belief hasn't changed but action has (panic selling), or belief has changed but action hasn't (lazy), both require explanation.

### Principle 2: Falsificationism (证伪主义)

**Theory:** Popper falsifiability; Munger/Byron Wien inversion thinking.

**Problem:** "I bought Lanqi because of DDR5 penetration + memory super-cycle" is NOT a falsifiable proposition — you can always find supporting evidence. A thesis is only manageable if it can be proven wrong.

**Fields:** `key_assumptions` (what must be true for the thesis to hold) + `disconfirmation_signals` (specific, observable, time-anchored events that would prove the thesis wrong). These must be defined in a calm state and cannot be redefined in panic. Maps to existing `Disconfirmation Signals` in SKILL.md Step 9 — but persisted, not ephemeral.

### Principle 3: Bayesian Updating (贝叶斯更新)

**Theory:** Bayesian inference; Grossman-Stiglitz information paradox.

**Problem:** Beliefs are binary in practice ("bullish/bearish"), causing violent flips. A -5.79% drop shouldn't flip "bullish" to "bearish" — it should marginally update the probability. Binary belief systems cause exactly the "yesterday bullish, today bearish" anchor drift that motivated this entire redesign.

**Fields:** `conviction_level` (continuous value, 0-1 or 0-100, NOT bullish/bearish) + `update_log` (each update records: new information, prior conviction, posterior conviction, update reasoning). Update thresholds: conviction drops below X → reduce position; below Y → exit.

### Principle 4: Time Inconsistency Constraint (时间不一致性约束)

**Theory:** Strotz (1955) time inconsistency; Thaler behavioral life-cycle hypothesis; Shefrin-Thaler mental accounting.

**Problem:** The optimal decision made in a calm state (yesterday: "memory super-cycle to 2027, hold") is NOT the optimal decision in a panicked state (today: "dropped 5.79%, sell"). The change is NOT in information or logic — it's in the decision-maker's emotional state. This is the fundamental reason the holding file exists.

**Fields:** `precommitment_rules` (decisions committed in a calm state). **Implementation detailed in ADR-010** (Belief-Anchored Risk System), which replaces the initial dual-layer price/conviction trigger design with a three-layer system: risk budget (tied to conviction) + market momentum state regulator + tail-risk circuit breaker. Key design: trigger conditions are defined WHEN CALM and executed WHEN EMOTIONAL. The holding file is not "what should I do now" — it is "what did I promise myself I would do." **See ADR-010 for the complete risk management framework.**

### Principle 5: Information Decay Management (信息衰减管理)

**Theory:** Information half-life concept; multi-timeframe analysis.

**Problem:** Different information types have different decay rates. Macro cycle information (1-3 year half-life) and market sentiment (1-5 day half-life) are processed as equivalent text tokens by LLMs. Without explicit decay tagging, short-term noise can override long-term anchors.

**Fields:** Each information item in the update_log is tagged with `time_horizon` (short 1-3d / medium 1-4Q / long 1-5y) and `decay_status` (fresh / aging / expired). Expired information must be re-verified before being used as decision input.

### Principle 6: Second-Order Consensus & Expectation Gap (二阶共识与预期差)

**Theory:** Keynes (1936) beauty contest; Grossman-Stiglitz (1980) information paradox; Soros (1987) reflexivity.

**Problem:** The first five principles all operate at the first-order level ("what is the fundamental truth?"). But alpha does NOT come from being right — it comes from being right BEFORE the market corrects. A holding file that only records "what I believe" without "what the market believes" cannot identify where alpha comes from. This was identified during the grilling session as a genuine design gap, not just a philosophical concern.

**Fields:** `market_consensus` (what the market currently prices in) + `expectation_gap` (where my view diverges, classified as convergent/divergent/stale) + `consensus_catalyst` (specific event that would force market reprice). Without a catalyst, the gap may persist indefinitely — being right but too early is indistinguishable from being wrong.

## Belief Hierarchy (Cross-Principle)

The six principles operate across three belief layers, which map to the memory structure:

| Layer | Content | Update Frequency | Memory Location | Falsification Standard |
|-------|---------|-------------------|------------------|----------------------|
| Paradigm | "AI is a ten-x industrial revolution" | Yearly | `theses/` | Total factor productivity持续提升 |
| Industry | "Memory super-cycle peaks 2027" | Quarterly | `theses/` + `holdings/entry_logic` | Penetration rates, orders, shipments |
| Trade | "Buy at this price, this quantity" | Daily/Weekly | `holdings/position_state` | Price triggers, earnings misses |

**Critical rule:** Paradigm-level belief must NOT justify trade-level errors. Trade-level volatility must NOT negate paradigm-level judgment. The memory structure enforces this: thesis files (paradigm) are the adjudication anchor; holding files (trade) are the execution layer.

## Reflexive Feedback Loop Guard

To prevent circular reasoning ("I believe X → price went up → X is confirmed"), the holding file must distinguish:
- **Fundamentally-validated signals:** External industry data (penetration rates, order flows, supply chain cross-validation) that independently confirm or deny the belief
- **Price-validated signals:** Price movements that may or may not reflect fundamental changes

Only fundamentally-validated signals can update `conviction_level`. Price-validated signals can trigger `precommitment_rules` (stop-loss, rebalance) but cannot change the belief itself.

## Rationale

Each field in the holding file is derived from a specific financial engineering principle, not from intuition or convention. This ensures:
1. **No redundant fields:** Every field prevents a specific failure mode
2. **Auditable:** Each update can be traced back to which principle drove it
3. **Theory-grounded:** The schema is defensible to investment professionals and can be stress-tested against known cognitive biases

The six principles are independent (no principle subsumes another) and collectively exhaustive (every known investment failure mode in the user's experience is covered by at least one principle).

## References

- Savage, L.J. (1954). The Foundations of Statistics.
- Popper, K. (1934). The Logic of Scientific Discovery.
- Strotz, R.H. (1955). Myopia and Inconsistency in Dynamic Utility Maximization.
- Kahneman, D. & Tversky, A. (1979). Prospect Theory.
- Keynes, J.M. (1936). The General Theory of Employment, Interest and Money.
- Grossman, S. & Stiglitz, J. (1980). On the Impossibility of Informationally Efficient Markets.
- Soros, G. (1987). The Alchemy of Finance.
- Grilling session (2026-07-03): Six principles identified and debated
