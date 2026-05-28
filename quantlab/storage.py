"""SQLite persistence for the local Phase 1 workflow."""

from __future__ import annotations

import re
import sqlite3
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

DEFAULT_DB_PATH = Path(".quantlab/phase1.sqlite3")
MANAGED_DB_DIR = Path(".quantlab")
_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
ALLOWED_TABLES = {
    "instrument_master",
    "daily_market_brief",
    "sector_theme_map",
    "premarket_watchlist",
    "stock_research_card",
    "intraday_signal_log",
    "user_decision_log",
    "trade_execution_log",
    "postmarket_review",
}
ALLOWED_WHERE = {
    "",
    "trade_date=?",
    "id=?",
    "trade_date=? AND ticker=?",
    "watchlist_item_id=?",
}
ALLOWED_ORDER_BY = {
    "",
    "sector_name",
    "grade, score DESC",
    "ticker",
    "signal_time",
    "decision_time",
    "id",
}

SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS instrument_master (
    ticker TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    market TEXT NOT NULL,
    sector_tags TEXT NOT NULL DEFAULT '',
    listing_status TEXT NOT NULL DEFAULT 'active'
);

CREATE TABLE IF NOT EXISTS daily_market_brief (
    trade_date TEXT PRIMARY KEY,
    market_mode TEXT NOT NULL,
    kospi_note TEXT NOT NULL DEFAULT '',
    kosdaq_note TEXT NOT NULL DEFAULT '',
    overseas_impact TEXT NOT NULL DEFAULT '',
    fx_rates_note TEXT NOT NULL DEFAULT '',
    major_events TEXT NOT NULL DEFAULT '',
    priority_sectors TEXT NOT NULL DEFAULT '',
    avoid_sectors TEXT NOT NULL DEFAULT '',
    operating_principles TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS sector_theme_map (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trade_date TEXT NOT NULL,
    sector_name TEXT NOT NULL,
    prior_move TEXT NOT NULL DEFAULT '',
    volume_change TEXT NOT NULL DEFAULT '',
    leader TEXT NOT NULL DEFAULT '',
    laggards TEXT NOT NULL DEFAULT '',
    news_note TEXT NOT NULL DEFAULT '',
    overseas_linkage TEXT NOT NULL DEFAULT '',
    overheated INTEGER NOT NULL DEFAULT 0,
    judgment TEXT NOT NULL,
    UNIQUE(trade_date, sector_name)
);

CREATE TABLE IF NOT EXISTS premarket_watchlist (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trade_date TEXT NOT NULL,
    ticker TEXT NOT NULL,
    name TEXT NOT NULL,
    market TEXT NOT NULL,
    sector_tags TEXT NOT NULL DEFAULT '',
    grade TEXT NOT NULL,
    bias TEXT NOT NULL,
    score INTEGER NOT NULL DEFAULT 0,
    thesis TEXT NOT NULL DEFAULT '',
    risk_tags TEXT NOT NULL DEFAULT '',
    observation_price TEXT NOT NULL DEFAULT '',
    alert_enabled INTEGER NOT NULL DEFAULT 0,
    final_action TEXT NOT NULL DEFAULT '',
    UNIQUE(trade_date, ticker),
    FOREIGN KEY(ticker) REFERENCES instrument_master(ticker)
);

CREATE TABLE IF NOT EXISTS stock_research_card (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    watchlist_item_id INTEGER NOT NULL UNIQUE,
    trade_date TEXT NOT NULL,
    ticker TEXT NOT NULL,
    confidence INTEGER NOT NULL DEFAULT 3,
    market_evidence TEXT NOT NULL DEFAULT '',
    sector_evidence TEXT NOT NULL DEFAULT '',
    news_evidence TEXT NOT NULL DEFAULT '',
    supply_evidence TEXT NOT NULL DEFAULT '',
    chart_evidence TEXT NOT NULL DEFAULT '',
    risks TEXT NOT NULL DEFAULT '',
    price_structure TEXT NOT NULL DEFAULT '',
    scenario TEXT NOT NULL DEFAULT '',
    invalidation TEXT NOT NULL DEFAULT '',
    stop_criteria TEXT NOT NULL DEFAULT '',
    forbidden_conditions TEXT NOT NULL DEFAULT '',
    result_note TEXT NOT NULL DEFAULT '',
    FOREIGN KEY(watchlist_item_id) REFERENCES premarket_watchlist(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS intraday_signal_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    watchlist_item_id INTEGER NOT NULL,
    trade_date TEXT NOT NULL,
    ticker TEXT NOT NULL,
    signal_time TEXT NOT NULL,
    signal_type TEXT NOT NULL,
    signal_source TEXT NOT NULL DEFAULT 'generated_alert',
    price REAL,
    volume_context TEXT NOT NULL DEFAULT '',
    interpretation TEXT NOT NULL DEFAULT '',
    FOREIGN KEY(watchlist_item_id) REFERENCES premarket_watchlist(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS user_decision_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    signal_id INTEGER NULL,
    watchlist_item_id INTEGER NOT NULL,
    trade_date TEXT NOT NULL,
    ticker TEXT NOT NULL,
    decision_time TEXT NOT NULL DEFAULT '',
    action TEXT NOT NULL,
    note TEXT NOT NULL DEFAULT '',
    execution_quality TEXT NOT NULL DEFAULT '',
    FOREIGN KEY(signal_id) REFERENCES intraday_signal_log(id) ON DELETE SET NULL,
    FOREIGN KEY(watchlist_item_id) REFERENCES premarket_watchlist(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS trade_execution_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    decision_id INTEGER NOT NULL,
    trade_date TEXT NOT NULL,
    ticker TEXT NOT NULL,
    entry_price REAL,
    exit_price REAL,
    fees REAL NOT NULL DEFAULT 0,
    result_r TEXT NOT NULL DEFAULT '',
    execution_note TEXT NOT NULL DEFAULT '',
    FOREIGN KEY(decision_id) REFERENCES user_decision_log(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS postmarket_review (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    watchlist_item_id INTEGER NOT NULL UNIQUE,
    trade_date TEXT NOT NULL,
    ticker TEXT NOT NULL,
    grade TEXT NOT NULL,
    bias TEXT NOT NULL,
    day_high_return REAL,
    day_low_return REAL,
    close_return REAL,
    bias_result TEXT NOT NULL DEFAULT 'ambiguous',
    signal_quality TEXT NOT NULL DEFAULT 'normal',
    execution_quality TEXT NOT NULL DEFAULT 'normal',
    failure_reason TEXT NOT NULL DEFAULT 'none',
    improvement_note TEXT NOT NULL DEFAULT '',
    FOREIGN KEY(watchlist_item_id) REFERENCES premarket_watchlist(id) ON DELETE CASCADE
);

CREATE TRIGGER IF NOT EXISTS enforce_ab_generated_alert_insert
BEFORE INSERT ON intraday_signal_log
WHEN NEW.signal_source = 'generated_alert' AND NOT EXISTS (
    SELECT 1 FROM premarket_watchlist
    WHERE id = NEW.watchlist_item_id
      AND grade IN ('A', 'B')
      AND alert_enabled = 1
)
BEGIN
    SELECT RAISE(ABORT, 'generated alerts are limited to alert-enabled A/B watchlist items');
END;

CREATE TRIGGER IF NOT EXISTS enforce_ab_generated_alert_update
BEFORE UPDATE OF signal_source, watchlist_item_id ON intraday_signal_log
WHEN NEW.signal_source = 'generated_alert' AND NOT EXISTS (
    SELECT 1 FROM premarket_watchlist
    WHERE id = NEW.watchlist_item_id
      AND grade IN ('A', 'B')
      AND alert_enabled = 1
)
BEGIN
    SELECT RAISE(ABORT, 'generated alerts are limited to alert-enabled A/B watchlist items');
END;

CREATE TRIGGER IF NOT EXISTS prevent_watchlist_downgrade_with_generated_alerts
BEFORE UPDATE OF grade, alert_enabled ON premarket_watchlist
WHEN (NEW.grade NOT IN ('A', 'B') OR NEW.alert_enabled != 1)
  AND EXISTS (
    SELECT 1 FROM intraday_signal_log
    WHERE watchlist_item_id = OLD.id
      AND signal_source = 'generated_alert'
  )
BEGIN
    SELECT RAISE(ABORT, 'cannot downgrade or disable alerts while generated alerts exist');
END;
"""


def managed_db_path(raw: str | Path) -> Path:
    """Return a safe app-managed DB path under `.quantlab/`.

    Streamlit exposes this for local convenience, but reset must never unlink arbitrary
    files. Only direct `.quantlab/*.sqlite3` paths are accepted.
    """

    candidate = Path(raw)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise ValueError("DB path must be a repo-local .quantlab/*.sqlite3 file")
    if len(candidate.parts) != 2 or candidate.parts[0] != MANAGED_DB_DIR.name:
        raise ValueError("DB path must be inside .quantlab/ and not in a subdirectory")
    if candidate.suffix != ".sqlite3":
        raise ValueError("DB path must use the .sqlite3 extension")
    if candidate.parent.is_symlink():
        raise ValueError("Managed DB directory must not be a symlink")
    if candidate.is_symlink():
        raise ValueError("DB path must not be a symlink")
    return candidate


def _require_table(table: str) -> None:
    if table not in ALLOWED_TABLES:
        raise ValueError(f"Unsupported table: {table}")


def _require_identifier(identifier: str) -> None:
    if not _IDENTIFIER.match(identifier):
        raise ValueError(f"Unsafe SQL identifier: {identifier}")


def _require_columns(columns: Iterable[str]) -> None:
    for column in columns:
        _require_identifier(column)


def _require_query_fragments(where: str, order_by: str) -> None:
    if where not in ALLOWED_WHERE:
        raise ValueError(f"Unsupported where clause: {where}")
    if order_by not in ALLOWED_ORDER_BY:
        raise ValueError(f"Unsupported order_by clause: {order_by}")

class Repository:
    def __init__(self, path: str | Path = DEFAULT_DB_PATH):
        self.path = Path(path)

    def connect(self) -> sqlite3.Connection:
        if self.path.parent.is_symlink():
            raise ValueError("Refusing to open database under symlinked directory")
        if self.path.is_symlink():
            raise ValueError("Refusing to open symlinked database path")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def initialize(self) -> None:
        with self.connect() as conn:
            conn.executescript(SCHEMA)

    def reset(self) -> None:
        if self.path.parent.is_symlink():
            raise ValueError("Refusing to reset database under symlinked directory")
        if self.path.is_symlink():
            raise ValueError("Refusing to reset symlinked database path")
        if self.path.exists():
            with self.path.open("rb") as fh:
                header = fh.read(16)
            if header and header != b"SQLite format 3\x00":
                raise ValueError("Refusing to overwrite a non-SQLite file")
            self.path.unlink()
        self.initialize()

    def upsert(self, table: str, values: Mapping[str, Any], conflict: str) -> int:
        _require_table(table)
        keys = list(values)
        _require_columns(keys)
        conflict_keys = [key.strip() for key in conflict.split(",")]
        _require_columns(conflict_keys)
        placeholders = ", ".join(["?"] * len(keys))
        cols = ", ".join(keys)
        updates = ", ".join(f"{k}=excluded.{k}" for k in keys if k not in conflict_keys)
        sql = (
            f"INSERT INTO {table} ({cols}) VALUES ({placeholders}) "
            f"ON CONFLICT({conflict}) DO UPDATE SET {updates}"
        )
        with self.connect() as conn:
            cur = conn.execute(sql, [values[k] for k in keys])
            if cur.lastrowid:
                return int(cur.lastrowid)
            row = conn.execute(
                f"SELECT rowid FROM {table} WHERE "
                + " AND ".join(f"{key}=?" for key in conflict_keys),
                [values[k] for k in conflict_keys],
            ).fetchone()
            if row is None:
                raise RuntimeError("Upsert did not return or find a row id")
            return int(row[0])

    def insert(self, table: str, values: Mapping[str, Any]) -> int:
        _require_table(table)
        keys = list(values)
        _require_columns(keys)
        placeholders = ", ".join(["?"] * len(keys))
        with self.connect() as conn:
            cur = conn.execute(
                f"INSERT INTO {table} ({', '.join(keys)}) VALUES ({placeholders})",
                [values[k] for k in keys],
            )
            if cur.lastrowid is None:
                raise RuntimeError("Insert did not return a row id")
            return int(cur.lastrowid)

    def update_by_id(self, table: str, row_id: int, values: Mapping[str, Any]) -> None:
        _require_table(table)
        if not values:
            return
        _require_columns(values.keys())
        assignments = ", ".join(f"{k}=?" for k in values)
        with self.connect() as conn:
            conn.execute(
                f"UPDATE {table} SET {assignments} WHERE id=?",
                [*values.values(), row_id],
            )

    def list_rows(
        self,
        table: str,
        where: str = "",
        params: Iterable[Any] = (),
        order_by: str = "",
    ) -> list[dict[str, Any]]:
        _require_table(table)
        _require_query_fragments(where, order_by)
        sql = f"SELECT * FROM {table}"
        if where:
            sql += f" WHERE {where}"
        if order_by:
            sql += f" ORDER BY {order_by}"
        with self.connect() as conn:
            return [dict(row) for row in conn.execute(sql, list(params)).fetchall()]

    def get_watchlist_item(self, trade_date: str, ticker: str) -> dict[str, Any] | None:
        rows = self.list_rows(
            "premarket_watchlist",
            "trade_date=? AND ticker=?",
            [trade_date, ticker],
        )
        return rows[0] if rows else None

    def get_watchlist_item_by_id(self, item_id: int) -> dict[str, Any] | None:
        rows = self.list_rows("premarket_watchlist", "id=?", [item_id])
        return rows[0] if rows else None

    def full_day(self, trade_date: str) -> dict[str, Any]:
        return {
            "brief": self.list_rows("daily_market_brief", "trade_date=?", [trade_date]),
            "sectors": self.list_rows("sector_theme_map", "trade_date=?", [trade_date], "sector_name"),
            "watchlist": self.list_rows("premarket_watchlist", "trade_date=?", [trade_date], "grade, score DESC"),
            "cards": self.list_rows("stock_research_card", "trade_date=?", [trade_date], "ticker"),
            "signals": self.list_rows("intraday_signal_log", "trade_date=?", [trade_date], "signal_time"),
            "decisions": self.list_rows("user_decision_log", "trade_date=?", [trade_date], "decision_time"),
            "executions": self.list_rows("trade_execution_log", "trade_date=?", [trade_date], "id"),
            "reviews": self.list_rows("postmarket_review", "trade_date=?", [trade_date], "ticker"),
        }
