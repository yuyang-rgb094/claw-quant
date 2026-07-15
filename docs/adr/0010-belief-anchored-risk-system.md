# ADR-010: Belief-Anchored Risk System — Replacing Fixed Stop-Loss

**Status:** Accepted

**Date:** 2026-07-05

## Context

ADR-009 (Holding File Six Principles) specified `precommitment_rules` as the field implementing Principle 4 (Time Inconsistency Constraint). The initial design proposed a dual-layer trigger: price-based safety net (automatic) + conviction-based decision layer (requires debate).

During grilling, this design was challenged on a fundamental level:

**Mechanical price-based stop-loss is fundamentally incompatible with a belief-driven framework.** It substitutes "price moved against me" for "I was wrong" — using volatility as a proxy for logic failure. In high-elasticity thesis-driven positions, fixed-percentage stop-loss is negative-expectation: it fails to catch genuine thesis collapse while washing you out of 90% of normal pullbacks, creating a cycle of "cut and chase."

Additional constraint: A-share T+1 rules mean no intraday smoothing tools and overnight gap risk amplification, making conventional stop-loss misfire probability even higher.

## Decision

Replace fixed-percentage stop-loss with a **Belief-Anchored Risk System** — a three-layer framework where price NEVER directly triggers final trade decisions. Price movements only trigger belief re-verification.

### Core Principle

> Price never directly triggers trades. Price only triggers belief re-verification. The only exception is tail-risk circuit breaker (extreme moves implying information asymmetry).

This is the strictest possible interpretation of Principle 1 (Belief-Action Separation) from ADR-009. It ensures that every trade decision is traceable to a belief change, not a price movement.

### Layer 1: Risk Budget (Replaces Fixed Stop-Loss)

**Risk Budget** = maximum allowed floating loss for a single position, tied to conviction level:

| Conviction Level | Risk Budget (% of portfolio NAV) | Rationale |
|-----------------|-----------------------------------|-----------|
| High (>0.7) | 2% | Strong statistical evidence, tolerate larger drawdown |
| Medium (0.5-0.7) | 1% | Moderate evidence, moderate risk |
| Low (0.3-0.5) | 0.3% | Weak evidence, minimal risk exposure |

When floating loss reaches the risk budget threshold, it does NOT trigger a sale. It triggers **belief re-verification**.

This is Kelly-criterion logic: conviction (derived from Evidence Level + IR + GMM) determines how much risk to assume. Higher conviction = larger risk budget = more room for normal volatility before forcing re-assessment.

### Layer 2: Market Momentum State Regulator

Risk budget is multiplied by a state-dependent coefficient, using two objective price momentum indicators as market consensus proxy:

| Market State | Definition | Multiplier | Core Rule |
|-------------|-----------|------------|-----------|
| Bull | 250-day momentum > 0 AND close > 60-day MA | ×1.5 | Drawdown triggers re-verification only; if belief unchanged, may evaluate adding |
| Sideways | Neither bull nor bear | ×1.0 | Baseline risk budget; drawdown triggers re-verification |
| Bear | 250-day momentum < 0 AND close < 60-day MA | ×0.5 | Temporary risk reduction (reversible) before re-verification |

**Rationale:** Market momentum is a second-order consensus signal (aggregate market pricing), NOT a first-order individual stock price. Using it as a risk environment variable is consistent with Principle 6 (Second-Order Consensus). In bull markets, most volatility is noise; in bear markets, most volatility is trend continuation.

**Bear-market temporary reduction:** In bear state, when risk budget is breached, position is temporarily reduced to 50% BEFORE re-verification completes. This is REVERSIBLE — if subsequent re-verification confirms belief unchanged, the reduction is reversed when price stabilizes.

**Design note:** This is the ONLY place where price triggers an action before belief update. It is explicitly acknowledged as a pragmatic exception, not a violation of the core principle. Market state itself is information about the risk environment — bear-market volatility carries higher persistence risk, justifying faster capital protection. The reduction is framed as temporary risk management, not a final sell decision.

### Layer 3: Tail Risk Circuit Breaker

The ONLY unconditional hard trigger in the system. Fires on extreme moves implying information asymmetry or systemic liquidity crisis:

| Condition | Threshold | A-share Adjustment |
|-----------|-----------|-------------------|
| Single-day extreme drop | Main board: ≥10% (limit-down); STAR/ChiNext: ≥15% | Main board can't exceed 10% due to limit rules |
| Consecutive limit-down | ≥2 days | Signals liquidity exhaustion; position marked as illiquid risk |
| 5-day cumulative drop | ≥30% | Captures multi-day cascading decline |

**Trigger action:** Immediate reduction to 30% of position, followed by emergency re-verification.

**Rationale:** This level of abnormal decline most likely means undisclosed negative information outside our information set, or systemic liquidity crisis. Survival-first principle: reduce exposure first, verify logic second. Normal 10-20% drawdowns never reach this threshold, preventing washout during routine volatility.

### Belief Re-Verification Protocol

When risk budget is breached (Layers 1-2) or circuit breaker fires (Layer 3), re-verification follows a two-tier protocol:

**Tier 1: Fast Check (5 minutes, immediate)**
- Scan for public fundamental negatives in last 5 trading days (earnings, announcements, industry news)
- Check disconfirmation signals from holding file — have any been triggered?
- Check cross-validation signals — any upstream/downstream anomalies?
- Output: `clear` / `suspicious` / `confirmed_break`

**Tier 2: Full Check (30 minutes, triggered by suspicious fast check)**
- Re-run complete Serenity Chokepoint Skill analysis
- Update Evidence Level, IR, GMM
- Recompute conviction_level

**Execution rules:**
- Fast Check `clear`: Hold position, no Full Check needed. In bull market, evaluate adding within risk budget.
- Fast Check `suspicious`: Run Full Check while maintaining current position (or temporary reduction in bear market).
- Fast Check `confirmed_break`: Immediately reduce per conviction rules. Do not wait for Full Check.

**Design rationale:** Fast Check eliminates 90% of normal pullback scenarios — only genuine fundamental concerns require the full regression analysis. This controls the latency cost of re-verification.

### Complete Daily Execution Logic

```
Position monitoring (executed after market close, daily):

Step 1: Check tail circuit breaker
  → Triggered: Reduce to 30% immediately, launch emergency re-verification
  → Not triggered: Continue

Step 2: Check risk budget breach
  → Not breached: Continue holding
  → Breached:
     a. Determine market state (bull/sideways/bear)
     b. Bull/Sideways: Launch Fast Check
        - clear: Hold, evaluate adding (bull only)
        - suspicious: Launch Full Check, maintain position
        - confirmed_break: Reduce per conviction rules
     c. Bear: Temporary reduction to 50% (reversible), then Fast Check
        - clear: Reduction reversible, restore when price stabilizes
        - suspicious: Launch Full Check at 50% position
        - confirmed_break: Further reduce per conviction rules

Step 3: Check belief update (independent of price, triggered by new information)
  → conviction drop < 0.1: No action
  → conviction drop 0.1-0.2: Flag for next committee meeting
  → conviction drop ≥ 0.2: Reduce per conviction rules
  → conviction < 0.3: Exit
```

## Compatibility with Six Principles (ADR-009)

| Principle | Compatibility |
|-----------|--------------|
| 1. Belief-Action Separation | Strengthened: price never drives final trade decision; only belief changes do |
| 2. Falsificationism | Each re-verification checks disconfirmation signals and key assumptions |
| 3. Bayesian Updating | Large drawdowns force belief update via re-verification, not binary flip |
| 4. Time Inconsistency | All rules pre-committed in calm state; panic state can only trigger verification, not redefine rules |
| 5. Information Decay | Market momentum state auto-updates as short-term information aggregates |
| 6. Second-Order Consensus | Market momentum IS market consensus quantified; when market moves against belief, expectation gap widens — holding through volatility is earning the gap convergence |

## What This Replaces

- ADR-009's `precommitment_rules` field (dual-layer price/conviction trigger) is superseded by this three-layer system
- The `precommitment_rules` field in the holding file schema now stores: risk_budget, market_state_regulator config, and circuit_breaker thresholds (all pre-committed in calm state)

## Rationale

Traditional stop-loss on thesis-driven positions is negative-expectation: it cuts winners during normal pullbacks while failing to catch genuine thesis collapse. The Belief-Anchored Risk System inverts the logic — price movement becomes a trigger for verification, not a trigger for transaction.

This is the strictest possible implementation of Principle 1 (Belief-Action Separation). It requires accepting that in rare tail-risk scenarios, the system may hold through larger drawdowns than a fixed stop-loss would allow — but this is the correct trade-off for thesis-driven investing, where the cost of being washed out of a correct thesis far exceeds the cost of holding through a wrong one.

The bear-market temporary reduction is the system's one pragmatic compromise: it acknowledges that market state carries information about risk environment, and that bear-market volatility has higher persistence risk. By making the reduction reversible, it preserves the principle that final trade decisions are always belief-driven.

## References

- ADR-009: Holding File Six Principles (this ADR supersedes the `precommitment_rules` design)
- Kelly, J.L. (1956). A New Interpretation of Information Rate. (Risk budget logic)
- Grilling session (2026-07-05): Three-layer framework proposed and stress-tested
