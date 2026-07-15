"""Task scheduler for Claw Quant automated pipeline runs.

Provides daily, weekly, and monthly run schedules. Designed to be invoked
by the AI Agent or by cron. The Agent says "run the weekly update" and the
scheduler executes all scripts in order, updating state files and databases.
"""

from __future__ import annotations

import logging
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from claw_quant.config import PROJECT_ROOT, SCRIPTS_DIR

logger = logging.getLogger("claw_quant.scheduler")


class Scheduler:
    """Lightweight task scheduler for automated pipeline runs.

    Usage:
        sched = Scheduler()
        sched.run_daily()   # CFFEX + crowding
        sched.run_weekly()  # Carhart + IC + options proxy + SFM state update
        sched.run_monthly() # Full backfill + performance report
    """

    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run
        self.results: dict[str, bool] = {}

    def run_daily(self) -> dict[str, bool]:
        """Run daily tasks: CFFEX scraper, crowding update."""
        logger.info("Running daily tasks...")
        self.results = {}

        # CFFEX scraper
        self.results["cffex_scraper"] = self._run_script(
            "cffex_scraper.py", ["--date", "yesterday"]
        )

        # Crowding update
        self.results["crowding"] = self._run_script(
            "long_short_cost.py", ["--factor", "all", "--output", "yaml"]
        )

        return self.results

    def run_weekly(self) -> dict[str, bool]:
        """Run weekly tasks: Carhart, IC, options proxy, SFM state update."""
        logger.info("Running weekly tasks...")
        self.results = {}

        # Carhart regression
        self.results["carhart"] = self._run_script(
            "carhart_regression.py", ["--output", "sfm_state.md"]
        )

        # Factor IC engine
        self.results["factor_ic"] = self._run_script(
            "factor_ic_engine.py", ["--factor", "all", "--output", "yaml"]
        )

        # Options proxy
        self.results["options_proxy"] = self._run_script(
            "options_proxy.py", ["--method", "proxy", "--output", "yaml"]
        )

        # SFM state update
        self.results["sfm_update"] = self._update_sfm_state()

        logger.info(
            "Weekly tasks complete: %d/%d successful",
            sum(self.results.values()),
            len(self.results),
        )
        return self.results

    def run_monthly(self) -> dict[str, bool]:
        """Run monthly tasks: full backfill, performance report."""
        logger.info("Running monthly tasks...")
        self.results = {}

        # Full backfill for all scripts
        self.results["carhart_backfill"] = self._run_script(
            "carhart_regression.py", ["--backfill"]
        )

        # Generate performance report
        self.results["performance_report"] = self._generate_performance_report()

        logger.info(
            "Monthly tasks complete: %d/%d successful",
            sum(self.results.values()),
            len(self.results),
        )
        return self.results

    def run_all(self) -> dict[str, bool]:
        """Run all tasks (daily + weekly)."""
        daily = self.run_daily()
        weekly = self.run_weekly()
        return {**daily, **weekly}

    def run_layer_refresh(self, layer: str, tasks: list[str]) -> dict[str, bool]:
        """Execute a specific set of refresh tasks for a layer.

        Called by RefreshManager to execute the scheduled tasks
        for a given layer.

        Args:
            layer: Layer name (fisher/sfm/graham/markowitz/damodaran).
            tasks: List of task names to execute (e.g., ['cffex', 'crowding']).

        Returns:
            Dict mapping task name to success status.
        """
        results = {}
        task_map = {
            # Fisher tasks
            "fed_watch": (None, None),  # Manual/LLM task
            "northbound_flows": (None, None),  # Requires external data
            "ust_10y": (None, None),
            "vix": (None, None),
            "usd_index": (None, None),
            "fed_balance_sheet": (None, None),
            "m2_china": (None, None),
            "cpi_pce": (None, None),
            # SFM tasks
            "cffex": ("cffex_scraper.py", ["--date", "yesterday"]),
            "crowding": ("long_short_cost.py", ["--factor", "all", "--output", "yaml"]),
            "carhart": ("carhart_regression.py", ["--output", "sfm_state.md"]),
            "factor_ic": ("factor_ic_engine.py", ["--factor", "all", "--output", "yaml"]),
            "options_proxy": ("options_proxy.py", ["--method", "proxy", "--output", "yaml"]),
            # Damodaran tasks
            "constraint_scan": (None, None),  # Logical check, not a script
            "forward_valuation": (None, None),  # Logical check, not a script
        }

        for task in tasks:
            if task not in task_map:
                logger.warning("Unknown task: %s for layer %s", task, layer)
                results[task] = False
                continue

            script, args = task_map[task]
            if script is None:
                # Task that doesn't map to a script (manual or logical)
                logger.info("Task %s (%s): no script, marked as done", task, layer)
                results[task] = True
            else:
                results[task] = self._run_script(script, args)

        return results

    def _run_script(self, script_name: str, args: list[str]) -> bool:
        """Run a Python script from the scripts/ directory.

        Args:
            script_name: Name of the script file (e.g., "carhart_regression.py").
            args: Command-line arguments to pass.

        Returns:
            True if the script exited with code 0, False otherwise.
        """
        script_path = SCRIPTS_DIR / script_name
        if not script_path.exists():
            logger.error("Script not found: %s", script_path)
            return False

        cmd = [sys.executable, str(script_path)] + args
        logger.info("Running: %s", " ".join(cmd))

        if self.dry_run:
            logger.info("[DRY RUN] Would execute: %s", " ".join(cmd))
            return True

        try:
            result = subprocess.run(
                cmd,
                cwd=str(PROJECT_ROOT),
                capture_output=True,
                text=True,
                timeout=600,  # 10 minute timeout
            )
            if result.returncode != 0:
                logger.error(
                    "Script %s failed (code %d): %s",
                    script_name,
                    result.returncode,
                    result.stderr[:500],
                )
                return False
            logger.info("Script %s completed successfully", script_name)
            return True
        except subprocess.TimeoutExpired:
            logger.error("Script %s timed out", script_name)
            return False
        except Exception as e:
            logger.error("Script %s error: %s", script_name, e)
            return False

    def _update_sfm_state(self) -> bool:
        """Update sfm_state.md with latest data from all modules."""
        try:
            from claw_quant.sfm_updater import SFMUpdater

            updater = SFMUpdater()
            updater.update_all()
            return True
        except Exception as e:
            logger.error("SFM state update failed: %s", e)
            return False

    def _generate_performance_report(self) -> bool:
        """Generate a monthly performance report."""
        try:
            from claw_quant.backtest.data_loader import HistoricalDataLoader
            from claw_quant.backtest.engine import BacktestConfig, BacktestEngine
            from claw_quant.backtest.report import generate_report

            loader = HistoricalDataLoader()
            start, end = loader.get_date_range()

            config = BacktestConfig(
                start_date=start,
                end_date=end,
                fisher_stock_vs_cash="neutral",
            )
            engine = BacktestEngine(loader, config)
            result = engine.run()

            report_path = PROJECT_ROOT / "data" / f"performance_report_{datetime.now().strftime('%Y%m')}.md"
            generate_report(result, output_path=str(report_path))
            logger.info("Performance report generated: %s", report_path)
            return True
        except Exception as e:
            logger.error("Performance report generation failed: %s", e)
            return False