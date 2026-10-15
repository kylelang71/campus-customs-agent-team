"""Campus Customs MCP server.

Exposes tools that agents call to read the shop's working database.
Only data/campus_customs_new.db is ever opened; the original
campus_customs.db is never touched (see output/harness.md).
"""

import sqlite3
from pathlib import Path

from fastmcp import FastMCP

import approvals

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "campus_customs_new.db"

mcp = FastMCP("campus-customs")


def _query(sql: str) -> list[dict]:
    con = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    try:
        return [dict(row) for row in con.execute(sql).fetchall()]
    finally:
        con.close()


def _today() -> str:
    """The shop's assumed date (desk.date_today), never the real date."""
    return _query("SELECT date_today FROM desk")[0]["date_today"]


@mcp.tool
def read_desk() -> list[dict]:
    """Read the desk table: date_today (the shop's assumed date, used for everything that is 'today') and notes."""
    return _query("SELECT date_today, notes FROM desk")


@mcp.tool
def read_inventory() -> list[dict]:
    """Read every row of the inventory table: sku, name, size, qty, location."""
    return _query("SELECT sku, size, name, qty, location FROM inventory ORDER BY sku, size")


@mcp.tool
def read_invoices() -> list[dict]:
    """Read every row of the invoices table: id, vendor_id, amount, due_date, status, description."""
    return _query("SELECT id, vendor_id, amount, due_date, status, description FROM invoices ORDER BY id")


@mcp.tool
def read_balance() -> list[dict]:
    """Read every row of the cash_accounts table: name, balance, date."""
    return _query("SELECT name, balance, date FROM cash_accounts")


@mcp.tool
def read_lease() -> list[dict]:
    """Read every row of the leases table, all fields: id, space_name, landlord, monthly_rent, next_due, notes."""
    return _query("SELECT * FROM leases ORDER BY id")


@mcp.tool
def read_vendor() -> list[dict]:
    """Read every row of the vendors table, all fields: id, name, specialty, lead_days."""
    return _query("SELECT * FROM vendors ORDER BY id")


@mcp.tool
def read_pricing() -> list[dict]:
    """Read every row of the pricing table, all fields: sku, unit_cost, list_price."""
    return _query("SELECT * FROM pricing ORDER BY sku")


@mcp.tool
def read_payments() -> list[dict]:
    """Read every row of the payments table, all fields: id, kind, ref_id, amount, account, paid_at, approved_by."""
    return _query("SELECT * FROM payments ORDER BY id")


@mcp.tool
def read_ticket() -> list[dict]:
    """Read every row of the tickets table, all fields: id, type, requester, subject, sku, size, qty, lease_id, invoice_id, status, notes, created_at."""
    return _query("SELECT * FROM tickets ORDER BY id")


@mcp.tool
def write_ticket(ticket_id: int, status: str, notes: str) -> dict:
    """Update a ticket's status and notes (no other field can be changed).

    status must be 'open' or 'closed'. The notes you pass are APPENDED to the
    ticket's existing notes, so the original request is kept. When closing,
    the shop date (desk.date_today) is stamped on the front automatically.
    Notes should cover the actions taken, suppliers worked with, the
    delegation path, and any exceptions a human had to handle.
    Returns the updated ticket row.
    """
    if status not in ("open", "closed"):
        raise ValueError("status must be 'open' or 'closed'")
    con = sqlite3.connect(DB_PATH)  # the working copy only; see module docstring
    con.row_factory = sqlite3.Row
    try:
        row = con.execute("SELECT notes FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
        if row is None:
            raise ValueError(f"No ticket with id {ticket_id}")
        stamp = f"[Closed {_today()}] " if status == "closed" else ""
        new_notes = " | ".join(part for part in (row["notes"], stamp + notes.strip()) if part)
        con.execute(
            "UPDATE tickets SET status = ?, notes = ? WHERE id = ?",
            (status, new_notes, ticket_id),
        )
        con.commit()
        return dict(con.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,)).fetchone())
    finally:
        con.close()


@mcp.tool
def write_inventory(sku: str, size: str, qty_change: int) -> dict:
    """Adjust the stock of one inventory row (sku + size) by a signed amount.

    Use a positive qty_change when stock arrives (e.g. a vendor reprint is
    received) and a negative one when stock leaves (e.g. an order is filled).
    Only qty can change; name and location are fixed and new rows can't be
    created. Stock can never go negative: a change that would drop qty below
    zero is rejected and nothing is written.
    Returns the updated inventory row.
    """
    if qty_change == 0:
        raise ValueError("qty_change must not be 0")
    con = sqlite3.connect(DB_PATH)  # the working copy only; see module docstring
    con.row_factory = sqlite3.Row
    try:
        row = con.execute(
            "SELECT qty FROM inventory WHERE sku = ? AND size = ?", (sku, size)
        ).fetchone()
        if row is None:
            raise ValueError(f"No inventory row for sku '{sku}' size '{size}'")
        if row["qty"] + qty_change < 0:
            raise ValueError(
                f"Only {row['qty']} in stock; can't remove {-qty_change} (stock can't go negative)"
            )
        # The WHERE clause re-checks the floor inside the UPDATE itself.
        con.execute(
            "UPDATE inventory SET qty = qty + ? WHERE sku = ? AND size = ? AND qty + ? >= 0",
            (qty_change, sku, size, qty_change),
        )
        con.commit()
        return dict(
            con.execute(
                "SELECT sku, size, name, qty, location FROM inventory WHERE sku = ? AND size = ?",
                (sku, size),
            ).fetchone()
        )
    finally:
        con.close()


@mcp.tool
def write_invoices(
    vendor_id: int,
    amount: float,
    due_date: str,
    description: str,
    justification: str,
    checks: list[str],
    margin_note: str,
    concerns: list[str] | None = None,
    ticket_id: int | None = None,
) -> dict:
    """PREPARE a purchase: a new vendor order that becomes an open invoice once a human approves it.

    due_date must be YYYY-MM-DD. This tool never creates the invoice itself, never edits
    an existing one, and never marks anything paid. It records a pending approval and
    returns it (status 'pending'). Paying an invoice is a separate step (write_payments),
    which also needs a human.

    The approval the human sees must make the case, so these are required:
    justification (why this order should be approved, in full sentences), checks (what was
    verified: stock, lead time, unpaid vendor invoices, other open tickets, cash), margin_note
    (the margin result under the 30% rule, or why it doesn't apply), and concerns (any cash or
    margin worries; an empty list means none). The tool also adds verified figures from the
    database (cash, other open obligations, warnings) to the approval itself.
    """
    return approvals.prepare_purchase(DB_PATH, vendor_id, amount, due_date, description, justification, checks, concerns, margin_note, ticket_id)


@mcp.tool
def write_payments(
    kind: str,
    ref_id: int,
    justification: str,
    checks: list[str],
    concerns: list[str] | None = None,
    ticket_id: int | None = None,
    margin_note: str | None = None,
) -> dict:
    """PREPARE a payment of an invoice or the rent. This never moves money.

    kind is 'invoice' (ref_id = invoices.id) or 'rent' (ref_id = leases.id).
    The amount is read from the invoice or lease, never supplied by the caller.
    It refuses if the item isn't payable. If checking can't cover it, it is still prepared,
    with a cash warning, and the dashboard blocks approving it until cash covers it.
    It records a pending approval and returns it (status 'pending').
    Cash changes only when a human approves it in the dashboard. Don't describe
    a payment as made until its approval status is 'approved'.

    The approval the human sees must make the case, so these are required: justification (why
    this should be paid now, in full sentences), checks (what was verified: the invoice or lease,
    the balance, other open tickets, the Boss's cash outlook), and concerns (any cash or margin
    worries given the shop rules and the open tickets; an empty list means none). margin_note is
    optional for a bill. The tool also adds verified figures from the database (cash before and
    after, other open obligations, overdue days, warnings) to the approval itself.
    """
    return approvals.prepare_payment(DB_PATH, kind, ref_id, justification, checks, concerns, ticket_id, margin_note)


@mcp.tool
def write_messages(
    ticket_id: int,
    subject: str,
    body: str,
    justification: str,
    checks: list[str],
    concerns: list[str] | None = None,
) -> dict:
    """PREPARE a reply to a customer for a human to approve. Nothing is ever sent.

    Use it only for text you (the Boss) have reviewed and approved as a DraftReview. The
    recipient is the ticket's requester, read from the database, not supplied by the caller.
    It records a pending approval (kind 'message') and returns it (status 'pending'); a person
    reads the exact text in the dashboard and approves or declines it. Approving records the
    text on the ticket's notes. It refuses a ticket with no customer (rent_notice) or one that
    is closed, and it refuses text that names a vendor or another customer, uses internal terms
    (margin, invoice, lease, rent, cash, balance...), or quotes a dollar amount that is not a
    list price. Fix the text and resend if it is refused.

    The approval the human sees must make the case, so these are required: justification (why
    this is the right reply), checks (what was verified: stock, lead time, list price, the draft
    review rounds), and concerns (anything the person should weigh; an empty list means none).
    """
    return approvals.prepare_message(DB_PATH, ticket_id, subject, body, justification, checks, concerns)


@mcp.tool
def read_approvals() -> list[dict]:
    """Read every approval: id, kind ('payment', 'purchase' or 'message'), summary, status
    (pending, approved, declined, failed), who decided and when, and the result."""
    return approvals.list_approvals(DB_PATH)


if __name__ == "__main__":
    mcp.run()
