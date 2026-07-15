"""SFM Engine — wraps factor computation from scripts into a clean API.

Provides a unified interface to the SFM layer's factor computation,
abstracting away the individual script invocations. Used by both the
backtesting engine and the live pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd

from claw_quant.backtest.data_loader import DailyState, HistoricalDataLoader
from claw_quant.config import (
    DURATION_BUCKETS,
    FACTOR_TO_BUCKET,
    FACTOR_ALIASES,
    resolve_factor_name,
)


@dataclass
class SFMInterface:
    """SFM layer output conforming to the Graham Interface Contract.

    Exactly 6 fields, ≤400 tokens total, factual expression only.
    """
    phase: str = "neutral"  # short_favored / medium_favored / long_favored / neutral
    preferred_factors: list[str] = field(default_factory=list)  # ≤3 items
    key_signal_1: str = ""  # ≤20 tokens, factual (e.g., "IC half-life 70.9d (stable)")
    key_signal_2: str = ""  # ≤20 tokens, factual (e.g., "crowding 0.36 (low)")
    gradient_direction: str = "stable"  # flowing_to_short / flowing_to_medium / flowing_to_long / stable
    confidence: float = 0.5  # 0-1 scalar


class SFMEngine:
    """Wraps SFM layer factor computation into a clean API.

    Usage:
        engine = SFMEngine()
        interface = engine.get_sfm_interface(date_str)
        print(interface.preferred_factors)
    """

    def __init__(self, loader: Optional[HistoricalDataLoader] = None):
        self.loader = loader or HistoricalDataLoader()

    def get_sfm_interface(
        self,
        date: str,
        fisher_config: Optional[dict] = None,
    ) -> SFMInterface:
        """Compute the SFM interface for a given date.

        Args:
            date: Date string in YYYY-MM-DD format.
            fisher_config: Optional Fisher state override.

        Returns:
            SFMInterface with 6 fields, compressing the full SFM state.
        """
        state = self.loader.get_daily_state(date, fisher_config)

        # Determine phase (which duration bucket is favored)
        phase = self._determine_phase(state)

        # Select preferred factors
        preferred = self._select_preferred_factors(state, top_n=3)

        # Build key signals
        signal_1 = self._build_key_signal_1(state, preferred)
        signal_2 = self._build_key_signal_2(state, preferred)

        # Gradient direction
        gradient = self._determine_gradient(state)

        # Confidence
        confidence = self._compute_confidence(state, preferred)

        return SFMInterface(
            phase=phase,
            preferred_factors=preferred,
            key_signal_1=signal_1,
            key_signal_2=signal_2,
            gradient_direction=gradient,
            confidence=confidence,
        )

    def _determine_phase(self, state: DailyState) -> str:
        """Determine which duration bucket is favored.

        Compares the average IC strength across short, medium, and long
        buckets. Returns the bucket with the highest average IC.
        """
        bucket_ics: dict[str, list[float]] = {
            "short_term": [],
            "medium_term": [],
            "long_term": [],
        }

        for bucket, factors in DURATION_BUCKETS.items():
            for factor in factors:
                ic = state.factor_ic.get(factor, 0.0)
                bucket_ics[bucket].append(abs(ic))

        # Average IC per bucket
        avg_ics = {
            b: np.mean(ics) if ics else 0.0
            for b, ics in bucket_ics.items()
        }

        max_avg = max(avg_ics.values())
        if max_avg < 0.01:
            return "neutral"

        if avg_ics["short_term"] > avg_ics["medium_term"] and avg_ics["short_term"] > avg_ics["long_term"]:
            return "short_favored"
        elif avg_ics["medium_term"] > avg_ics["short_term"] and avg_ics["medium_term"] > avg_ics["long_term"]:
            return "medium_favored"
        elif avg_ics["long_term"] > avg_ics["short_term"] and avg_ics["long_term"] > avg_ics["medium_term"]:
            return "long_favored"
        return "neutral"

    def _select_preferred_factors(
        self, state: DailyState, top_n: int = 3
    ) -> list[str]:
        """Select preferred factors by IC strength, excluding crowded/reversing."""
        candidates = []
        for factor, ic in state.factor_ic.items():
            if abs(ic) < 0.01:
                continue
            decay = state.factor_decay_status.get(factor, "stable")
            if decay == "reversing":
                continue
            crowding = state.crowding_score.get(factor, 0.5)
            if crowding > 0.65:
                continue
            candidates.append((factor, abs(ic)))

        candidates.sort(key=lambda x: x[1], reverse=True)
        return [f for f, _ in candidates[:top_n]]

    def _build_key_signal_1(self, state: DailyState, preferred: list[str]) -> str:
        """Build first key signal: IC and half-life of strongest factor."""
        if not preferred:
            return "no_clear_signal"
        top = preferred[0]
        ic = state.factor_ic.get(top, 0.0)
        hl = state.factor_half_life.get(top, 0.0)
        decay = state.factor_decay_status.get(top, "stable")
        return f"IC({top})={ic:.3f} HL={hl:.0f}d ({decay})"

    def _build_key_signal_2(self, state: DailyState, preferred: list[str]) -> str:
        """Build second key signal: crowding of preferred factors."""
        if not preferred:
            return "no_clear_signal"
        crowding_scores = [
            state.crowding_score.get(f, 0.0) for f in preferred
        ]
        avg_crowding = np.mean(crowding_scores) if crowding_scores else 0.0
        level = "low" if avg_crowding < 0.35 else ("moderate" if avg_crowding < 0.60 else "high")
        return f"crowding {avg_crowding:.2f} ({level})"

    def _determine_gradient(self, state: DailyState) -> str:
        """Determine gradient direction from CFFEX signals and factor trends."""
        # Use CFFEX aggregate signal as a proxy for gradient
        cffex_net = sum(state.cffex_signals.values())
        if cffex_net > 1000:
            return "flowing_to_long"
        elif cffex_net < -1000:
            return "flowing_to_short"

        # Otherwise, use the phase
        phase = self._determine_phase(state)
        if phase == "long_favored":
            return "flowing_to_long"
        elif phase == "short_favored":
            return "flowing_to_short"
        return "stable"

    def _compute_confidence(self, state: DailyState, preferred: list[str]) -> float:
        """Compute SFM confidence based on signal quality.

        Confidence is based on:
        - Number of preferred factors found
        - Average IC of preferred factors
        - Carhart IR
        """
        if not preferred:
            return 0.2

        avg_ic = np.mean([
            abs(state.factor_ic.get(f, 0.0)) for f in preferred
        ])
        ic_score = min(avg_ic / 0.05, 1.0)  # IC=0.05 => full score

        ir_score = min(abs(state.carhart_information_ratio) / 1.0, 1.0)

        n_score = min(len(preferred) / 3, 1.0)

        confidence = 0.4 * ic_score + 0.4 * ir_score + 0.2 * n_score
        return round(max(min(confidence, 1.0), 0.1), 2)