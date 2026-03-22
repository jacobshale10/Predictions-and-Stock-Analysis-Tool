-- schema.sql — Human-readable reference for the trades database schema.
-- This file is NOT executed by the app. The app uses db.py which contains
-- the CREATE TABLE IF NOT EXISTS statement inline.
-- You can open trades.db in "DB Browser for SQLite" (free app) to inspect data.

CREATE TABLE IF NOT EXISTS trades (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker              TEXT NOT NULL,
    company_name        TEXT,
    entry_date          TEXT NOT NULL,           -- ISO 8601: YYYY-MM-DD
    entry_price         REAL NOT NULL,
    position_size_usd   REAL,                    -- optional dollar amount

    -- Snapshot of scores at entry time (for future backtest/correlation analysis)
    score_at_entry      REAL,
    grade_at_entry      TEXT,                    -- STRONG / MODERATE / WEAK
    dcf_margin_at_entry REAL,                    -- margin of safety % at entry
    decline_at_entry    REAL,                    -- % decline from 52w high at entry
    catalyst_type       TEXT,                    -- confirmed_one_time / likely_one_time /
                                                 -- uncertain / likely_structural / structural_damage

    -- Exit data (NULL while trade is open)
    exit_date           TEXT,                    -- ISO 8601: YYYY-MM-DD
    exit_price          REAL,
    exit_reason         TEXT,                    -- target_hit / stop_loss / thesis_broken / other

    -- Calculated on exit
    pnl_pct             REAL,                    -- (exit_price - entry_price) / entry_price
    holding_days        INTEGER,                 -- calendar days held

    -- Qualitative notes
    thesis_notes        TEXT,                    -- why you entered
    review_notes        TEXT,                    -- post-trade review

    created_at          TEXT DEFAULT (datetime('now')),
    updated_at          TEXT DEFAULT (datetime('now'))
);
