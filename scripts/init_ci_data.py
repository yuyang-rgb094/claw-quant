"""Initialize SQLite databases with schemas and minimal test data.

Used by CI (GitHub Actions) to enable the validate job to run without
real Wind API data. Also called by tests/conftest.py for the same purpose.

Usage:
    python scripts/init_ci_data.py          # initialize + seed
    python scripts/init_ci_data.py --check  # verify tables exist
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

# Ensure project root is importable
_project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_project_root))

from claw_quant.database import init_all_databases, get_connection, DBName


def seed_test_data() -> None:
    """Insert minimal but valid test data into all databases.

    Idempotent — uses INSERT OR IGNORE to avoid duplicates on re-runs.
    """
    # ── carhart_results.db ──
    conn = get_connection(DBName.CARHART)
    conn.executescript("""
        INSERT OR IGNORE INTO regressions
            (id, portfolio, window_start, window_end, alpha, alpha_t_stat,
             alpha_p_value, r_squared, adj_r_squared, residual_std,
             information_ratio, n_observations, computed_at)
        VALUES
            (1, 'A_share', '2024-01-01', '2024-06-30',
             0.025, 2.1, 0.035, 0.82, 0.80, 0.015, 0.45, 120, '2024-07-01'),
            (2, 'A_share', '2024-02-01', '2024-07-31',
             0.020, 1.8, 0.072, 0.78, 0.75, 0.016, 0.38, 120, '2024-08-01');

        INSERT OR IGNORE INTO factor_details
            (regression_id, portfolio, window_start, window_end,
             factor_name, beta, t_stat, p_value, premia_gamma,
             significant, vif)
        VALUES
            (1, 'A_share', '2024-01-01', '2024-06-30',
             'MKT', 1.02, 15.3, 0.001, 0.008, 1, 1.2),
            (1, 'A_share', '2024-01-01', '2024-06-30',
             'SMB', 0.35, 3.1, 0.002, 0.003, 1, 1.5),
            (1, 'A_share', '2024-01-01', '2024-06-30',
             'HML', 0.28, 2.5, 0.012, 0.004, 1, 1.3),
            (1, 'A_share', '2024-01-01', '2024-06-30',
             'MOM', 0.15, 1.8, 0.072, 0.002, 0, 1.1);
    """)
    conn.commit()
    conn.close()

    # ── factor_ic.db ──
    conn = get_connection(DBName.FACTOR_IC)
    conn.executescript("""
        INSERT OR IGNORE INTO ic_series (factor, date, forward_days, ic)
        VALUES
            ('MKT', '2024-06-01', 5, 0.08),
            ('MKT', '2024-06-08', 5, 0.07),
            ('MKT', '2024-06-15', 5, 0.09),
            ('MKT', '2024-06-01', 10, 0.06),
            ('SMB', '2024-06-01', 5, 0.03),
            ('SMB', '2024-06-08', 5, 0.02),
            ('HML', '2024-06-01', 5, 0.04),
            ('MOM', '2024-06-01', 5, 0.02);

        INSERT OR IGNORE INTO half_life
            (factor, ic_0, tau, half_life_days, r_squared,
             decay_status, updated_at)
        VALUES
            ('MKT', 0.08, 15.0, 10.5, 0.92, 'healthy', '2024-07-01'),
            ('SMB', 0.03, 8.0, 5.6, 0.85, 'healthy', '2024-07-01'),
            ('HML', 0.04, 12.0, 8.3, 0.88, 'healthy', '2024-07-01'),
            ('MOM', 0.02, 5.0, 3.5, 0.72, 'decaying', '2024-07-01');
    """)
    conn.commit()
    conn.close()

    # ── crowding.db ──
    conn = get_connection(DBName.CROWDING)
    conn.executescript("""
        INSERT OR IGNORE INTO crowding
            (factor, duration_bucket, crowding_score,
             long_short_cost_bps, concentration, corr_distortion,
             trend, updated_at)
        VALUES
            ('MKT', 'short', 0.35, 25, 0.42, 0.12, 'stable',
             '2024-07-01'),
            ('SMB', 'short', 0.28, 18, 0.35, 0.08, 'rising',
             '2024-07-01'),
            ('HML', 'medium', 0.45, 35, 0.55, 0.18, 'rising',
             '2024-07-01'),
            ('MOM', 'medium', 0.52, 40, 0.60, 0.22, 'extreme',
             '2024-07-01');

        INSERT OR IGNORE INTO margin_data
            (date, margin_balance, margin_sell_balance,
             margin_buy_balance, margin_sell_rate)
        VALUES
            ('2024-06-28', 1.5e12, 8e11, 7e11, 0.53),
            ('2024-06-21', 1.45e12, 7.8e11, 6.7e11, 0.54);

        INSERT OR IGNORE INTO crowding_history (factor, date, crowding_score)
        VALUES
            ('MKT', '2024-06-01', 0.30),
            ('MKT', '2024-06-15', 0.33),
            ('MKT', '2024-06-28', 0.35),
            ('SMB', '2024-06-01', 0.25),
            ('SMB', '2024-06-15', 0.27),
            ('SMB', '2024-06-28', 0.28);
    """)
    conn.commit()
    conn.close()

    # ── cffex_positions.db ──
    conn = get_connection(DBName.CFFEX)
    conn.executescript("""
        INSERT OR IGNORE INTO signals
            (trading_day, symbol, top20_net_long_change,
             top20_net_short_change, net_position_signal,
             total_open_interest, computed_at)
        VALUES
            ('2024-06-28', 'IF', 100, -50, 1, 120000, '2024-06-28');
    """)
    conn.commit()
    conn.close()

    print("Test data seeded successfully.")


def check_tables() -> bool:
    """Verify all expected tables exist."""
    expected = {
        DBName.CARHART: ["regressions", "factor_details"],
        DBName.FACTOR_IC: ["ic_series", "half_life"],
        DBName.CROWDING: ["crowding", "margin_data", "crowding_history"],
        DBName.CFFEX: ["position_rankings", "signals", "fetch_log"],
    }
    all_ok = True
    for db, tables in expected.items():
        conn = get_connection(db)
        for table in tables:
            row = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                (table,)
            ).fetchone()
            status = "OK" if row else "MISSING"
            if not row:
                all_ok = False
            print(f"  {db.value}.{table}: {status}")
        conn.close()
    return all_ok


if __name__ == "__main__":
    if "--check" in sys.argv:
        ok = check_tables()
        sys.exit(0 if ok else 1)
    else:
        print("Initializing databases...")
        init_all_databases()
        print("Seeding test data...")
        seed_test_data()
        print("Done.")
