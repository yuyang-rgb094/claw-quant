"""Shared test helpers for schema validation of .md state/template files.

These helpers parse YAML embedded in Markdown files (state files like
fisher_state.md, sfm_state.md, and template files) by stripping HTML
comment lines and parsing the remainder as YAML. Markdown headers (#)
are valid YAML comments, so they pass through cleanly.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Optional

import yaml

PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent


def parse_md_yaml(filepath: Path | str) -> dict[str, Any]:
    """Parse YAML from a .md file, stripping HTML comment lines.

    State files like fisher_state.md embed YAML after a markdown title.
    HTML comment lines (<!-- ... -->) are removed before parsing.
    Markdown header lines (# ...) are valid YAML comments and pass through.
    """
    path = Path(filepath)
    content = path.read_text(encoding="utf-8")
    # Remove HTML comment lines
    lines = [
        line for line in content.splitlines()
        if not line.strip().startswith("<!--")
    ]
    parsed = yaml.safe_load("\n".join(lines))
    if parsed is None:
        return {}
    if not isinstance(parsed, dict):
        raise ValueError(f"{filepath}: expected YAML dict, got {type(parsed).__name__}")
    return parsed


def md_file_exists(relative_path: str) -> bool:
    """Check if a file exists relative to project root."""
    return (PROJECT_ROOT / relative_path).exists()


def get_required_keys(schema_name: str) -> list[str]:
    """Return required top-level keys for a given schema (ADR-defined)."""
    schemas = {
        "fisher_state": [
            "global_financial_cycle",
            "transmission_channels",
            "a_share_marginal_liquidity",
            "composite_assessment",
        ],
        "thesis": [
            "graham_region",
            "markowitz_region",
        ],
        "holdings": [
            "holding_id",
            "ticker",
            "thesis_refs",
            "entry_date",
            "entry_price",
            "position_state",
            "execution_log",
        ],
        "capital_allocation_registry": [
            "total_capital",
            "fisher_max_aggregate_equity",
            "active_theses",
            "available_capital",
            "aggregate_equity_exposure",
        ],
        "damodaran_state": [
            "belief_pool",
            "holdings_pool",
            "constraints",
            "forward_valuation",
        ],
    }
    return schemas.get(schema_name, [])
