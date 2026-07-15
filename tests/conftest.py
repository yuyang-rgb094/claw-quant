"""pytest configuration — adds tests/, project root, and scripts/ to sys.path."""

import sys
from pathlib import Path

_project_root = Path(__file__).parent.parent

# Make helpers.py importable from test files
sys.path.insert(0, str(Path(__file__).parent))

# Make scripts/ importable from test files
sys.path.insert(0, str(_project_root / "scripts"))

# Make claw_quant/ package importable
sys.path.insert(0, str(_project_root))
