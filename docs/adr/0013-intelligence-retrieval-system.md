# ADR-013: Political/Policy Intelligence Retrieval System

**Status:** Accepted

**Date:** 2026-07-07

## Context

ADR-012 defines a three-tier update protocol with seven regime surveillance points, and a bidirectional Feynman protocol for Tier 3 processing. However, ADR-012 does not define **how information about those seven points is retrieved and classified** before it enters the update pipeline. Without a defined retrieval architecture, the system has three blind spots:

1. **No source authority distinction** — a Reuters headline and an NPC legislative announcement would be treated with equal weight, causing over-reaction to media noise
2. **No scheduled polling discipline** — the Agent relies on ad-hoc web searches rather than systematic tracking of official publication schedules, missing releases or reacting late
3. **No classification logic** — retrieved information has no automated routing decision, so everything either triggers human review (alert fatigue) or gets ignored (under-reaction)

This ADR defines the "sensory system" that feeds ADR-012's "nervous system." The bidirectional Feynman protocol (Tier 3) is triggered BY this system's classification output.

## Decision

### 1. Source Authority Hierarchy

All information sources are classified into five authority tiers. The tier determines whether a source can directly trigger Tier 3 processing or must first pass through AI classification:

| Tier | Name | Sources | Can Trigger Tier 3 Directly? |
|------|------|---------|------------------------------|
| **S** | Sovereign | Fed, PBoC, NPC, State Council, FSDC | Yes |
| **A** | Regulatory | CSRC, SAFE, MOF, CBIRC, NDRC, US Treasury, USTR, SCIO | Yes (legislative level only) |
| **B** | Official Data | NBS, BLS, BEA, HKEX, SWIFT | No — feeds Tier 1 |
| **C** | Reputable Media | Reuters, Bloomberg, FT, WSJ, Xinhua, People's Daily, Caixin | No — triggers AI classification first |
| **D** | Informal Signal | CASS, Peterson Institute, state media editorials, analyst reports | No — early warning only |

**Critical rule:** Tier C/D sources can NEVER directly trigger Tier 3. They can only trigger AI classification, which then decides whether to escalate based on corroboration from Tier S/A sources.

### 2. Dual-Mode Retrieval

Two retrieval modes operate in parallel:

**Scheduled Polling:** Periodic checks aligned with known publication schedules. Each source has a defined polling frequency (daily, weekly, monthly, quarterly, semi-annual, or every-6-weeks for FOMC). The Agent polls the source, checks for new publications since last poll, and routes any new content to AI classification.

**Event-Driven Scan:** Continuous keyword monitoring of news sources and RSS feeds. When a keyword match is detected, the full context is extracted and routed to AI classification. This mode catches unscheduled announcements, breaking news, and policy previews.

The two modes serve different purposes: scheduled polling ensures nothing is missed from known publication calendars; event-driven scan catches surprises and early signals.

### 3. Intelligence Source Registry

Each of the seven regime surveillance points (ADR-012 Tier 3) maps to specific sources with defined metadata. The full registry is maintained as a standalone YAML file (`world/intelligence_source_registry.yaml`). The structure for each monitoring point:

```yaml
monitoring_point:
  scheduled_sources:
    - source: "PBoC"
      authority_tier: tier_s
      frequency: monthly
      publication: "MLF rate, LPR announcement"
      keywords: ["MLF", "LPR", "结构性货币政策"]
      classification: regulatory
      routing: tier1
  event_driven_sources:
    - source: "Reuters"
      authority_tier: tier_c
      keywords: ["PBoC new tool", "structural monetary policy"]
      classification: verbal
      routing: log_only
  special_handling:
    - pattern: "new_monetary_tool"
      trigger: "PBoC announces new structural monetary policy tool"
      classification: regulatory
      routing: tier3
      feynman_protocol: true
```

**Monitoring Point → Source Mapping Summary:**

| Point | Scheduled Sources | Event-Driven Sources | Special Processing |
|-------|-------------------|---------------------|-------------------|
| 3.1 Capital Account | SAFE (quarterly), HKEX (event), PBoC (semi-annual) | Reuters, Xinhua, Caixin | Legislative change → Tier 3 |
| 3.2 PBoC Transmission | PBoC MLF/LPR (monthly), Monetary Policy Report (quarterly) | Reuters, Caixin | New tool → Tier 3 |
| 3.3 Contribution Drift | Wind API (quarterly regression) | N/A (quantitative) | Chow/CUSUM test → Tier 3 |
| 3.4 Regulatory Framework | NPC (event), CSRC (event), State Council (weekly) | Caixin, Reuters | Legislative → Tier 3; Regulatory → Tier 2; Verbal → log |
| 3.5 Geopolitical | None (event-driven only) | Reuters, MFA, White House, US Treasury | Risk level jump → Tier 3 |
| 3.6 FOMC Paradigm | Fed (every 6 weeks), Minutes (3 weeks after), SEP (quarterly) | Reuters, Fed unscheduled | **FOMC statement diff analysis** (see §5) |
| 3.7 Trade Settlement | PBoC (semi-annual), SAFE (quarterly), SWIFT (monthly) | Reuters, Xinhua | Significant RMB share change → Tier 3 |

### 4. AI Classification Pipeline

When information is retrieved (by either mode), AI classifies it along five dimensions:

| Dimension | Values | Purpose |
|-----------|--------|---------|
| **Source Authority** | tier_s / tier_a / tier_b / tier_c / tier_d | Determines escalation rights |
| **Change Level** | legislative / regulatory / verbal / data | Determines processing tier |
| **Monitoring Point** | mp_3_1 through mp_3_7 | Routes to correct surveillance point |
| **Routing** | tier1 / tier2 / tier3 / log_only | Determines downstream processing |
| **Urgency** | immediate / next_cycle / log_only | Determines timing of processing |

**Routing Rules (deterministic, not AI-discretionary):**

| Condition | Route | Processing |
|-----------|-------|------------|
| Tier B source + data release | tier1 | Automated field update (ADR-012 Tier 1) |
| Tier A source + regulatory change | tier2 | Semi-automated re-evaluation (ADR-012 Tier 2) |
| Tier S/A source + legislative change | tier3 | Bidirectional Feynman protocol (ADR-012 Tier 3) |
| Tier C/D source + breaking news | ai_classification_first | AI determines if escalation is warranted |
| Any source + verbal level change | log_only | Record as `[SIGNAL]`, no action |

**AI's role in classification is constrained:** AI does NOT decide the routing rules — those are deterministic. AI's role is to determine the *values* of the five classification dimensions (especially: what is the change level? which monitoring point does this map to?). The routing is then applied mechanically based on those values.

### 5. FOMC Statement Diff Analysis (Special Case)

FOMC statements are the primary tool for Tier 3.6 (FOMC Communication Paradigm). Unlike other sources where keyword matching suffices, FOMC statements require **semantic diff analysis** because governance paradigm shifts are encoded in language changes, not in explicit announcements.

**Method:**

1. **Versioned storage:** Each FOMC statement stored as a versioned document with date, full text, and parsed sentence list
2. **Sentence-level diff:** Compare current statement with previous at the sentence level (not word-level — sentence semantics matter). Classify each change:
   - `addition`: New concern, new tool, new risk mentioned
   - `deletion`: Abandoned guidance, removed concern
   - `modification`: Qualifier changes (e.g., "moderate" → "significant", "some" → "broad-based")
   - `structural`: Section reordering, new sections, removed sections
3. **Governance paradigm mapping:** Map detected changes to ADR-008's four governance paradigm dimensions:

| Diff Type | Forward Guidance | Data Dependence | Balance Sheet Comm. | Risk Balance |
|-----------|-----------------|-----------------|---------------------|-------------|
| Addition | New explicit path language | New "data-dependent" phrasing | New QT/QE language | New risk language |
| Deletion | Removed forward guidance | Removed data reference | Removed QT language | Removed risk balance |
| Modification | Qualifier on path language | "Considerable period" → "meeting-by-meeting" | Pace language change | "Balanced" → "tilted" |
| Structural | New section on guidance | New framework section | New balance sheet section | Restructured risk section |

4. **Trigger rule:** Any `structural` change OR any `deletion` in forward guidance / balance sheet communication → triggers Tier 3 bidirectional Feynman protocol. `modification` and `addition` alone trigger Tier 2 (event-driven re-evaluation).

**Connection to ADR-008:** If the FOMC statement diff triggers Tier 3 and the human confirms a governance paradigm shift, the `governance_paradigm.md` master switch file is updated, cascading to the entire CBC Simulator behavior.

### 6. Chinese Policy Intelligence Layer

Chinese political/policy intelligence has a unique multi-layer signal system that requires specialized retrieval logic. Unlike US policy (where Fed statements are transparent and data-dependent), Chinese policy direction is signaled through layers with different lead times:

| Layer | Signal Type | Source | Lead Time | Authority Tier | Action |
|-------|-------------|--------|-----------|---------------|--------|
| **1** | 最高领导讲话 (Leadership speeches) | Politburo meetings, major conferences | 6-12 months | S | Record as `[STRATEGIC_SIGNAL]`, activate watch mode |
| **2** | 党报社论 (State media editorials) | People's Daily front-page, Xinhua commentaries | 1-3 months | C | Record as `[POLICY_PREVIEW]`, increase event-driven scan sensitivity |
| **3** | 正式文件 (Formal documents) | State Council executive meetings, ministry documents | Immediate | S/A | Process through AI classification pipeline |
| **4** | 实施细则 (Implementation rules) | Window guidance reported by media, implementation notices | Immediate | C/D | Record as `[IMPLEMENTATION_SIGNAL]` |

**Key insight:** Chinese policy intelligence is **hierarchical and interpretive**. You cannot rely on Layer 3 alone (formal announcements) — by the time the formal document arrives, the market has already priced in Layer 1-2 signals. The retrieval system must track all four layers, with Layer 1-2 serving as early warning that increases the sensitivity of event-driven scanning for the relevant monitoring points.

**Special sources for Chinese policy:**

- **国务院新闻办公室 (SCIO):** Regular policy briefings where formal policy is communicated. Tier A authority.
- **金融委 (FSDC):** Cross-regulatory coordination body. Its statements signal coordination across CSRC, CBIRC, and PBoC — critical for Tier 3.4. Tier S authority.
- **发改委 (NDRC):** Macro-economic planning body. Announcements on industrial policy, investment approval, and project pipelines are leading indicators for regulatory framework changes.

### 7. Personnel Surveillance (Political Leading Indicator)

Political intelligence (WHO is in power) is a leading indicator of policy intelligence (WHAT policies emerge). The system tracks key personnel positions. A personnel change does NOT directly trigger Tier 3 — it activates **watch mode** for the relevant monitoring points, increasing event-driven scan sensitivity:

| Position | Authority | On Change: Activate Watch Mode For |
|----------|-----------|-------------------------------------|
| Fed Chair | S | Tier 3.6 (FOMC Communication Paradigm) — governance paradigm review |
| CSRC Chair | S | Tier 3.4 (Regulatory Framework) — regulatory positioning review |
| PBoC Governor | S | Tier 3.2 (PBoC Transmission) — transmission pathway review |
| US Treasury Secretary | S | Tier 3.5 (Geopolitical) + Tier 3.7 (Trade Settlement) |
| USTR Representative | A | Tier 3.5 (Geopolitical) + Tier 3.7 (Trade Settlement) |
| FSDC Chair | S | Tier 3.4 (Regulatory Framework) — cross-regulatory coordination |

**Watch mode behavior:** When activated, the event-driven scan for the affected monitoring point(s) runs at increased frequency (daily instead of continuous-monitoring threshold) and with expanded keyword sets (including the new official's known policy preferences, past speeches, and institutional affiliations). Watch mode expires after 90 days or upon the first Tier S/A formal policy announcement from the new official, whichever comes first.

### 8. Noise Filtering & Alert Fatigue Prevention

A continuous monitoring system's biggest risk is alert fatigue — too many signals, most of which are noise. Four mechanisms prevent this:

**1. Source Authority Gate:** Only Tier S/A sources can directly trigger Tier 3. Tier C/D sources must first pass through AI classification, which checks for corroboration from Tier S/A sources before escalating. A Reuters headline alone never triggers Tier 3 — it must be followed by an official confirmation.

**2. Change Level Gate:** Only `legislative` and `regulatory` level changes can trigger Tier 3. `verbal` level changes (speeches, comments, editorials) are always logged as `[SIGNAL]` with no action triggered. This prevents leadership rhetoric from causing framework re-evaluation before formal policy follows.

**3. Cooldown Period:** After a Tier 3 trigger fires for a monitoring point, a 30-day cooldown prevents re-triggering for the same point unless a *higher-level* change is detected (e.g., if `regulatory` triggered Tier 3, only a subsequent `legislative` change can re-trigger during cooldown). This prevents the same structural change from being processed multiple times as it cascades through media coverage.

**4. Keyword Specificity Rule:** Keywords must be specific enough to avoid false positives. Broad keywords ("Fed", "央行", "stock market") are excluded from the registry. Specific phrases are required: "forward guidance abandoned", "SFISF扩容", "证券法修订", "资本账户开放". The keyword registry is reviewed quarterly for precision.

## Implementation Notes

- **Market data:** Wind API (already configured in user's local agent) for Tier 1 data refresh and Tier 3.3 quantitative regression
- **Official sources:** Web scraping / RSS for PBoC, CSRC, NPC, State Council, Fed websites. Many Chinese official sources lack RSS — implementation requires scheduled HTML scraping with change detection
- **News sources:** RSS feeds for Reuters, Bloomberg, Caixin; keyword monitoring via search APIs
- **AI classification:** DeepSeek (user's existing agent) with structured classification prompt
- **Scheduled polling:** Can be implemented via cron-based recurring tasks. Each monitoring point's scheduled sources define their own polling frequency
- **Companion file:** Full source registry at `world/intelligence_source_registry.yaml` — created during implementation, not during design phase

## What This Does NOT Do

- Does NOT predict policy changes — only retrieves and classifies information that has already been published or signaled
- Does NOT replace human judgment in Tier 3 — the bidirectional Feynman protocol (ADR-012) remains the final arbiter. This system only determines *what enters* the pipeline, not *how it is processed*
- Does NOT automate Tier 3 triggering for Tier C/D sources — media reports must be corroborated by official sources before escalation
- Does NOT track informal political intelligence (factional dynamics, internal debates) — only officially observable signals. Unverifiable political rumors are explicitly excluded
- Does NOT attempt real-time processing — scheduled polling + event-driven scan have latency (minutes to hours). This is by design: the system monitors structural change, not intraday trading signals

## Rationale

The three-tier update protocol (ADR-012) is only as good as the information that feeds it. Without a defined retrieval architecture, the Agent would either:

1. **Over-rely on ad-hoc web search** — missing scheduled releases, reacting late to structural changes, and being biased toward whatever the search engine surfaces (the retrieval bias problem from ADR-007)
2. **Treat all sources equally** — causing a Reuters headline to trigger the same processing as an NPC legislative announcement, leading to either alert fatigue (if everything triggers Tier 3) or dangerous under-reaction (if nothing does)

The source authority hierarchy solves problem 2. The dual-mode retrieval solves problem 1. The AI classification pipeline provides the connective tissue — determining which tier each piece of information should enter. The noise filtering mechanisms ensure the system remains usable over time.

The Chinese multi-layer signal system (§6) is a domain-specific contribution: Chinese policy retrieval cannot use the same logic as US policy retrieval because the signaling mechanisms are fundamentally different. The four-layer structure (leadership speech → editorial → formal document → implementation) has no direct US equivalent.

The personnel surveillance (§7) addresses the user's explicit concern about "政治情报" (political intelligence). By treating personnel changes as leading indicators that activate watch mode (rather than as direct triggers), the system captures the political dimension without over-reacting to rumor or speculation.

## References

- ADR-012: Fisher Layer Update Protocol — three-tier structure (this ADR defines its sensory input)
- ADR-011: Fisher Layer Mundell-Fleming framework (the data structure receiving updates)
- ADR-008: CBC Simulator Governance Paradigm (Tier 3.6 FOMC diff feeds the governance paradigm master switch)
- ADR-007: Investment Committee Architecture (three-layer memory structure — `world/` directory)
- ADR-004: Fact-Opinion-Inference Tagging (source authority tiers map to fact/signal tagging)
- Grilling session (2026-07-07): User proposed bidirectional Feynman method and requested intelligence retrieval system design
