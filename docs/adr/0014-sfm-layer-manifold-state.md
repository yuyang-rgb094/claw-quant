# ADR-014: Sharpe-Fama-Merton Layer — Manifold State Tracking

**Note:** This layer was originally named 'Keynes Layer' (ADR-014). It has been renamed to 'Sharpe-Fama-Merton Layer' to reflect its evolved scope: Sharpe (1964) equation as theoretical scaffold, Fama/Carhart factor models as baseline, Merton (1973) intertemporal CAPM for factor duration dynamics.

**Status:** Accepted

**Date:** 2026-07-08

## Context

Layer 0 (Fisher) answers "what is the monetary environment." Layer 1 (Sharpe-Fama-Merton) answers "what is the market's current pricing of risk, and where is capital being forced to move."

The design challenge: how to structure a prompt-based agent's analysis of factor markets without (a) over-fitting to current market conditions (e.g., only tracking momentum crashes), (b) conflating linear attribution (Carhart) with dynamic configuration (实战), or (c) trying to replicate what neural-network-driven quant funds do implicitly.

Three inputs from the domain expert shaped this design:

1. **Sharpe (1964) as theoretical scaffold.** E(R^e_i) = α_i + β'_i · γ. The β·γ component is the systematic risk premium (the "shape" of the return manifold). The α component is the anomaly (the "position" on the manifold). Market trading rules (vol targeting, stop-loss, crowding costs) are constraints. Investors seek global optima on a manifold no one can fully see. Short-term edge = closer to gradient direction than opponents; long-term edge = better understanding of the manifold's true shape.

2. **Carhart as academic baseline, not configuration tool.** Academic Carhart four-factor model (MKT/SMB/HML/MOM) is a linear attribution framework — it answers "what am I exposed to" but not "what should I configure." Top quant funds (幻方 etc.) use it as a starting point, then extend with factor duration (half-life), dynamic IC monitoring, and AI-driven nonlinear modeling. The Sharpe-Fama-Merton Layer must do the same: start from Carhart, extend with duration and crowding, and let the LLM's attention mechanism handle nonlinear factor dependencies through prompt design rather than numerical modeling.

3. **Three necessary dimensions.** Factor type, factor exposure, and factor duration are all necessary — none is redundant. Duration is added to serve a concrete practical goal: choose the right factor, hold for the right time, exit before crowding. This is a temporal game: correct factor + wrong holding period = either stepping into crowding (too long) or wasting signal (too short).

## Decision

### Naming

**Keynes** — after John Maynard Keynes (1930/36), whose "beauty contest" metaphor describes the core problem: investment is not about identifying fundamental truth, but about anticipating what the market believes others believe. The Sharpe-Fama-Merton Layer tracks the market's consensus pricing of risk factors and the gradient direction of capital flow.

### Layer Boundary

| Layer | Responsibility | Does NOT Do |
|-------|---------------|-------------|
| **Sharpe-Fama-Merton (Layer 1)** | Manifold state: shape + position + gradient | Individual stock selection, position sizing |
| **Graham (Layer 2)** | Investment belief formation on the manifold | Changing manifold state assessment |
| **Markowitz (Layer 3)** | Portfolio construction and risk expression | Changing thesis judgment |

The Sharpe-Fama-Merton Layer receives `fisher_state.md` composite assessment as input (ΔUST direction, stock_vs_cash_baseline). It outputs manifold state + factor preference distribution + environment constraints to Graham and Markowitz layers.

### Module Structure

Four modules, each mapping to a component of Sharpe's equation:

```
sfm_state.md
├── Module 1: Factor Landscape (β'_i · γ)
│   ├── 1a: Carhart Baseline — academic starting point, linear approximation
│   ├── 1b: Factor Duration Spectrum — half-life by duration bucket
│   └── 1c: Extended Premia — factors beyond Carhart, with decay tracking
│
├── Module 2: Anomaly Map (α_i)
│   ├── 2a: Crowding by Duration — long/short costs, concentration
│   ├── 2b: Institutional Constraints — vol targeting, risk model signals
│   └── 2c: Transient Anomaly — short-term irrationality, IC reversal
│
├── Module 3: Gradient Estimation
│   ├── 3a: Duration Regime Assessment — which duration bucket is favored
│   ├── 3b: Forced Movement Analysis — institutional behavior + signal hierarchy
│   └── 3c: Rotation Path — from current to target state
│
└── Module 4: Composite Output
    ├── Manifold state summary
    ├── Factor preference (conditional probability, NOT point prediction)
    └── Environment constraints → Graham / Markowitz layers
```

### Module 1: Factor Landscape (β'_i · γ)

The systematic topology of the return manifold.

**1a: Carhart Baseline**

Rolling 2-year regression of portfolio/factor returns against MKT/SMB/HML/MOM. Outputs β vector and γ (factor premia) estimates. Explicitly tagged as "linear approximation" — the starting point for analysis, not the conclusion. Residual α from this regression feeds into Module 2.

**1b: Factor Duration Spectrum**

Factors organized by half-life into three buckets:

| Bucket | Half-Life Range | Typical Factors | Role |
|--------|----------------|-----------------|------|
| Short-term | <5 trading days | 5d reversal, overnight gap, volume shock | Intraday/week trading; high decay, requires high-frequency execution |
| Medium-term | 5-90 trading days | 12m momentum, 200d trend, earnings revision | Core swing trading; Daniel & Moskowitz (2016) reports 12m momentum half-life ~70.9 days |
| Long-term | >90 trading days | Value, quality, low volatility, dividend yield | Position holding; slow decay, fundamental drift |

Each bucket tracks: current IC (mean + std), signal strength, and decay status (stable / accelerating / reversing).

**1c: Extended Premia**

Factors beyond Carhart, each tracked with premia + half-life + decay status:
- Earnings revision (fundamental, ~30d half-life)
- Residual momentum (technical, ~45d — strips systematic component, lower crowding)
- Option-implied duration (second-order consensus — market's implied cash flow timing via deep ITM/OTM term structure, compared against fundamental duration estimate; divergence = α anomaly point)

### Module 2: Anomaly Map (α_i)

The position on the manifold — where current pricing deviates from systematic prediction.

**2a: Crowding by Duration**

Each factor tracked with:
- `crowding_score` (0-1): composite of long/short hedging cost (bps), position concentration, factor correlation distortion
- `long_short_cost_bps`: annualized cost of maintaining factor exposure
- `trend`: increasing / stable / decreasing

Crowding is tracked **per duration bucket**, not just per factor — a crowded medium-term bucket signals different risk than a crowded long-term bucket.

**2b: Institutional Constraints**

- `vol_targeting`: realized vol vs. target vol → implied adjustment (reducing/increasing gross)
- `risk_model_signals`: momentum variance rising, factor correlation elevated (nonlinear dependency indicator)
- `net_exposure_trend`: aggregate market net exposure direction

**2c: Transient Anomaly**

Short-term irrational deviations that create medium-term opportunities:
- `irrational_deviation`: description of pricing deviation from fundamental support
- `ic_reversal_risk`: IC approaching zero, reversal IC rising, status (not_yet_inverted / inverting / inverted)
- `option_implied_divergence`: market-implied duration vs. fundamental duration estimate

### Module 3: Gradient Estimation

Where capital is flowing and why. This module must generalize across all market states, not just momentum-crowded environments.

**3a: Duration Regime Assessment**

The generalization mechanism. For any market state, outputs which duration bucket is currently favored, driven by Fisher layer's ΔUST input:

| Fisher Input | Duration Implication |
|-------------|---------------------|
| UST declining | Long-duration factors favored (momentum, growth — discount rate falling) |
| UST rising | Short-duration factors favored (value, dividend — discount rate rising) |
| UST stable | Duration-neutral; no strong signal; hold existing configuration |

Output includes dominant duration bucket + confidence level. In low-signal environments, explicitly outputs "gradient unreliable, low-confidence regime" rather than forcing a signal.

**3b: Forced Movement Analysis — Signal Strength Hierarchy**

Institutional actions tracked on a five-tier signal hierarchy:

| Tier | Behavior | Signal Meaning | Strength | Observable Sources |
|------|----------|---------------|----------|-------------------|
| **S1** | Position/style change | "I changed my mind" | Strongest | Capital flow data, fund NAV vs. benchmark deviation |
| **S2** | Profit-taking | "This is good enough" | Strong | Volume anomaly, sector fund outflow |
| **S3** | Position reduction (lock profit) | "Trend intact, taking some off" | Medium | Block trade data, dragon-tiger list |
| **S4** | Hedging (options/futures) | "Trend intact, don't want phase volatility" | Weak but quantifiable | IF/IH/IC short positions (publicly disclosed), options PCR |
| **S5** | Long volatility | "Expecting gradient acceleration" | Indirect | VIX/IV auction data, option skew |

**Cross-validation framework:** Single signals may be noise. Module 3b uses multi-source cross-validation:

- If S4 signal (IF shorts surge) coincides with S1 signal (momentum sector fund outflow) → high-confidence gradient confirmation
- If S4 signal appears alone → record as `[WEAK_SIGNAL]`, low confidence
- If S1 signal appears with S3 (reduction + style change) → confirms rotation, not just hedging

**Momentum crash precondition monitoring** (Daniel & Moskowitz, 2016): Three conditions must ALL be present for crash:
1. Market decline (preceding period)
2. High market volatility
3. Market rebound (contemporaneous)

Module 3b tracks each condition's status. Crash risk is only elevated when all three are satisfied or approaching satisfaction. Partial satisfaction (e.g., volatility rising but no decline yet) is noted but not triggered.

**3c: Rotation Path**

From current state → target state, with:
- Friction analysis (rebalancing cost, liquidity constraints)
- Estimated transition duration
- Key risks during transition
- Alternative paths (e.g., via residual momentum as bridge)

### Module 4: Composite Output

**Manifold state summary:** shape (gradient direction) + position (crowding/underweight) + gradient (flow direction)

**Factor preference:** Conditional probability distribution, NOT point prediction. Output is conditioned on Fisher layer input:

```yaml
factor_preference:
  conditional_on_fisher:
    ust_continues_declining:
      preferred_factors:
        - { factor: residual_momentum, duration: medium, hold_period: 1-2m }
        - { factor: quality, duration: long, hold_period: 3-6m }
      avoid: [12m_momentum]  # crowding >0.8
      confidence: 0.6
    ust_reverses_rising:
      preferred_factors:
        - { factor: value, duration: long, hold_period: 3-6m }
        - { factor: low_volatility, duration: long, hold_period: 3-6m }
      avoid: [12m_momentum, growth]
      confidence: 0.5
    ust_stable:
      preferred_factors: [no_strong_signal, monitor]
      confidence: 0.3
```

**Environment constraints** passed to Graham and Markowitz layers:
- Crowding warnings (avoid specific crowded factors)
- Duration guidance (favor specific duration bucket)
- Regime confidence level
- Holding period guidance for new positions
- Risk budget modifier (reduce in crowded segments)

### System Prompt Design Principles

The prompt is not an accessory to the schema — it is the mechanism that releases the LLM's attention-based nonlinear reasoning capability. Five principles:

**1. Sharpe Equation as Cognitive Anchor.** Prompt opens with E(R^e_i) = α_i + β'_i · γ. Every analytical step must distinguish: "Am I processing β·γ (systematic topology) or α (anomaly position)?" Prevents conflating systematic risk premia with anomaly returns.

**2. Manifold Metaphor as Reasoning Guide.** Market as a surface (saddle point analogy). Current factor configuration is a point on the surface. Gradient direction is where capital will flow. LLM always answers three questions: "What shape is the surface? (Module 1)" / "Where are we? (Module 2)" / "Which way does water flow? (Module 3)."

**3. Carhart as Starting Point, Extension as Path.** Analysis must begin with Carhart four-factor baseline ("academic foundation"). Then extend along: factor duration → extended premia → crowding → institutional game theory. LLM cannot skip Carhart to discuss crowding — must establish systematic baseline first, then discuss anomalies.

**4. Nonlinear Dependency via Attention.** No explicit `[NONLINEAR_DEP]` tagging. Instead:
- Present all factor states simultaneously (attention naturally discovers cross-factor relationships)
- Require LLM in "forced movement analysis" to consider "how does reducing one factor affect other factors' crowding" (natural trigger for nonlinear reasoning)
- Require "second-order effects" in rotation path analysis (e.g., reducing momentum → momentum crash → spillover to value)

**5. Market State Generalization.** Module 3a prompt is structured as conditional logic covering all states:
- High volatility + high crowding → evaluate momentum crash conditions
- Low volatility + low crowding → output "low-signal environment, gradient unreliable"
- Factor rotation in progress → evaluate transition path and friction
- No dominant factor → output "duration-neutral, hold existing configuration"

## What This Does NOT Do

- Does NOT predict which factor will outperform — it outputs conditional probability distributions given Fisher layer input
- Does NOT replicate neural-network quant fund capabilities — operates on medium/long timescales (weeks/months/quarters) where LLM reasoning has advantage over millisecond-speed ML models
- Does NOT use Carhart as a configuration tool — Carhart is the attribution baseline, configuration decisions come from duration analysis + crowding + gradient estimation
- Does NOT force a signal in low-information environments — explicitly outputs "gradient unreliable" when conditions don't support confident assessment
- Does NOT track intraday/short-term anomalies as primary signals — short-duration bucket is tracked but the layer's strength is in medium-to-long duration analysis

## Rationale

The Sharpe-Fama-Merton Layer's design rests on a single insight: **alpha comes from being closer to the gradient direction than the counterparty, not from seeing the entire manifold.** No investor has full information (Grossman-Stiglitz paradox), but some investors have better local topology estimation. The four-module structure organizes this estimation:

- Module 1 measures the manifold's shape (β·γ)
- Module 2 locates current position on the manifold (α)
- Module 3 estimates gradient direction (capital flow)
- Module 4 synthesizes into actionable constraints

The factor duration dimension is the key generalization mechanism. Without it, the module would need to be restructured every time the market's dominant factor changes. With it, the same tracking logic works in any market state — only the signal strengths across duration buckets change.

The signal-strength hierarchy in Module 3b (S1-S5) with cross-validation prevents two failure modes: (1) over-reacting to weak hedging signals that don't indicate conviction change, and (2) under-reacting to forced movements because they weren't cross-validated.

## References

- Sharpe, W. (1964). Capital Asset Prices: A Theory of Market Equilibrium under Conditions of Risk. Journal of Finance.
- Daniel, K. & Moskowitz, T. (2016). Momentum Crashes. Journal of Financial Economics, 122(2):221-247.
- Carhart, M. (1997). On Persistence in Mutual Fund Performance. Journal of Finance.
- Blitz, D., Huij, J. & Martens, M. (2011). Residual Momentum. Journal of Empirical Finance.
- Grilling session (2026-07-08): Sharpe equation framework, Carhart vs. quant practice distinction, factor duration as organizational axis, signal-strength hierarchy for institutional behavior
- ADR-011: Fisher Layer (provides ΔUST input)
- ADR-012: Fisher Layer Update Protocol (Sharpe-Fama-Merton Layer inherits similar tier structure)
- ADR-007: Investment Committee Architecture (Sharpe-Fama-Merton is Layer 1 of the three-layer memory)
