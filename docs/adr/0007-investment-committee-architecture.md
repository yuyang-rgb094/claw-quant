# ADR-0007: Investment Committee Architecture (Ensemble Debate, NOT MoE)

**Status:** Accepted

**Date:** 2026-07-03

## Context

The existing Serenity Chokepoint skill is a stateless research workflow. In practice, the deployed agent exhibits "anchor drift" — it rebuilds its analytical framework from scratch each session, causing short-term noise (e.g., a single-day -5.79% drop) to override long-term logic (e.g., memory super-cycle to 2027) established in prior sessions.

Root cause analysis identified three failure modes:

1. **Retrieval Bias:** Search engines rank by "latest + hottest," not "most relevant to long-term logic." Short-term noise dominates the input information mix.

2. **Anchor Drift in Zero-Shot:** Each session, the LLM reconstructs its analytical framework from the current context. Without persistent framework constraint, the framework slides toward whatever the latest input emphasizes.

3. **Missing Time-Weighting:** LLMs process "memory super-cycle to 2027" and "today -5.79%" as equivalent text tokens. There is no built-in temporal decay function that weights long-term anchors above short-term fluctuations.

The user proposed a "MoE architecture" with multiple specialized agents. However, MoE implies sparse activation (routing inputs to a subset of experts), while investment decisions almost always require all dimensions simultaneously (industry, macro, risk, quant, strategy).

## Decision

Add an **Investment Committee** layer above the existing skill. The skill serves as an industry research analyst feeding the committee. The committee produces long-term investment opinions and short-term trading plans.

### Key Constraints

1. **Ensemble debate, NOT MoE.** Every committee member participates in every deliberation. Each provides their dimensional assessment. A final adjudicator synthesizes. No sparse routing.

2. **Committee members are methodology-driven, not persona-driven.** Each member has an `analytical_prior` (stable analytical bias) and a `framework` (structured analysis steps). Famous investor names appear only in `inspired_by` field, never in reasoning. Rationale: methodology is auditable and evolvable; persona is a black box.

3. **Three-layer memory structure:**
   - `theses/` — cross-ticker investment logic (the adjudication anchor)
   - `holdings/` — single-ticker position logic (references a thesis)
   - `world/` — external environment state (CBC Simulator maintains)

   Thesis files are the final anchor for adjudication: short-term signals can trigger position adjustment, never thesis overthrow. Only disconfirmation signals at the thesis level (e.g., memory prices turning down) can invalidate a thesis.

4. **Prompt harness + explicit memory protocol (Option C).** Multi-role debate is implemented via prompt (role rotation in a single LLM context). Memory read/write is code-enforced:
   - Analysis cannot start without reading framework files
   - Analysis cannot conclude without updating framework files
   - Tool protocol (parallel search, full-text retrieval) requires code-layer enforcement
   - Output verification (JSON schema, probability sum check) requires code-layer enforcement

5. **Time-weighted information tagging.** Every input is classified by:
   - Time horizon: short-term (1-3 days) / medium-term (1-4 quarters) / long-term (1-5 years)
   - Framework impact: none / minor / major / thesis-overturning

   This is the mechanism that prevents short-term noise from overriding long-term logic.

### Committee Composition (Methodology-Driven Roles)

| Role | Responsibility | Analytical Prior |
|------|---------------|-----------------|
| Industry Research Analyst | The existing Serenity Chokepoint skill. Chokepoint identification, evidence staging, alpha verification. | Bottleneck-first, statistics-second |
| Macro & Liquidity Analyst | Macro environment, rate cycle, liquidity conditions. Consumes CBC Simulator output. | Liquidity contraction pressures high-valuation assets |
| Risk Controller | Portfolio-level risk: correlation, tail risk, position constraints, stop-loss discipline. Pure mathematical tools, no subjective judgment. | Downside protection over upside capture |
| Quantitative Factor Researcher | Factor exposure analysis, crowding measurement, statistical evidence assessment. | Statistical significance before economic significance |
| Strategy & Trading Plan Architect | Translates committee conclusions into actionable trading plans: entry/exit levels, position sizing, catalyst timeline. | Execution discipline over conviction |
| Chief Investment Officer (Adjudicator) | Synthesizes all members' inputs. Makes final call on long-term opinion and short-term plan. | Long-term framework over short-term noise |

## Rationale

The "anchor drift" problem is fundamentally a memory problem, not an orchestration problem. Code-enforced memory protocol solves the root cause. Prompt-based multi-role debate provides structured adjudication without the overhead of code orchestration.

The existing skill's research methodology (chokepoint scoring, Fama-MacBeth regression, evidence stages) is preserved unchanged — the committee consumes its output, does not replace it. This follows the "minimal viable solution, reserve upgrade path" principle: the prompt harness can later be upgraded to code orchestration without changing the memory protocol.

## References

- Grilling session (2026-07-03): Full design rationale documented in session
- ADR-001 through ADR-006: Existing skill decisions, all preserved
- ADR-008: CBC Simulator design
