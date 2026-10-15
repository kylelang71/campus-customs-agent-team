"""Database helpers for the backend, and the reset function.

The original (data/campus_customs.db) is only ever read. The working copy
(data/campus_customs_new.db) is what the agents and the approve route change.
"""

from __future__ import annotations

import os
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent  # HW5/
ORIGINAL_DB = ROOT / "data" / "campus_customs.db"
WORKING_DB = ROOT / "data" / "campus_customs_new.db"
LAST_RESET = ROOT / "data" / "last_reset.txt"  # written by reset_database; the board only restores runs started after it


def _read(sql: str, args: tuple = ()) -> list[dict[str, Any]]:
    con = sqlite3.connect(f"file:{WORKING_DB}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in con.execute(sql, args)]
    finally:
        con.close()


def list_tickets() -> list[dict[str, Any]]:
    return _read("SELECT * FROM tickets ORDER BY id")


def get_ticket(ticket_id: int) -> dict[str, Any] | None:
    rows = _read("SELECT * FROM tickets WHERE id = ?", (ticket_id,))
    return rows[0] if rows else None


def checking_balance() -> dict[str, Any]:
    row = _read("SELECT name, balance, date FROM cash_accounts WHERE name = 'checking'")[0]
    return {"account": row["name"], "balance": row["balance"], "balance_date": row["date"], "shop_date": shop_date()}


def shop_date() -> str:
    return _read("SELECT date_today FROM desk")[0]["date_today"]


def reset_database() -> dict[str, str]:
    """Put the working database back to the original values, for a fresh run.

    Not called automatically and not a route: use it on purpose, when no team run is
    in progress. It replaces the working copy with a consistent copy of the original
    (which also drops every pending approval). The original is opened read-only, and
    the audit trail is not touched.
    """
    if not ORIGINAL_DB.exists():
        raise FileNotFoundError(f"Original database not found: {ORIGINAL_DB}")
    tmp = WORKING_DB.with_suffix(".db.tmp")
    tmp.unlink(missing_ok=True)
    src = sqlite3.connect(f"file:{ORIGINAL_DB}?mode=ro", uri=True)
    dst = sqlite3.connect(tmp)
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()
    for leftover in (WORKING_DB.with_name(WORKING_DB.name + "-wal"), WORKING_DB.with_name(WORKING_DB.name + "-shm")):
        leftover.unlink(missing_ok=True)
    os.replace(tmp, WORKING_DB)
    LAST_RESET.write_text(datetime.now().astimezone().isoformat(timespec="seconds") + "\n", encoding="utf-8")
    return {"original": str(ORIGINAL_DB), "working": str(WORKING_DB), "status": "reset"}


def last_reset() -> str | None:
    """When the working database was last reset (ISO time), or None if that was never recorded."""
    try:
        return LAST_RESET.read_text(encoding="utf-8").strip() or None
    except OSError:
        return None


if __name__ == "__main__":
    if sys.argv[1:] == ["reset"]:
        print(reset_database())
    else:
        print("Usage: python db.py reset   (puts the working database back to the original values)")
