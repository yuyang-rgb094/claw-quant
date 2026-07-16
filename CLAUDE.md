# CLAUDE.md — Agent Configuration for Claw Quant Multi-Layer Investment Framework

## Project Identity

Multi-layer investment agent architecture for A-share equity investing.
This is NOT a trading bot — it is a structured research and portfolio
management framework operated by an AI Agent.

## Architecture

```
Fisher (Layer 0) → SFM (Layer 1) → Graham (Layer 2) → Markowitz (Layer 3)
         ↑                                                     ↓
         └──────────── Damodaran Cross-Section Supervisor ──────┘
```

- **Fisher** (ADR-011/012/013): Monetary environment — Fed cycle, transmission channels, A-share liquidity
- **SFM** (ADR-014/015): Factor manifold — Carhart baseline, IC/half-life, crowding, gradient
- **Graham** (ADR-016/009/010): Investment belief formation — thesis, conviction, expectation gap
- **Markowitz** (ADR-017): Portfolio construction — composition, risk budget, alpha capture schedule
- **Damodaran** (ADR-018): Cross-section supervisor — 7 constraints, belief/holdings pool, forward valuation

## Agent's Role

**You ONLY operate the Graham layer.** The computation layer (Fisher, SFM, Markowitz, Damodaran)
runs automatically via Python. Your job is to:

1. Read compressed interfaces from the computation layer
2. Form investment beliefs
3. Manage thesis files and holdings
4. Check Damodaran constraints before executing

## Quick Start — AgentInterface

```python
from claw_quant.agent_interface import AgentInterface
ai = AgentInterface()

# Step 1: Read the environment (≤800 tokens total)
fisher = ai.get_fisher_summary()      # 6 fields, ≤400 tokens
sfm = ai.get_sfm_summary()            # 6 fields, ≤400 tokens
recs = ai.get_factor_recommendations() # Preferred/avoided factors, crowding alerts

# Step 2: Check refresh status
status = ai.get_refresh_status()
# If any layer is "expired", run: ai.check_and_refresh()

# Step 3: Form beliefs (YOUR JOB)
# Based on fisher + sfm + recs, decide:
#   - What is the investment thesis?
#   - Which factors to target?
#   - What is the conviction level?
# Then create/update thesis files in theses/<name>.md

# Step 4: Validate before executing
# Step 4a: Damodaran constraint check
check = ai.get_constraint_check(
    preferred_factors=["12m_momentum", "value"],
    conviction_tier="high",
    fisher_stock_vs_cash=fisher["stock_vs_cash"],
)
if not check["is_valid"]:
    print("CONSTRAINT VIOLATIONS:", check["violations"])
    # Do NOT proceed — fix the thesis first

# Step 4b: Walk-Through Audit (ADR-019) — hallucination prevention hard gate
audit = ai.walkthrough_check("theses/my_thesis.md")
if not audit["passed"]:
    print("WALK-THROUGH AUDIT FAILED:")
    for v in audit["violations"]:
        print(f"  BLOCKING: {v['description']}")
        print(f"  Fix: {v['fix_suggestion']}")
    # Do NOT proceed — fix all BLOCKING violations first

# Step 5: Run pipeline for portfolio construction
pipeline = ai.run_pipeline(
    fisher_stock_vs_cash=fisher["stock_vs_cash"],
    total_capital=1_000_000.0,
    thesis_path="theses/my_thesis.md",  # Triggers walk-through audit
)
```

## What You MUST NOT Do

- ❌ Run Python scripts directly (cffex_scraper.py, carhart_regression.py, etc.)
- ❌ Compute factors or Carhart regressions
- ❌ Look at raw SQLite data
- ❌ Update state files manually (fisher_state.md, sfm_state.md)
- ❌ Make price-driven conviction changes (price triggers re-verification, not conviction update)
- ❌ Create a new thesis without checking Damodaran constraints first
- ❌ Execute a thesis without passing the walk-through audit (ADR-019)

## Information Flow (DOWN only)

```
Fisher → SFM → Graham → Markowitz
```

- Graham NEVER changes Fisher or SFM state
- Markowitz NEVER changes Graham beliefs
- Price signals trigger risk actions (ADR-010) but CANNOT update conviction (reflexive feedback loop guard)

## Refresh Mechanism

Every time you call `ai.get_fisher_summary()` or `ai.get_sfm_summary()`, the system
auto-checks freshness. If a layer is stale (>12h for Fisher/SFM), it auto-refreshes.

Cascade rule: Fisher direction change → triggers SFM → triggers Graham → triggers Markowitz.

```python
# Manual refresh
ai.refresh_layer("fisher")   # Single layer, cascades automatically
ai.refresh_all()              # Force-refresh all layers
ai.check_and_refresh()        # Auto-refresh only stale layers
```

## Data Sources

| Provider | Type | Priority | Status |
|----------|------|----------|--------|
| Wind MCP | Institutional-grade data | 🥇 Primary | ⚠️ Requires local wind-skills CLI |
| AKShare | Free A-share data | 🥈 Secondary | ⚠️ Requires `pip install akshare` |
| Synthetic | Fake data for testing | 🥉 Tertiary | ✅ Always available |

**Hybrid mode (default):** `DATA_PROVIDER = "hybrid"` — Wind → AKShare → Synthetic chain.
Each method independently tries Wind first, falls back to AKShare, then synthetic.
This ensures the best available data quality with graceful degradation.

To check which sources are active:
```python
from claw_quant.data_factory import get_data_provider
dp = get_data_provider('hybrid')
print(dp.get_availability_report())
```

## First-Time Setup

The default **hybrid** provider auto-detects available data sources and uses the best one.
No config change needed — just install the data sources you want:

```bash
# Install AKShare (free, ~2 min)
pip install "akshare>=1.14.0"

# Install Wind MCP (institutional, requires API key)
git clone https://github.com/Wind-Information-Co-Ltd/wind-skills
cd wind-skills && npm install
# API key is read from environment variable: export WIND_API_KEY="your_key"

# Initialize all layers (~2-5 minutes, network-dependent)
python3 -c "
from claw_quant.agent_interface import AgentInterface
ai = AgentInterface()
ai.refresh_all()
print(ai.get_refresh_status())
"
```

After initialization, the pipeline uses real data from the best available source.

## Weekly Maintenance

```python
ai.run_weekly_update()  # Runs all scripts, updates state files, recomputes interfaces
ai.run_daily_update()   # CFFEX scraper + crowding update
```

## Conviction Update Rule

Only fundamental signals update conviction_level (ADR-016 Principle 3).
Quantitative floor: `0.3×Evidence + 0.5×IR + 0.2×GMM` (ADR-009).
Bayesian adjustment: fundamental signals, Feynman-gated (ADR-016).

- Conviction > 0.7 → high → full position
- 0.4-0.7 → medium → ≤75% base
- 0.3-0.5 → low → small/watch
- < 0.3 → none → exit

## Damodaran Constraints (check before any new thesis)

1. max 5 active theses
2. max 15 unique tickers
3. max 40% per single thesis
4. max 15% per single ticker (across all theses)
5. max 60% per single duration bucket
6. max 50% per single sector
7. Fisher max_aggregate_equity (from fisher_state.md)

## Walk-Through Audit (ADR-019) — Hard Gate before execution

The walk-through layer is a **code-enforced hard gate** between Graham and Markowitz.
It checks 7 dimensions to prevent LLM hallucination from reaching portfolio construction:

| Dimension | Check |
|-----------|-------|
| A. Factor Provenance | Factors must match SFM output, not LLM-invented |
| B. Conviction Audit | Bayesian adjustment capped at 1.3× quantitative floor |
| C. Claim Verification | Quantitative claims sanity-checked against bounds |
| D. Disconfirmation Testability | Signals must be falsifiable with thresholds |
| E. Ticker Validity | Tickers must exist in universe with valid format |
| F. Cross-Reference | No internal contradictions (type vs bucket vs factors) |
| G. Source Traceability | Every [FACT] must be traceable to a data source |

**If the audit fails, the thesis CANNOT proceed to Markowitz.** The LLM must fix
all BLOCKING violations before re-running.

```python
# Run walk-through audit before executing any thesis
audit = ai.walkthrough_check("theses/my_thesis.md")
if not audit["passed"]:
    print("BLOCKING VIOLATIONS:")
    for v in audit["violations"]:
        print(f"  [{v['dimension']}] {v['description']}")
        print(f"  → Fix: {v['fix_suggestion']}")
    # STOP — do not run pipeline until fixed
```

## Alpha Capture (Kelly Dynamic)

As expectation_gap closes, position shrinks — even when conviction is unchanged.
Conviction measures "is the thesis correct?"; alpha capture measures "how much alpha is left?"
These are ORTHOGONAL dimensions.

## File Map

### State Files (computation layer writes, Agent reads)
- `fisher_state.md` — Layer 0 output (auto-refreshed)
- `sfm_state.md` — Layer 1 output (auto-refreshed)
- `portfolio/capital_allocation_registry.md` — Markowitz capital state tracker
- `portfolio/damodaran_state.md` — Damodaran cross-section state

### Agent-Managed Files (Agent writes)
- `theses/<name>.md` — One per active thesis (Graham Region + Markowitz Region)
- `holdings/<ticker>_<id>.yaml` — Pure execution record, NO belief fields

### Scripts (scheduled, NOT run by Agent)
- `scripts/carhart_regression.py` — Module 1a: Carhart four-factor rolling regression
- `scripts/factor_ic_engine.py` — Module 1b: IC + half-life estimation
- `scripts/long_short_cost.py` — Module 2a: Crowding metrics
- `scripts/options_proxy.py` — Module 1c: Duration proxy
- `scripts/cffex_scraper.py` — Module 3b: CFFEX futures positions (S4 signal)

## Test Commands

```bash
cd "/Users/yangyu/Documents/Claw Quant" && python3 -m pytest tests/ -q

# Run specific layer tests
python3 -m pytest tests/test_backtest_engine.py -v
python3 -m pytest tests/test_pipeline.py -v
python3 -m pytest tests/test_refresh.py -v
```

## Quick Validation

```bash
# Verify data source
python3 -c "
from claw_quant.config import DATA_PROVIDER
from claw_quant.data_factory import get_data_provider
dp = get_data_provider(DATA_PROVIDER)
print(f'Provider: {dp.name} | Synthetic: {dp.is_synthetic}')
"

# Check if system is initialized (all layers should show 'fresh' or 'stale', not 'never')
python3 -c "
from claw_quant.agent_interface import AgentInterface
ai = AgentInterface()
for layer, s in ai.get_refresh_status().items():
    status = '✅' if s['freshness'] in ('fresh', 'stale') else '❌'
    print(f'{status} {layer}: {s[\"freshness\"]}')
"

# Run pipeline (synthetic data = placeholder values; real data = actual signals)
python3 -c "
from claw_quant.agent_interface import AgentInterface
ai = AgentInterface()
pipeline = ai.run_pipeline(
    fisher_stock_vs_cash='neutral',
    total_capital=1_000_000.0,
)
print(pipeline['summary'])
"
```

## Key Design Principles (from 27 in CONTEXT.md)

1. **Belief-Action Separation**: Thesis file = belief, holdings file = execution
2. **Code Over Intuition for Alpha**: LLMs generate hypotheses; code validates them
3. **Kelly Dynamic Over Conviction Static**: Alpha capture is orthogonal to conviction
4. **Look Forward, Not Backward**: Value by what investments will earn, not what they earned
5. **Capital Is Fungible**: Realized profit = new deposits; no special reallocation path
6. **Cross-Section Supervision**: Damodaran enforces constraints, never allocates capital