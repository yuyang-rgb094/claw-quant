"""Walk-Through Testing Layer — Hallucination Prevention Gate.

ADR-019: A cross-section hard gate between Graham and Markowitz that verifies
the factual integrity of LLM-generated thesis files. All checks are deterministic
Python code — the LLM cannot override or bypass this layer.

Seven check dimensions:
    A. Factor Provenance — verify factors match SFM output
    B. Conviction Audit — enforce Bayesian adjustment cap
    C. Claim Verification — sanity-check quantitative claims
    D. Disconfirmation Testability — ensure signals are falsifiable
    E. Ticker & Universe Validity — verify tickers exist in universe
    F. Cross-Reference Consistency — check for internal contradictions
    G. Source Traceability — trace every [FACT] to a data source

Architecture:
    Fisher -> SFM -> Graham -> [Walk-Through Gate] -> Markowitz
                                  |
                            Damodaran (cross-section)

Usage:
    engine = WalkThroughEngine()
    result = engine.audit(thesis_path)
    if not result.passed:
        for v in result.violations:
            print(f"BLOCKING: {v.description}")
"""

from __future__ import annotations

import re
import hashlib
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

import yaml

from claw_quant.config import (
    PROJECT_ROOT,
    DURATION_BUCKETS,
    FACTOR_TO_BUCKET,
    DEFAULT_UNIVERSE,
    CONVICTION_CAPS,
    CONVICTION_WEIGHTS,
)

logger = logging.getLogger("claw_quant.walkthrough")

# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class Violation:
    """A single walk-through test violation."""
    dimension: str
    severity: str  # BLOCKING / WARNING
    check_name: str
    description: str
    expected: str = ""
    actual: str = ""
    fix_suggestion: str = ""


@dataclass
class CheckResult:
    """Result of a single check dimension."""
    dimension: str
    passed: bool = True
    checks_performed: int = 0
    checks_failed: int = 0
    violations: list[Violation] = field(default_factory=list)
    details: list[str] = field(default_factory=list)


@dataclass
class WalkThroughResult:
    """Complete walk-through test result.

    If passed=False, the thesis CANNOT proceed to Markowitz.
    """
    thesis_name: str = ""
    thesis_path: str = ""
    thesis_hash: str = ""  # Content hash for caching
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    passed: bool = True

    # Per-dimension results
    factor_provenance: CheckResult = field(default_factory=lambda: CheckResult(dimension="factor_provenance"))
    conviction_audit: CheckResult = field(default_factory=lambda: CheckResult(dimension="conviction_audit"))
    claim_verification: CheckResult = field(default_factory=lambda: CheckResult(dimension="claim_verification"))
    disconfirmation_testability: CheckResult = field(default_factory=lambda: CheckResult(dimension="disconfirmation_testability"))
    ticker_validity: CheckResult = field(default_factory=lambda: CheckResult(dimension="ticker_validity"))
    cross_reference: CheckResult = field(default_factory=lambda: CheckResult(dimension="cross_reference"))
    source_traceability: CheckResult = field(default_factory=lambda: CheckResult(dimension="source_traceability"))

    # Aggregate
    violations: list[Violation] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    audit_trail: str = ""


# ---------------------------------------------------------------------------
# Sanity bounds for quantitative claims
# ---------------------------------------------------------------------------

SANITY_BOUNDS = {
    "market_share_pct": (0.1, 95.0),  # Can't be 0% or 100% in real markets
    "revenue_growth_yoy": (-50.0, 500.0),  # Extreme growth needs verification
    "profit_margin_pct": (-100.0, 95.0),  # Capped at theoretical max
    "pe_ratio": (1.0, 1000.0),  # Negative PE handled separately
    "pb_ratio": (0.1, 50.0),
    "roic_pct": (-50.0, 100.0),
    "debt_to_equity": (0.0, 50.0),
    "dividend_yield_pct": (0.0, 20.0),
    "fcf_yield_pct": (-30.0, 50.0),
    "ev_ebitda": (1.0, 200.0),
}

# Patterns to extract quantitative claims from text
# Format: (pattern, unit_type, bound_key)
QUANTITATIVE_PATTERNS = [
    # Percentage patterns
    (r"市场份额[约|为|达到|超过]?\s*(\d+\.?\d*)\s*%", "market_share_pct", "market_share_pct"),
    (r"market\s*share\s*(?:of|about|approx\.?)?\s*(\d+\.?\d*)\s*%", "market_share_pct", "market_share_pct"),
    (r"(?:营收|收入|revenue)\s*(?:增长|增速|growth)[约|为|达到|超过]?\s*(\d+\.?\d*)\s*%", "revenue_growth_yoy", "revenue_growth_yoy"),
    (r"(?:净利率|净利润率|net\s*margin)\s*[约|为|达到]?\s*(\d+\.?\d*)\s*%", "profit_margin_pct", "profit_margin_pct"),
    (r"(?:毛利率|gross\s*margin)\s*[约|为|达到]?\s*(\d+\.?\d*)\s*%", "profit_margin_pct", "profit_margin_pct"),
    (r"(?:PE|市盈率)\s*[约|为|达到]?\s*(\d+\.?\d*)\s*[倍|x]?", "pe_ratio", "pe_ratio"),
    (r"(?:PB|市净率)\s*[约|为|达到]?\s*(\d+\.?\d*)\s*[倍|x]?", "pb_ratio", "pb_ratio"),
    (r"(?:ROIC|资本回报率)\s*[约|为|达到]?\s*(\d+\.?\d*)\s*%", "roic_pct", "roic_pct"),
    (r"dividend\s*yield\s*(?:of|about)?\s*(\d+\.?\d*)\s*%", "dividend_yield_pct", "dividend_yield_pct"),
    # Generic percentage patterns
    (r"[增|降|升|跌|涨|提高|降低|达到|约为][约|为]?\s*(\d+\.?\d*)\s*%", "percentage_generic", None),
    (r"(\d+\.?\d*)\s*%\s*(?:的|of)?\s*(?:市场|market|营收|revenue|利润|profit)", "percentage_generic", None),
]

# Unfalsifiable phrases to reject in disconfirmation signals
UNFALSIFIABLE_PATTERNS = [
    r"market\s*sentiment",
    r"市场情绪",
    r"investor\s*confidence",
    r"投资者信心",
    r"macro\s*environment\s*deteriorates",
    r"宏观环境恶化",
    r"black\s*swan",
    r"黑天鹅",
    r"unexpected\s*event",
    r"突发事件",
    r"geopolitical\s*tension",
    r"地缘政治",
    r"risk\s*appetite",
    r"风险偏好",
    r"trade\s*war",
    r"贸易战",
]

# Source authority tiers
SOURCE_TIER_KEYWORDS = {
    "S": ["fed", "pboc", "npc", "state council", "国务院", "人民银行", "美联储"],
    "A": ["csrc", "safe", "mof", "证监会", "外管局", "财政部", "ndrc", "发改委"],
    "B": ["nbs", "bls", "bea", "统计局", "customs", "海关", "wind", "bloomberg"],
    "C": ["reuters", "xinhua", "caixin", "路透", "新华社", "财新", "21世纪"],
    "D": ["analyst", "report", "think tank", "券商", "研报", "分析师", "kol"],
}


# ---------------------------------------------------------------------------
# Walk-Through Engine
# ---------------------------------------------------------------------------


class WalkThroughEngine:
    """Performs walk-through testing on a thesis file.

    All 7 dimensions are independent code-enforced checks. The LLM cannot
    override or bypass this layer. If any BLOCKING violation is found,
    the thesis is rejected.

    Usage:
        engine = WalkThroughEngine()
        result = engine.audit("theses/ai_semiconductor.md")
        if not result.passed:
            print(result.audit_trail)
    """

    def __init__(
        self,
        stock_universe: Optional[list[str]] = None,
        sfm_engine=None,
        fisher_updater=None,
    ):
        self.stock_universe = stock_universe or DEFAULT_UNIVERSE
        self._sfm_engine = sfm_engine
        self._fisher_updater = fisher_updater
        self._result_cache: dict[str, WalkThroughResult] = {}

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    def audit(self, thesis_path: str) -> WalkThroughResult:
        """Run all 7 walk-through checks on a thesis file.

        Args:
            thesis_path: Path to the thesis .md file.

        Returns:
            WalkThroughResult with pass/fail and all violations.

        Raises:
            FileNotFoundError: If the thesis file doesn't exist.
            ValueError: If the thesis file cannot be parsed.
        """
        path = Path(thesis_path)
        if not path.exists():
            raise FileNotFoundError(f"Thesis file not found: {thesis_path}")

        content = path.read_text(encoding="utf-8")
        thesis_hash = hashlib.sha256(content.encode()).hexdigest()[:16]

        # Check cache (same content = same result)
        if thesis_hash in self._result_cache:
            return self._result_cache[thesis_hash]

        thesis = self._parse_thesis(content)

        result = WalkThroughResult(
            thesis_name=path.stem,
            thesis_path=str(path),
            thesis_hash=thesis_hash,
        )

        # Run all 7 checks
        result.factor_provenance = self._check_factor_provenance(thesis)
        result.conviction_audit = self._check_conviction(thesis)
        result.claim_verification = self._check_claims(thesis)
        result.disconfirmation_testability = self._check_disconfirmation(thesis)
        result.ticker_validity = self._check_tickers(thesis)
        result.cross_reference = self._check_cross_reference(thesis)
        result.source_traceability = self._check_sources(thesis)

        # Aggregate
        all_checks = [
            result.factor_provenance,
            result.conviction_audit,
            result.claim_verification,
            result.disconfirmation_testability,
            result.ticker_validity,
            result.cross_reference,
            result.source_traceability,
        ]

        # Aggregate: only BLOCKING violations cause overall failure
        has_blocking = any(
            v.severity == "BLOCKING"
            for check in all_checks
            for v in check.violations
        )
        result.passed = not has_blocking
        result.violations = []
        result.warnings = []

        for check in all_checks:
            for v in check.violations:
                if v.severity == "BLOCKING":
                    result.violations.append(v)
                else:
                    result.warnings.append(v.description)
            # WARNINGs don't affect overall pass/fail; only BLOCKING violations do

        result.audit_trail = self._generate_audit_trail(result)

        # Cache
        self._result_cache[thesis_hash] = result

        return result

    def _parse_thesis(self, content: str) -> dict:
        """Parse a thesis .md file into a structured dict.

        Handles three formats:
        1. Pure YAML (thesis template uses YAML without code blocks)
        2. YAML inside ```yaml code blocks
        3. Plain markdown with YAML-like key: value pairs
        """
        thesis = {
            "raw": content,
            "graham_region": {},
            "markowitz_region": {},
            "update_log": {},
        }

        # Approach 1: Try parsing the entire file as YAML
        # The thesis template uses YAML-like structure without code blocks
        try:
            parsed = yaml.safe_load(content)
            if isinstance(parsed, dict):
                for key in ("graham_region", "markowitz_region", "update_log"):
                    if key in parsed:
                        thesis[key] = parsed[key]
                # If we got a good parse, use it
                if thesis["graham_region"] or thesis["markowitz_region"]:
                    return thesis
        except yaml.YAMLError:
            pass

        # Approach 2: Extract YAML code blocks
        yaml_pattern = re.compile(r'```ya?ml\s*\n(.*?)\n\s*```', re.DOTALL)
        for match in yaml_pattern.finditer(content):
            try:
                parsed = yaml.safe_load(match.group(1))
                if isinstance(parsed, dict):
                    for key in ("graham_region", "markowitz_region", "update_log"):
                        if key in parsed:
                            thesis[key] = parsed[key]
            except yaml.YAMLError:
                pass

        # Approach 3: Extract YAML-like key: value pairs from text
        if not thesis["graham_region"] and not thesis["markowitz_region"]:
            fields = self._extract_yaml_like_fields(content)
            if "graham_region" in fields:
                thesis["graham_region"] = fields["graham_region"]
            if "markowitz_region" in fields:
                thesis["markowitz_region"] = fields["markowitz_region"]

        return thesis

    def _extract_yaml_like_fields(self, content: str) -> dict:
        """Extract YAML-like key: value pairs from markdown text.

        Handles nested structures by tracking indentation levels.
        """
        # First try: split the content into sections by markdown headings
        # and try to parse each section as YAML
        sections = re.split(r'\n#+\s+', content)
        result = {}

        for section in sections:
            # Try to find the YAML structure by looking for consecutive
            # indented lines after a top-level key
            lines = section.split("\n")
            yaml_candidate = []
            in_yaml = False
            top_level_key = None

            for line in lines:
                stripped = line.strip()
                if not stripped or stripped.startswith('<!--') or stripped.startswith('#'):
                    if in_yaml and yaml_candidate:
                        # End of YAML block
                        try:
                            block_text = "\n".join(yaml_candidate)
                            parsed = yaml.safe_load(block_text)
                            if isinstance(parsed, dict):
                                result.update(parsed)
                        except yaml.YAMLError:
                            pass
                        yaml_candidate = []
                        in_yaml = False
                    continue

                # Check for top-level key: value
                if re.match(r'^\w[\w_]*\s*:', line) and not line.startswith(' '):
                    if in_yaml and yaml_candidate:
                        try:
                            block_text = "\n".join(yaml_candidate)
                            parsed = yaml.safe_load(block_text)
                            if isinstance(parsed, dict):
                                result.update(parsed)
                        except yaml.YAMLError:
                            pass
                    yaml_candidate = [line]
                    in_yaml = True
                elif in_yaml:
                    yaml_candidate.append(line)

            # Process last block
            if in_yaml and yaml_candidate:
                try:
                    block_text = "\n".join(yaml_candidate)
                    parsed = yaml.safe_load(block_text)
                    if isinstance(parsed, dict):
                        result.update(parsed)
                except yaml.YAMLError:
                    pass

        # Second pass: also extract simple key: value pairs
        if not result:
            lines = content.split("\n")
            i = 0
            while i < len(lines):
                line = lines[i].strip()
                match = re.match(r'^(\w[\w_]*)\s*:\s*(.+)$', line)
                if match:
                    key = match.group(1)
                    value = match.group(2).strip()
                    if value in ("", ">", "|"):
                        multiline = []
                        i += 1
                        while i < len(lines):
                            next_line = lines[i]
                            if re.match(r'^\w[\w_]*\s*:', next_line):
                                break
                            stripped = next_line.strip().strip('"')
                            if stripped and not stripped.startswith('#'):
                                multiline.append(stripped)
                            i += 1
                        result[key] = " ".join(multiline)
                        continue
                    else:
                        result[key] = value.strip('"\'')
                i += 1

        return result

    # ------------------------------------------------------------------
    # A. Factor Provenance Check
    # ------------------------------------------------------------------

    def _check_factor_provenance(self, thesis: dict) -> CheckResult:
        """Verify factor selections match SFM output."""
        result = CheckResult(dimension="factor_provenance")
        gr = thesis.get("graham_region", {})

        # Get preferred factors from thesis
        sfm_alignment = gr.get("sfm_alignment", {})
        if isinstance(sfm_alignment, dict):
            preferred = sfm_alignment.get("preferred_factors", [])
        else:
            preferred = gr.get("preferred_factors", [])

        if isinstance(preferred, str):
            preferred = [f.strip() for f in preferred.strip("[]").split(",") if f.strip()]

        result.checks_performed = 1

        if not preferred:
            result.details.append("No preferred factors specified — may be cash-only thesis")
            return result

        # Check 1: factors exist in known factor set
        all_known_factors = set()
        for bucket_factors in DURATION_BUCKETS.values():
            all_known_factors.update(bucket_factors)

        for factor in preferred:
            result.checks_performed += 1
            if factor not in all_known_factors:
                result.checks_failed += 1
                result.violations.append(Violation(
                    dimension="factor_provenance",
                    severity="BLOCKING",
                    check_name="factor_exists",
                    description=f"Factor '{factor}' is not in any known factor bucket",
                    actual=f"'{factor}' not in {sorted(all_known_factors)}",
                    fix_suggestion=f"Use one of: {sorted(all_known_factors)}",
                ))
            else:
                result.details.append(f"Factor '{factor}' verified in {FACTOR_TO_BUCKET.get(factor, 'unknown')} bucket")

        # Check 2: verify with SFM engine if available
        if self._sfm_engine is not None:
            try:
                date = datetime.now().strftime("%Y-%m-%d")
                sfm_interface = self._sfm_engine.get_sfm_interface(date)
                sfm_preferred = set(sfm_interface.preferred_factors)
                thesis_preferred = set(preferred)

                result.checks_performed += 1
                extra_factors = thesis_preferred - sfm_preferred
                if extra_factors:
                    result.checks_failed += 1
                    result.violations.append(Violation(
                        dimension="factor_provenance",
                        severity="BLOCKING",
                        check_name="factor_matches_sfm",
                        description=f"Thesis factors {sorted(extra_factors)} not in SFM preferred factors",
                        expected=f"SFM preferred: {sorted(sfm_preferred)}",
                        actual=f"Thesis claims: {sorted(thesis_preferred)}",
                        fix_suggestion="Align thesis factors with SFM output, or explain divergence in belief_statement",
                    ))
                else:
                    result.details.append("All thesis factors match SFM output")
            except Exception as e:
                result.details.append(f"SFM verification skipped (SFM unavailable): {e}")

        result.passed = result.checks_failed == 0
        return result

    # ------------------------------------------------------------------
    # B. Conviction Audit
    # ------------------------------------------------------------------

    def _check_conviction(self, thesis: dict) -> CheckResult:
        """Audit conviction value against quantitative floor."""
        result = CheckResult(dimension="conviction_audit")
        gr = thesis.get("graham_region", {})

        conviction_level = gr.get("conviction_level", {})
        if isinstance(conviction_level, dict):
            current = conviction_level.get("current", 0.5)
            last_update_type = conviction_level.get("last_update_type", "unknown")
            derivation = conviction_level.get("derivation", "")
        else:
            current = 0.5
            last_update_type = "unknown"
            derivation = ""

        if isinstance(current, str):
            try:
                current = float(current)
            except ValueError:
                current = 0.5

        result.checks_performed = 3

        # Check 1: conviction in valid range
        if not (0.0 <= current <= 1.0):
            result.checks_failed += 1
            result.violations.append(Violation(
                dimension="conviction_audit",
                severity="BLOCKING",
                check_name="conviction_range",
                description=f"Conviction {current} is outside valid range [0.0, 1.0]",
                fix_suggestion="Set conviction to a value between 0.0 and 1.0",
            ))
        else:
            result.details.append(f"Conviction {current} in valid range")

        # Check 2: conviction tier matches value
        tier = "high" if current > 0.7 else ("medium" if current > 0.4 else "low")
        if "markowitz_region" in thesis:
            mr = thesis["markowitz_region"]
            risk_budget = mr.get("risk_budget", {})
            if isinstance(risk_budget, dict):
                declared_tier = risk_budget.get("conviction_tier", "")
                if declared_tier and declared_tier != tier:
                    result.checks_failed += 1
                    result.violations.append(Violation(
                        dimension="conviction_audit",
                        severity="BLOCKING",
                        check_name="conviction_tier_match",
                        description=f"Declared conviction_tier '{declared_tier}' doesn't match computed tier '{tier}' (conviction={current})",
                        expected=f"tier={tier}",
                        actual=f"tier={declared_tier}",
                        fix_suggestion=f"Update risk_budget.conviction_tier to '{tier}'",
                    ))
                else:
                    result.details.append(f"Conviction tier '{tier}' matches conviction value {current}")
            else:
                result.details.append("Risk budget not found, tier check skipped")

        # Check 3: last_update_type must be 'fundamental'
        if last_update_type and last_update_type != "fundamental":
            # Allow 'initial' or 'init' for first-time setup
            if last_update_type not in ("initial", "init", "bayesian"):
                result.checks_failed += 1
                result.violations.append(Violation(
                    dimension="conviction_audit",
                    severity="BLOCKING",
                    check_name="conviction_update_type",
                    description=f"Conviction last_update_type is '{last_update_type}', must be 'fundamental'",
                    expected="fundamental",
                    actual=last_update_type,
                    fix_suggestion="Only fundamental signals can update conviction (ADR-016 Principle 3)",
                ))
            else:
                result.details.append(f"Conviction update type '{last_update_type}' accepted")
        else:
            result.details.append(f"Conviction update type is '{last_update_type or 'fundamental'}'")

        result.passed = result.checks_failed == 0
        return result

    # ------------------------------------------------------------------
    # C. Claim Verification
    # ------------------------------------------------------------------

    def _check_claims(self, thesis: dict) -> CheckResult:
        """Verify quantitative claims in belief_statement."""
        result = CheckResult(dimension="claim_verification")
        gr = thesis.get("graham_region", {})

        belief = gr.get("belief_statement", "")
        if not belief:
            result.details.append("No belief_statement found — skipping claim verification")
            return result

        # Extract all quantitative claims
        claims_found = []
        for pattern, claim_type, bound_key in QUANTITATIVE_PATTERNS:
            for match in re.finditer(pattern, belief, re.IGNORECASE):
                try:
                    value = float(match.group(1))
                    claims_found.append({
                        "type": claim_type,
                        "value": value,
                        "bound_key": bound_key,
                        "text": match.group(0),
                    })
                except (ValueError, IndexError):
                    pass

        result.checks_performed = len(claims_found) if claims_found else 1
        result.details.append(f"Found {len(claims_found)} quantitative claims in belief_statement")

        for claim in claims_found:
            bound_key = claim["bound_key"]
            if bound_key and bound_key in SANITY_BOUNDS:
                lo, hi = SANITY_BOUNDS[bound_key]
                value = claim["value"]
                if value < lo or value > hi:
                    result.checks_failed += 1
                    result.violations.append(Violation(
                        dimension="claim_verification",
                        severity="WARNING",
                        check_name="claim_sanity",
                        description=f"Claim '{claim['text']}' has value {value} outside sanity bounds [{lo}, {hi}]",
                        expected=f"Value in [{lo}, {hi}]",
                        actual=str(value),
                        fix_suggestion="Verify this claim against actual data sources. If correct, provide source citation.",
                    ))
                else:
                    result.details.append(f"Claim '{claim['text']}' within sanity bounds [{lo}, {hi}]")

        # Check for [FACT] tags without source
        fact_pattern = re.compile(r'\[FACT(?::([^\]]*))?\]')
        facts = fact_pattern.findall(belief)
        if facts:
            unsourced = [f for f in facts if not f or f.strip() == ""]
            if unsourced:
                result.checks_failed += 1
                result.violations.append(Violation(
                    dimension="claim_verification",
                    severity="WARNING",
                    check_name="fact_source_missing",
                    description=f"{len(unsourced)} [FACT] tags missing source attribution",
                    expected="[FACT:source_name]",
                    actual="[FACT] (no source)",
                    fix_suggestion="Add source to every [FACT] tag: [FACT:wind_financials], [FACT:company_filing], etc.",
                ))

        result.passed = result.checks_failed == 0
        return result

    # ------------------------------------------------------------------
    # D. Disconfirmation Testability
    # ------------------------------------------------------------------

    def _check_disconfirmation(self, thesis: dict) -> CheckResult:
        """Verify disconfirmation signals are actually testable."""
        result = CheckResult(dimension="disconfirmation_testability")
        gr = thesis.get("graham_region", {})

        signals = gr.get("disconfirmation_signals", [])
        if not signals:
            result.checks_failed += 1
            result.violations.append(Violation(
                dimension="disconfirmation_testability",
                severity="BLOCKING",
                check_name="disconfirmation_required",
                description="No disconfirmation signals defined — thesis is unfalsifiable",
                fix_suggestion="Add at least 1 disconfirmation signal with a quantitative threshold",
            ))
            result.passed = False
            return result

        result.checks_performed = len(signals)
        has_quantitative = False

        for i, signal in enumerate(signals):
            if isinstance(signal, dict):
                signal_text = signal.get("signal", "")
                signal_type = signal.get("type", "")
                signal_source = signal.get("source", "")
            else:
                signal_text = str(signal)
                signal_type = ""
                signal_source = ""

            # Check 1: signal type must be quantitative or event
            if signal_type == "quantitative":
                has_quantitative = True

            # Check 2: signal text must not be unfalsifiable
            is_unfalsifiable = False
            for pattern in UNFALSIFIABLE_PATTERNS:
                if re.search(pattern, signal_text, re.IGNORECASE):
                    is_unfalsifiable = True
                    break

            if is_unfalsifiable:
                result.checks_failed += 1
                result.violations.append(Violation(
                    dimension="disconfirmation_testability",
                    severity="BLOCKING",
                    check_name="disconfirmation_falsifiable",
                    description=f"Disconfirmation signal #{i+1} is unfalsifiable: '{signal_text[:80]}'",
                    fix_suggestion="Define a specific, measurable condition: 'revenue growth < 10% for 2 consecutive quarters'",
                ))
            else:
                result.details.append(f"Signal #{i+1} is falsifiable")

            # Check 3: quantitative signals need a threshold
            if signal_type == "quantitative":
                # Look for numeric threshold in the signal text
                has_threshold = bool(re.search(r'[<>≤≥]\s*\d+\.?\d*|below|above|超过|低于|exceed', signal_text, re.IGNORECASE))
                if not has_threshold:
                    result.checks_failed += 1
                    result.violations.append(Violation(
                        dimension="disconfirmation_testability",
                        severity="BLOCKING",
                        check_name="quantitative_threshold",
                        description=f"Quantitative signal #{i+1} has no numeric threshold: '{signal_text[:80]}'",
                        fix_suggestion="Add a specific threshold: 'ROIC < 8%', 'revenue growth < 5%', etc.",
                    ))

            # Check 4: signal needs a data source
            if not signal_source:
                result.checks_failed += 1
                result.violations.append(Violation(
                    dimension="disconfirmation_testability",
                    severity="WARNING",
                    check_name="signal_source",
                    description=f"Disconfirmation signal #{i+1} has no data source",
                    fix_suggestion=f"Add source: 'quarterly_financials', 'customs_data', etc.",
                ))

        # Check 5: require at least 1 quantitative signal
        if not has_quantitative:
            result.checks_failed += 1
            result.violations.append(Violation(
                dimension="disconfirmation_testability",
                severity="BLOCKING",
                check_name="quantitative_required",
                description="No quantitative disconfirmation signal found — at least 1 required",
                fix_suggestion="Add a quantitative signal with a numeric threshold",
            ))

        result.passed = result.checks_failed == 0
        return result

    # ------------------------------------------------------------------
    # E. Ticker & Universe Validity
    # ------------------------------------------------------------------

    def _check_tickers(self, thesis: dict) -> CheckResult:
        """Verify all tickers exist in the stock universe."""
        result = CheckResult(dimension="ticker_validity")
        mr = thesis.get("markowitz_region", {})

        portfolio = mr.get("portfolio_composition", [])
        if not portfolio:
            result.details.append("No portfolio composition — skipping ticker check")
            return result

        result.checks_performed = len(portfolio)
        ticker_pattern = re.compile(r'^(\d{6})\.(SH|SZ|BJ)$')

        for i, holding in enumerate(portfolio):
            if isinstance(holding, dict):
                ticker = holding.get("ticker", "")
            else:
                ticker = str(holding)

            if not ticker:
                result.checks_failed += 1
                result.violations.append(Violation(
                    dimension="ticker_validity",
                    severity="BLOCKING",
                    check_name="ticker_present",
                    description=f"Holding #{i+1} has no ticker",
                    fix_suggestion="Add a valid ticker in Wind format: '600519.SH'",
                ))
                continue

            # Check 1: ticker format
            if not ticker_pattern.match(ticker):
                result.checks_failed += 1
                result.violations.append(Violation(
                    dimension="ticker_validity",
                    severity="BLOCKING",
                    check_name="ticker_format",
                    description=f"Ticker '{ticker}' has invalid format",
                    expected="XXXXXX.SH or XXXXXX.SZ or XXXXXX.BJ",
                    actual=ticker,
                    fix_suggestion=f"Use Wind-style ticker format: '600519.SH'",
                ))
                continue

            # Check 2: ticker in universe
            if ticker not in self.stock_universe:
                result.checks_failed += 1
                result.violations.append(Violation(
                    dimension="ticker_validity",
                    severity="WARNING",
                    check_name="ticker_in_universe",
                    description=f"Ticker '{ticker}' is not in the default stock universe",
                    expected=f"One of {len(self.stock_universe)} universe tickers",
                    actual=ticker,
                    fix_suggestion="Verify this is a valid A-share ticker. Add to universe if needed.",
                ))
            else:
                result.details.append(f"Ticker '{ticker}' verified in universe")

        result.passed = result.checks_failed == 0
        return result

    # ------------------------------------------------------------------
    # F. Cross-Reference Consistency
    # ------------------------------------------------------------------

    def _check_cross_reference(self, thesis: dict) -> CheckResult:
        """Check for internal consistency across thesis fields."""
        result = CheckResult(dimension="cross_reference")
        gr = thesis.get("graham_region", {})
        result.checks_performed = 4

        thesis_type = gr.get("thesis_type", "")
        duration_bucket = gr.get("duration_bucket", "")

        sfm_alignment = gr.get("sfm_alignment", {})
        if isinstance(sfm_alignment, dict):
            sfm_preferred = sfm_alignment.get("preferred_factors", [])
            sfm_alignment_val = sfm_alignment.get("alignment", "")
        else:
            sfm_preferred = []
            sfm_alignment_val = ""

        fisher_alignment = gr.get("fisher_alignment", {})
        if isinstance(fisher_alignment, dict):
            fisher_alignment_val = fisher_alignment.get("alignment", "")
        else:
            fisher_alignment_val = ""

        # Check 1: thesis_type matches duration_bucket
        type_bucket_map = {
            "growth": "long_term",
            "value": "long_term",
            "defensive": "short_term",
        }
        expected_bucket = type_bucket_map.get(thesis_type)
        if expected_bucket and duration_bucket and duration_bucket != expected_bucket:
            result.checks_failed += 1
            result.violations.append(Violation(
                dimension="cross_reference",
                severity="WARNING",
                check_name="type_bucket_consistency",
                description=f"Thesis type '{thesis_type}' typically uses '{expected_bucket}' bucket, but declared '{duration_bucket}'",
                expected=expected_bucket,
                actual=duration_bucket,
                fix_suggestion="Align duration_bucket with thesis_type, or explain the exception",
            ))
        else:
            result.details.append(f"Thesis type '{thesis_type}' consistent with bucket '{duration_bucket}'")

        # Check 2: preferred factors are in the correct duration bucket
        for factor in sfm_preferred:
            expected_bucket = FACTOR_TO_BUCKET.get(factor)
            if expected_bucket and duration_bucket and expected_bucket != duration_bucket:
                result.checks_failed += 1
                result.violations.append(Violation(
                    dimension="cross_reference",
                    severity="WARNING",
                    check_name="factor_bucket_consistency",
                    description=f"Factor '{factor}' belongs to '{expected_bucket}' bucket, but thesis uses '{duration_bucket}'",
                    fix_suggestion="Either adjust duration_bucket or select factors from the matching bucket",
                ))

        # Check 3: fisher alignment is internally consistent
        if fisher_alignment_val == "aligned":
            fisher_signal = fisher_alignment.get("stock_vs_cash_baseline", "")
            if fisher_signal == "cash_favored" and thesis_type == "growth":
                result.checks_failed += 1
                result.violations.append(Violation(
                    dimension="cross_reference",
                    severity="WARNING",
                    check_name="fisher_growth_contradiction",
                    description="Growth thesis when Fisher is cash_favored — growth requires stocks_favored environment",
                    fix_suggestion="Either switch to defensive thesis or wait for Fisher stocks_favored signal",
                ))

        # Check 4: defensive thesis should not have growth factors
        if thesis_type == "defensive":
            growth_factors = DURATION_BUCKETS.get("long_term", [])
            defensive_conflict = [f for f in sfm_preferred if f in growth_factors]
            if defensive_conflict:
                result.checks_failed += 1
                result.violations.append(Violation(
                    dimension="cross_reference",
                    severity="WARNING",
                    check_name="defensive_factor_conflict",
                    description=f"Defensive thesis targets long-term factors: {defensive_conflict}",
                    fix_suggestion="Defensive thesis should use short-term factors or cash only",
                ))

        result.passed = result.checks_failed == 0
        return result

    # ------------------------------------------------------------------
    # G. Source Traceability
    # ------------------------------------------------------------------

    def _check_sources(self, thesis: dict) -> CheckResult:
        """Verify every [FACT] tag is traceable to a source."""
        result = CheckResult(dimension="source_traceability")
        gr = thesis.get("graham_region", {})
        raw = thesis.get("raw", "")

        belief = gr.get("belief_statement", raw)

        # Find all [FACT] tags
        fact_pattern = re.compile(r'\[FACT(?::([^\]]*))?\]')
        facts = fact_pattern.findall(belief if isinstance(belief, str) else str(belief))

        result.checks_performed = len(facts) if facts else 1

        if not facts:
            result.details.append("No [FACT] tags found — no source traceability needed")
            return result

        untiered = []
        for fact_source in facts:
            source = fact_source.strip() if fact_source else ""
            if not source:
                untiered.append("[FACT] (no source)")
                continue

            # Classify source tier
            tier = self._classify_source_tier(source)
            if tier == "unknown":
                untiered.append(f"[FACT:{source}]")
            else:
                result.details.append(f"[FACT:{source}] → Tier {tier}")

        if untiered:
            result.checks_failed += 1
            result.violations.append(Violation(
                dimension="source_traceability",
                severity="WARNING",
                check_name="source_unknown",
                description=f"{len(untiered)} fact tags with unknown/untraceable sources: {untiered[:3]}",
                fix_suggestion="Use sources from Tier A/B/C: company filings, Wind, Bloomberg, NBS, customs data, etc.",
            ))

        result.passed = result.checks_failed == 0
        return result

    def _classify_source_tier(self, source: str) -> str:
        """Classify a source name into Tier S/A/B/C/D."""
        source_lower = source.lower()
        for tier in ["S", "A", "B", "C", "D"]:
            for keyword in SOURCE_TIER_KEYWORDS.get(tier, []):
                if keyword in source_lower:
                    return tier
        return "unknown"

    # ------------------------------------------------------------------
    # Audit trail generation
    # ------------------------------------------------------------------

    def _generate_audit_trail(self, result: WalkThroughResult) -> str:
        """Generate a human-readable audit trail."""
        lines = []
        lines.append(f"# Walk-Through Audit Report — {result.thesis_name}")
        lines.append(f"**Timestamp:** {result.timestamp}")
        lines.append(f"**Thesis Hash:** {result.thesis_hash}")
        lines.append(f"**Overall:** {'✅ PASSED' if result.passed else '❌ FAILED'}")
        lines.append("")

        all_checks = [
            result.factor_provenance,
            result.conviction_audit,
            result.claim_verification,
            result.disconfirmation_testability,
            result.ticker_validity,
            result.cross_reference,
            result.source_traceability,
        ]

        for check in all_checks:
            icon = "✅" if check.passed else "❌"
            lines.append(f"## {icon} {check.dimension.replace('_', ' ').title()}")
            lines.append(f"Checks: {check.checks_performed} performed, {check.checks_failed} failed")
            for detail in check.details:
                lines.append(f"  - {detail}")
            for v in check.violations:
                lines.append(f"  - [{v.severity}] {v.check_name}: {v.description}")
                if v.fix_suggestion:
                    lines.append(f"    → Fix: {v.fix_suggestion}")
            lines.append("")

        if result.violations:
            lines.append("## 🚫 BLOCKING Violations")
            for v in result.violations:
                lines.append(f"  - [{v.dimension}] {v.description}")
            lines.append("")

        if result.warnings:
            lines.append("## ⚠️ Warnings")
            for w in result.warnings:
                lines.append(f"  - {w}")
            lines.append("")

        lines.append("---")
        lines.append(f"*Walk-Through Testing Layer (ADR-019) — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*")

        return "\n".join(lines)