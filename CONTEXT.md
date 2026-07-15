# CONTEXT.md — Serenity Chokepoint Investing Framework (Enhanced)

## Project Overview

An enhanced research skill for AI infrastructure supply-chain chokepoint investing,
deployed on OpenClaw / Hermes-compatible agent platforms.

The core thesis: **find the bottleneck first, find the listed exposure second,
verify through evidence third, validate with statistics fourth, size by alpha significance fifth.**

This is NOT a buy/sell recommendation engine. It is a structured research workflow
that helps an agent:
1. Identify whether a company sits inside a real supply-chain bottleneck
2. Generate a testable hypothesis about abnormal alpha
3. Verify the hypothesis with statistical methods (Fama-MacBeth regression, Information Ratio)
4. Size positions based on statistical evidence

---

## Glossary

### Domain Terms

| Term | Definition |
|------|-----------|
| **Chokepoint** | A node in the AI industrial supply chain where demand is structurally growing, supply is constrained, capacity expansion is slow, and substitute technologies are limited. The node exhibits pricing power and affects system-level delivery. |
| **Supertrend** | A major long-term demand driver for AI infrastructure (e.g., AI compute expansion, memory bandwidth demand, data center power shortage, optical interconnect adoption). |
| **Supply-Chain Layer** | A position in the AI value chain defined by process node and value-add stage, NOT by material type. Examples: compute layer, memory layer, packaging layer, optical module layer, laser layer, materials layer (substrate vs. epitaxy), silicon photonics layer, equipment layer, power layer, cooling layer, data center layer, robotics layer. |
| **First-Order Beneficiary** | A company whose core product is directly consumed by the end-demand driver (e.g., NVIDIA for AI compute). |
| **Second-Order Beneficiary** | A company supplying critical components to first-order beneficiaries (e.g., HBM suppliers to NVIDIA). |
| **Third-Order Node** | A company supplying materials, equipment, or sub-components to second-order beneficiaries. Often the most underappreciated chokepoint opportunities. |
| **Evidence Stage** | A milestone in the customer validation timeline: Concept → Sample Submission → Pilot Order → Mass Production Ramp → Primary/Exclusive Supplier. Each stage has distinct factor exposure implications. |
| **Evidence Level** | The current validation strength of the investment thesis: A (financially verified), B (order/customer verified), C (management/industry supported), D (narrative only). |
| **Factor Exposure Change** | A shift in the portfolio of risk factors that a security loads on, triggered by milestone events (e.g., from "narrative-driven speculation" to "order-backed growth"). |
| **Milestone-Rerating Lag** | The time delay between a milestone event (e.g., mass production qualification) and the market's full recognition of the factor exposure change. The alpha window exists within this lag. |
| **Catalyst Window** | The period (typically 1-2 quarters) during which a milestone event's factor exposure change is partially but not fully priced in. The optimal entry zone for catalyst-driven positions. |
| **Crowding** | The degree to which the investment thesis is already held and discussed by market participants. Measured by KOL attention, social media volume, options activity, short interest, and sell-side coverage. |
| **Alpha Source** | The specific mechanism by which the investment thesis generates excess returns: (1) milestone-rerating lag, (2) super-trend duration, (3) factor mispricing, (4) crowding dislocation. |
| **Position Sizing Framework** | A risk-adjusted allocation scheme that maps statistical evidence (α, IR), bet type, evidence stage, crowding, and liquidity to conservative position size ranges. Uses weighted (not multiplicative) adjustments with hard floor. |
| **Fact** | An objectively verifiable statement supported by primary data (filings, contracts, customs data, financial numbers). Must be tagged `[FACT]` in agent output. |
| **Opinion** | A subjective judgment, prediction, or evaluation. Must be tagged `[OPINION]` in agent output. |
| **Inference** | A conclusion derived by the agent from facts via logical reasoning. Must be tagged `[INFERENCE]` and include the derivation chain. |
| **Triangulated Fact** | A fact that has been verified against at least two independent data sources with consistent numerical values. |

### Architecture Terms

| Term | Definition |
|------|-----------|
| **Primary Analysis Subagent** | The main agent performing the chokepoint analysis, evidence evaluation, and opportunity classification. |
| **Verification Subagent** | A dedicated subagent responsible for cross-checking every analytical conclusion: (1) verifying the authenticity of data sources cited by the primary agent, (2) retrieving non-correlated data sources to confirm the same fact. |
| **Quantitative Verification Subagent** | A dedicated subagent that writes and executes Python code to run Fama-MacBeth regression, compute Information Ratio, and perform GMM robustness checks. Spawned after the LLM generates a qualitative hypothesis. |
| **Data Source Layer** | The hierarchy of information sources: L1 (company filings), L2 (earnings calls / investor presentations), L3 (official press releases / customer announcements), L4 (industry reports), L5 (financial news), L6 (social media / KOL). |
| **Cross-Validation Layer** | The process of comparing target company financials against upstream/downstream peer financials to detect corroborating or contradicting signals in the "hidden space" of numerical intersections. |
| **Supply-Chain Ontology** | A pre-defined knowledge graph mapping AI infrastructure supply chain nodes by process stage, NOT by material type. Used to validate whether a claimed supplier actually sits at the asserted node. |
| **Catalyst Signal Scanner** | A periodic (quarterly) scan of target supply chain layers for leading indicators of milestone events: inventory changes, prepayment shifts, capex guidance divergences, customs data anomalies. |
| **Fact-Opinion Discriminator** | A methodological layer (system prompt + structured rules) that forces the agent to explicitly tag every statement as Fact, Opinion, or Inference. |
| **Information Ratio (IR)** | A measure of risk-adjusted abnormal return: IR = α / σ(ε), where α is the intercept from Fama-MacBeth regression and σ(ε) is the standard deviation of residuals. IR > 1.0 indicates strong alpha; IR < 0.3 indicates alpha not economically meaningful. |
| **Fama-MacBeth Regression** | A two-pass regression procedure used to estimate factor exposures and abnormal returns (alpha). First pass: time-series regression for each asset. Second pass: cross-sectional regression to estimate risk premia. |
| **GMM Robustness Check** | Generalized Method of Moments check to verify alpha persistence across sub-periods and stability of factor loadings over time. |

### Investment Committee Terms

| Term | Definition |
|------|-----------|
| **Investment Committee (投委会)** | A multi-agent ensemble debate architecture that sits above the existing Serenity Chokepoint skill. The skill serves as an industry research analyst feeding the committee. The committee produces long-term investment opinions and short-term trading plans. NOT an MoE (sparse activation) — every committee member participates in every deliberation. |
| **Committee Member** | A role defined by analytical framework and responsibility, NOT by persona. Each member has an `analytical_prior` (stable analytical bias) and a `framework` (structured analysis steps). Famous investor names appear only in `inspired_by` field, never in reasoning. |
| **Framework Persistence** | A cross-session state mechanism that prevents anchor drift. The agent MUST read the thesis file and holding file before analysis begins, and MUST update them after analysis ends. Code-enforced: analysis cannot start without reading, cannot conclude without writing. |
| **Thesis File** | A persistent file describing a cross-ticker long-term investment logic (e.g., "memory super-cycle to 2027"). Contains: entry logic, time anchors, key assumptions, disconfirmation conditions, status (active/challenged/invalidated). Multiple holdings reference one thesis. The thesis file is the final anchor for adjudication: short-term signals can only trigger position adjustment, not thesis overthrow. |
| **Holding File** | A persistent file describing a single ticker's position logic. References a thesis file via foreign key. Contains: entry logic, bet type (Super Beta / Catalyst Alpha / Event-Driven), chokepoint score, evidence stage, position size, stop-loss conditions, update log. |
| **Time-Weighted Information** | An explicit classification applied to every piece of information during analysis. Each input is tagged with: time horizon (short-term 1-3 days / medium-term 1-4 quarters / long-term 1-5 years) and framework impact (none / minor / major / thesis-overturning). Prevents short-term noise from overriding long-term logic. |
| **Second-Order Consensus** | The market's current pricing-implied expectation for a ticker or thesis. Distinct from first-order belief (what the agent thinks the fundamental truth is). A holding file must record both: the agent's belief AND the market consensus, because alpha comes from the convergence of the two — being right alone is not enough; being right before the market corrects is what generates excess returns. |
| **Holding Expectation Gap** | The difference between the agent's belief and the market consensus for a specific holding. Classified as: convergent (market will come around to my view), divergent (market is moving away from my view), or stale (no new information to resolve the gap). The gap must have a `consensus_catalyst` — a specific event that would force the market to reprice. Without a catalyst, the gap may persist indefinitely (being right but too early). |
| **Belief Hierarchy** | Three-layer separation of investment conviction: (1) Paradigm-level (e.g., "AI is a ten-x industrial revolution") — updates on yearly timescale, stored in thesis files; (2) Industry-level (e.g., "memory super-cycle peaks in 2027") — updates quarterly, stored in thesis/holding files; (3) Trade-level (e.g., "buy now at this price") — updates daily/weekly, stored in holding position_state. Critical rule: paradigm-level belief must NOT be used to justify trade-level errors, and trade-level volatility must NOT be used to negate paradigm-level judgment. |
| **Reflexive Feedback Loop** | The bidirectional relationship between price and fundamentals (Soros): price changes alter fundamentals (via financing conditions, management incentives, competitive dynamics), which in turn change prices. A holding thesis is NOT circular reasoning if it has external inputs (industry data, penetration rates, order flows) that independently verify or falsify the belief. Pure price-validation of belief ("it went up so I'm right") IS circular reasoning. The holding file must distinguish between price-validated signals and fundamentally-validated signals. |
| **Conviction Level** | A continuous value (0.0-1.0) representing the strength of belief in a holding thesis. NOT an LLM subjective score — derived from three existing quantitative outputs: `conviction = 0.3 × Evidence_norm + 0.5 × IR_norm + 0.2 × GMM_norm`. Hard caps: IR<0.3 → cap 0.4; GMM non-persistent → cap 0.6; Evidence Level D → cap 0.5; code-unavailable fallback → cap 0.5. Thresholds: >0.7 high conviction (full position), 0.5-0.7 medium (≤75% base), 0.3-0.5 low (small/watch), <0.3 none (exit). LLM cannot directly set this value — it can only change it by improving the underlying statistical evidence. |

### Risk Management Terms

| Term | Definition |
|------|-----------|
| **Belief-Anchored Risk System** | A risk management framework where price NEVER directly triggers final trade decisions. Price movements only trigger belief re-verification. The only exceptions are tail-risk circuit breakers (extreme moves implying information asymmetry). Replaces traditional fixed-percentage stop-loss, which substitutes "price moved against me" for "I was wrong" — fundamentally incompatible with a belief-driven framework. |
| **Risk Budget** | The maximum allowed floating loss for a single position, tied to conviction level (NOT to a fixed percentage of entry price). High conviction (>0.7): 2% of portfolio NAV; Medium (0.5-0.7): 1%; Low (0.3-0.5): 0.3%. When floating loss reaches the risk budget, it does NOT trigger a sale — it triggers a belief re-verification. This is Kelly-criterion logic: higher conviction permits larger risk assumption. |
| **Belief Re-verification** | A structured re-assessment triggered when price reaches the risk budget boundary. Two tiers: (1) Fast Check — immediate, 5 min: scans for public fundamental negatives, checks disconfirmation signals, checks cross-validation; (2) Full Check — 30 min: re-runs complete Skill analysis including Fama-MacBeth regression and GMM. Fast Check verdicts: clear (hold, no full check needed) / suspicious (run full check) / confirmed_break (reduce immediately). |
| **Market Momentum State Regulator** | An adaptive risk multiplier based on objective price momentum (market consensus proxy). Three states: Bull (250-day momentum > 0 AND price > 60-day MA, multiplier ×1.5), Sideways (neither condition, ×1.0), Bear (both negative, ×0.5). In bull markets, wider risk budget tolerates noise; in bear markets, tighter budget protects capital. Market momentum is a second-order consensus signal, not a first-order price signal — it reflects aggregate market pricing, not individual stock movement. |
| **Temporary Risk Reduction** | A REVERSIBLE position reduction applied in bear-market state when risk budget is breached, BEFORE belief re-verification completes. Rationale: bear-market volatility carries higher persistence risk. If subsequent re-verification confirms belief unchanged, the reduction is reversed when price stabilizes. This is risk management, not a final trade decision — it acknowledges that market state itself is information about risk environment. |
| **Tail Risk Circuit Breaker** | The ONLY unconditional hard trigger in the system. Fires on extreme moves implying information asymmetry or liquidity crisis: (1) main board single-day ≥10% (limit-down), (2) STAR/ChiNext single-day ≥15%, (3) consecutive 2+ limit-down days, (4) 5-day cumulative drop ≥30%. Trigger forces immediate reduction to 30% of position, followed by emergency re-verification. Normal 10-20% drawdowns never reach this threshold. |

### World Simulation Terms

| Term | Definition |
|------|-----------|
| **Central Bank Committee Simulator (CBC Simulator)** | An independent agent that simulates the decision-making process of central bank committees (FOMC, ECB, etc.). Outputs: (1) strategy space probability distribution, (2) expectation gap assessment (priced_in / not_priced / directional_bias). Scope: macro environment + committee strategy space + expectation gap. Does NOT cover transmission chain or individual stock impact — those are the committee's job. |
| **Policy Stance** | A committee member's preference for interest rate level (hawkish / dovish / neutral). One of two orthogonal dimensions of a central banker's influence. |
| **Governance Paradigm** | A central bank chair's institutional philosophy: how decisions are made, communicated, and framed. The SECOND orthogonal dimension, independent of policy stance. A "reformist" chair (e.g., Warsh abandoning forward guidance and dot plot) can shift the governance paradigm without changing rate direction. This shift has larger impact on asset pricing than a simple hawkish/dovish pivot. |
| **Constructive Ambiguity** | A governance paradigm where the central bank deliberately withholds explicit forward guidance, weakens the dot plot's signal value, and retains maximum policy discretion. Characteristic of the Warsh era. Increases market volatility and shifts the expectation anchor from "central bank commitment" to "data博弈". |
| **Market Regime** | The current market pricing paradigm: whether the market is pricing based on forward guidance (commitment-driven) or data dependence (博弈-driven). A slow variable (changes over quarters). Determined by the governance paradigm in effect. Stored in `market_regime.md` and defines the calculation framework for expectation gaps. |
| **Expectation Gap** | The difference between the CBC Simulator's strategy space assessment and market-implied expectations (CME FedWatch, institutional consensus). Classified as: priced_in (market already expects this outcome), not_priced (market has not accounted for this), or directional_bias (market expects the opposite). A fast variable, updated each meeting. The primary alpha source from world simulation. |
| **Aggregation Fallacy** | The systematic error that occurs when committee decisions are simulated by aggregating individual member attributes (hawkish/dovish labels → majority vote). Four failure modes: (1) judgment aggregation paradox, (2) process omission bias, (3) label granularity distortion, (4) common belief assumption bias. Mitigated by: institutional rules layer, continuous belief vectors, multi-round deliberation simulation, and triple aggregation cross-check. |
| **Governance Paradigm Master Switch** | A single file (`governance_paradigm.md`) that stores the current FOMC chair's institutional rules (observable communication patterns, decision protocols, tool usage norms). Switching chairs requires only replacing this file — the entire simulation behavior shifts accordingly. Contains only `[FACT]` (observable rules) and `[INFERENCE]` (motivation analysis), never untagged "constant undertone". |

---

### Fisher Foundation Terms

| Term | Definition |
|------|-----------|
| **Fisher Layer** | Layer 0 of the architecture — the monetary foundation upon which all investment decisions rest. Based on Fisher (1920): the purchasing power of money is uncertain, and its trend determines whether holding stocks or cash is positive expected return. Tracked via the Fisher Equation M·V = P·Y. This layer answers the most basic question: in the current monetary environment, is cash a positive or negative real return asset? All thesis decisions are conditional on this baseline. |
| **Purchasing Power Trend** | The direction (rising/falling/stable) of money's purchasing power (1/P). Rising purchasing power → cash has positive real return → defensive thesis valid. Falling purchasing power → cash has negative real return → stocks favored as real-asset hedge. Computed from M·V = P·Y: if M grows faster than Y, P rises and purchasing power falls. |
| **Stock-vs-Cash Baseline** | The Fisher Layer's primary output. Classification: stocks_favored / cash_favored / neutral. Determines the environment-level asset allocation stance. If cash_favored, even correct theses should run at reduced position sizes. If stocks_favored, the monetary environment supports risk-asset exposure. This is NOT a stock-picking signal — it is a monetary environment assessment that constrains all downstream decisions. |
| **Defensive Thesis** | A thesis type where the investment logic is to hold cash (or cash-equivalents) rather than specific equities. Grounded in Fisher (1920): if purchasing power is rising (M contracting, P falling), cash has positive real return and is a valid "position." Entry logic: "monetary contraction → purchasing power rising → cash positive real return." Disconfirmation: "Fed/PBoC resumes QE (M expansion)." Prior to the Fisher Layer, the schema had no way to represent "holding cash as a deliberate conviction." |
| **Global Financial Cycle** | The single monetary cycle driven by the Federal Reserve, per Rey (2013) "Dilemma not Trilemma." Under partially open capital accounts, Fed policy drives global capital flows, risk asset prices, and leverage — regardless of exchange rate regime. China is a "middle state" (managed float + partial capital account + macroprudential controls). Capital controls reduce short-term spillover volatility but do NOT eliminate directional transmission. Fed is the gravitational center; PBoC is an auxiliary modifier within the same system, not a parallel cycle. |
| **Three Liquidity Layers** | Strict distinction required to avoid conflating monetary expansion with stock market liquidity: (1) Base money — central bank balance sheet, high-powered money, the liquidity source; (2) Broad liquidity — M2, social financing, interbank + credit markets; (3) Stock marginal liquidity — incremental trading funds that directly determine stock prices. Critical: PBoC expanding M2 does NOT directly increase stock liquidity — empirically <10% reaches equities, 70% goes to bonds/credit. |
| **Three Transmission Channels** | The mechanisms by which Fed policy transmits to A-share marginal liquidity: (1) Cross-border portfolio investment — northbound flows, 35-40% of marginal volatility, direct and fast; (2) FX reserves — passive base money creation via trade surplus, 8-10% spillover to equities, slow and indirect; (3) Risk discounting — UST yield + VIX → A-share discount rate, no capital flow needed, -12% growth stock valuation per 100bp UST rise. Total Fed-driven: 40-50% of A-share marginal liquidity volatility. |
| **Equity Transmission Efficiency** | The proportion of central bank liquidity that ultimately reaches the stock market. For PBoC: empirically <10% (70% to bonds/credit). This field prevents the error of interpreting PBoC easing as "liquidity entering stocks." Low efficiency means PBoC easing alone cannot drive equity bull markets. Can be temporarily elevated by special tools (e.g., SFISF) but returns to baseline quickly. |
| **Bull Market Conditions** | Two conditions that must BOTH be met for an A-share bull market: (1) Fed enters clear easing cycle; (2) PBoC policy coordination. Domestic easing alone during Fed tightening produces only bounces, not trends. This is the gating check — if unmet, no new offensive theses are permitted; only defensive thesis or existing position management. |
| **SFISF (Tail-Risk Tool)** | Securities Fund Insurance Company Swap Facility — a liquidity safety net tool, NOT a trend driver. Mechanics: non-bank institutions pledge equity assets for high-liquidity bonds. Does not create new base money or buy stocks directly. Effect: reduces extreme decline probability (~60% reduction in >3% drop days) and liquidity-crash risk. Does NOT change medium-term trend. Trading implication: deploy only during liquidity panic for bounce; do not hold as trend position. |
| **Data Refresh vs Regime Surveillance** | Two fundamentally different update types. Data Refresh: updating field values within the existing framework (e.g., M2 updated, CPI released) — high-frequency, low-risk, automated. Regime surveillance: detecting whether the framework's assumptions still hold (e.g., capital account policy changed, Securities Law revised) — low-frequency, high-risk, requires human judgment. Conflating these two causes either over-reaction (noise treated as structural change) or under-reaction (missing genuine regime shifts). |
| **Regime Surveillance Log** | An append-only log recording detected structural changes that may invalidate Fisher Layer framework assumptions. Each entry includes: monitor point (one of seven), detection event, source, level (legislative/regulatory/verbal), framework impact analysis, and human assessment with downstream impact. Only `author: human` entries can conclude that framework assumptions have changed. |
| **Seven Regime Surveillance Points** | The structural monitoring dimensions for the Fisher Layer: (1) Capital account openness, (2) PBoC transmission pathway changes, (3) Contribution weight drift (quarterly regression validation), (4) Regulatory framework definition (CSRC functional positioning — legislative vs regulatory vs verbal), (5) Geopolitical risk premium (orthogonal to monetary policy), (6) FOMC communication paradigm (connects to ADR-008 Governance Paradigm Master Switch), (7) Trade settlement currency structure (RMB internationalization). |
| **Bidirectional Feynman Protocol** | A three-round AI-first analysis process for Tier 3 regime surveillance (ADR-012). Replaces pure human judgment: Round 1 (AI Initial Analysis — aggregates sources, assesses framework impact) → Round 2 (Human Review — confirms/corrects/supplements with domain judgment) → Round 3 (AI Re-examination — incorporates feedback, executes or tags disputed). All three rounds logged, forming a complete reasoning chain. Rationale: AI has information breadth; human has domain depth; neither alone is sufficient. |
| **Intelligence Source Registry** | A structured YAML file (`world/intelligence_source_registry.yaml`) mapping each of the seven regime surveillance points to their data sources, keywords, polling frequencies, and classification rules. The executable specification of ADR-013. Contains: source authority hierarchy, scheduled/event-driven source lists per monitoring point, personnel surveillance positions, Chinese multi-layer signal system, noise filtering rules, and retrieval workflow. |

### Intelligence Retrieval Terms

| Term | Definition |
|------|-----------|
| **Source Authority Hierarchy** | Five-tier classification of information sources determining escalation rights: Tier S (Sovereign — Fed, PBoC, NPC, State Council — can trigger Tier 3 directly), Tier A (Regulatory — CSRC, SAFE, MOF, etc. — can trigger Tier 3 for legislative changes), Tier B (Official Data — NBS, BLS, BEA — feeds Tier 1 only), Tier C (Reputable Media — Reuters, Bloomberg, Xinhua, Caixin — triggers AI classification, never Tier 3 directly), Tier D (Informal Signal — think tanks, analyst reports — early warning only). |
| **Scheduled Polling** | Periodic source checks aligned with known publication schedules (daily, weekly, monthly, quarterly, semi-annual, every-6-weeks for FOMC). Ensures no scheduled release is missed. Implemented via cron-based recurring tasks. |
| **Event-Driven Scan** | Continuous keyword monitoring of news sources and RSS feeds for unscheduled announcements and early signals. Catches surprises that scheduled polling would miss. Requires keyword specificity to avoid false positives. |
| **AI Classification Pipeline** | A five-dimension classification applied to all retrieved information: (1) source authority tier, (2) change level (legislative/regulatory/verbal/data), (3) monitoring point mapping (which of 7 points), (4) routing destination (Tier 1/2/3/log_only), (5) urgency (immediate/next_cycle/log_only). AI determines the VALUES of these dimensions; routing RULES are deterministic and mechanical. |
| **FOMC Statement Diff Analysis** | A special processing method for FOMC statements (Tier 3.6). Sentence-level comparison (not word-level) with the previous statement, classifying changes as: addition (new language), deletion (abandoned guidance — strongest paradigm shift signal), modification (qualifier changes), or structural (section reordering). Maps changes to four governance paradigm dimensions: forward guidance mode, data dependence language, balance sheet communication, risk balance framing. Structural changes or deletions in forward guidance/balance sheet language trigger Tier 3. |
| **Chinese Multi-Layer Signal System** | China's policy signaling operates through four layers with different lead times: Layer 1 (leadership speeches — 6-12 month lead, Tier S), Layer 2 (state media editorials — 1-3 month lead, Tier C but high signal value as policy preview), Layer 3 (formal documents — immediate, Tier S/A), Layer 4 (window guidance/implementation rules — immediate, Tier C/D). Unlike US policy (transparent, data-dependent), Chinese policy is hierarchical and interpretive — by the time formal documents arrive, Layers 1-2 have already been priced. The retrieval system must track all four layers. |
| **Personnel Surveillance** | Political intelligence (WHO is in power) as a leading indicator of policy intelligence (WHAT policies emerge). A personnel change does NOT directly trigger Tier 3 — it activates watch mode for relevant monitoring points: increased event-driven scan frequency (daily) + expanded keyword sets (new official's policy preferences, past speeches). Watch mode expires after 90 days or upon first formal policy announcement. Tracked positions: Fed Chair, CSRC Chair, PBoC Governor, US Treasury Secretary, USTR, FSDC Chair. |
| **Watch Mode** | An elevated monitoring state activated by personnel changes or Layer 1-2 Chinese policy signals. In watch mode, the affected monitoring point(s) receive daily event-driven scans (vs. continuous-monitoring threshold) with expanded keyword sets. Watch mode is a sensitivity increase, not a trigger — it ensures the system catches the first formal policy signal from the new official or direction. |
| **Noise Filtering** | Four mechanisms preventing alert fatigue: (1) Source Authority Gate — only Tier S/A can trigger Tier 3; Tier C/D must be corroborated within 72 hours, (2) Change Level Gate — only legislative/regulatory changes trigger Tier 3; verbal changes logged as [SIGNAL] only, (3) Cooldown Period — 30-day post-trigger cooldown prevents re-processing the same structural change as it cascades through media, (4) Keyword Specificity Rule — broad keywords excluded; specific phrases required. |
| **Corroboration Window** | The 72-hour window during which a Tier C/D source report of a structural change must be confirmed by a Tier S/A source before escalation. If no official corroboration arrives within 72 hours, the report remains as [SIGNAL] and does not trigger Tier 3. Prevents media-driven false alarms. |

### Sharpe-Fama-Merton Layer Terms

| Term | Definition |
|------|-----------|
| **Sharpe-Fama-Merton Layer (formerly Keynes Layer)** | Layer 1 of the architecture — manifold state tracking. Based on Keynes (1930/36) "beauty contest" metaphor: investment is about anticipating what the market believes others believe, not identifying fundamental truth. The Sharpe-Fama-Merton Layer tracks the market's consensus pricing of risk factors (β·γ systematic topology), current position on the return manifold (α anomaly), and gradient direction of capital flow. Receives Fisher layer ΔUST as input. Outputs conditional factor preference distributions and environment constraints to Graham and Markowitz layers. |
| **Return Manifold** | The surface on which all assets' expected returns distribute, per the Sharpe (1964) equation E(R^e_i) = α_i + β'_i · γ. The β·γ component defines the manifold's shape (systematic risk premia topology); the α component defines position on the manifold (anomaly). Market trading rules (vol targeting, crowding costs, stop-loss) are constraints. No investor sees the entire manifold (Grossman-Stiglitz paradox); alpha comes from better local topology estimation — being closer to the gradient direction than the counterparty. |
| **Factor Duration** | A factor's half-life — the time for its predictive power (IC) to decay by half. Determines: rebalancing frequency, transaction cost budget, and whether the factor is a persistent advantage or an expiring ticket. Three buckets: short-term (<5 trading days, e.g., 5d reversal), medium-term (5-90 days, e.g., 12m momentum at ~70.9 days per Daniel & Moskowitz 2016), long-term (>90 days, e.g., value, quality). Factor duration is a necessary dimension alongside factor type and factor exposure — it serves the temporal game of choosing the right factor, holding for the right time, and exiting before crowding. |
| **Factor Crowding** | The degree to which a factor's return is already captured by participants holding similar positions. Measured by: long/short hedging cost (bps), position concentration, factor correlation distortion. Tracked per duration bucket — a crowded medium-term bucket signals different risk than a crowded long-term bucket. High crowding indicates the factor's alpha is likely partially consumed and that forced deleveraging risk is elevated. |
| **Carhart Baseline** | The academic four-factor model (MKT/SMB/HML/MOM) used as the starting point for Sharpe-Fama-Merton Layer (formerly Keynes Layer) analysis. Explicitly a linear attribution framework — answers "what am I exposed to" but not "what should I configure." Extended with factor duration, crowding, and institutional game theory. The Sharpe-Fama-Merton Layer prompt requires analysis to begin with Carhart baseline before extending to duration and crowding — establishing systematic baseline first, then discussing anomalies. |
| **Gradient Estimation** | Module 3 of the Sharpe-Fama-Merton Layer (formerly Keynes Layer) — estimates the direction capital will flow on the return manifold. Three components: (1) Duration regime assessment (which duration bucket is favored, driven by Fisher layer ΔUST), (2) Forced movement analysis (institutional behavior on a five-tier signal hierarchy with cross-validation), (3) Rotation path (from current to target state with friction analysis). Must generalize across all market states — in low-signal environments, outputs "gradient unreliable" rather than forcing a signal. |
| **Signal Strength Hierarchy** | Five-tier classification of institutional actions by signal value: S1 (position/style change — strongest, "I changed my mind"), S2 (profit-taking — strong), S3 (position reduction — medium), S4 (hedging — weak but quantifiable, "trend intact, smoothing phase volatility"), S5 (long volatility — indirect signal). Single signals may be noise; multi-source cross-validation confirms gradient direction (e.g., S4 IF shorts + S1 fund outflow = high-confidence confirmation). |
| **Option-Implied Duration** | A second-order consensus measure — the market's implied cash flow timing extracted from deep ITM/OTM option term structure. Compared against fundamental duration estimate; divergence indicates an α anomaly point on the manifold. Connects to the holding file's expectation_gap concept — when the market's implied duration diverges from fundamental analysis, the gap is a tradable anomaly. |
| **Momentum Crash Preconditions** | Per Daniel & Moskowitz (2016, JFE 122(2):221-247): momentum crashes occur in panic states — following market declines, when volatility is high, and contemporaneous with market rebounds. All three conditions must be present. The past losers' option-like payoffs command a conditionally high premium in panic states, making momentum's ex ante expected returns low. Module 3b tracks each condition's status; crash risk is only elevated when all three are satisfied or approaching satisfaction. |

### Graham Layer Terms

| Term | Definition |
|------|-----------|
| **Graham Layer** | Layer 2 of the architecture — investment belief formation. Based on Graham (1934, Security Analysis): intrinsic value vs. market price separation, "margin of safety" concept, "Mr. Market" metaphor. The Graham layer operationalizes these: thesis beliefs are formed from fundamental analysis independent of market price; market consensus is tracked separately (Mr. Market's mood); the expectation gap between the two is where alpha lives. Receives Fisher and SFM interface objects as input. Outputs conviction_level and belief state to the Markowitz region. |
| **Thesis File** | A persistent file representing one investment thesis that drives a portfolio of holdings. One thesis = one portfolio = one group of holdings. Contains two coexisting regions: Graham Region (belief — only fundamental signals update this) and Markowitz Region (portfolio — belief changes + risk rules drive this), plus a three-layer append-only Update Log. The conviction_level field is the interface between the two regions — belief changes trigger portfolio adjustments, never the reverse. Supersedes the ADR-009 definition which described thesis files as cross-ticker logic only. |
| **Graham Region** | The belief section of a thesis file. Contains: thesis_type (growth/value/defensive), belief_statement, key_assumptions (with falsification status), disconfirmation_signals, conviction_level (Bayesian, fundamental-only updates), market_consensus, expectation_gap, consensus_catalyst, fisher_alignment, sfm_alignment. Operationalizes ADR-009 Principles 1 (Belief-Action Separation), 2 (Falsificationism), 3 (Bayesian Updating), and 6 (Second-Order Consensus). |
| **Markowitz Region** | The portfolio section of a thesis file. Contains: total_allocation, portfolio_composition (tickers with weights and roles), risk_budget (from ADR-010), rebalancing_triggers. Driven by conviction changes (from Graham Region) + risk rules (from ADR-010). Cannot modify Graham beliefs — information flows DOWN only. |
| **Defensive Thesis** | A thesis type where the investment belief is to hold cash rather than specific equities. NOT "doing nothing" — an active conviction position grounded in Fisher (1920): if purchasing power is rising (M contracting), cash has positive real return. Exit requires BOTH Fisher improvement (stock_vs_cash_baseline → stocks_favored) AND SFM factor opportunity (confidence > 0.6, crowding < 0.5). Uses Logic B + prompt calibration for exit decisions. |
| **Three-Layer Update Log** | Append-only, never-deleted log structure within a thesis file. Layer 1: Narrative Log (human insight, events, AI verification — free-text). Layer 2: Conviction Log (Bayesian updates with prior, evidence, posterior, reasoning — structured). Layer 3: Position Log (quantifiable portfolio changes — risk budget updates, rebalancing actions). Maps to ADR-009's belief hierarchy (paradigm/industry/trade). |
| **Graham Interface Contract** | A fixed-schema, fixed-token-budget output contract that each upstream layer (Fisher, SFM) must satisfy before its context enters Graham's attention window. Symmetric YAML schema with equal field count (6), equal token budget (≤400 tokens), parallel structure (enum + factual signals + confidence scalar). Addresses three structural attention biases (length, position, semantic strength) that mHC head specialization cannot resolve. Complemented by the Distillation Gate as a fallback for oversized upstream state. |
| **Distillation Gate** | A compression step triggered when an upstream layer's raw state exceeds the token budget (e.g., Fisher during regime shift). A lightweight LLM call compresses the full state file into the Graham Interface Contract schema. NOT a filter — normalizes the input distribution so the attention mechanism operates without structural bias. The full upstream state remains accessible via file reference. |
| **Logic B + Prompt Calibration** | The decision framework for inter-layer information flow. Rejects Logic A (hard gate, which zeros out valid signals — equivalent to forcing attention weight = 0). Chooses Logic B (full context to Transformer) + prompt-level calibration (semantic prior for overconfidence prevention) + Graham Interface Contract (structural prior for input distribution balance). The attention mechanism does the actual weighting; the prompt and schema ensure calibration priors are present. |
| **Conviction Level (Thesis)** | A continuous value (0.0-1.0) representing the strength of belief in a thesis. ONLY fundamental signals update this (reflexive feedback loop guard — price signals cannot update conviction). Maps to conviction tiers: high (>0.7), medium (0.5-0.7), low (0.3-0.5), none (<0.3). The interface between Graham Region and Markowitz Region — conviction changes trigger portfolio adjustments via risk budget recalculation. |
| **Consensus Catalyst** | A specific, observable event that would force the market to reprice — closing the expectation gap. Without a catalyst, being right but too early is indistinguishable from being wrong. Required field in the Graham Region. Types: earnings_release, product_launch, regulatory_decision, macro_event. Includes expected_date and market_reprice_direction. |
| **Thesis Invalidation Protocol** | The defined process for declaring a thesis dead and winding down its portfolio. Three automatic triggers (conviction < 0.3, ≥50% disconfirmation signals triggered, critical assumption refuted) and two review-required triggers (Fisher regime shift, SFM gradient reversal). Process: trigger detection → ADR-010 Full Check → confirmed/partial/intact → graduated wind-down (immediate 50% reduction, orderly exit over 5-10 days, final close within 3 weeks). Thesis file archived, NEVER deleted — invalidated theses serve as negative examples for future conviction calibration. Price signals alone CANNOT invalidate a thesis. |
| **Precommitment Rules** | The thesis file's implementation of ADR-009 Principle 4 (Time Inconsistency Constraint). Rules committed in a calm state, executed in an emotional state. Supersedes ADR-009's original `precommitment_rules` design per ADR-010. Each rule includes: condition, action, source, and verification protocol (ADR-010 Fast Check 5min or Full Check 30min). Covers: conviction change > 0.15, alignment shifts, disconfirmation triggered, risk budget breach, tail circuit breaker. |

### Markowitz Layer Terms

| Term | Definition |
|------|-----------|
| **Markowitz Layer** | Layer 3 of the architecture — portfolio construction and execution. Based on Markowitz (1952, Portfolio Selection): portfolio theory, efficient frontier, risk-return optimization. The Markowitz layer receives conviction_level from Graham Region and constructs the actual portfolio: weight allocation, risk budget assignment, profit-taking schedule, and execution tracking. Portfolio construction IS trade meta-plan generation — defining weights simultaneously defines entry, rebalancing, profit-taking, and exit plans across time dimensions. |
| **Alpha Capture Schedule** | The normal profit-taking path — what happens when the thesis SUCCEEDS. Based on Kelly dynamics: as alpha is captured (expectation_gap closes), the remaining edge shrinks, so optimal position size shrinks proportionally — even when conviction_level is unchanged. Four milestones: alpha_emerging (30% captured), alpha_accelerating (50%), alpha_maturing (75%), alpha_exhausted (90%). Residual position (10%) retains optionality. Orthogonal to conviction: thesis can be 100% correct while position shrinks. Contrasts with precommitment_rules (abnormal/deviation path). |
| **Capital Allocation Registry** | A portfolio-level state tracker (NOT decision maker) that tracks aggregate capital across all active theses. Records: total capital, Fisher max_aggregate_equity constraint, per-thesis allocations, alpha_captured_ratio, capital_released, available_capital, aggregate equity/cash exposure. When capital is released (profit-taking), it re-enters the framework as available_capital — capital is fungible, no special reallocation decision tree needed. The framework re-runs normally (Fisher → SFM → Graham → Markowitz) to allocate. |
| **Holdings File** | A persistent file recording the execution state of a single physical position (one ticker = one file). Pure execution record — NO belief fields (conviction, assumptions, disconfirmation signals all live in thesis file Graham Region). Contains: entry info, current position state, risk budget consumption, execution log. Multiple thesis_refs for cross-thesis ticker overlap. Supersedes ADR-009's holding file schema (belief fields relocated to thesis file). |
| **Conviction Level (Dual Definition)** | ADR-009's quantitative formula (`0.3×Evidence + 0.5×IR + 0.2×GMM`) provides the quantitative floor (recalculated by offline scripts). ADR-016's fundamental-signal updates provide the Bayesian adjustment (event-driven, Feynman-gated). Both are needed: quantitative floor anchors to statistical evidence; Bayesian adjustment reflects fundamental judgment. Neither alone is sufficient. |

### Damodaran Layer Terms

| Term | Definition |
|------|-----------|
| **Damodaran Layer** | A cross-section supervisor layer — NOT a sequential Layer 5. Cuts across all four sequential layers (Fisher/SFM/Graham/Markowitz) simultaneously. Role: Adjudicator (constraint enforcer + risk monitor), NOT Allocator (no capital allocation decisions). Reads all layers' output, flags violations to responsible layers, never modifies other layers' state. Named after Aswath Damodaran, honoring his "look forward" valuation philosophy — value investments by what they will earn, not what they have earned. |
| **Cross-Section Architecture** | The Damodaran layer operates orthogonally to the sequential pipeline. Sequential layers process information top-down (Fisher → SFM → Graham → Markowitz). The Damodaran layer cuts horizontally across all theses and holdings simultaneously, providing aggregate visibility that no single sequential layer possesses. |
| **Belief Pool** | The total population of active investment theses managed by the Damodaran layer. Tracks: total active theses count, belief type diversity (growth/value/defensive), duration bucket distribution, factor exposure distribution. Constraint: max 5 active theses — beyond this, portfolio becomes an index with no edge. |
| **Holdings Pool** | The total population of physical positions across all theses. Tracks: total unique tickers, cross-thesis overlap detection, aggregate exposure (equity/cash/sector), risk budget stacking on overlapping tickers. Constraints: max 15 tickers, max 15% per ticker across all theses, max 50% per sector. |
| **Forward-Looking Aggregate Valuation** | Damodaran's "look forward" at portfolio level: sum of (thesis belief × target price × confidence) across all active theses. Compares aggregate forward intrinsic value to current market value. If aggregate forward return < 5%, portfolio is flagged as "index-like" — too diversified to have edge. Backward P&L is reference only, never a decision input. |
| **Alpha Capture Conflict Resolution** | When theses sharing a ticker disagree on profit-taking (Thesis A says reduce, Thesis B says hold), Damodaran computes a merged action based on each thesis's proportional weight in the physical position. The merged reduction ratio reflects the weighted average of each thesis's alpha capture milestone. Physical execution is one trade. |
| **Constraint Suite** | Seven portfolio-level constraints enforced by the Damodaran layer: max 5 active theses, max 15 tickers, max 40% per thesis, max 15% per ticker, max 60% per duration bucket, max 50% per sector, Fisher max_aggregate_equity. When breached, Damodaran flags to the responsible layer for correction — does not itself reduce positions or reallocate. |

## Key Decisions

### ADR-001: Two-Layer Architecture (LLM Qualitative + Code Quantitative)

**Status:** Accepted (Revised v2.1)

**Context:** The original framework (v1.0) used a linear 100-point additive scoring model. v2.0 attempted to fix this with a four-dimensional multiplicative probability model, but peer review identified critical flaws:
1. P(is_bottleneck) was double-counted (Stage 1 filter + Stage 2 dimension)
2. Multiplicative over-penalty: four dimensions at 0.7 scored 0.24, producing excessive false negatives
3. LLMs are systematically poor at probability calibration
4. In low-SNR markets, averaging or multiplying noisy estimates further dilutes signal

**Decision:**
Replace the LLM-driven multiplicative model with a **two-layer architecture**:

**Layer 1 — LLM Qualitative (Hypothesis Generation):**
- Identify supertrend, validate process node, score chokepoint quality (Stage 1 hard filter)
- Assess evidence stage, cross-validate supply chain, classify bet type
- Generate testable hypothesis: "This company has abnormal alpha not explained by the four-factor model"

**Layer 2 — Code Quantitative (Hypothesis Testing):**
- Pull 3-5 years historical returns + four-factor data (MKT, SMB, HML, MOM)
- Run Fama-MacBeth regression: R_i - R_f = α + β₁·MKT + β₂·SMB + β₃·HML + β₄·MOM + ε
- Test H₀: α = 0 (significance at 5% level)
- Compute Information Ratio: IR = α / σ(ε)
- Run GMM robustness check for alpha persistence

**Layer 3 — LLM Synthesis (Interpretation):**
- Compare qualitative hypothesis with quantitative results
- Is α economically meaningful given target holding period?
- Final classification based on BOTH evidence types

**Hard Constraints:**
- Chokepoint score < 12 → Reject
- α not significant (p > 0.05) → Downgrade to "Watchlist" or "Avoid"
- IR < 0.3 → Reject — alpha not economically meaningful
- Any qualitative dimension < 0.3 → Reject

**Fallback:** If code execution unavailable, LLM performs qualitative-only with explicit warning and position sizing capped at 50%.

**Rationale:** Alpha should be computed by statistical methods, not guessed by language models. The Information Ratio ensures alpha is economically meaningful (significantly above noise), not just statistically significant. Fama-MacBeth regression provides rigorous factor control. GMM validates persistence.

---

### ADR-002: Supply-Chain Layer Classification by Process Node

**Status:** Accepted

**Context:** The original framework grouped "InP, GaAs, SOI, substrates, epitaxy wafers" into a single "Materials layer." This is investment-practice fatal: InP substrate (upstream, high barrier, few suppliers) and InP epitaxy wafer (downstream, different equipment, different competitive dynamics) are fundamentally different investment opportunities.

**Decision:**
Reclassify supply-chain layers by **process node and value-add stage**, not by material chemistry:
- Raw Material → Substrate → Epitaxy → Device Fabrication → Module Assembly → System Integration

Each layer has independent competitive dynamics, barrier heights, and pricing power profiles. The agent must validate which specific node a company occupies before analysis begins.

**Rationale:** Misidentifying a company's supply-chain node leads to incorrect barrier assessment, wrong competitor mapping, and flawed valuation. The ontology layer prevents "search engine bias" (e.g., SEO-optimized content pushing a downstream company as an upstream play).

---

### ADR-003: Evidence Stage Transition Map

**Status:** Accepted

**Context:** The original framework used a static Evidence Level (A/B/C/D). Real-world investment validation is a dynamic process with conditional transition probabilities. "Sample submission" does NOT guarantee "mass production ramp."

**Decision:**
Replace static Evidence Level with a **dynamic Evidence Stage Transition Map**:

```
Concept ──→ Sample Submission ──→ Pilot Order ──→ Mass Production ──→ Primary/Exclusive Supplier
   │              │                  │                  │                      │
  C级            C+级               B级                B+/A-级                A级
```

For each analyzed company, the agent must:
1. Identify current stage
2. Estimate probability of advancing to next stage within 1-2 quarters
3. Identify specific signals that would trigger stage advancement
4. Identify specific signals that would indicate stage regression (disconfirmation)

**Rationale:** The alpha window is often between stages, not at a static point. Understanding transition probabilities allows better position sizing and stop-loss definition.

---

### ADR-004: Fact-Opinion-Inference Tagging with Triangulation

**Status:** Accepted

**Context:** Financial text is dense with opinions packaged as facts. LLMs can be misled by confident-sounding management guidance or KOL narratives. The original framework had no systematic fact/opinion discrimination.

**Decision:**
Implement a **dual-layer fact verification system**:

**Layer 1 (System Prompt):** Force the agent to tag every substantive statement:
- `[FACT:source]` — verifiable objective data with source URL/DOI
- `[OPINION:holder]` — subjective judgment with identified holder (management, analyst, KOL)
- `[INFERENCE:chain]` — agent-derived conclusion with explicit derivation chain

**Layer 2 (Verification Subagent):** For every `[FACT]` tag:
- Verify source URL is accessible and content matches citation
- Search for at least one non-correlated source confirming the same fact
- Compare numerical values across sources (flag discrepancies >5%)
- For financial figures, cross-check against primary filings

Facts that pass Layer 2 are promoted to `[TRIANGULATED_FACT]`.

**Rationale:** Agent hallucination and retrieval bias are the two largest risks in AI-driven research. This system makes verification explicit, auditable, and human-reviewable.

---

### ADR-005: Cross-Validation Layer (Upstream/Downstream Financial Intersection)

**Status:** Accepted

**Context:** The original framework's data source hierarchy prioritized company filings but treated each company in isolation. True signals often hide in the "hidden space" where upstream and downstream financials intersect.

**Decision:**
For every target company analysis, the agent MUST retrieve and compare:
- Target company: inventory turnover, prepayments received, capex, revenue by segment
- 2-3 downstream customers: cost of goods sold, supplier concentration, inventory levels
- 1-2 upstream suppliers (if relevant): capacity utilization, pricing trends
- Customs data (if available): import/export volumes for relevant product categories

The agent should flag **resonance signals** (consistent directional changes across the chain) and **divergence signals** (contradictory trends that require explanation).

**Rationale:** A single company's management commentary is opinion. The intersection of multiple companies' financial numbers is fact. Resonance across the supply chain dramatically increases signal-to-noise ratio.

---

### ADR-006: Catalyst-Driven Position Sizing with Dynamic Holding Period

**Status:** Accepted

**Context:** The original framework assumed a uniform "buy and hold" logic. In practice, optimal holding periods vary dramatically: a super-beta bet (e.g., 2015-2022 BYD) may warrant multi-year holding, while a catalyst-alpha bet (e.g., 2018 sugar substitute) may only have a 1-4 quarter window.

**Decision:**
The agent must classify each opportunity by **bet type** before position sizing:

| Bet Type | Holding Period | Key Framework Focus |
|----------|---------------|---------------------|
| Super Beta | 2-5 years | Supertrend durability, competitive evolution, TAM expansion |
| Catalyst Alpha | 1-4 quarters | Milestone timeline, catalyst window, factor exposure change timing |
| Event-Driven | 0-3 months | Specific catalyst event (earnings, contract announcement, regulatory decision) |

Position sizing uses **weighted (not multiplicative)** adjustments:
- Base size determined by bet type
- Adjustments applied as absolute percentage point modifiers (e.g., -1%, -2%)
- Hard floor: max(Base Size × 25%, 0.5%) — prevents compounding to near-zero
- Hard cap: 20% for any single position

Adjustment factors:
- Evidence stage (earlier stage = smaller size)
- Crowding level (higher crowding = reduced size)
- Catalyst clarity (clearer timeline = larger size)
- Liquidity constraint (lower liquidity = smaller size)
- Statistical evidence: IR > 1.0 allows full size; IR 0.5-1.0 reduces size; IR < 0.5 caps at small position

**Rationale:** Mismatched holding period and bet type is a major source of investor losses. Multiplicative adjustments (e.g., ×0.5 ×0.75) can compress a 5% base to <1%, making positions economically meaningless. Weighted adjustments with hard floor ensure viable position sizes while preserving risk discipline.

---

### ADR-007: Investment Committee Architecture (Ensemble Debate, NOT MoE)

**Status:** Accepted

**Context:** The existing skill is a stateless research workflow. In practice, the agent exhibits "anchor drift" — it rebuilds its analytical framework from scratch each session, causing short-term noise (today's -5.79% drop) to override long-term logic (memory super-cycle to 2027) established in prior sessions. The root cause is the absence of cross-session framework persistence and structured multi-perspective adjudication.

The user proposed a "MoE architecture" with multiple specialized agents. However, MoE implies sparse activation (routing inputs to a subset of experts), while investment decisions almost always require all dimensions simultaneously. The correct pattern is **ensemble debate**: every committee member participates in every deliberation, each providing their dimensional assessment, with a final adjudicator synthesizing.

**Decision:**
Add an investment committee layer above the existing skill. The skill serves as an industry research analyst feeding the committee. Key constraints:

1. **Committee members are methodology-driven, not persona-driven.** Each member has an `analytical_prior` (stable bias) and `framework` (structured steps). Famous investor names appear only in `inspired_by`. Rationale: methodology is auditable and evolvable; persona is a black box. (See grilling session for detailed argumentation.)

2. **Three-layer memory structure:** `theses/` (cross-ticker investment logic), `holdings/` (single-ticker position logic), `world/` (external environment state). Thesis files are the adjudication anchor — short-term signals can trigger position adjustment, never thesis overthrow.

3. **Prompt harness + explicit memory protocol (Option C).** Multi-role debate is implemented via prompt (role rotation in a single LLM context). Memory read/write is code-enforced: analysis cannot start without reading framework files, cannot conclude without updating them. Tool protocol (parallel search, full-text retrieval) and output verification (JSON schema, probability sum check) require code-layer enforcement.

4. **Time-weighted information tagging.** Every input is classified by time horizon (short/medium/long) and framework impact (none/minor/major/thesis-overturning). This is the mechanism that prevents short-term noise from overriding long-term logic.

**Rationale:** The "anchor drift" problem is fundamentally a memory problem, not an orchestration problem. Code-enforced memory protocol solves the root cause. Prompt-based multi-role debate provides structured adjudication without the overhead of code orchestration. The existing skill's research methodology (chokepoint scoring, Fama-MacBeth, evidence stages) is preserved unchanged — the committee consumes its output, not replaces it.

---

### ADR-008: Central Bank Committee Simulator (CBC Simulator)

**Status:** Accepted

**Context:** The investment committee requires macro-environmental input that the existing skill cannot provide. Empirical testing (DeepSeek dialogue, 2026-06) demonstrated that LLM-based policy simulation can effectively estimate (1) FOMC strategy space probability distributions and (2) expectation gaps between simulated outcomes and market-implied pricing. However, the term "Institution Simulator" is ambiguous in financial contexts (where "institution" typically means financial institutions, not regulatory bodies).

**Decision:**
Add a **Central Bank Committee Simulator (CBC Simulator)** as an independent agent feeding the investment committee. Scope: macro environment + committee strategy space + expectation gap. Does NOT cover transmission chain or individual stock impact (those are the committee's job).

Key design decisions:

1. **Naming:** "Central Bank Committee Simulator" — explicitly names the simulation target as the decision committee, not a commercial institution. Abbreviation: CBC Simulator.

2. **Aggregation fallacy as design constraint.** Pure member-attribute aggregation (hawkish/dovish labels → majority vote) produces systematic error (judgment aggregation paradox, process omission bias, label granularity distortion, common belief assumption bias). Mitigated by: institutional rules layer, continuous belief vectors, and (Phase 2+) multi-round deliberation simulation. Academic basis: MiniFed (arXiv:2410.18012), FedSight AI (arXiv:2512.15728), FOMC In Silico (Kazinnik & Sinclair, 2025).

3. **Two orthogonal dimensions of central banker influence.** Policy Stance (hawkish/dovish — preference for rate level) and Governance Paradigm (how decisions are made/communicated — institutional philosophy). These are independent: a reformist chair can shift the governance paradigm without changing rate direction, and this shift has larger impact on asset pricing than a simple hawkish/dovish pivot.

4. **Governance Paradigm Master Switch.** A single file (`governance_paradigm.md`) stores the current chair's observable institutional rules (communication patterns, decision protocols, tool usage norms). Switching chairs requires only replacing this file. Contains only `[FACT]` (observable rules) and `[INFERENCE]` (motivation analysis, tagged) — never untagged "constant undertone" that cannot be updated.

5. **Phased implementation.** Phase 1 (MVP): governance_paradigm.md + simplified member states (2-dimensional continuous beliefs, not 4+) + single-round deliberation + expectation gap tracking (group + market layers). Phase 2: multi-round debate + individual expectation gap + market_regime.md. Phase 3: triple aggregation cross-check.

**Rationale:** The CBC Simulator addresses the committee's blind spot: the existing skill only sees micro-industry dynamics (chokepoint), not macro-liquidity environment. The DeepSeek dialogue proved that strategy-space estimation + expectation-gap identification is the correct output format — not precise rate prediction. The phased approach follows the "minimal viable solution, reserve upgrade path" principle: Phase 1's single-round simulation already outperforms pure attribute aggregation (per FOMC In Silico findings), while multi-round debate is a marginal improvement that can wait.

---

### ADR-009: Holding File Six Principles

**Status:** Partially Superseded by ADR-017

**Decision:** Holding files are designed from six financial engineering first principles: (1) Belief-Action Separation, (2) Falsificationism, (3) Bayesian Updating, (4) Time Inconsistency Constraint, (5) Information Decay Management, (6) Second-Order Consensus & Expectation Gap. Each principle maps to specific holding file fields and constraints. **Principles remain valid.** However, belief fields (`conviction_level`, `key_assumptions`, `disconfirmation_signals`, `market_consensus`, `expectation_gap`, `consensus_catalyst`) are relocated to thesis file Graham Region (ADR-016). Holdings file (ADR-017) is now a pure execution record — entry price, position state, risk budget consumption, execution log.

**See:** `docs/adr/0009-holding-file-six-principles.md` and `docs/adr/0017-markowitz-layer-portfolio-construction.md`

---

### ADR-010: Belief-Anchored Risk System

**Status:** Accepted

**Decision:** Replace traditional fixed-percentage stop-loss with a three-layer risk system: (1) Risk Budget — tied to conviction level (high=2%, medium=1%, low=0.3%), (2) Market Momentum State Regulator — adaptive multiplier (bull ×1.5, sideways ×1.0, bear ×0.5), (3) Tail Risk Circuit Breaker — the only unconditional hard trigger. Price NEVER directly triggers trades; it triggers belief re-verification.

**See:** `docs/adr/0010-belief-anchored-risk-system.md`

---

### ADR-011: Fisher Layer — Mundell-Fleming / Rey Framework

**Status:** Accepted

**Decision:** Replace the dual-section Fisher design (US + China parallel) with a single-system four-layer framework based on Rey (2013) "Dilemma not Trilemma." One global financial cycle driven by Fed; PBoC is auxiliary modifier. Three liquidity layers (base money / broad liquidity / stock marginal liquidity) and three transmission channels (cross-border portfolio 35-40% / FX reserves 8-10% / risk discount 12-15%).

**See:** `docs/adr/0011-fisher-layer-mundell-fleming.md`

---

### ADR-012: Fisher Layer Update Protocol — Three-Tier Structure

**Status:** Accepted

**Decision:** Three-tier update protocol: Tier 1 (Data Refresh — high-frequency, automated, field values only), Tier 2 (Event-Driven Re-evaluation — medium-frequency, semi-automated, may change baseline), Tier 3 (Regime Surveillance — low-frequency, bidirectional Feynman protocol, framework assumptions). Seven monitoring points for Tier 3. Tier 3 uses three-round AI-first process: AI Initial Analysis → Human Review → AI Re-examination.

**See:** `docs/adr/0012-fisher-layer-update-protocol.md`

---

### ADR-013: Political/Policy Intelligence Retrieval System

**Status:** Accepted

**Decision:** Define the "sensory system" that feeds ADR-012's update protocol. Five-tier source authority hierarchy (S/A/B/C/D) determines escalation rights. Dual-mode retrieval: scheduled polling (known publication schedules) + event-driven scan (keyword monitoring). AI classification pipeline determines five dimensions (source authority, change level, monitoring point, routing, urgency); routing rules are deterministic. Special handling: FOMC statement diff analysis (sentence-level, governance paradigm mapping), Chinese multi-layer signal system (leadership speech → editorial → formal document → implementation), personnel surveillance (watch mode for political leading indicators). Four noise filtering mechanisms: source authority gate, change level gate, 30-day cooldown, keyword specificity.

**See:** `docs/adr/0013-intelligence-retrieval-system.md` and `world/intelligence_source_registry.yaml`

---

### ADR-014: Sharpe-Fama-Merton Layer — Manifold State Tracking

**Status:** Accepted

**Decision:** Layer 1 tracks the return manifold's state using Sharpe (1964) equation as scaffold: E(R^e_i) = α_i + β'_i · γ. Four modules: (1) Factor Landscape (β·γ — Carhart baseline + factor duration spectrum + extended premia), (2) Anomaly Map (α — crowding by duration + institutional constraints + transient anomaly), (3) Gradient Estimation (duration regime + forced movement signal hierarchy S1-S5 with cross-validation + rotation path), (4) Composite Output (conditional factor preference distribution, NOT point prediction). Factor duration (half-life) is the key generalization mechanism — ensures the module works in any market state. System prompt designed to release LLM attention mechanism for nonlinear factor dependency handling.

**See:** `docs/adr/0014-sfm-layer-manifold-state.md`

---

### ADR-015: Sharpe-Fama-Merton Layer Data Pipeline

**Status:** Accepted

**Decision:** Five Python scripts fill Wind API gaps for the Sharpe-Fama-Merton layer: (1) Carhart regression (offline OLS, VIF check, SQLite), (2) Factor IC engine (Spearman rank IC, exponential decay half-life), (3) Options proxy (MVP high-beta vs low-beta spread, Breeden-Litzenberger upgrade stub), (4) CFFEX futures scraper (daily XML fetch, net position signal, SQLite), (5) Long/short cost (margin trading data, composite crowding score). Scripts run daily/weekly, output YAML for sfm_state.md, store data in SQLite databases under `data/`.

**See:** `docs/adr/0015-sfm-layer-data-pipeline.md`

---

### ADR-016: Graham Layer — Thesis Architecture

**Status:** Accepted

**Decision:** Layer 2 defines investment belief formation. One thesis = one portfolio = one group of holdings. Thesis file contains: Graham Region (belief — only fundamental signals update), Markowitz Region (portfolio — conviction changes + risk rules drive), three-layer append-only Update Log. Defensive Thesis as active cash position (Fisher 1920 grounding). Inter-layer information flow: Logic B (full context) + prompt-level calibration (semantic prior) + Graham Interface Contract (symmetric schema, ≤400 tokens per layer, factual expression only, distillation gate fallback). Information flows DOWN only — Graham never changes Fisher/SFM state; Markowitz never changes Graham beliefs; price signals trigger risk actions but cannot update conviction (reflexive feedback loop guard).

**See:** `docs/adr/0016-graham-layer-thesis-architecture.md`

---

### ADR-017: Markowitz Layer — Portfolio Construction & Holdings Schema

**Status:** Accepted

**Decision:** Layer 3 defines portfolio construction and execution. Four components: (1) Portfolio Composition (target weights + roles), (2) Risk Budget (ADR-010 integration), (3) Precommitment Rules (abnormal path — conviction drop, alignment shift, risk breach), (4) Alpha Capture Schedule (normal path — Kelly dynamic profit-taking as expectation_gap closes). Capital Allocation Registry tracks aggregate state (NOT a decision maker — capital is fungible, framework re-runs normally). Holdings file simplified to pure execution record — belief fields relocated to thesis file Graham Region, partially superseding ADR-009. Conviction level dual definition: quantitative floor (ADR-009 formula) + Bayesian adjustment (ADR-016 fundamental signals). Cross-thesis ticker overlap: one holdings file per ticker, weighted-average risk budget, merged alpha capture action.

**See:** `docs/adr/0017-markowitz-layer-portfolio-construction.md`

---

### ADR-018: Damodaran Layer — Cross-Section Supervisor

**Status:** Accepted

**Decision:** A cross-section supervisor layer (NOT sequential Layer 5) that cuts across all four sequential layers simultaneously. Role: Adjudicator (constraint enforcer + risk monitor), NOT Allocator (no capital allocation decisions). Manages belief pool (max 5 theses), holdings pool (max 15 tickers, overlap detection), and seven portfolio-level constraints. Forward-looking aggregate valuation (Damodaran's "look forward"): sum of thesis belief × target price × confidence — if aggregate forward return < 5%, portfolio flagged as index-like. Alpha capture conflict resolution: merged action based on thesis proportional weights. Trigger: Mode C (event-driven + periodic — weekly constraint scan, monthly forward valuation assessment). Reads all layers, flags violations, never modifies other layers' state.

**See:** `docs/adr/0018-damodaran-layer-cross-section-supervisor.md`

---

## Design Principles

1. **Bottleneck First, Statistics Second:** A real bottleneck is necessary but not sufficient. Alpha must be verified by statistical methods (Fama-MacBeth regression, Information Ratio), not guessed by language models.
2. **Milestone Over Narrative:** Invest in evidence stage transitions, not in stories. KOL posts generate ideas; financial numbers validate them.
3. **Cross-Validation Over Isolation:** No single company's filings tell the full story. The truth lives in the intersection of upstream, downstream, and competitor data.
4. **Catalyst Window Discipline:** Enter when factor exposure change is beginning. Exit when fully priced or thesis disconfirmed. Time is not on the side of catalyst trades.
5. **Fact Discrimination:** Every statement must be tagged as Fact, Opinion, or Inference. Facts must be triangulated. Opinions must be attributed.
6. **Verification by Subagent:** No analytical conclusion stands without independent verification. The verification subagent is not optional — it is a structural safeguard.
7. **Code Over Intuition for Alpha:** LLMs generate hypotheses; code validates them. Alpha should be computed, not estimated. Information Ratio ensures economic significance, not just statistical significance.
8. **Framework Persistence Over Stateless Analysis:** Analysis without reading the thesis file is anchor drift, not analysis. The framework file is the constraint that prevents short-term noise from overriding long-term logic. Code-enforced: no read, no start; no write, no conclusion.
9. **Ensemble Debate, NOT Sparse Routing:** Investment decisions require all dimensions simultaneously. Every committee member participates in every deliberation. The adjudicator synthesizes, never routes to a subset.
10. **Methodology Over Persona:** Committee members are defined by analytical framework and stable bias, not by simulated personality. Methodology is auditable and evolvable; persona is a black box. Famous investor names inspire, never participate in reasoning.
11. **Two Orthogonal Dimensions of Central Banker Influence:** Policy Stance (rate level preference) and Governance Paradigm (decision/communication philosophy) are independent. A governance paradigm shift has larger impact on asset pricing than a rate pivot. The simulation must model both.
12. **Strategy Space Over Point Prediction:** The CBC Simulator outputs probability distributions and expectation gaps, not single-point rate forecasts. Alpha comes from identifying what the market has not priced, not from guessing the exact outcome.
13. **Aggregation Fallacy Awareness:** Simulating committee decisions by aggregating individual attributes (labels → vote) produces systematic error. Mitigation: institutional rules, continuous beliefs, deliberation process — phased from simple to complex.
14. **Authority-Gated Escalation:** Information source authority determines escalation rights. Only sovereign/regulatory sources (Tier S/A) can directly trigger structural change processing. Media sources must be corroborated by official sources within a defined window. This prevents media-driven false alarms from polluting the framework.
15. **Bidirectional Feynman Over Pure Human Judgment:** Structural change assessment uses AI-first analysis (breadth) + human review (depth) + AI re-examination (incorporation), not pure human judgment. AI aggregates sources and produces initial analysis; human corrects and supplements with domain expertise; AI incorporates feedback and executes. All rounds logged for traceability.
16. **Return Manifold as Unifying Framework:** All factor analysis rests on Sharpe (1964): E(R^e_i) = α_i + β'_i · γ. The β·γ component (systematic risk premia) defines the manifold's shape; the α component (anomaly) defines position on the manifold. Alpha comes from better local topology estimation — being closer to the gradient direction than the counterparty — not from seeing the entire manifold.
17. **Factor Duration as Generalization Axis:** Factor half-life ensures the analysis framework works in any market state. Without it, the module would need restructuring whenever the dominant factor changes. With it, only signal strengths across duration buckets change — the tracking logic remains stable.
18. **Carhart as Foundation, Not Ceiling:** The academic four-factor model is the starting point for analysis, not its conclusion. Extended with factor duration, crowding, and institutional game theory. Analysis must begin with Carhart baseline before extending to duration and crowding — establishing systematic baseline first, then discussing anomalies.
19. **Conditional Probability Over Point Prediction:** Factor preference outputs are conditional probability distributions given Fisher layer input, not point predictions. In low-signal environments, the system explicitly outputs "gradient unreliable" rather than forcing a signal.
20. **Belief-Action Separation Requires Structural Enforcement:** Graham Region (belief) and Markowitz Region (portfolio) coexist in one thesis file but are updated by different signals. The interface is `conviction_level` — belief changes trigger portfolio adjustments, never the reverse. Information flows DOWN only: Graham never changes Fisher/SFM state; Markowitz never changes Graham beliefs.
21. **Attention Bias Correction at Input Distribution, Not Architecture:** Multi-head attention resolves what signals get attended to (head specialization) but does not resolve how much total weight each source receives. Length bias, position bias, and semantic strength bias persist regardless of head count because softmax normalization is global. The Graham Interface Contract corrects these biases at the input distribution level — symmetric schema, equal token budget, factual expression only — without requiring model weight access.
22. **Structural Prior Complements Semantic Prior:** Prompt-level calibration (semantic instruction: "when Fisher says cash_favored, override needs elevated evidence") and Graham Interface Contract (structural constraint: symmetric schema, ≤400 tokens) are complementary, not redundant. The former calibrates attention allocation; the latter normalizes input distribution. Together they cover both the semantic and structural dimensions of the inter-layer bias problem.
23. **Portfolio Construction IS Trade Meta-Plan Generation:** Defining portfolio weights simultaneously defines entry, rebalancing, profit-taking, and exit plans across time dimensions. The trade meta-plan is not a separate function — it is the portfolio construction process viewed through a temporal lens. Weight allocation = entry plan; weight maintenance = rebalancing plan; alpha capture schedule = profit-taking plan; precommitment rules = deviation response plan; invalidation protocol = termination plan.
24. **Capital Is Fungible — No Special Profit Path:** Realized profit is indistinguishable from new deposits. No special reallocation decision tree is needed for profit-taking capital — it re-enters the framework as available_capital and is allocated by the normal Fisher → SFM → Graham → Markowitz flow. The Capital Allocation Registry tracks state; the framework makes decisions.
25. **Kelly Dynamic Over Conviction Static:** As alpha is captured and expectation_gap closes, the remaining edge shrinks. Optimal position size shrinks proportionally — even when conviction_level is unchanged. Conviction measures "is the thesis correct?"; alpha capture measures "how much alpha is left?" These are orthogonal dimensions. A thesis can be 100% correct while the position should still shrink because the remaining alpha no longer justifies the current exposure.
26. **Cross-Section Supervision Over Sequential Accumulation:** When multiple theses coexist, aggregate problems (ticker overlap, risk budget stacking, portfolio complexity creep, loss of edge) require simultaneous visibility across all theses — which no sequential layer possesses. A cross-section supervisor (Damodaran layer) provides this visibility without violating belief-action separation: it enforces constraints and flags violations, but does not make allocation decisions or modify other layers' state.
27. **Look Forward, Not Backward:** Portfolio decisions are driven by forward-looking intrinsic value (what investments will earn), not by backward-looking P&L (what they have earned). Backward P&L is reference only. If aggregate forward return falls below a threshold, the portfolio is flagged as "index-like" — too diversified to have edge. This is Damodaran's valuation philosophy applied at the portfolio level: value by future earnings, not historical returns.
