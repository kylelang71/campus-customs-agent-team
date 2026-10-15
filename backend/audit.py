"""Append-only audit trail and the daily spending cap.

Every agent loop-step is written to output/audit_trail.json: the time, the tool
used, the data or message returned, and to whom or what it went. The file is a
JSON array that is only ever appended to: new entries are written over the
closing bracket at the end of the file, so existing entries are never read back
and rewritten. If the file isn't a well-formed array, nothing is written and an
error is raised instead of starting over.

The same file holds each run's token cost ("usage" entries), which is how the
daily spending cap is computed.
"""

from __future__ import annotations

import json
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

from models import AuditEntry

ROOT = Path(__file__).resolve().parent.parent  # HW5/
AUDIT_PATH = ROOT / "output" / "audit_trail.json"

DAILY_BUDGET_USD = 10.00
# USD per 1M tokens for gpt-6-luna (same prices as Lectures 11 tokenomics).
PRICE_INPUT, PRICE_CACHED_INPUT, PRICE_OUTPUT = 0.10, 0.01, 0.50
MAX_FIELD_CHARS = 20_000  # a single returned value is cut here so one huge reply can't bloat the file

_lock = threading.Lock()


class AuditError(RuntimeError):
    """The audit trail can't be safely appended to."""


class BudgetExceeded(RuntimeError):
    """The daily spending cap has been reached; all agent runs stop."""


def now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _clip(value: Any) -> Any:
    text = value if isinstance(value, str) else json.dumps(value, default=str, ensure_ascii=False)
    if len(text) <= MAX_FIELD_CHARS:
        return value
    return text[:MAX_FIELD_CHARS] + f"... [cut, {len(text)} chars total]"


def append(**fields: Any) -> None:
    """Append one entry. Never rewrites or removes what is already in the file."""
    if "returned" in fields:
        fields["returned"] = _clip(fields["returned"])
    entry = AuditEntry(time=now(), **fields).model_dump(mode="json", by_alias=True, exclude_none=True)
    block = "\n".join("  " + line for line in json.dumps(entry, indent=2, ensure_ascii=False).splitlines())

    with _lock:
        AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
        if not AUDIT_PATH.exists() or AUDIT_PATH.stat().st_size == 0:
            AUDIT_PATH.write_text(f"[\n{block}\n]\n", encoding="utf-8")  # only for a missing or empty file
            return
        with open(AUDIT_PATH, "r+b") as f:
            f.seek(0, 2)
            size = f.tell()
            tail_start = max(size - 512, 0)
            f.seek(tail_start)
            tail = f.read()
            close = tail.rfind(b"]")
            if close == -1 or tail[close + 1 :].strip():
                raise AuditError(f"{AUDIT_PATH} doesn't end in ']'; refusing to modify it.")
            before = tail[:close].rstrip()
            if before.endswith(b"["):
                separator = "\n"  # empty array
            elif before.endswith(b"}"):
                separator = ",\n"
            else:
                raise AuditError(f"{AUDIT_PATH} isn't a JSON array of entries; refusing to modify it.")
            end_of_last_entry = tail_start + len(before)
            f.seek(end_of_last_entry)
            f.write((separator + block + "\n]\n").encode("utf-8"))
            f.truncate()


def read_all() -> list[dict[str, Any]]:
    with _lock:  # never read while an append is half written (the events route reads from another thread)
        if not AUDIT_PATH.exists() or AUDIT_PATH.stat().st_size == 0:
            return []
        text = AUDIT_PATH.read_text(encoding="utf-8")
    try:
        rows = json.loads(text)
    except json.JSONDecodeError as exc:
        raise AuditError(f"{AUDIT_PATH} isn't valid JSON ({exc}); not continuing.") from None
    if not isinstance(rows, list):
        raise AuditError(f"{AUDIT_PATH} isn't a JSON array; not continuing.")
    return rows


def price(input_tokens: int, output_tokens: int, cached_tokens: int = 0) -> float:
    """Dollar cost of one run's usage. input_tokens includes the cached part."""
    cached = min(cached_tokens, input_tokens)
    return ((input_tokens - cached) * PRICE_INPUT + cached * PRICE_CACHED_INPUT + output_tokens * PRICE_OUTPUT) / 1_000_000


def spent_today() -> float:
    """Dollars used so far in today's allowance (the real calendar day, local time).

    A human can reset the allowance. That is written as a "budget_reset" entry (the trail is
    never edited or removed), and spending counts only from the latest reset today.
    """
    today = now()[:10]
    total = 0.0
    for row in read_all():
        if not str(row.get("time", "")).startswith(today):
            continue
        if row.get("kind") == "budget_reset":
            total = 0.0
        elif row.get("kind") == "usage":
            total += row.get("cost_usd") or 0.0
    return total


def budget_status() -> dict[str, Any]:
    """Today's allowance, for the dashboard's meter."""
    spent = spent_today()
    return {
        "limit": DAILY_BUDGET_USD,
        "spent": round(spent, 4),
        "remaining": round(max(DAILY_BUDGET_USD - spent, 0.0), 4),
        "percent": round(min(spent / DAILY_BUDGET_USD, 1.0) * 100, 2),
        "paused": spent >= DAILY_BUDGET_USD,
    }


def reset_allowance(name: str) -> dict[str, Any]:
    """A human gives permission to continue: start a fresh allowance. Appends a marker, removes nothing."""
    before = spent_today()
    append(
        run_id="budget-reset",
        agent="Human",
        kind="budget_reset",
        message=f"Daily allowance reset by {name} after ${before:.4f} was used",
        returned={"spent_before": round(before, 4), "approved_by": name},
        to="team",
    )
    return budget_status()


def check_budget(extra_usd: float = 0.0) -> None:
    """Raise BudgetExceeded if today's spend (plus a run still in progress) hit the cap."""
    spent = spent_today() + extra_usd
    if spent >= DAILY_BUDGET_USD:
        raise BudgetExceeded(f"Daily token budget of ${DAILY_BUDGET_USD:.2f} reached (${spent:.4f} spent today).")
