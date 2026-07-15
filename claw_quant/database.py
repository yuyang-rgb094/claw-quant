"""Shared database layer for Claw Quant.

Unifies the four separate init_db() / get_connection() implementations
from the 5 scripts into a single module. Each script previously defined
its own DB_PATH, connection logic, and table creation — all duplicated.
"""

from __future__ import annotations

import sqlite3
from enum import Enum
from pathlib import Path

from claw_quant.config import DB_PATHS, DATA_DIR


class DBName(str, Enum):
    """Named database identifiers matching config.DB_PATHS keys."""
    CARHART = "carhart"
    FACTOR_IC = "factor_ic"
    CROWDING = "crowding"
    CFFEX = "cffex"
    VALIDATION = "validation"


def get_connection(db_name: str | DBName) -> sqlite3.Connection:
    """Return a connection to the named database, creating the directory if needed.

    Args:
        db_name: One of DBName enum values or their string equivalents.

    Returns:
        An sqlite3.Connection with row_factory set to sqlite3.Row.
    """
    if isinstance(db_name, DBName):
        db_name = db_name.value
    db_path = DB_PATHS.get(db_name)
    if db_path is None:
        raise ValueError(
            f"Unknown database: {db_name}. Valid names: {list(DB_PATHS.keys())}"
        )
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def init_all_databases() -> None:
    """Ensure all 4 production databases exist with their schemas.

    Idempotent — safe to call multiple times.
    """
    _init_carhart_db()
    _init_factor_ic_db()
    _init_crowding_db()
    _init_cffex_db()


def _init_carhart_db() -> None:
    """Create carhart_results.db tables."""
    conn = get_connection(DBName.CARHART)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS regressions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            portfolio TEXT NOT NULL,
            window_start TEXT NOT NULL,
            window_end TEXT NOT NULL,
            alpha REAL,
            alpha_t_stat REAL,
            alpha_p_value REAL,
            r_squared REAL,
            adj_r_squared REAL,
            residual_std REAL,
            information_ratio REAL,
            n_observations INTEGER,
            computed_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS factor_details (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            regression_id INTEGER NOT NULL,
            portfolio TEXT NOT NULL,
            window_start TEXT NOT NULL,
            window_end TEXT NOT NULL,
            factor_name TEXT NOT NULL,
            beta REAL,
            t_stat REAL,
            p_value REAL,
            premia_gamma REAL,
            significant INTEGER,
            vif REAL,
            FOREIGN KEY (regression_id) REFERENCES regressions(id)
        );

        CREATE INDEX IF NOT EXISTS idx_regressions_window
            ON regressions(portfolio, window_start, window_end);
        CREATE INDEX IF NOT EXISTS idx_factor_details
            ON factor_details(regression_id, factor_name);
    """)
    conn.commit()
    conn.close()


def _init_factor_ic_db() -> None:
    """Create factor_ic.db tables."""
    conn = get_connection(DBName.FACTOR_IC)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS ic_series (
            factor     TEXT NOT NULL,
            date       TEXT NOT NULL,
            forward_days INTEGER NOT NULL,
            ic         REAL,
            PRIMARY KEY (factor, date, forward_days)
        );

        CREATE TABLE IF NOT EXISTS half_life (
            factor          TEXT PRIMARY KEY,
            ic_0            REAL,
            tau             REAL,
            half_life_days  REAL,
            r_squared       REAL,
            decay_status    TEXT,
            updated_at      TEXT
        );
    """)
    conn.commit()
    conn.close()


def _init_crowding_db() -> None:
    """Create crowding.db tables."""
    conn = get_connection(DBName.CROWDING)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS crowding (
            factor              TEXT PRIMARY KEY,
            duration_bucket     TEXT,
            crowding_score      REAL,
            long_short_cost_bps REAL,
            concentration       REAL,
            corr_distortion     REAL,
            trend               TEXT,
            updated_at          TEXT
        );

        CREATE TABLE IF NOT EXISTS margin_data (
            date        TEXT PRIMARY KEY,
            margin_balance REAL,
            margin_sell_balance REAL,
            margin_buy_balance REAL,
            margin_sell_rate REAL
        );

        CREATE TABLE IF NOT EXISTS crowding_history (
            factor        TEXT,
            date          TEXT,
            crowding_score REAL,
            PRIMARY KEY (factor, date)
        );
    """)
    conn.commit()
    conn.close()


def _init_cffex_db() -> None:
    """Create cffex_positions.db tables."""
    conn = get_connection(DBName.CFFEX)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS position_rankings (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            trading_day     TEXT    NOT NULL,
            symbol          TEXT    NOT NULL,
            contract        TEXT    NOT NULL,
            data_type       INTEGER NOT NULL,
            rank            INTEGER NOT NULL,
            broker_name     TEXT    NOT NULL,
            party_id        TEXT,
            volume          INTEGER NOT NULL,
            volume_change   INTEGER NOT NULL,
            fetched_at      TEXT    NOT NULL DEFAULT (datetime('now', 'localtime'))
        );

        CREATE INDEX IF NOT EXISTS idx_pos_day_sym
            ON position_rankings(trading_day, symbol);
        CREATE INDEX IF NOT EXISTS idx_pos_day_sym_type
            ON position_rankings(trading_day, symbol, data_type);
        CREATE UNIQUE INDEX IF NOT EXISTS uq_pos_record
            ON position_rankings(trading_day, symbol, contract, data_type, rank);

        CREATE TABLE IF NOT EXISTS signals (
            id                      INTEGER PRIMARY KEY AUTOINCREMENT,
            trading_day             TEXT    NOT NULL,
            symbol                  TEXT    NOT NULL,
            top20_net_long_change   INTEGER NOT NULL,
            top20_net_short_change  INTEGER NOT NULL,
            net_position_signal     INTEGER NOT NULL,
            total_open_interest     INTEGER NOT NULL,
            computed_at             TEXT    NOT NULL DEFAULT (datetime('now', 'localtime'))
        );

        CREATE UNIQUE INDEX IF NOT EXISTS uq_signal
            ON signals(trading_day, symbol);

        CREATE TABLE IF NOT EXISTS fetch_log (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            trading_day     TEXT    NOT NULL,
            symbol          TEXT    NOT NULL,
            status          TEXT    NOT NULL,
            record_count    INTEGER DEFAULT 0,
            message         TEXT,
            fetched_at      TEXT    NOT NULL DEFAULT (datetime('now', 'localtime'))
        );
    """)
    conn.commit()
    conn.close()