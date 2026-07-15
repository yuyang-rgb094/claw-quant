"""Layer refresh manager — coordinates refresh cycles with cascade logic.

Each layer has a defined refresh cadence, freshness thresholds, and
cascade rules. When an upstream layer refreshes and its key signals
change direction, downstream layers are automatically triggered to
re-evaluate.

Cascade chain: Fisher → SFM → Graham → Markowitz

The RefreshManager integrates with:
- Scheduler: executes underlying scripts/data fetches
- FreshnessTracker: checks staleness to trigger refreshes
- SFMEngine / GrahamEngine: re-evaluates layer outputs
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional

from claw_quant.freshness import FreshnessTracker

logger = logging.getLogger("claw_quant.refresh")


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class RefreshStatus:
    """Current refresh state of a single layer."""
    layer: str
    last_refreshed: Optional[datetime] = None
    freshness: str = "unknown"  # fresh / stale / expired / never
    next_scheduled: Optional[datetime] = None
    pending_cascade: bool = False
    cascade_from: Optional[str] = None
    refresh_count: int = 0


@dataclass
class RefreshResult:
    """Result of a single layer refresh operation."""
    layer: str
    trigger: str = "manual"  # scheduled / triggered / manual
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    success: bool = False
    state_before: dict = field(default_factory=dict)
    state_after: dict = field(default_factory=dict)
    direction_changed: bool = False
    cascade_triggered: list[str] = field(default_factory=list)
    message: str = ""


# ---------------------------------------------------------------------------
# Layer refresh configuration
# ---------------------------------------------------------------------------

LAYER_CADENCES = {
    "fisher": {
        "description": "Monetary environment — Fed cycle, PBoC, transmission channels",
        "scheduled": {
            "daily": ["fed_watch", "northbound_flows", "ust_10y", "vix", "usd_index"],
            "weekly": ["fed_balance_sheet"],
            "monthly": ["m2_china", "cpi_pce"],
        },
        "fresh_threshold_hours": 12,    # 0.5 day
        "stale_threshold_hours": 24,    # 1 day → auto-refresh
        "downstream": ["sfm"],
        "cascade_condition": "direction_changed",
        "key_fields": ["stock_vs_cash", "fed_cycle_phase"],
    },
    "sfm": {
        "description": "Factor manifold — Carhart, IC, crowding, gradient",
        "scheduled": {
            "daily": ["cffex", "crowding"],
            "weekly": ["carhart", "factor_ic", "options_proxy"],
        },
        "fresh_threshold_hours": 12,
        "stale_threshold_hours": 24,
        "downstream": ["graham"],
        "cascade_condition": "factor_preference_changed",
        "key_fields": ["phase", "preferred_factors", "gradient_direction"],
    },
    "graham": {
        "description": "Investment belief formation — thesis, conviction, expectation gap",
        "scheduled": {},
        "fresh_threshold_hours": 168,    # 7 days
        "stale_threshold_hours": 336,    # 14 days
        "downstream": ["markowitz"],
        "cascade_condition": "conviction_changed",
        "key_fields": ["conviction", "conviction_tier", "is_defensive"],
    },
    "markowitz": {
        "description": "Portfolio construction — weights, risk budget, alpha capture",
        "scheduled": {},
        "fresh_threshold_hours": 168,
        "stale_threshold_hours": 336,
        "downstream": [],
        "cascade_condition": None,
        "key_fields": ["factor_weights", "equity_exposure", "risk_budget"],
    },
    "damodaran": {
        "description": "Cross-section supervisor — constraints, belief pool, forward valuation",
        "scheduled": {
            "weekly": ["constraint_scan"],
            "monthly": ["forward_valuation"],
        },
        "fresh_threshold_hours": 168,
        "stale_threshold_hours": 336,
        "downstream": [],
        "cascade_condition": None,
        "key_fields": ["constraint_violations", "aggregate_forward_return"],
    },
}

# Refresh order (topological sort of the cascade DAG)
REFRESH_ORDER = ["fisher", "sfm", "graham", "markowitz", "damodaran"]


# ---------------------------------------------------------------------------
# RefreshManager
# ---------------------------------------------------------------------------

class RefreshManager:
    """Coordinates refresh cycles across all layers with cascade logic.

    Usage:
        rm = RefreshManager()
        result = rm.refresh("fisher")    # Refreshes Fisher, cascades to SFM if needed
        status = rm.get_status("sfm")     # Check SFM refresh state
        rm.check_and_refresh()            # Auto-refresh any stale layers
    """

    def __init__(self):
        self._status: dict[str, RefreshStatus] = {
            layer: RefreshStatus(layer=layer) for layer in REFRESH_ORDER
        }
        self._freshness = FreshnessTracker()
        self._history: list[RefreshResult] = []

    # ------------------------------------------------------------------
    # Core refresh method
    # ------------------------------------------------------------------

    def refresh(self, layer: str, trigger: str = "manual") -> RefreshResult:
        """Refresh a specific layer and cascade to downstream layers.

        Args:
            layer: Layer name (fisher/sfm/graham/markowitz/damodaran).
            trigger: What triggered this refresh (scheduled/triggered/manual).

        Returns:
            RefreshResult with the refresh outcome and cascade chain.
        """
        if layer not in LAYER_CADENCES:
            return RefreshResult(
                layer=layer,
                trigger=trigger,
                success=False,
                message=f"Unknown layer: {layer}",
            )

        cadence = LAYER_CADENCES[layer]
        result = RefreshResult(layer=layer, trigger=trigger)

        # Step 1: Capture state before refresh
        result.state_before = self._capture_state(layer)

        # Step 2: Execute the refresh
        result.success = self._execute_refresh(layer, trigger)

        if not result.success:
            result.message = f"Refresh failed for {layer}"
            return result

        # Step 3: Capture state after refresh
        result.state_after = self._capture_state(layer)

        # Step 4: Check if key fields changed direction
        result.direction_changed = self._detect_direction_change(
            layer, result.state_before, result.state_after
        )

        # Step 5: Update status
        status = self._status[layer]
        status.last_refreshed = datetime.now()
        status.freshness = "fresh"
        status.refresh_count += 1
        status.pending_cascade = False
        status.cascade_from = None

        # Step 6: Cascade to downstream layers if direction changed
        if result.direction_changed and cadence.get("downstream"):
            for downstream in cadence["downstream"]:
                cascade_result = self.refresh(downstream, trigger="triggered")
                result.cascade_triggered.append(downstream)
                # Mark downstream as pending cascade from this layer
                self._status[downstream].pending_cascade = True
                self._status[downstream].cascade_from = layer

        result.message = self._build_message(layer, result)
        self._history.append(result)

        logger.info(
            "Refreshed %s (trigger=%s, success=%s, direction_changed=%s, cascade=%s)",
            layer, trigger, result.success, result.direction_changed,
            result.cascade_triggered,
        )

        return result

    # ------------------------------------------------------------------
    # Batch refresh
    # ------------------------------------------------------------------

    def check_and_refresh(self) -> dict[str, RefreshResult]:
        """Check all layers and auto-refresh any that are stale.

        Refreshes layers in topological order (fisher first, then SFM, etc.)
        so that cascade triggers are handled correctly.

        Returns:
            Dict mapping layer name to RefreshResult.
        """
        results: dict[str, RefreshResult] = {}

        for layer in REFRESH_ORDER:
            status = self._status[layer]
            cadence = LAYER_CADENCES[layer]

            # Check if this layer needs refresh
            needs_refresh = False
            reason = ""

            if status.last_refreshed is None:
                needs_refresh = True
                reason = "never refreshed"
            elif status.pending_cascade:
                needs_refresh = True
                reason = f"pending cascade from {status.cascade_from}"
            else:
                # Check staleness
                age_hours = (datetime.now() - status.last_refreshed).total_seconds() / 3600
                stale_threshold = cadence.get("stale_threshold_hours", 72)
                if age_hours > stale_threshold:
                    needs_refresh = True
                    reason = f"stale ({age_hours:.1f}h > {stale_threshold}h threshold)"

            if needs_refresh:
                trigger = "triggered" if status.pending_cascade else "scheduled"
                logger.info("Auto-refreshing %s: %s", layer, reason)
                results[layer] = self.refresh(layer, trigger=trigger)
            else:
                results[layer] = RefreshResult(
                    layer=layer,
                    trigger="scheduled",
                    success=True,
                    message=f"Already fresh (last: {status.last_refreshed})",
                )

        return results

    def refresh_all(self) -> dict[str, RefreshResult]:
        """Force-refresh all layers in order.

        Returns:
            Dict mapping layer name to RefreshResult.
        """
        results: dict[str, RefreshResult] = {}
        for layer in REFRESH_ORDER:
            results[layer] = self.refresh(layer, trigger="manual")
        return results

    # ------------------------------------------------------------------
    # Status queries
    # ------------------------------------------------------------------

    def get_status(self, layer: str) -> RefreshStatus:
        """Get the current refresh status of a layer."""
        if layer not in self._status:
            return RefreshStatus(layer=layer)

        status = self._status[layer]
        cadence = LAYER_CADENCES.get(layer, {})

        # Update freshness based on age
        if status.last_refreshed is not None:
            age_hours = (datetime.now() - status.last_refreshed).total_seconds() / 3600
            fresh_threshold = cadence.get("fresh_threshold_hours", 24)
            stale_threshold = cadence.get("stale_threshold_hours", 72)

            if age_hours <= fresh_threshold:
                status.freshness = "fresh"
            elif age_hours <= stale_threshold:
                status.freshness = "stale"
            else:
                status.freshness = "expired"

            # Calculate next scheduled refresh
            if cadence.get("scheduled"):
                # Simplest: next scheduled is fresh_threshold from last refresh
                status.next_scheduled = status.last_refreshed + timedelta(
                    hours=fresh_threshold
                )
        else:
            status.freshness = "never"

        return status

    def get_all_status(self) -> dict[str, RefreshStatus]:
        """Get refresh status for all layers."""
        return {layer: self.get_status(layer) for layer in REFRESH_ORDER}

    def get_refresh_chain(self, layer: str) -> list[str]:
        """Get the cascade chain starting from a layer.

        Returns the ordered list of layers that would be refreshed
        if this layer is refreshed and direction changes at each step.
        """
        chain = [layer]
        current = layer
        while True:
            cadence = LAYER_CADENCES.get(current, {})
            downstream = cadence.get("downstream", [])
            if not downstream:
                break
            # Take the first downstream (cascade is linear)
            current = downstream[0]
            chain.append(current)
        return chain

    def get_history(self, limit: int = 20) -> list[RefreshResult]:
        """Get recent refresh history."""
        return self._history[-limit:]

    # ------------------------------------------------------------------
    # Internal methods
    # ------------------------------------------------------------------

    def _execute_refresh(self, layer: str, trigger: str) -> bool:
        """Execute the actual refresh for a layer.

        Fisher: update from fisher_state.md (or external data)
        SFM: re-run factor computation via SFMEngine
        Graham: re-form beliefs via GrahamEngine
        Markowitz: re-construct portfolio via MarkowitzEngine
        Damodaran: re-scan constraints
        """
        try:
            if layer == "fisher":
                return self._refresh_fisher()
            elif layer == "sfm":
                return self._refresh_sfm()
            elif layer == "graham":
                return self._refresh_graham()
            elif layer == "markowitz":
                return self._refresh_markowitz()
            elif layer == "damodaran":
                return self._refresh_damodaran()
            return False
        except Exception as e:
            logger.error("Refresh %s failed: %s", layer, e)
            return False

    def _refresh_fisher(self) -> bool:
        """Refresh Fisher layer.

        Currently reads the fisher_state.md file. In production, this would
        fetch external data (Fed H.4.1, CME FedWatch, northbound flows, etc.)
        and update the state file.
        """
        from claw_quant.fisher_automation import FisherStateUpdater

        updater = FisherStateUpdater()
        # Create a snapshot for historical record
        updater.snapshot()
        return True

    def _refresh_sfm(self) -> bool:
        """Refresh SFM layer.

        Re-computes the SFM interface from current database data.
        In production, this would run the daily/weekly scripts first.
        """
        from claw_quant.sfm_engine import SFMEngine

        engine = SFMEngine()
        today = datetime.now().strftime("%Y-%m-%d")
        interface = engine.get_sfm_interface(today)
        return interface is not None

    def _refresh_graham(self) -> bool:
        """Refresh Graham layer.

        Re-forms investment beliefs using the latest Fisher and SFM interfaces.
        """
        from claw_quant.graham_engine import GrahamEngine
        from claw_quant.sfm_engine import SFMEngine
        from claw_quant.fisher_automation import FisherStateUpdater

        sfm = SFMEngine()
        graham = GrahamEngine()
        fisher = FisherStateUpdater()

        today = datetime.now().strftime("%Y-%m-%d")
        sfm_interface = sfm.get_sfm_interface(today)
        fisher_interface = fisher.get_fisher_interface()

        decision = graham.form_belief(
            sfm_interface,
            fisher_stock_vs_cash=fisher_interface.get("stock_vs_cash", "neutral"),
            fisher_max_equity=float(
                fisher_interface.get("position_constraint", "max_equity: 0.8")
                .replace("max_equity: ", "")
            ),
        )
        return decision is not None

    def _refresh_markowitz(self) -> bool:
        """Refresh Markowitz layer.

        Re-constructs portfolio from latest Graham decision.
        """
        from claw_quant.graham_engine import GrahamEngine
        from claw_quant.markowitz_engine import MarkowitzEngine
        from claw_quant.sfm_engine import SFMEngine
        from claw_quant.fisher_automation import FisherStateUpdater

        sfm = SFMEngine()
        graham = GrahamEngine()
        markowitz = MarkowitzEngine()
        fisher = FisherStateUpdater()

        today = datetime.now().strftime("%Y-%m-%d")
        sfm_interface = sfm.get_sfm_interface(today)
        fisher_interface = fisher.get_fisher_interface()

        decision = graham.form_belief(
            sfm_interface,
            fisher_stock_vs_cash=fisher_interface.get("stock_vs_cash", "neutral"),
        )
        allocation = markowitz.construct_portfolio(decision)
        return allocation is not None

    def _refresh_damodaran(self) -> bool:
        """Refresh Damodaran cross-section supervisor.

        Re-scans all constraints across active theses and holdings.
        """
        # For now, run a constraint check via the Markowitz engine
        from claw_quant.markowitz_engine import MarkowitzEngine
        from claw_quant.graham_engine import GrahamDecision

        engine = MarkowitzEngine()
        decision = GrahamDecision(
            preferred_factors=[],
            conviction_tier="medium",
        )
        allocation = engine.construct_portfolio(decision)
        return allocation is not None

    def _capture_state(self, layer: str) -> dict:
        """Capture the current key fields of a layer for change detection."""
        cadence = LAYER_CADENCES.get(layer, {})
        key_fields = cadence.get("key_fields", [])

        if not key_fields:
            return {}

        try:
            if layer == "fisher":
                from claw_quant.fisher_automation import FisherStateUpdater
                updater = FisherStateUpdater()
                interface = updater.get_fisher_interface()
                return {k: interface.get(k) for k in key_fields if k in interface}

            elif layer == "sfm":
                from claw_quant.sfm_engine import SFMEngine
                engine = SFMEngine()
                today = datetime.now().strftime("%Y-%m-%d")
                interface = engine.get_sfm_interface(today)
                return {
                    "phase": interface.phase,
                    "preferred_factors": interface.preferred_factors,
                    "gradient_direction": interface.gradient_direction,
                }

            elif layer == "graham":
                from claw_quant.graham_engine import GrahamEngine
                from claw_quant.sfm_engine import SFMEngine
                engine = SFMEngine()
                graham = GrahamEngine()
                today = datetime.now().strftime("%Y-%m-%d")
                sfm = engine.get_sfm_interface(today)
                decision = graham.form_belief(sfm)
                return {
                    "conviction": decision.conviction,
                    "conviction_tier": decision.conviction_tier,
                    "is_defensive": decision.is_defensive,
                }

            elif layer == "markowitz":
                from claw_quant.markowitz_engine import MarkowitzEngine
                from claw_quant.graham_engine import GrahamDecision
                engine = MarkowitzEngine()
                decision = GrahamDecision(preferred_factors=[], conviction_tier="medium")
                allocation = engine.construct_portfolio(decision)
                return {
                    "factor_weights": allocation.factor_weights,
                    "equity_exposure": allocation.total_equity_exposure,
                    "risk_budget": allocation.effective_risk_budget,
                }

            return {}
        except Exception as e:
            logger.warning("Failed to capture state for %s: %s", layer, e)
            return {}

    def _detect_direction_change(
        self,
        layer: str,
        before: dict,
        after: dict,
    ) -> bool:
        """Detect whether key fields changed direction between two states.

        Direction change means the qualitative assessment changed
        (e.g., 'stocks_favored' → 'cash_favored'), not just a numerical shift.

        Returns:
            True if a direction change was detected.
        """
        if not before or not after:
            return False

        cadence = LAYER_CADENCES.get(layer, {})
        condition = cadence.get("cascade_condition")

        if condition == "direction_changed":
            # Fisher: stock_vs_cash or fed_cycle_phase changed
            for field in ["stock_vs_cash", "fed_cycle_phase", "phase"]:
                if field in before and field in after:
                    if before[field] != after[field]:
                        return True

        elif condition == "factor_preference_changed":
            # SFM: preferred_factors or gradient_direction changed
            if "preferred_factors" in before and "preferred_factors" in after:
                if set(before["preferred_factors"]) != set(after["preferred_factors"]):
                    return True
            if "gradient_direction" in before and "gradient_direction" in after:
                if before["gradient_direction"] != after["gradient_direction"]:
                    return True

        elif condition == "conviction_changed":
            # Graham: conviction tier changed
            if "conviction_tier" in before and "conviction_tier" in after:
                if before["conviction_tier"] != after["conviction_tier"]:
                    return True
            # Or conviction changed by > 0.15
            if "conviction" in before and "conviction" in after:
                if abs(before["conviction"] - after["conviction"]) > 0.15:
                    return True

        return False

    def _build_message(self, layer: str, result: RefreshResult) -> str:
        """Build a human-readable message for the refresh result."""
        parts = [f"{layer} refreshed ({result.trigger})"]
        if result.direction_changed:
            parts.append("DIRECTION CHANGED")
        if result.cascade_triggered:
            parts.append(f"→ cascaded to {', '.join(result.cascade_triggered)}")
        return " | ".join(parts)