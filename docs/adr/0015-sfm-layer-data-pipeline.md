# ADR-015: Sharpe-Fama-Merton Layer Data Pipeline

**Status:** Accepted

**Date:** 2026-07-09

## Context

ADR-014 defines the Sharpe-Fama-Merton Layer's four-module structure. The modules require quantitative data that cannot be produced by LLM reasoning alone — factor regressions, IC calculations, crowding metrics, and futures position signals need dedicated Python scripts running offline.

Wind Skills (`wind-mcp-skill`) provides stock/fund/index/bond/macro data but has three gaps: no futures positions (IF/IH/IC/IM), no option chain data, and no pre-built Carhart regression or IC computation. This ADR defines the supplementary data pipeline that fills these gaps.

## Decision

### Architecture: Five Scripts + Three SQLite Databases

```
scripts/
├── cffex_scraper.py         → data/cffex_positions.db
├── carhart_regression.py    → data/carhart_results.db
├── factor_ic_engine.py      → data/factor_ic.db
├── long_short_cost.py        → data/crowding.db
└── options_proxy.py          → (no DB, outputs YAML directly)

data/
├── cffex_positions.db       (daily futures positions, CFFEX)
├── carhart_results.db        (rolling regression results)
├── factor_ic.db              (IC time series + half-life)
└── crowding.db               (crowding metrics + margin data)
```

### Script Responsibilities

| Script | SFM Module | Data Source | Output Format | Run Frequency |
|--------|------------|-------------|---------------|---------------|
| `cffex_scraper.py` | 3b (S4 signal) | CFFEX website (`/sj/ccpm/`) | SQLite + JSON summary | Daily (after market close) |
| `carhart_regression.py` | 1a (Carhart baseline) | Wind API (stock K-line + fundamentals) | YAML → sfm_state.md + SQLite | Weekly |
| `factor_ic_engine.py` | 1b (duration spectrum) | Wind API (stock K-line) | YAML → sfm_state.md + SQLite | Weekly |
| `long_short_cost.py` | 2a (crowding) | Wind API (融资融券) | YAML → sfm_state.md + SQLite | Daily |
| `options_proxy.py` | 1c (implied duration) | Wind API (high/low beta stock returns) | YAML stdout | Weekly |

### CFFEX Scraper (Gap 3/4 Solution)

**URL pattern:** `http://www.cffex.com.cn/sj/ccpm/{YYYYMM}/{DD}/{SYMBOL}.xml`
- Symbols: IF (CSI 300), IC (CSI 500), IM (CSI 1000), IH (SSE 50)
- Returns: top 20 futures company positions (long volume, short volume, position changes)

**Key signal:** `net_position_signal` = top20_net_long_change - top20_net_short_change
- Positive = bullish hedging (more longs added than shorts)
- Negative = bearish hedging (more shorts added than longs)

This provides the S4 signal (hedging via futures) for Module 3b's forced movement analysis. Cross-validated with S1 (fund flow) and S2 (volume anomaly) signals from other sources.

### Carhart Regression (Module 1a)

**Method:** Rolling 2-year OLS regression of portfolio excess returns on MKT/SMB/HML/MOM.

**Critical design decision:** Results are computed OFFLINE and written as static YAML to `sfm_state.md`. The AI Agent reads pre-computed values — it does NOT compute regressions. This ensures:
- Quantitative calculations use proper statistical tools (statsmodels, scipy)
- LLM reasoning focuses on interpretation, not numerical estimation
- Results are auditable and reproducible

### Factor IC Engine (Module 1b)

**Method:** For each factor, compute Spearman rank correlation between factor values and future returns (1d/5d/10d/20d/60d/120d). Fit exponential decay model to estimate half-life.

**Factor definitions by duration bucket:**
- Short (<5d): 5d_reversal, overnight_gap, volume_shock
- Medium (5-90d): 12m_momentum (half-life ~70.9d per Daniel & Moskowitz 2016), 200d_trend, earnings_revision
- Long (>90d): value, quality, low_volatility, dividend_yield

### Long-Short Cost (Module 2a)

**Crowding score (0-1 composite):**
- 40% long/short cost percentile rank (from 融资融券 data)
- 35% position concentration (top 10 stocks weight)
- 25% factor correlation distortion (rolling correlation vs historical mean)

### Options Proxy (Module 1c — MVP)

**MVP approach:** High-beta vs low-beta stock relative performance as duration proxy:
- `proxy_implied_duration = (high_beta_return - low_beta_return) / ust_yield_change`

**Future path:** When option data becomes available (via Tushare or exchange scraping), replace proxy with:
- Deep ITM/OTM IV term structure extraction
- Breeden-Litzenberger method for implied risk-neutral density
- Market-implied cash flow timing estimation

The `compute_implied_duration_from_options` function stub is pre-written and documented for this future upgrade.

### Wind API Integration

Scripts use `subprocess` to call `wind-mcp-skill` CLI:
```python
result = subprocess.run(
    ["node", "scripts/cli.mjs", "call", "stock_data", "get_stock_kline",
     json.dumps({"windcode": "600519.SH", "begin_date": "20240101", "end_date": "20260701"})],
    capture_output=True, text=True
)
```

Each script includes a `fetch_data_from_wind()` reference implementation. Actual Wind API key configuration is handled by wind-mcp-skill's existing setup.

### Daily Update Workflow

```
1. cffex_scraper.py --date yesterday
   → Fetches IF/IH/IC/IM top-20 positions
   → Computes net_position_signal
   → Updates cffex_positions.db

2. long_short_cost.py --factor momentum,value,quality
   → Fetches 融资融券 from Wind
   → Computes crowding scores
   → Outputs YAML for sfm_state.md Module 2a

3. (Weekly) carhart_regression.py --portfolio "..." --output sfm_state.md
   → Runs rolling 2-year regression
   → Outputs YAML for sfm_state.md Module 1a

4. (Weekly) factor_ic_engine.py --factor all --output yaml
   → Computes IC + half-life
   → Outputs YAML for sfm_state.md Module 1b

5. (Weekly) options_proxy.py --method proxy --output yaml
   → Computes duration proxy
   → Outputs YAML for sfm_state.md Module 1c
```

## What This Does NOT Do

- Does NOT replace Wind Skills — it supplements them. Wind Skills remain the primary data access layer for stock/fund/index/bond data
- Does NOT run in real-time — all scripts are designed for offline batch processing
- Does NOT make investment decisions — scripts compute quantitative metrics; the AI Agent interprets them
- Does NOT handle intraday data — designed for daily/weekly frequency, matching the Sharpe-Fama-Merton layer's medium-to-long duration focus

## References

- ADR-014: Sharpe-Fama-Merton Layer Manifold State Tracking (defines the modules these scripts feed)
- Wind Skills: `https://github.com/Wind-Information-Co-Ltd/wind-skills` (primary data source)
- CFFEX: `http://www.cffex.com.cn/cn/ccpm.html` (futures positions)
- Daniel, K. & Moskowitz, T. (2016). Momentum Crashes. JFE 122(2):221-247 (half-life reference)
