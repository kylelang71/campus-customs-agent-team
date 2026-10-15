"""Pending approvals: agents PREPARE payments, purchases and customer messages, a human APPROVES them.

`prepare_*` (called by the MCP tools) only writes a row to the pending_approvals
table of the working database. Cash, invoices, payments and leases change only in
`decide`, which the backend calls when a person clicks approve. Nothing in this file
is exposed to the agents as a tool.

The table lives in the working copy (campus_customs_new.db), so resetting the
database to the original values also clears every pending approval.
"""

from __future__ import annotations

import calendar
import json
import math
import re
import sqlite3
from datetime import date, datetime
from pathlib import Path
from typing import Any

SCHEMA = """
CREATE TABLE IF NOT EXISTS pending_approvals (
    id INTEGER PRIMARY KEY,
    kind TEXT NOT NULL,            -- 'payment', 'purchase' or 'message'
    payload TEXT NOT NULL,         -- JSON of what will happen on approval
    summary TEXT NOT NULL,         -- what the human is shown
    status TEXT NOT NULL,          -- pending, approved, declined, failed
    created_at TEXT NOT NULL,
    decided_at TEXT,
    decided_by TEXT,
    result TEXT                    -- JSON of the payment/invoice row, or the failure reason
)
"""


def _connect(db_path: Path) -> sqlite3.Connection:
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    con.execute(SCHEMA)
    return con


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _shop_date(con: sqlite3.Connection) -> str:
    return con.execute("SELECT date_today FROM desk").fetchone()["date_today"]


def _add_month(iso: str) -> str:
    d = date.fromisoformat(iso)
    year, month = (d.year + (d.month == 12), d.month % 12 + 1)
    return date(year, month, min(d.day, calendar.monthrange(year, month)[1])).isoformat()


def _row(r: sqlite3.Row) -> dict[str, Any]:
    out = dict(r)
    out["payload"] = json.loads(out["payload"])
    out["result"] = json.loads(out["result"]) if out["result"] else None
    return out


class InsufficientCash(ValueError):
    """Approving would take checking below zero. The approval stays pending."""


def _cash_block(con: sqlite3.Connection, kind: str, payload: dict) -> str | None:
    """Why a pending approval can't be approved right now because of cash, or None.

    A payment spends cash now. A purchase becomes an open invoice that has to be paid from checking, so an order
    larger than the balance is refused too: the shop can't commit to what it can't pay. Messages spend nothing.
    """
    if kind == "message":
        return None
    if kind == "purchase":
        amount = payload["amount"]
    else:
        try:
            amount, _ = _payment_facts(con, payload["kind"], payload["ref_id"])
        except ValueError:
            return None  # not payable any more: that is reported when someone tries to approve
    balance = con.execute("SELECT balance FROM cash_accounts WHERE name = 'checking'").fetchone()[0]
    if amount <= balance:
        return None
    short = amount - balance
    if kind == "purchase":
        return (
            f"Can't approve: this order is ${amount:,.2f} but checking holds ${balance:,.2f}, so it could not be paid "
            f"(short by ${short:,.2f}; cash can't go negative). It stays pending until cash covers it."
        )
    return (
        f"Can't approve: this pays ${amount:,.2f} but checking holds ${balance:,.2f}, so cash would go to -${short:,.2f}. "
        "It stays pending until cash covers it."
    )


def _annotate(con: sqlite3.Connection, row: dict[str, Any]) -> dict[str, Any]:
    """Add what the board needs to halt an approval that would overdraw checking (pending items only)."""
    reason = _cash_block(con, row["kind"], row["payload"]) if row["status"] == "pending" else None
    return {**row, "blocked": reason is not None, "block_reason": reason}


def _read_only(db_path: Path) -> sqlite3.Connection | None:
    """A read-only connection, or None if the approvals table doesn't exist yet. Never changes the database."""
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    if con.execute("SELECT 1 FROM sqlite_master WHERE name = 'pending_approvals'").fetchone() is None:
        con.close()
        return None
    return con


def list_approvals(db_path: Path, status: str | None = None) -> list[dict[str, Any]]:
    con = _read_only(db_path)
    if con is None:
        return []
    try:
        sql, args = "SELECT * FROM pending_approvals", ()
        if status:
            sql, args = sql + " WHERE status = ?", (status,)
        return [_annotate(con, _row(r)) for r in con.execute(sql + " ORDER BY id", args)]
    finally:
        con.close()


def get_approval(db_path: Path, approval_id: int) -> dict[str, Any] | None:
    con = _read_only(db_path)
    if con is None:
        return None
    try:
        r = con.execute("SELECT * FROM pending_approvals WHERE id = ?", (approval_id,)).fetchone()
        return _annotate(con, _row(r)) if r else None
    finally:
        con.close()


def _payment_facts(con: sqlite3.Connection, kind: str, ref_id: int) -> tuple[float, str]:
    """(amount, description) of what would be paid; raises if it can't be paid."""
    if kind == "invoice":
        r = con.execute(
            "SELECT i.amount, i.status, i.description, v.name FROM invoices i "
            "LEFT JOIN vendors v ON v.id = i.vendor_id WHERE i.id = ?",
            (ref_id,),
        ).fetchone()
        if r is None:
            raise ValueError(f"No invoice with id {ref_id}")
        if r["status"] != "open":
            raise ValueError(f"Invoice {ref_id} is '{r['status']}', not open")
        detail = f" ({r['description']})" if r["description"] else ""
        return r["amount"], f"invoice {ref_id} to {r['name']}{detail}"
    r = con.execute("SELECT monthly_rent, landlord, next_due FROM leases WHERE id = ?", (ref_id,)).fetchone()
    if r is None:
        raise ValueError(f"No lease with id {ref_id}")
    return r["monthly_rent"], f"rent to {r['landlord']} (due {r['next_due']})"


def _insert(con: sqlite3.Connection, kind: str, payload: dict, summary: str) -> dict[str, Any]:
    cur = con.execute(
        "INSERT INTO pending_approvals (kind, payload, summary, status, created_at) VALUES (?, ?, ?, 'pending', ?)",
        (kind, json.dumps(payload), summary, _now()),
    )
    con.commit()
    return _row(con.execute("SELECT * FROM pending_approvals WHERE id = ?", (cur.lastrowid,)).fetchone())


def _clean_review(justification: str, checks: list[str], concerns: list[str], ticket_id: int | None, margin_note: str | None, need_margin: bool) -> dict[str, Any]:
    """The team's own reasoning, checked for completeness. Agents get a clear error and must resend."""
    justification = " ".join((justification or "").split())
    checks = [" ".join(c.split()) for c in (checks or []) if c and c.strip()]
    concerns = [" ".join(c.split()) for c in (concerns or []) if c and c.strip()]
    margin_note = " ".join(margin_note.split()) if margin_note and margin_note.strip() else None
    if len(justification) < 20:
        raise ValueError("justification is required: say why this should be approved, in at least a full sentence.")
    if not checks:
        raise ValueError("checks is required: list what was verified (for example the invoice, the balance, other open tickets, lead time).")
    if need_margin and not margin_note:
        raise ValueError("margin_note is required for a purchase: state the margin result under the 30% rule, or why it does not apply.")
    return {"justification": justification, "checks": checks, "concerns": concerns, "margin_note": margin_note, "ticket_id": ticket_id}


def _facts(con: sqlite3.Connection, kind: str, ref_id: int | None, amount: float, vendor_id: int | None = None, pays_now: bool = True) -> dict[str, Any]:
    """Numbers worked out here from the database, not supplied by an agent, plus warnings the human should see."""
    today = _shop_date(con)
    cash = con.execute("SELECT balance FROM cash_accounts WHERE name = 'checking'").fetchone()["balance"]
    others = []  # other firm obligations: open invoices and rent
    for r in con.execute("SELECT i.id, i.amount, i.due_date, v.name FROM invoices i LEFT JOIN vendors v ON v.id = i.vendor_id WHERE i.status = 'open'"):
        if not (kind == "invoice" and r["id"] == ref_id):
            others.append({"what": f"invoice {r['id']} ({r['name']})", "amount": r["amount"], "due": r["due_date"]})
    for r in con.execute("SELECT id, landlord, monthly_rent, next_due FROM leases"):
        if not (kind == "rent" and r["id"] == ref_id):
            others.append({"what": f"rent ({r['landlord']})", "amount": r["monthly_rent"], "due": r["next_due"]})
    others_total = round(sum(o["amount"] for o in others), 2)
    facts: dict[str, Any] = {
        "shop_date": today,
        "cash_before": cash,
        "cash_after_this": round(cash - amount, 2) if pays_now else cash,
        "other_firm_obligations": others,
        "other_firm_obligations_total": others_total,
        "cash_after_all_firm": round(cash - amount - others_total, 2),
        "open_tickets": [dict(r) for r in con.execute("SELECT id, type, subject FROM tickets WHERE status = 'open' ORDER BY id")],
        "warnings": [],
    }
    warn: list[str] = facts["warnings"]
    if cash < amount:  # a payment spends it now; a purchase becomes an invoice that must be paid from it
        warn.append(f"Cash is short: this needs ${amount:,.2f} but checking holds ${cash:,.2f}. Approval is blocked until cash covers it.")
    if facts["cash_after_all_firm"] < 0:
        warn.append(
            f"Cash concern: after this ${amount:,.2f}, the other open invoices and rent (${others_total:,.2f}) "
            f"can't all be covered. Short by ${-facts['cash_after_all_firm']:,.2f}."
        )
    if pays_now and 0 <= cash - amount < 0.2 * cash:
        warn.append(f"Cash concern: this leaves ${cash - amount:,.2f} ({(cash - amount) / cash:.0%} of today's ${cash:,.2f}).")
    due = None
    if kind == "invoice":
        due = con.execute("SELECT due_date FROM invoices WHERE id = ?", (ref_id,)).fetchone()["due_date"]
    elif kind == "rent":
        due = con.execute("SELECT next_due FROM leases WHERE id = ?", (ref_id,)).fetchone()["next_due"]
    if due:
        days = (date.fromisoformat(today) - date.fromisoformat(due)).days
        facts["due"] = due
        facts["days_overdue"] = max(days, 0)
        facts["days_until_due"] = max(-days, 0)
        if days > 0:
            warn.append(f"Overdue by {days} day{'s' if days != 1 else ''} (due {due}).")
    if vendor_id is not None:
        v = con.execute("SELECT name, lead_days FROM vendors WHERE id = ?", (vendor_id,)).fetchone()
        facts["vendor"], facts["vendor_lead_days"] = v["name"], v["lead_days"]
        blocking = [o for o in others if o["what"].startswith("invoice") and v["name"] in o["what"]]
        if blocking:
            warn.append(f"This vendor still has an open invoice ({blocking[0]['what']}); vendors won't ship until it is paid.")
    return facts


def prepare_payment(db_path: Path, kind: str, ref_id: int, justification: str = "", checks: list[str] | None = None, concerns: list[str] | None = None, ticket_id: int | None = None, margin_note: str | None = None) -> dict[str, Any]:
    """Prepare (never make) a payment. Refuses if the item isn't payable. A payment that cash can't cover can still be
    prepared; it carries a warning, and approving it is blocked (see `decide`) until cash covers it."""
    if kind not in ("invoice", "rent"):
        raise ValueError("kind must be 'invoice' or 'rent'")
    review = _clean_review(justification, checks or [], concerns or [], ticket_id, margin_note, need_margin=False)
    con = _connect(db_path)
    try:
        con.execute("BEGIN IMMEDIATE")  # one prepare at a time, so duplicates can't slip in together
        amount, what = _payment_facts(con, kind, ref_id)
        balance = con.execute("SELECT balance FROM cash_accounts WHERE name = 'checking'").fetchone()["balance"]
        for r in con.execute("SELECT * FROM pending_approvals WHERE kind = 'payment' AND status = 'pending'"):
            p = json.loads(r["payload"])
            if p["kind"] == kind and p["ref_id"] == ref_id:
                return _row(r)  # already waiting for a human
        summary = (
            f"Pay ${amount:,.2f} for {what}. Checking balance ${balance:,.2f}, "
            f"${balance - amount:,.2f} after this payment."
        )
        facts = _facts(con, kind, ref_id, amount)
        return _insert(con, "payment", {"kind": kind, "ref_id": ref_id, "amount": amount, "review": review, "facts": facts}, summary)
    finally:
        con.close()


def prepare_purchase(db_path: Path, vendor_id: int, amount: float, due_date: str, description: str, justification: str = "", checks: list[str] | None = None, concerns: list[str] | None = None, margin_note: str | None = None, ticket_id: int | None = None) -> dict[str, Any]:
    """Prepare (never place) a vendor order, which becomes an open invoice once a human approves."""
    if amount <= 0:
        raise ValueError("amount must be greater than 0")
    try:
        date.fromisoformat(due_date)
    except ValueError:
        raise ValueError("due_date must be a real date in YYYY-MM-DD format") from None
    review = _clean_review(justification, checks or [], concerns or [], ticket_id, margin_note, need_margin=True)
    con = _connect(db_path)
    try:
        con.execute("BEGIN IMMEDIATE")  # one prepare at a time, so duplicates can't slip in together
        v = con.execute("SELECT name FROM vendors WHERE id = ?", (vendor_id,)).fetchone()
        if v is None:
            raise ValueError(f"No vendor with id {vendor_id}")
        payload = {"vendor_id": vendor_id, "amount": amount, "due_date": due_date, "description": description.strip()}
        for r in con.execute("SELECT * FROM pending_approvals WHERE kind = 'purchase' AND status = 'pending'"):
            old = json.loads(r["payload"])
            if all(old.get(k) == payload[k] for k in payload):
                return _row(r)
        payload = {**payload, "review": review, "facts": _facts(con, "purchase", None, amount, vendor_id=vendor_id, pays_now=False)}
        summary = f"Place an order with {v['name']}: ${amount:,.2f}, due {due_date}. {description.strip()}"
        return _insert(con, "purchase", payload, summary)
    finally:
        con.close()


# Words that never belong in a message to a customer (see the Boss's draft-review list).
INTERNAL_TERMS = ("unit cost", "margin", "invoice", "invoices", "lease", "landlord", "rent", "cash", "balance", "checking account", "agent", "agents", "prompt", "database")
MAX_MESSAGE_CHARS = 1500
MIN_MARGIN = 0.30  # same floor as backend/models.py: the lowest allowed unit price is cost / 0.70, rounded up to the cent


def _message_problems(con: sqlite3.Connection, ticket: sqlite3.Row, body: str) -> list[str]:
    """Rules a customer message can be checked against without a model. The Boss's own review still applies."""
    ticket_id, requester = ticket["id"], ticket["requester"]
    low = body.lower()
    problems = []
    for (name,) in con.execute("SELECT name FROM vendors"):
        if name.lower() in low:
            problems.append(f"it names a vendor ({name}); customers may only hear the lead time")
    for (name,) in con.execute("SELECT DISTINCT requester FROM tickets WHERE id != ?", (ticket_id,)):
        if name and name != requester and name.lower() in low:
            problems.append(f"it names another customer ({name})")
    for term in INTERNAL_TERMS:
        if re.search(rf"\b{re.escape(term)}\b", low):
            problems.append(f"it uses the internal term '{term}'")
    list_prices = {round(r[0], 2) for r in con.execute("SELECT list_price FROM pricing")}
    # On a price override the decided unit price (above the 30% floor, below list) and its quantity total may be quoted.
    low = high = None
    qty = ticket["qty"] or 1
    row = con.execute("SELECT unit_cost, list_price FROM pricing WHERE sku = ?", (ticket["sku"],)).fetchone() if ticket["type"] == "price_override" else None
    if row:
        low, high = math.ceil(row["unit_cost"] / (1 - MIN_MARGIN) * 100) / 100, row["list_price"]
    decided = False
    for m in re.finditer(r"\$\s?(\d[\d,]*(?:\.\d+)?)", body):
        amount = round(float(m.group(1).replace(",", "")), 2)
        if amount in list_prices:
            pass  # the list price may always be mentioned; it is not the team's decision
        elif low is not None and low < amount < high:
            decided = True  # a unit price in the allowed band: above the margin floor, below list
        elif low is not None and qty * low < amount <= qty * high:
            pass  # the total for the quantity
        else:
            problems.append(f"it quotes ${m.group(1)}, which is not a price a customer may be quoted")
    if row and not decided:
        problems.append("it doesn't state the unit price the team decided; a price override reply must name one specific price per unit (above the minimum margin, below the list price)")
    return problems


def prepare_message(db_path: Path, ticket_id: int, subject: str, body: str, justification: str = "", checks: list[str] | None = None, concerns: list[str] | None = None) -> dict[str, Any]:
    """Prepare (never send) a reply to a customer. A human approves the exact text; nothing is ever sent."""
    subject, body = " ".join((subject or "").split()), (body or "").strip()
    if not subject or not body:
        raise ValueError("subject and body are required.")
    if len(body) > MAX_MESSAGE_CHARS:
        raise ValueError(f"body is {len(body)} characters; keep a customer message under {MAX_MESSAGE_CHARS}.")
    review = _clean_review(justification, checks or [], concerns or [], ticket_id, None, need_margin=False)
    con = _connect(db_path)
    try:
        con.execute("BEGIN IMMEDIATE")  # one prepare at a time, so duplicates can't slip in together
        t = con.execute("SELECT id, type, requester, subject, status, sku, qty FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
        if t is None:
            raise ValueError(f"No ticket with id {ticket_id}")
        if t["type"] == "rent_notice":
            raise ValueError(f"Ticket {ticket_id} is a {t['type']}: it has no customer to write to.")
        if t["status"] != "open":
            raise ValueError(f"Ticket {ticket_id} is already {t['status']}.")
        problems = _message_problems(con, t, f"{subject}\n{body}")
        if problems:
            raise ValueError("Not prepared. The message breaks the customer-information rules: " + "; ".join(problems) + ". Fix the text, get it reviewed again, and resend.")
        for r in con.execute("SELECT * FROM pending_approvals WHERE kind = 'message' AND status = 'pending'"):
            old = json.loads(r["payload"])
            if old["ticket_id"] == ticket_id:
                return _row(r)  # a reply for this ticket is already waiting for a human
        payload = {
            "ticket_id": ticket_id,
            "to": t["requester"],
            "subject": subject,
            "body": body,
            "review": review,
            "context": {"shop_date": _shop_date(con), "ticket_type": t["type"], "ticket_subject": t["subject"], "rules_checked": "no vendor or other-customer names, no internal terms, only list prices"},
        }
        return _insert(con, "message", payload, f"Reply to {t['requester']} about ticket {ticket_id} ({t['subject']}): \"{subject}\"")
    finally:
        con.close()


def decide(db_path: Path, approval_id: int, approve: bool, name: str) -> dict[str, Any]:
    """Record a human's decision. Approving is the ONLY place cash, invoices, payments and leases change."""
    name = name.strip()
    if not name:
        raise ValueError("A name is required.")
    con = _connect(db_path)
    try:
        con.execute("BEGIN IMMEDIATE")
        r = con.execute("SELECT * FROM pending_approvals WHERE id = ?", (approval_id,)).fetchone()
        if r is None:
            raise LookupError(f"No approval with id {approval_id}")
        if r["status"] != "pending":
            raise ValueError(f"Approval {approval_id} is already {r['status']}")
        payload = json.loads(r["payload"])
        result: Any = None
        status = "declined"
        if approve:
            reason = _cash_block(con, r["kind"], payload)
            if reason:
                raise InsufficientCash(reason)  # nothing is written; the approval stays pending
            try:
                result = _execute(con, r["kind"], payload, name)
                status = "approved"
            except ValueError as exc:
                con.rollback()
                con.execute("BEGIN IMMEDIATE")
                result, status = {"error": str(exc)}, "failed"
        con.execute(
            "UPDATE pending_approvals SET status = ?, decided_at = ?, decided_by = ?, result = ? WHERE id = ?",
            (status, _now(), name, json.dumps(result) if result is not None else None, approval_id),
        )
        con.commit()
        out = _row(con.execute("SELECT * FROM pending_approvals WHERE id = ?", (approval_id,)).fetchone())
        return out
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


def _execute(con: sqlite3.Connection, kind: str, payload: dict, approver: str) -> dict[str, Any]:
    today = _shop_date(con)
    if kind == "message":
        # Approval clears the exact text and records it on the ticket. Nothing is sent: there is no mail connection.
        t = con.execute("SELECT notes FROM tickets WHERE id = ?", (payload["ticket_id"],)).fetchone()
        if t is None:
            raise ValueError(f"No ticket with id {payload['ticket_id']}")
        note = f"[Customer reply approved by {approver} on {today}] {payload['subject']}: {payload['body']}"
        con.execute("UPDATE tickets SET notes = ? WHERE id = ?", (" | ".join(p for p in (t["notes"], note) if p), payload["ticket_id"]))
        return {"ticket_id": payload["ticket_id"], "to": payload["to"], "subject": payload["subject"], "body": payload["body"], "approved_by": approver, "sent": False}
    if kind == "purchase":
        cur = con.execute(
            "INSERT INTO invoices (vendor_id, amount, due_date, status, description) VALUES (?, ?, ?, 'open', ?)",
            (payload["vendor_id"], payload["amount"], payload["due_date"], payload["description"]),
        )
        return dict(con.execute("SELECT * FROM invoices WHERE id = ?", (cur.lastrowid,)).fetchone())

    # payment: re-check everything now, since time has passed since it was prepared
    amount, _ = _payment_facts(con, payload["kind"], payload["ref_id"])
    spent = con.execute(
        "UPDATE cash_accounts SET balance = ROUND(balance - ?, 2), date = ? WHERE name = 'checking' AND balance >= ?",
        (amount, today, amount),
    )
    if spent.rowcount != 1:
        raise ValueError("Not enough cash. No payment made.")
    cur = con.execute(
        "INSERT INTO payments (kind, ref_id, amount, account, paid_at, approved_by) VALUES (?, ?, ?, 'checking', ?, ?)",
        (payload["kind"], payload["ref_id"], amount, today, approver),
    )
    if payload["kind"] == "invoice":
        con.execute("UPDATE invoices SET status = 'paid' WHERE id = ?", (payload["ref_id"],))
    else:
        old = con.execute("SELECT next_due FROM leases WHERE id = ?", (payload["ref_id"],)).fetchone()["next_due"]
        con.execute("UPDATE leases SET next_due = ? WHERE id = ?", (_add_month(old), payload["ref_id"]))
    return dict(con.execute("SELECT * FROM payments WHERE id = ?", (cur.lastrowid,)).fetchone())
