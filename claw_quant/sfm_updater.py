"""SFM state file updater — centralizes writes to sfm_state.md.

Extracts the logic from the 5 scripts that writes to sfm_state.md and
centralizes it. Each module has its own update function that writes the
relevant YAML section to the state file.
"""

from __future__ import annotations

import logging
from datetime import datetime

from claw_quant.config import SFM_STATE_PATH

logger = logging.getLogger("claw_quant.sfm_updater")


class SFMUpdater:
    """Updates sfm_state.md with data from all SFM modules.

    Usage:
        updater = SFMUpdater()
        updater.update_module_1a(carhart_result)
        updater.update_module_1b(factor_reports)
        updater.update_sfm_interface()
        updater.update_all()
    """

    def __init__(self):
        self.state_path = SFM_STATE_PATH

    def update_all(self) -> bool:
        """Run all module updates and recompute the SFM interface.

        Returns:
            True if the state file was updated successfully.
        """
        try:
            # Update timestamp
            self._write_timestamp()

            # Recompute SFM interface
            self.update_sfm_interface()

            logger.info("SFM state updated: %s", self.state_path)
            return True
        except Exception as e:
            logger.error("SFM state update failed: %s", e)
            return False

    def update_sfm_interface(self) -> None:
        """Recompute the sfm_interface from current module data.

        The sfm_interface is a 6-field, ≤400 token compressed contract
        for the Graham layer. It summarizes the full SFM state into a
        balanced, factual format.
        """
        # Read current state
        current = self._read_state()

        # Build interface from current data
        interface = self._build_interface(current)

        # Write back
        self._write_section("sfm_interface", interface)

    def _read_state(self) -> dict:
        """Read the current SFM state file."""
        if not self.state_path.exists():
            return {}
        content = self.state_path.read_text(encoding="utf-8")
        # Simple parsing — in production, use proper YAML-within-markdown parsing
        return {"content": content}

    def _write_section(self, section_name: str, data: dict) -> None:
        """Write a YAML section to the state file.

        Creates the file if it doesn't exist, or appends/updates the section.
        """
        import yaml

        yaml_block = yaml.dump(data, default_flow_style=False, allow_unicode=True)
        section = f"\n# {section_name}\n```yaml\n{yaml_block}```\n"

        if self.state_path.exists():
            content = self.state_path.read_text(encoding="utf-8")
            # Replace existing section or append
            marker = f"# {section_name}"
            if marker in content:
                # Remove existing section
                lines = content.split("\n")
                new_lines = []
                skip = False
                for line in lines:
                    if line.strip() == marker:
                        skip = True
                        continue
                    if skip and line.strip().startswith("```") and not line.strip().startswith("```yaml"):
                        skip = False
                        continue
                    if skip:
                        continue
                    new_lines.append(line)
                content = "\n".join(new_lines)
            content += section
        else:
            content = section

        self.state_path.write_text(content, encoding="utf-8")

    def _write_timestamp(self) -> None:
        """Write a timestamp to the state file."""
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self._write_section("last_updated", {"timestamp": ts})

    def _build_interface(self, state: dict) -> dict:
        """Build the SFM interface from current state data.

        This is a simplified version. In production, it would read from
        the actual module data in the state file.
        """
        from claw_quant.sfm_engine import SFMEngine

        engine = SFMEngine()
        interface = engine.get_sfm_interface(datetime.now().strftime("%Y-%m-%d"))

        return {
            "phase": interface.phase,
            "preferred_factors": interface.preferred_factors,
            "key_signal_1": interface.key_signal_1,
            "key_signal_2": interface.key_signal_2,
            "gradient_direction": interface.gradient_direction,
            "confidence": interface.confidence,
        }