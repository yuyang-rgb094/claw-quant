"""Fisher layer automation — structured state updates and historical snapshots.

The Fisher layer is currently a manually-filled markdown file. This module
provides a structured update mechanism and, critically, creates timestamped
snapshots that enable historical Fisher state replay in backtesting.
"""

from __future__ import annotations

import logging
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional

import yaml

from claw_quant.config import FISHER_STATE_PATH, DATA_DIR

logger = logging.getLogger("claw_quant.fisher_automation")

FISHER_SNAPSHOTS_DIR = DATA_DIR / "fisher_snapshots"


class FisherStateUpdater:
    """Reads, updates, and snapshots the Fisher layer state file.

    Usage:
        updater = FisherStateUpdater()
        updater.snapshot()  # Save current state as historical snapshot
        updater.update_field("composite_assessment", {"stock_vs_cash_baseline": "stocks_favored"})
    """

    def __init__(self):
        self.state_path = FISHER_STATE_PATH
        self.snapshots_dir = FISHER_SNAPSHOTS_DIR

    def read_state(self) -> dict:
        """Read the current Fisher state as a dict.

        Parses the YAML sections embedded in fisher_state.md.
        """
        if not self.state_path.exists():
            logger.warning("Fisher state file not found: %s", self.state_path)
            return {}

        content = self.state_path.read_text(encoding="utf-8")

        # Extract YAML blocks from markdown
        state = {}
        in_yaml = False
        yaml_lines = []
        for line in content.split("\n"):
            if line.strip().startswith("```yaml"):
                in_yaml = True
                yaml_lines = []
                continue
            if line.strip().startswith("```") and in_yaml:
                in_yaml = False
                try:
                    block = yaml.safe_load("\n".join(yaml_lines))
                    if isinstance(block, dict):
                        state.update(block)
                except yaml.YAMLError:
                    pass
                continue
            if in_yaml:
                yaml_lines.append(line)

        return state

    def get_fisher_interface(self) -> dict:
        """Extract the fisher_interface (6 fields, ≤400 tokens) from state.

        Returns:
            Dict with keys: phase, stock_vs_cash, key_signal_1, key_signal_2,
            position_constraint, confidence, plus freshness info.
        """
        from claw_quant.freshness import FreshnessTracker

        state = self.read_state()
        tracker = FreshnessTracker()
        freshness = tracker.check("fisher")

        # Build interface from composite assessment or defaults
        composite = state.get("composite_assessment", {})
        if not composite:
            return {
                "phase": "neutral",
                "stock_vs_cash": "neutral",
                "key_signal_1": "no_data",
                "key_signal_2": "no_data",
                "position_constraint": "max_equity: 0.8",
                "confidence": 0.5,
                "data_freshness": freshness.status,
                "last_updated": freshness.last_updated.isoformat() if freshness.last_updated else None,
                "freshness_multiplier": tracker.get_confidence_multiplier("fisher"),
            }

        return {
            "phase": composite.get("fed_cycle_phase", "neutral"),
            "stock_vs_cash": composite.get("stock_vs_cash_baseline", "neutral"),
            "key_signal_1": composite.get("signal_1", "no_data"),
            "key_signal_2": composite.get("signal_2", "no_data"),
            "position_constraint": f"max_equity: {composite.get('position_constraint', {}).get('max_aggregate_equity', 0.8)}",
            "confidence": composite.get("confidence", 0.5),
            "data_freshness": freshness.status,
            "last_updated": freshness.last_updated.isoformat() if freshness.last_updated else None,
            "freshness_multiplier": tracker.get_confidence_multiplier("fisher"),
        }

    def snapshot(self, date: Optional[str] = None) -> Path:
        """Create a timestamped snapshot of the current Fisher state.

        This is the critical function for backtesting — it creates historical
        snapshots that the backtesting engine can replay.

        Args:
            date: Optional date string for the snapshot filename.
                 Defaults to today's date.

        Returns:
            Path to the created snapshot file.
        """
        if not self.state_path.exists():
            raise FileNotFoundError(f"Fisher state file not found: {self.state_path}")

        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")

        self.snapshots_dir.mkdir(parents=True, exist_ok=True)
        snapshot_path = self.snapshots_dir / f"{date}.md"

        shutil.copy2(self.state_path, snapshot_path)
        logger.info("Fisher snapshot created: %s", snapshot_path)
        return snapshot_path

    def get_historical_snapshot(self, date: str) -> Optional[dict]:
        """Retrieve a historical Fisher state snapshot.

        Args:
            date: Date string in YYYY-MM-DD format.

        Returns:
            Parsed state dict, or None if no snapshot exists for that date.
        """
        snapshot_path = self.snapshots_dir / f"{date}.md"
        if not snapshot_path.exists():
            # Find the most recent snapshot before the given date
            snapshots = sorted(self.snapshots_dir.glob("*.md"))
            for snap in reversed(snapshots):
                snap_date = snap.stem
                if snap_date <= date:
                    snapshot_path = snap
                    break
            else:
                return None

        # Read and parse the snapshot
        temp_path = self.state_path
        # We need to temporarily swap the path
        self.state_path = snapshot_path
        try:
            return self.read_state()
        finally:
            self.state_path = temp_path

    def has_snapshot(self, date: str) -> bool:
        """Check if a snapshot exists for the given date."""
        return (self.snapshots_dir / f"{date}.md").exists()

    def list_snapshots(self) -> list[str]:
        """List all available snapshot dates."""
        if not self.snapshots_dir.exists():
            return []
        return sorted([
            p.stem for p in self.snapshots_dir.glob("*.md")
        ])