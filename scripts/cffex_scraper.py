#!/usr/bin/env python3
"""
CFFEX (China Financial Futures Exchange) Daily Position Ranking Scraper
=======================================================================

Scrapes daily position ranking data from CFFEX for stock-index futures
(IF/IC/IM/IH) and stores it in a SQLite database for use by the
SFM Layer Module 3b (Forced Movement Analysis, S4 signal).

Data Source
-----------
The CFFEX publishes daily position rankings as XML files at:

    http://www.cffex.com.cn/sj/ccpm/{YYYYMM}/{DD}/{SYMBOL}.xml

Where:
  - {YYYYMM}  e.g. 202506
  - {DD}      zero-padded day, e.g. 27
  - {SYMBOL}  **uppercase** product code: IF, IC, IM, IH

IMPORTANT: Although the original spec mentioned lowercase symbols, live
testing confirmed that CFFEX requires **uppercase** codes.  Lowercase
returns a 404 HTML page.

XML Structure (verified by fetching a live sample on 2025-06-27)
-----------------------------------------------------------------
::

    <?xml version="1.0" encoding="UTF-8"?>
    <positionRank>
        <data Value="1" Text="IF2507">
            <instrumentid>IF2507</instrumentid>
            <tradingday>20250627</tradingday>
            <datatypeid>1</datatypeid>   <!-- 0=volume, 1=long, 2=short -->
            <rank>1</rank>
            <shortname>国泰君安(代客)</shortname>
            <volume>10762</volume>
            <varvolume>1272</varvolume>
            <partyid>0001</partyid>
            <productid>IF</productid>
        </data>
        ...
    </positionRank>

Each symbol typically has 2-3 active contracts, each with 20 ranks
for three data types (volume / long position / short position),
yielding ~120-180 <data> elements per XML file.

SFM Layer S4 Signal
----------------------
For every symbol we compute:

  * top20_net_long_change   = sum(varvolume) for datatypeid=1
  * top20_net_short_change  = sum(varvolume) for datatypeid=2
  * net_position_signal     = top20_net_long_change - top20_net_short_change
  * total_open_interest      = sum(volume) for datatypeid=1 across contracts

A positive net_position_signal means top-20 long holders are adding
positions faster than top-20 short holders (bullish hedging pressure);
a negative value indicates bearish hedging pressure.

Usage
-----
::

    # Scrape yesterday (default)
    python cffex_scraper.py

    # Scrape a specific date
    python cffex_scraper.py --date 2025-06-27

    # Backfill a date range
    python cffex_scraper.py --backfill 2025-06-20 2025-06-27

Author: AI Agent for SOLO / Claw Quant
"""

from __future__ import annotations

import argparse
import datetime
import logging
import os
import random
import sqlite3
import sys
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import Any, Optional

import requests

# ---------------------------------------------------------------------------
# Configuration (imported from shared package)
# ---------------------------------------------------------------------------

from claw_quant.config import CFFEX_BASE_URL, DB_PATHS

BASE_URL: str = CFFEX_BASE_URL
DB_PATH: str = str(DB_PATHS["cffex"])

# Symbol → human-readable name (CFFEX uses UPPERCASE in URLs)
SYMBOLS: dict[str, str] = {
    "IF": "CSI 300",
    "IC": "CSI 500",
    "IM": "CSI 1000",
    "IH": "SSE 50",
}

# HTTP settings
REQUEST_HEADERS: dict[str, str] = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/xml, text/xml, */*",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}
REQUEST_TIMEOUT: int = 30          # seconds
MAX_RETRIES: int = 3               # max retry attempts per request
RETRY_BASE_DELAY: float = 5.0      # seconds, doubled each retry
INTER_SYMBOL_DELAY: float = 3.0    # delay between different symbols

# Data type constants (from CFFEX XML <datatypeid>)
DATA_TYPE_VOLUME: int = 0    # 成交量排名
DATA_TYPE_LONG: int = 1      # 持买单量排名 (long position)
DATA_TYPE_SHORT: int = 2     # 持卖单量排名 (short position)

DATA_TYPE_LABELS: dict[int, str] = {
    DATA_TYPE_VOLUME: "volume",
    DATA_TYPE_LONG: "long",
    DATA_TYPE_SHORT: "short",
}

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("cffex_scraper")


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class PositionRecord:
    """A single position-ranking row extracted from CFFEX XML."""

    trading_day: str          # YYYYMMDD
    symbol: str               # IF / IC / IM / IH
    contract: str             # e.g. IF2507
    data_type: int            # 0=volume, 1=long, 2=short
    rank: int                 # 1-20
    broker_name: str          # shortname, e.g. 国泰君安(代客)
    party_id: str             # broker party id, e.g. 0001
    volume: int               # position or volume amount
    volume_change: int        # varvolume (change vs previous day)


@dataclass
class SignalResult:
    """Computed S4 signal for one symbol on one trading day."""

    trading_day: str
    symbol: str
    symbol_name: str
    top20_net_long_change: int
    top20_net_short_change: int
    net_position_signal: int
    total_open_interest: int
    contracts: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to a plain dict (for JSON serialisation / state files)."""
        return {
            "trading_day": self.trading_day,
            "symbol": self.symbol,
            "symbol_name": self.symbol_name,
            "top20_net_long_change": self.top20_net_long_change,
            "top20_net_short_change": self.top20_net_short_change,
            "net_position_signal": self.net_position_signal,
            "signal_direction": (
                "bullish" if self.net_position_signal > 0
                else "bearish" if self.net_position_signal < 0
                else "neutral"
            ),
            "total_open_interest": self.total_open_interest,
            "contracts": self.contracts,
        }


# ---------------------------------------------------------------------------
# Database layer
# ---------------------------------------------------------------------------

def get_connection(db_path: str = DB_PATH) -> sqlite3.Connection:
    """Return a SQLite connection, creating the data directory if needed."""
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: str = DB_PATH) -> None:
    """Create database tables if they do not already exist."""
    conn = get_connection(db_path)
    try:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS position_rankings (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                trading_day     TEXT    NOT NULL,   -- YYYYMMDD
                symbol          TEXT    NOT NULL,   -- IF / IC / IM / IH
                contract        TEXT    NOT NULL,   -- e.g. IF2507
                data_type       INTEGER NOT NULL,   -- 0=vol, 1=long, 2=short
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
                ON position_rankings(trading_day, symbol, contract,
                                     data_type, rank);

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
                status          TEXT    NOT NULL,   -- ok / no_data / error
                record_count    INTEGER DEFAULT 0,
                message         TEXT,
                fetched_at      TEXT    NOT NULL DEFAULT (datetime('now', 'localtime'))
            );
            """
        )
        conn.commit()
    finally:
        conn.close()


def date_symbol_exists(
    conn: sqlite3.Connection,
    trading_day: str,
    symbol: str,
) -> bool:
    """Check whether data for a given (date, symbol) pair already exists."""
    row = conn.execute(
        "SELECT COUNT(*) AS cnt FROM position_rankings "
        "WHERE trading_day = ? AND symbol = ?",
        (trading_day, symbol),
    ).fetchone()
    return row["cnt"] > 0


def store_records(
    conn: sqlite3.Connection,
    records: list[PositionRecord],
) -> int:
    """Bulk-insert position-ranking records.  Returns the number inserted."""
    if not records:
        return 0
    rows = [
        (
            r.trading_day, r.symbol, r.contract, r.data_type,
            r.rank, r.broker_name, r.party_id, r.volume, r.volume_change,
        )
        for r in records
    ]
    with conn:
        conn.executemany(
            """
            INSERT OR REPLACE INTO position_rankings
                (trading_day, symbol, contract, data_type, rank,
                 broker_name, party_id, volume, volume_change)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
    return len(rows)


def store_signal(conn: sqlite3.Connection, sig: SignalResult) -> None:
    """Upsert a computed signal into the signals table."""
    with conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO signals
                (trading_day, symbol, top20_net_long_change,
                 top20_net_short_change, net_position_signal, total_open_interest)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                sig.trading_day, sig.symbol,
                sig.top20_net_long_change, sig.top20_net_short_change,
                sig.net_position_signal, sig.total_open_interest,
            ),
        )


def log_fetch(
    conn: sqlite3.Connection,
    trading_day: str,
    symbol: str,
    status: str,
    record_count: int = 0,
    message: str = "",
) -> None:
    """Record a fetch attempt in the fetch_log table."""
    with conn:
        conn.execute(
            """
            INSERT INTO fetch_log
                (trading_day, symbol, status, record_count, message)
            VALUES (?, ?, ?, ?, ?)
            """,
            (trading_day, symbol, status, record_count, message),
        )


def get_latest_trading_day(conn: sqlite3.Connection) -> Optional[str]:
    """Return the most recent trading_day present in the database."""
    row = conn.execute(
        "SELECT MAX(trading_day) AS latest FROM position_rankings"
    ).fetchone()
    return row["latest"] if row and row["latest"] else None


# ---------------------------------------------------------------------------
# HTTP layer
# ---------------------------------------------------------------------------

def build_url(date: datetime.date, symbol: str) -> str:
    """
    Build the CFFEX position-ranking XML URL for a given date and symbol.

    URL format:  http://www.cffex.com.cn/sj/ccpm/{YYYYMM}/{DD}/{SYMBOL}.xml
    A random query parameter is appended to defeat caching.
    """
    yyyy_mm = date.strftime("%Y%m")
    dd = date.strftime("%d")
    symbol_upper = symbol.upper()
    cache_buster = random.randint(1, 99)
    return (
        f"{BASE_URL}/{yyyy_mm}/{dd}/{symbol_upper}.xml?id={cache_buster}"
    )


def fetch_xml(
    url: str,
    retries: int = MAX_RETRIES,
) -> Optional[str]:
    """
    Fetch XML text from CFFEX with retry logic.

    Returns the response body as a string on success, or ``None`` if the
    URL does not exist (404 / non-XML response — typical for weekends and
    holidays).  Transient errors (timeouts, 5xx) are retried with
    exponential back-off.
    """
    for attempt in range(1, retries + 1):
        try:
            logger.debug(
                "Fetching %s (attempt %d/%d)", url, attempt, retries
            )
            resp = requests.get(
                url,
                headers=REQUEST_HEADERS,
                timeout=REQUEST_TIMEOUT,
                allow_redirects=False,  # CFFEX 404 redirects to an HTML page
            )

            # ---- Non-trading day / file not found ----------------------
            # CFFEX returns 302 → 404 HTML for missing dates.
            if resp.status_code in (301, 302, 404):
                logger.info("No data (HTTP %d) — likely a non-trading day.", resp.status_code)
                return None

            # Some servers return 200 with an HTML error page
            content_type = resp.headers.get("Content-Type", "")
            if "xml" not in content_type and "text/xml" not in content_type:
                # Could be a 404 HTML page served with 200
                body_preview = resp.text[:200].lower()
                if "404" in body_preview or "error" in body_preview:
                    logger.info("No data (HTML error page) — likely a non-trading day.")
                    return None
                logger.warning(
                    "Unexpected Content-Type '%s' — attempting to parse anyway.",
                    content_type,
                )

            resp.raise_for_status()
            return resp.text

        except requests.exceptions.Timeout:
            logger.warning(
                "Timeout (attempt %d/%d) for %s", attempt, retries, url
            )
        except requests.exceptions.ConnectionError as exc:
            logger.warning(
                "Connection error (attempt %d/%d): %s", attempt, retries, exc
            )
        except requests.exceptions.HTTPError as exc:
            status_code = exc.response.status_code if exc.response else "?"
            if 500 <= (exc.response.status_code if exc.response else 0):
                logger.warning(
                    "Server error %s (attempt %d/%d)", status_code, attempt, retries
                )
            else:
                logger.error("HTTP error %s — not retrying: %s", status_code, exc)
                return None
        except Exception as exc:  # noqa: BLE001
            logger.error("Unexpected error (attempt %d/%d): %s", attempt, retries, exc)

        if attempt < retries:
            delay = RETRY_BASE_DELAY * (2 ** (attempt - 1))
            logger.info("Retrying in %.1f seconds…", delay)
            time.sleep(delay)

    logger.error("All %d retries exhausted for %s", retries, url)
    return None


# ---------------------------------------------------------------------------
# XML parsing
# ---------------------------------------------------------------------------

def _safe_int(text: Optional[str], default: int = 0) -> int:
    """Parse an integer from XML text, returning *default* on failure."""
    if text is None:
        return default
    text = text.strip()
    if not text:
        return default
    try:
        return int(text)
    except ValueError:
        try:
            return int(float(text))
        except (ValueError, TypeError):
            return default


def parse_xml(
    xml_text: str,
    symbol: str,
) -> list[PositionRecord]:
    """
    Parse a CFFEX position-ranking XML string into a list of records.

    The XML has the structure::

        <positionRank>
          <data Value="1" Text="IF2507">
            <instrumentid>IF2507</instrumentid>
            <tradingday>20250627</tradingday>
            <datatypeid>1</datatypeid>
            <rank>1</rank>
            <shortname>国泰君安(代客)</shortname>
            <volume>10762</volume>
            <varvolume>1272</varvolume>
            <partyid>0001</partyid>
            <productid>IF</productid>
          </data>
          ...
        </positionRank>
    """
    records: list[PositionRecord] = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        logger.error("XML parse error for symbol %s: %s", symbol, exc)
        return records

    for data_elem in root.findall("data"):
        trading_day = (data_elem.findtext("tradingday") or "").strip()
        contract = (data_elem.findtext("instrumentid") or "").strip()
        data_type = _safe_int(data_elem.findtext("datatypeid"))
        rank = _safe_int(data_elem.findtext("rank"))
        broker_name = (data_elem.findtext("shortname") or "").strip()
        party_id = (data_elem.findtext("partyid") or "").strip()
        volume = _safe_int(data_elem.findtext("volume"))
        varvolume = _safe_int(data_elem.findtext("varvolume"))

        if not trading_day or not contract:
            continue

        records.append(
            PositionRecord(
                trading_day=trading_day,
                symbol=symbol.upper(),
                contract=contract,
                data_type=data_type,
                rank=rank,
                broker_name=broker_name,
                party_id=party_id,
                volume=volume,
                volume_change=varvolume,
            )
        )

    return records


# ---------------------------------------------------------------------------
# Signal computation (SFM Layer Module 3b — S4 signal)
# ---------------------------------------------------------------------------

def compute_net_position_change(
    conn: sqlite3.Connection,
    trading_day: str,
    symbol: Optional[str] = None,
) -> list[SignalResult]:
    """
    Compute the net position-change signal for one or all symbols on a
    given trading day.

    For each symbol:

      * top20_net_long_change   = Σ varvolume  (datatypeid = 1, all contracts)
      * top20_net_short_change  = Σ varvolume  (datatypeid = 2, all contracts)
      * net_position_signal     = top20_net_long_change − top20_net_short_change
      * total_open_interest     = Σ volume     (datatypeid = 1, all contracts)

    A positive net_position_signal → top-20 long holders are adding
    positions faster than short holders (bullish hedging).
    A negative value → bearish hedging.

    Parameters
    ----------
    conn
        Active SQLite connection.
    trading_day
        Trading day in ``YYYYMMDD`` format.
    symbol
        If given, compute only for that symbol; otherwise compute for all
        four (IF/IC/IM/IH).

    Returns
    -------
    list[SignalResult]
        One ``SignalResult`` per symbol.
    """
    symbols_to_compute = [symbol.upper()] if symbol else list(SYMBOLS.keys())
    results: list[SignalResult] = []

    for sym in symbols_to_compute:
        # Sum varvolume for long positions (datatypeid=1)
        long_row = conn.execute(
            """
            SELECT
                COALESCE(SUM(volume_change), 0) AS net_long_change,
                COALESCE(SUM(volume), 0)         AS total_long_pos
            FROM position_rankings
            WHERE trading_day = ? AND symbol = ? AND data_type = ?
            """,
            (trading_day, sym, DATA_TYPE_LONG),
        ).fetchone()

        # Sum varvolume for short positions (datatypeid=2)
        short_row = conn.execute(
            """
            SELECT
                COALESCE(SUM(volume_change), 0) AS net_short_change
            FROM position_rankings
            WHERE trading_day = ? AND symbol = ? AND data_type = ?
            """,
            (trading_day, sym, DATA_TYPE_SHORT),
        ).fetchone()

        # Distinct contracts for reference
        contract_rows = conn.execute(
            """
            SELECT DISTINCT contract FROM position_rankings
            WHERE trading_day = ? AND symbol = ?
            ORDER BY contract
            """,
            (trading_day, sym),
        ).fetchall()
        contracts = [r["contract"] for r in contract_rows]

        top20_net_long_change = int(long_row["net_long_change"])
        top20_net_short_change = int(short_row["net_short_change"])
        total_open_interest = int(long_row["total_long_pos"])

        sig = SignalResult(
            trading_day=trading_day,
            symbol=sym,
            symbol_name=SYMBOLS.get(sym, sym),
            top20_net_long_change=top20_net_long_change,
            top20_net_short_change=top20_net_short_change,
            net_position_signal=top20_net_long_change - top20_net_short_change,
            total_open_interest=total_open_interest,
            contracts=contracts,
        )
        results.append(sig)

        # Persist to DB
        store_signal(conn, sig)

    return results


def get_latest_signals(
    conn: sqlite3.Connection,
    num_days: int = 1,
) -> dict[str, Any]:
    """
    Return the most recent day's net position-change signals for all
    four symbols, formatted as a summary dict suitable for writing into
    ``sfm_state.md``.

    Parameters
    ----------
    conn
        Active SQLite connection.
    num_days
        Number of most-recent trading days to include (default 1).

    Returns
    -------
    dict
        A nested dict with the structure::

            {
                "latest_trading_day": "20250627",
                "symbols": {
                    "IF": { ... },
                    "IC": { ... },
                    "IM": { ... },
                    "IH": { ... },
                },
                "summary": "Bullish: IF, IC  |  Bearish: IH  |  Neutral: IM",
            }
    """
    latest_day = get_latest_trading_day(conn)
    if latest_day is None:
        return {
            "latest_trading_day": None,
            "symbols": {},
            "summary": "No data available.",
        }

    # Compute (or re-compute) signals for the latest day
    signals = compute_net_position_change(conn, latest_day)

    # Optionally include additional recent days
    history: list[dict[str, Any]] = []
    if num_days > 1:
        recent_days = conn.execute(
            """
            SELECT DISTINCT trading_day FROM signals
            ORDER BY trading_day DESC
            LIMIT ?
            """,
            (num_days,),
        ).fetchall()
        for row in recent_days:
            td = row["trading_day"]
            if td == latest_day:
                continue
            day_sigs = compute_net_position_change(conn, td)
            history.append(
                {
                    "trading_day": td,
                    "signals": [s.to_dict() for s in day_sigs],
                }
            )

    symbol_map: dict[str, dict[str, Any]] = {}
    bullish: list[str] = []
    bearish: list[str] = []
    neutral: list[str] = []

    for sig in signals:
        d = sig.to_dict()
        symbol_map[sig.symbol] = d
        direction = d["signal_direction"]
        if direction == "bullish":
            bullish.append(sig.symbol)
        elif direction == "bearish":
            bearish.append(sig.symbol)
        else:
            neutral.append(sig.symbol)

    parts: list[str] = []
    if bullish:
        parts.append(f"Bullish: {', '.join(bullish)}")
    if bearish:
        parts.append(f"Bearish: {', '.join(bearish)}")
    if neutral:
        parts.append(f"Neutral: {', '.join(neutral)}")
    summary = "  |  ".join(parts) if parts else "No signals."

    result: dict[str, Any] = {
        "latest_trading_day": latest_day,
        "symbols": symbol_map,
        "summary": summary,
    }
    if history:
        result["history"] = history

    return result


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

def scrape_date(
    date: datetime.date,
    db_path: str = DB_PATH,
    skip_existing: bool = True,
    compute_signals: bool = True,
) -> dict[str, Any]:
    """
    Scrape position-ranking data for all four symbols on a given date.

    Parameters
    ----------
    date
        The calendar date to scrape.
    db_path
        Path to the SQLite database.
    skip_existing
        If ``True``, skip symbols whose data already exists for this date.
    compute_signals
        If ``True``, compute and store S4 signals after fetching.

    Returns
    -------
    dict
        Summary dict with per-symbol status and record counts.
    """
    trading_day = date.strftime("%Y%m%d")
    init_db(db_path)
    conn = get_connection(db_path)

    results: dict[str, Any] = {
        "date": date.isoformat(),
        "trading_day": trading_day,
        "symbols": {},
    }

    try:
        for idx, (symbol, name) in enumerate(SYMBOLS.items()):
            # Incremental update check
            if skip_existing and date_symbol_exists(conn, trading_day, symbol):
                logger.info(
                    "[%s] %s — already in DB, skipping.", trading_day, symbol
                )
                results["symbols"][symbol] = {
                    "status": "skipped",
                    "records": 0,
                    "message": "Data already exists.",
                }
                # Still compute signal from existing data
                continue

            # Delay between symbols (except before the first one)
            if idx > 0:
                logger.debug("Sleeping %.1fs before next symbol…", INTER_SYMBOL_DELAY)
                time.sleep(INTER_SYMBOL_DELAY)

            url = build_url(date, symbol)
            logger.info("[%s] Fetching %s (%s) — %s", trading_day, symbol, name, url)

            xml_text = fetch_xml(url)
            if xml_text is None:
                logger.info("[%s] %s — no data (non-trading day).", trading_day, symbol)
                log_fetch(conn, trading_day, symbol, "no_data")
                results["symbols"][symbol] = {
                    "status": "no_data",
                    "records": 0,
                    "message": "Non-trading day or data unavailable.",
                }
                continue

            records = parse_xml(xml_text, symbol)
            if not records:
                logger.warning("[%s] %s — XML parsed but no records found.", trading_day, symbol)
                log_fetch(conn, trading_day, symbol, "error", message="No records parsed")
                results["symbols"][symbol] = {
                    "status": "error",
                    "records": 0,
                    "message": "XML parsed but no records.",
                }
                continue

            inserted = store_records(conn, records)
            log_fetch(conn, trading_day, symbol, "ok", inserted)
            logger.info("[%s] %s — stored %d records.", trading_day, symbol, inserted)
            results["symbols"][symbol] = {
                "status": "ok",
                "records": inserted,
                "contracts": sorted({r.contract for r in records}),
            }

        # Compute signals only if at least one symbol has data
        if compute_signals:
            has_data = any(
                v.get("status") == "ok" or v.get("status") == "skipped"
                for v in results["symbols"].values()
            )
            if has_data:
                signals = compute_net_position_change(conn, trading_day)
                results["signals"] = [s.to_dict() for s in signals]
                for sig in signals:
                    logger.info(
                        "[%s] %s signal: long_change=%d, short_change=%d, "
                        "net=%d (%s)",
                        trading_day,
                        sig.symbol,
                        sig.top20_net_long_change,
                        sig.top20_net_short_change,
                        sig.net_position_signal,
                        "bullish" if sig.net_position_signal > 0
                        else "bearish" if sig.net_position_signal < 0
                        else "neutral",
                    )
            else:
                logger.info(
                    "[%s] No data for any symbol — skipping signal computation.",
                    trading_day,
                )
    finally:
        conn.close()

    return results


def backfill(
    start_date: datetime.date,
    end_date: datetime.date,
    db_path: str = DB_PATH,
    skip_existing: bool = True,
) -> dict[str, Any]:
    """
    Fetch historical position-ranking data for a date range (inclusive).

    Iterates over calendar days from *start_date* to *end_date*.  Non-trading
    days (weekends / holidays) are automatically skipped because CFFEX
    returns no XML for them.

    Parameters
    ----------
    start_date, end_date
        Inclusive date range.
    db_path
        Path to the SQLite database.
    skip_existing
        If ``True``, skip dates whose data already exists.

    Returns
    -------
    dict
        Summary with per-date status.
    """
    if start_date > end_date:
        start_date, end_date = end_date, start_date

    total_days = (end_date - start_date).days + 1
    logger.info(
        "Backfilling %d calendar days from %s to %s",
        total_days,
        start_date.isoformat(),
        end_date.isoformat(),
    )

    summary: dict[str, Any] = {
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "total_calendar_days": total_days,
        "dates": {},
    }

    current = start_date
    success_count = 0
    no_data_count = 0
    error_count = 0

    while current <= end_date:
        day_str = current.isoformat()
        try:
            result = scrape_date(current, db_path, skip_existing=skip_existing)

            # Determine overall status for the day
            statuses = [v["status"] for v in result["symbols"].values()]
            if all(s == "skipped" for s in statuses):
                day_status = "skipped"
            elif all(s == "no_data" for s in statuses):
                day_status = "no_data"
                no_data_count += 1
            elif any(s == "ok" for s in statuses):
                day_status = "ok"
                success_count += 1
            else:
                day_status = "error"
                error_count += 1

            summary["dates"][day_str] = {
                "status": day_status,
                "symbols": result["symbols"],
            }
            logger.info("[%s] %s", day_str, day_status)

        except Exception as exc:  # noqa: BLE001
            logger.error("[%s] Unexpected error: %s", day_str, exc)
            error_count += 1
            summary["dates"][day_str] = {
                "status": "error",
                "error": str(exc),
            }

        current += datetime.timedelta(days=1)

    summary["summary"] = {
        "success_days": success_count,
        "no_data_days": no_data_count,
        "error_days": error_count,
    }
    logger.info(
        "Backfill complete: %d ok, %d no-data, %d errors",
        success_count,
        no_data_count,
        error_count,
    )
    return summary


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_date_arg(value: str) -> datetime.date:
    """Parse a YYYY-MM-DD string into a date (for argparse)."""
    try:
        return datetime.datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"Invalid date '{value}'. Expected format: YYYY-MM-DD"
        )


def get_previous_trading_day(today: Optional[datetime.date] = None) -> datetime.date:
    """
    Return the previous trading day.

    CFFEX does not trade on weekends.  If today is Monday, the previous
    trading day is the preceding Friday.  (Holidays are handled at fetch
    time — the scraper will simply find no XML and log 'no_data'.)
    """
    if today is None:
        today = datetime.date.today()
    offset = 1
    # Skip Saturday (5) and Sunday (6)
    if today.weekday() == 0:    # Monday → go back to Friday
        offset = 3
    elif today.weekday() == 6:  # Sunday → go back to Friday
        offset = 2
    return today - datetime.timedelta(days=offset)


def main() -> None:
    """CLI entry point."""
    global INTER_SYMBOL_DELAY
    parser = argparse.ArgumentParser(
        description=(
            "Scrape CFFEX daily position-ranking data for IF/IC/IM/IH "
            "and compute SFM Layer S4 (net position change) signals."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python cffex_scraper.py                          # yesterday\n"
            "  python cffex_scraper.py --date 2025-06-27        # specific date\n"
            "  python cffex_scraper.py --backfill 2025-06-20 2025-06-27\n"
            "  python cffex_scraper.py --signals                # latest signals only\n"
        ),
    )

    parser.add_argument(
        "--date",
        type=parse_date_arg,
        default=None,
        help="Specific date to scrape (YYYY-MM-DD). Default: previous trading day.",
    )
    parser.add_argument(
        "--backfill",
        nargs=2,
        metavar=("START", "END"),
        type=parse_date_arg,
        default=None,
        help="Backfill a date range: --backfill START END (YYYY-MM-DD).",
    )
    parser.add_argument(
        "--signals",
        action="store_true",
        help="Print latest S4 signals from the database and exit.",
    )
    parser.add_argument(
        "--db",
        type=str,
        default=DB_PATH,
        help=f"Path to SQLite database (default: {DB_PATH}).",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-fetch even if data already exists (skip incremental check).",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=INTER_SYMBOL_DELAY,
        help=f"Delay between symbol requests in seconds (default: {INTER_SYMBOL_DELAY}).",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable debug-level logging.",
    )

    args = parser.parse_args()

    if args.verbose:
        logger.setLevel(logging.DEBUG)

    # Override the inter-symbol delay from CLI
    INTER_SYMBOL_DELAY = args.delay

    # ---- Mode: signals only ------------------------------------------------
    if args.signals:
        init_db(args.db)
        conn = get_connection(args.db)
        try:
            signals = get_latest_signals(conn)
            import json
            print(json.dumps(signals, ensure_ascii=False, indent=2))
        finally:
            conn.close()
        return

    # ---- Mode: backfill ----------------------------------------------------
    if args.backfill:
        start_date, end_date = args.backfill
        backfill(start_date, end_date, db_path=args.db, skip_existing=not args.force)
        return

    # ---- Mode: single date (default) --------------------------------------
    target_date = args.date or get_previous_trading_day()
    logger.info("Scraping CFFEX data for %s", target_date.isoformat())
    result = scrape_date(
        target_date,
        db_path=args.db,
        skip_existing=not args.force,
    )

    # Print summary
    print(f"\n{'=' * 60}")
    print(f"CFFEX Position Ranking — {target_date.isoformat()}")
    print(f"{'=' * 60}")
    for symbol, info in result.get("symbols", {}).items():
        status = info["status"]
        records = info.get("records", 0)
        contracts = info.get("contracts", [])
        contract_str = f" [{', '.join(contracts)}]" if contracts else ""
        print(f"  {symbol} ({SYMBOLS.get(symbol, '?'):<10})  "
              f"{status:<8}  {records:>4} records{contract_str}")

    if "signals" in result:
        print(f"\n--- S4 Signals (SFM Layer Module 3b) ---")
        for sig in result["signals"]:
            direction = sig.get("signal_direction", "?")
            print(
                f"  {sig['symbol']} ({sig['symbol_name']:<10})  "
                f"net_long={sig['top20_net_long_change']:>+8d}  "
                f"net_short={sig['top20_net_short_change']:>+8d}  "
                f"SIGNAL={sig['net_position_signal']:>+8d}  "
                f"OI={sig['total_open_interest']:>12d}  "
                f"[{direction.upper()}]"
            )
    print()


if __name__ == "__main__":
    main()
