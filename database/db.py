"""
database/db.py — SQLite persistence layer for the trade log.
Uses Python's built-in sqlite3 — no installation required.
The database file (trades.db) is created automatically on first run.
"""

import sqlite3
import os
from datetime import date, datetime

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "trades.db")

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS trades (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker              TEXT NOT NULL,
    company_name        TEXT,
    entry_date          TEXT NOT NULL,
    entry_price         REAL NOT NULL,
    position_size_usd   REAL,
    score_at_entry      REAL,
    grade_at_entry      TEXT,
    dcf_margin_at_entry REAL,
    decline_at_entry    REAL,
    catalyst_type       TEXT,
    exit_date           TEXT,
    exit_price          REAL,
    exit_reason         TEXT,
    pnl_pct             REAL,
    holding_days        INTEGER,
    thesis_notes        TEXT,
    review_notes        TEXT,
    created_at          TEXT DEFAULT (datetime('now')),
    updated_at          TEXT DEFAULT (datetime('now'))
);
"""


def _connect():
    return sqlite3.connect(DB_PATH)


def init_db():
    """Create the trades table if it doesn't exist. Call once at app startup."""
    with _connect() as conn:
        conn.execute(CREATE_TABLE_SQL)
        conn.commit()


def insert_trade(
    ticker: str,
    entry_date: str,
    entry_price: float,
    company_name: str = None,
    position_size_usd: float = None,
    score_at_entry: float = None,
    grade_at_entry: str = None,
    dcf_margin_at_entry: float = None,
    decline_at_entry: float = None,
    catalyst_type: str = None,
    thesis_notes: str = None,
) -> int:
    """Insert a new open trade. Returns the new row id."""
    sql = """
    INSERT INTO trades (
        ticker, company_name, entry_date, entry_price, position_size_usd,
        score_at_entry, grade_at_entry, dcf_margin_at_entry, decline_at_entry,
        catalyst_type, thesis_notes
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
    with _connect() as conn:
        cursor = conn.execute(sql, (
            ticker.upper(), company_name, entry_date, entry_price, position_size_usd,
            score_at_entry, grade_at_entry, dcf_margin_at_entry, decline_at_entry,
            catalyst_type, thesis_notes,
        ))
        conn.commit()
        return cursor.lastrowid


def get_all_trades() -> list[dict]:
    """Return all trades as a list of dicts, newest first."""
    sql = "SELECT * FROM trades ORDER BY entry_date DESC, id DESC"
    with _connect() as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(sql).fetchall()
    return [dict(row) for row in rows]


def get_open_trades() -> list[dict]:
    """Return all trades where exit_date is NULL."""
    sql = "SELECT * FROM trades WHERE exit_date IS NULL ORDER BY entry_date DESC"
    with _connect() as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(sql).fetchall()
    return [dict(row) for row in rows]


def update_trade_exit(
    trade_id: int,
    exit_date: str,
    exit_price: float,
    exit_reason: str,
    review_notes: str = None,
) -> None:
    """Record the exit for an open trade and calculate P&L."""
    # Fetch entry data to compute P&L
    with _connect() as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT entry_price, entry_date FROM trades WHERE id = ?", (trade_id,)).fetchone()
        if row is None:
            raise ValueError(f"Trade id {trade_id} not found")

        entry_price = row["entry_price"]
        entry_date_str = row["entry_date"]

    pnl_pct = (exit_price - entry_price) / entry_price

    entry_dt = datetime.strptime(entry_date_str, "%Y-%m-%d").date()
    exit_dt  = datetime.strptime(exit_date, "%Y-%m-%d").date()
    holding_days = (exit_dt - entry_dt).days

    sql = """
    UPDATE trades SET
        exit_date    = ?,
        exit_price   = ?,
        exit_reason  = ?,
        pnl_pct      = ?,
        holding_days = ?,
        review_notes = ?,
        updated_at   = datetime('now')
    WHERE id = ?
    """
    with _connect() as conn:
        conn.execute(sql, (exit_date, exit_price, exit_reason, pnl_pct, holding_days, review_notes, trade_id))
        conn.commit()


def delete_trade(trade_id: int) -> None:
    """Permanently delete a trade record."""
    with _connect() as conn:
        conn.execute("DELETE FROM trades WHERE id = ?", (trade_id,))
        conn.commit()
