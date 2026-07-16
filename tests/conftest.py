"""pytest configuration — adds tests/, project root, and scripts/ to sys.path.

Also sets up temporary databases with schemas and minimal test data
so tests can run on CI without real database files.
"""

import sys
import tempfile
import shutil
from pathlib import Path

import pytest

_project_root = Path(__file__).parent.parent

# Make helpers.py importable from test files
sys.path.insert(0, str(Path(__file__).parent))

# Make scripts/ importable from test files
sys.path.insert(0, str(_project_root / "scripts"))

# Make claw_quant/ package importable
sys.path.insert(0, str(_project_root))


# ---------------------------------------------------------------------------
# Session-scoped test database fixture
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True, scope="session")
def _test_databases():
    """Create temporary databases with schemas and minimal test data.

    This fixture ensures tests can run on CI without real database files.
    It patches DB_PATHS in-place so all modules that imported it at
    module level (e.g. database.py) see the temp databases.
    """
    from claw_quant import config, database
    from init_ci_data import seed_test_data

    tmpdir = Path(tempfile.mkdtemp(prefix="claw_quant_test_"))

    new_paths = {
        "carhart": tmpdir / "carhart_results.db",
        "factor_ic": tmpdir / "factor_ic.db",
        "crowding": tmpdir / "crowding.db",
        "cffex": tmpdir / "cffex_positions.db",
        "validation": tmpdir / "validation_metrics.db",
    }

    # In-place update — critical because database.py holds a reference
    # to the same dict object imported at module level.
    # Using .clear() + .update() ensures both config.DB_PATHS and
    # database.DB_PATHS see the new paths.
    config.DB_PATHS.clear()
    config.DB_PATHS.update(new_paths)
    database.DB_PATHS.clear()
    database.DB_PATHS.update(new_paths)

    # Create all table schemas
    database.init_all_databases()

    # Insert minimal test data via shared seeding function
    # (same data used by CI validate job via scripts/init_ci_data.py)
    seed_test_data()

    yield

    shutil.rmtree(tmpdir, ignore_errors=True)
