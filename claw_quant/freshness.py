"""State freshness tracker — monitors staleness of state files.

Each state file (fisher_state.md, sfm_state.md) should have a `last_updated`
field. The FreshnessTracker checks these timestamps and classifies freshness:

- fresh:  updated within the freshness threshold
- stale:  past the threshold but not yet expired
- expired: past the expiry threshold, data should not be used for decisions

Downstream layers (Graham) use this to adjust confidence:
- fresh → normal confidence
- stale → conviction × 0.9
- expired → conviction × 0.7, plus warning
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from claw_quant.config import (
    FISHER_STATE_PATH,
    SFM_STATE_PATH,
    DAMODARAN_STATE_PATH,
)


@dataclass
class FreshnessStatus:
    """Freshness assessment for a single state file."""
    file_path: str
    last_updated: Optional[datetime] = None
    age_hours: float = 0.0
    status: str = "unknown"  # fresh / stale / expired / missing
    message: str = ""


class FreshnessTracker:
    """Tracks the freshness of Claw Quant state files.

    Usage:
        tracker = FreshnessTracker()
        status = tracker.check("fisher")
        if status.status == "expired":
            print("WARNING: Fisher state is expired!")
    """

    # Default thresholds (in hours)
    DEFAULT_FRESH_THRESHOLD: float = 12.0    # 0.5 day
    DEFAULT_STALE_THRESHOLD: float = 24.0    # 1 day → auto-refresh
    DEFAULT_EXPIRED_THRESHOLD: float = 72.0   # 3 days

    def __init__(
        self,
        fresh_threshold: float = 12.0,
        stale_threshold: float = 24.0,
        expired_threshold: float = 72.0,
    ):
        self.fresh_threshold = fresh_threshold
        self.stale_threshold = stale_threshold
        self.expired_threshold = expired_threshold

    def check(self, state_name: str) -> FreshnessStatus:
        """Check the freshness of a named state file.

        Args:
            state_name: One of 'fisher', 'sfm', 'damodaran'.

        Returns:
            FreshnessStatus with age and classification.
        """
        state_paths = {
            "fisher": FISHER_STATE_PATH,
            "sfm": SFM_STATE_PATH,
            "damodaran": DAMODARAN_STATE_PATH,
        }

        path = state_paths.get(state_name)
        if path is None:
            return FreshnessStatus(
                file_path=str(path),
                status="unknown",
                message=f"Unknown state: {state_name}",
            )

        return self._check_file(path)

    def check_all(self) -> dict[str, FreshnessStatus]:
        """Check freshness of all state files."""
        return {
            name: self.check(name)
            for name in ["fisher", "sfm", "damodaran"]
        }

    def _check_file(self, path: Path) -> FreshnessStatus:
        """Check freshness of a single file."""
        status = FreshnessStatus(file_path=str(path))

        if not path.exists():
            status.status = "missing"
            status.message = f"File does not exist: {path}"
            return status

        # Get modification time
        mtime = datetime.fromtimestamp(path.stat().st_mtime)
        status.last_updated = mtime

        age = datetime.now() - mtime
        status.age_hours = age.total_seconds() / 3600

        if status.age_hours <= self.fresh_threshold:
            status.status = "fresh"
            status.message = f"Updated {self._format_age(status.age_hours)} ago"
        elif status.age_hours <= self.stale_threshold:
            status.status = "stale"
            status.message = (
                f"Stale — updated {self._format_age(status.age_hours)} ago. "
                f"Consider re-running the update."
            )
        elif status.age_hours <= self.expired_threshold:
            status.status = "expired"
            status.message = (
                f"EXPIRED — updated {self._format_age(status.age_hours)} ago. "
                f"Data may be unreliable."
            )
        else:
            status.status = "expired"
            status.message = (
                f"CRITICALLY EXPIRED — updated {self._format_age(status.age_hours)} ago. "
                f"Do not use for trading decisions."
            )

        return status

    def get_confidence_multiplier(self, state_name: str) -> float:
        """Get the confidence multiplier for a state file's freshness.

        - fresh: 1.0 (no adjustment)
        - stale: 0.9 (slight reduction)
        - expired: 0.7 (significant reduction)
        - missing: 0.5 (major reduction)

        This is used by the Graham engine to adjust conviction
        based on data freshness.
        """
        status = self.check(state_name)
        multipliers = {
            "fresh": 1.0,
            "stale": 0.9,
            "expired": 0.7,
            "missing": 0.5,
            "unknown": 0.8,
        }
        return multipliers.get(status.status, 0.8)

    def get_aggregate_freshness(self) -> float:
        """Get the aggregate freshness score across all state files.

        Returns a value 0.0-1.0 representing overall data freshness.
        """
        statuses = self.check_all()
        multipliers = [
            self.get_confidence_multiplier(name)
            for name in statuses
        ]
        return sum(multipliers) / len(multipliers) if multipliers else 0.5

    @staticmethod
    def _format_age(hours: float) -> str:
        """Format age in human-readable form."""
        if hours < 1:
            return f"{int(hours * 60)}m"
        elif hours < 24:
            return f"{hours:.0f}h"
        else:
            return f"{hours / 24:.1f}d"