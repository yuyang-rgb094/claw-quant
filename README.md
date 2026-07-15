# Claw Quant — 多层投资智能体框架 | Multi-Layer Investment Agent Framework

> 基于 A 股的结构化投资研究与组合管理框架，专为 AI Agent 操作设计。
>
> A structured investment research and portfolio management framework for A-share equities,
> designed for AI Agent operation (OpenClaw / Claude Code / similar).

---

## 架构 | Architecture

```
Fisher (Layer 0)    → SFM (Layer 1)     → Graham (Layer 2)   → Markowitz (Layer 3)
货币环境              因子流形              投资信念形成            组合构建
Monetary Env          Factor Manifold      Belief Formation      Portfolio + Alpha Capture
      ↑                                                                     ↓
      └──────────── Damodaran 横切监管层 · Cross-Section Supervisor (ADR-018) ──────────┘
                     7 项组合约束 · 信念池 · 持仓池 · 前瞻估值
```

### 各层职责 | Layer Responsibilities

| Layer | ADR | 职责 | 关键输出 |
|-------|-----|------|----------|
| **Fisher** | 011/012/013 | 货币环境 (Mundell-Fleming / Rey) | `fisher_interface` (≤400 tokens) |
| **SFM** | 014/015 | 因子流形状态 (Sharpe-Fama-Merton) | `sfm_interface` (≤400 tokens) |
| **Graham** | 016/009/010 | 投资信念形成 | Thesis file (Graham + Markowitz Region) |
| **Markowitz** | 017 | 组合构建 + Alpha 捕获 | Holdings file + Capital Allocation Registry |
| **Damodaran** | 018 | 横切监管层 | 7 约束, 前瞻估值 |
| **WalkThrough** | 019 | Graham→Markowitz 硬门 | 因子来源/信念审计/可证伪性验证 |

### 信息流 | Information Flow

信息**只向下流动**，上游层级不能修改下游层级的状态。
Information flows **DOWN only**. No upstream layer can modify a downstream layer's state.

Damodaran 横切所有层，作为裁决者（监控和标记，不做决策）。
Damodaran cuts horizontally as an Adjudicator (monitors and flags, does not decide).

---

## 仓库结构 | Repository Structure

```
Claw Quant/
├── CLAUDE.md                                # Agent 配置 | Agent configuration
├── CONTEXT.md                               # 领域术语表 + 设计原则 | Glossary + principles
├── fisher_state.md                          # Layer 0 状态 (ADR-011)
├── sfm_state.md                             # Layer 1 状态 (ADR-014, 4 modules)
├── pyproject.toml                           # Python 包配置 | Package config
├── LICENSE                                  # MIT
│
├── claw_quant/                              # Python 包 | Python package
│   ├── pipeline.py                          # 全流程编排 | Full pipeline orchestrator
│   ├── refresh.py                           # 层级刷新管理 | Layer refresh manager
│   ├── freshness.py                         # 数据新鲜度追踪 | Freshness tracker
│   ├── scheduler.py                         # 定时任务调度 | Scheduler
│   ├── sfm_engine.py                        # SFM 引擎 | SFM engine
│   ├── graham_engine.py                     # Graham 引擎 | Graham engine
│   ├── markowitz_engine.py                  # Markowitz 引擎 | Markowitz engine
│   ├── walkthrough.py                       # 审计硬门 | Walk-through audit gate
│   ├── agent_interface.py                   # Agent 接口 | Agent interface
│   ├── validation.py                        # 验证工具 | Validation utilities
│   ├── validation_loop.py                   # 验证循环 | Validation loop
│   ├── metrics_tracker.py                  # 指标追踪 | Metrics tracker
│   ├── calibration.py                       # 校准 | Calibration
│   ├── ab_test.py                           # 接口 A/B 测试 | Interface A/B test
│   ├── config.py                            # 全局配置 | Global config
│   ├── state_init.py                        # 状态初始化 | State initialization
│   ├── fisher_automation.py                 # Fisher 自动化 | Fisher automation
│   ├── sfm_updater.py                       # SFM 更新器 | SFM updater
│   ├── walkthrough.py                       # 走查引擎 | Walk-through engine
│   ├── data_provider.py                     # 数据提供者基类 | Data provider base
│   ├── data_factory.py                      # 数据工厂 | Data factory
│   ├── data_hybrid.py                       # 混合数据源 | Hybrid provider (Wind→AKShare→Synthetic)
│   ├── data_wind.py                         # Wind 数据源 | Wind data provider
│   ├── data_akshare.py                      # AKShare 数据源 | AKShare provider
│   ├── data_synthetic.py                    # 合成数据源 | Synthetic data provider
│   ├── database.py                           # 数据库工具 | Database utilities
│   ├── backtest/                            # 回测模块 | Backtesting
│   │   ├── engine.py                        # 回测引擎 | Backtest engine
│   │   ├── data_loader.py                   # 历史数据加载 | Historical data loader
│   │   ├── performance.py                   # 业绩分析 | Performance analysis
│   │   └── report.py                        # 回测报告 | Backtest report
│   └── synthetic.py                         # 合成数据生成 | Synthetic data generation
│
├── docs/
│   ├── adr/                                 # 18 架构决策记录 | Architecture Decision Records
│   │   ├── 0001-0008/                       # 遗留 ADR | Legacy (chokepoint framework)
│   │   ├── 0009-holding-file-six-principles.md
│   │   ├── 0010-belief-anchored-risk-system.md
│   │   ├── 0011-fisher-layer-mundell-fleming.md
│   │   ├── 0012-fisher-layer-update-protocol.md
│   │   ├── 0013-intelligence-retrieval-system.md
│   │   ├── 0014-sfm-layer-manifold-state.md
│   │   ├── 0015-sfm-layer-data-pipeline.md
│   │   ├── 0016-graham-layer-thesis-architecture.md
│   │   ├── 0017-markowitz-layer-portfolio-construction.md
│   │   └── 0018-damodaran-layer-cross-section-supervisor.md
│   └── architecture-overview.html           # 交互式架构图 | Interactive architecture diagram
│
├── scripts/                                 # 离线批处理脚本 | Offline batch scripts
│   ├── carhart_regression.py                # Module 1a: Carhart 四因子回归
│   ├── factor_ic_engine.py                  # Module 1b: IC + 半衰期估计
│   ├── long_short_cost.py                   # Module 2a: 拥挤度指标
│   ├── options_proxy.py                     # Module 1c: 久期代理
│   ├── cffex_scraper.py                     # Module 3b: 中金所期货持仓
│   └── requirements.txt
│
├── templates/                                # 模板文件 | Templates
│   ├── thesis_template.md                   # → theses/<name>.md
│   ├── holdings_template.yaml               # → holdings/<ticker>_<id>.yaml
│   ├── capital_allocation_registry_template.md
│   └── damodaran_state_template.md
│
├── theses/                                  # 活跃 thesis (运行时) | Active theses (runtime)
├── holdings/                                # 活跃持仓 (运行时) | Active holdings (runtime)
├── portfolio/
│   ├── capital_allocation_registry.md       # 跨 thesis 资本状态
│   └── damodaran_state.md                   # 横切监管层状态
│
├── tests/                                   # 271 tests (pytest)
│   ├── conftest.py                          # pytest 配置
│   ├── helpers.py                           # YAML schema 验证工具
│   ├── test_fisher_state.py                 # Fisher Layer schema (ADR-011)
│   ├── test_state_files.py                  # Interface outputs + SFM modules
│   ├── test_thesis_template.py              # Thesis Graham + Markowitz Region
│   ├── test_holdings_template.py            # Holdings belief-action separation
│   ├── test_capital_allocation_registry.py  # CAR schema (ADR-017)
│   ├── test_damodaran_state.py              # Damodaran 7 constraints (ADR-018)
│   ├── test_carhart_regression.py           # Carhart regression core functions
│   ├── test_factor_ic_engine.py             # IC + half-life core functions
│   ├── test_pipeline.py                     # Pipeline orchestrator
│   ├── test_refresh.py                      # Layer refresh manager
│   ├── test_validation.py                   # Validation loop + metrics
│   ├── test_walkthrough.py                  # Walk-through audit gate
│   ├── test_hybrid_provider.py              # Hybrid data provider
│   └── test_backtest_engine.py              # Backtest engine
│
├── .github/workflows/validate.yml           # CI/CD pipeline
├── world/
│   └── intelligence_source_registry.yaml    # ADR-013 信息源层级
│
└── serenity-chokepoint-investing/
    └── SKILL.md                             # 遗留技能 | Legacy skill (ADR-001 to 008)
```

---

## 核心设计决策 | Key Design Decisions

### 信念-行为分离 | Belief-Action Separation (ADR-009)
Thesis 文件包含信念 (Graham Region) 和组合 (Markowitz Region)。
Holdings 文件是纯执行记录，不含任何信念字段。

### Alpha 捕获计划 | Alpha Capture Schedule (ADR-017)
Kelly 动态获利了结：随着 expectation_gap 闭合 (30%→50%→75%→90%)，
仓位按比例缩小。与信念正交——thesis 可以 100% 正确同时仓位缩小。
释放的资本视为同质资金，重新进入框架正常流程。

### Graham 接口契约 | Graham Interface Contract (ADR-016)
每层上游输出 ≤400 token 压缩接口（各 6 个字段），
消除长度偏差和语义强度偏差。

### Damodaran 7 约束 | 7 Constraints (ADR-018)
1. 最多 5 个活跃 thesis
2. 最多 15 个独立标的
3. 单一 thesis ≤ 40%
4. 单一标的 ≤ 15%
5. 单一久期桶 ≤ 60%
6. 单一行业 ≤ 50%
7. Fisher 最大总权益暴露 (来自 fisher_state.md)

### 走查审计门 | Walk-Through Audit Gate (ADR-019)
Graham→Markowitz 之间的硬门，验证因子来源可追溯、信念可证伪、
声明有据可查、标的合法、跨层一致性。

---

## 快速开始 | Quick Start

### 安装 | Install
```bash
git clone https://github.com/yuyang-rgb094/claw-quant.git
cd claw-quant
pip install -e ".[dev]"
```

### 运行测试 | Run Tests
```bash
python -m pytest tests/ -v
# 271 tests, all passing
```

### 运行管线 | Run Pipeline
```bash
# 设置 Wind API Key (可选，不设则使用合成数据)
export WIND_API_KEY="your_key_here"

# 运行完整管线
python -c "
from claw_quant.pipeline import PipelineRunner
runner = PipelineRunner()
output = runner.run()
print(output.summary)
"
```

### 运行离线脚本 | Run Offline Scripts
```bash
# Carhart regression (weekly)
python scripts/carhart_regression.py --portfolio "600519.SH,000858.SZ"

# Factor IC engine (weekly)
python scripts/factor_ic_engine.py --factor all

# Crowding metrics (daily)
python scripts/long_short_cost.py --factor momentum,value,quality

# CFFEX futures (daily after close)
python scripts/cffex_scraper.py --date yesterday
```

### 创建新 Thesis | Create a New Thesis
1. 复制 `templates/thesis_template.md` → `theses/<name>.md`
2. 填充 Graham Region（基本面分析）
3. 填充 Markowitz Region（组合构成 + 风险预算 + Alpha 捕获计划）
4. 运行 Damodaran 约束检查

---

## 依赖 | Requirements

- Python 3.9+
- pandas, numpy, scipy, statsmodels, pyyaml, requests, lxml
- pytest (dev)
- Wind API (optional — scripts include synthetic data fallback)
- AKShare (optional — `pip install -e ".[akshare]"`)

---

## 免责声明 | Disclaimer

本框架仅供教育和研究目的。不提供财务建议、投资推荐或个性化组合管理服务。
所有输出应视为研究辅助，而非买卖指令。

This framework is for educational and research purposes only. It does not provide
financial advice, investment recommendations, or personalized portfolio management.
All outputs should be treated as research assistance, not buy or sell instructions.

---

## License

MIT
