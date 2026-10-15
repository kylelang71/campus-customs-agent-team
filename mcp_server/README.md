# Campus Customs MCP Server

A [FastMCP](https://gofastmcp.com) server that gives the shop's agents a controlled way to read and update the Campus Customs database. Agents never open the database themselves; they call the tools below. It has **15 tools**: 10 that only read and 5 that write. None of the write tools moves money or sends anything: payments, purchases and customer messages are only *prepared*, and a human approves them in the backend.

## Database

The server uses **`data/campus_customs_new.db`** (the path is set once as `DB_PATH` in `server.py`).

- `data/campus_customs.db` is the read-only original and is never opened by this server.
- `campus_customs_new.db` is the working copy that agents are allowed to modify. To start clean, replace it with a fresh copy of the original.
- The 10 `read_*` tools open the database in SQLite read-only mode (`mode=ro`) and can't change anything.
- The 5 `write_*` tools are the only ones that open it for writing, each limited to the fields described below.

## Running the server

From the `HW5` folder:

```bash
.venv/bin/python mcp_server/server.py
```

This starts the server over stdio, which is how an MCP client (such as Claude Code or an agent) launches and talks to it. `HW5/.mcp.json` registers it as `campus-customs`.

## Tools at a glance

| Tool | Table | Arguments | Changes data? |
|---|---|---|---|
| `read_desk` | `desk` | none | no |
| `read_inventory` | `inventory` | none | no |
| `read_invoices` | `invoices` | none | no |
| `read_balance` | `cash_accounts` | none | no |
| `read_lease` | `leases` | none | no |
| `read_vendor` | `vendors` | none | no |
| `read_pricing` | `pricing` | none | no |
| `read_payments` | `payments` | none | no |
| `read_approvals` | `pending_approvals` | none | no |
| `read_ticket` | `tickets` | none | no |
| `write_ticket` | `tickets` | `ticket_id`, `status`, `notes` | yes: a ticket's `status` and `notes` |
| `write_inventory` | `inventory` | `sku`, `size`, `qty_change` | yes: one row's `qty` |
| `write_invoices` | `pending_approvals` | `vendor_id`, `amount`, `due_date`, `description`, `justification`, `checks`, `margin_note`, optional `concerns`, `ticket_id` | prepares a purchase; the invoice exists only after a human approves |
| `write_messages` | `pending_approvals` | `ticket_id`, `subject`, `body`, `justification`, `checks`, optional `concerns` | prepares a customer reply for a human to approve; nothing is sent |
| `write_payments` | `pending_approvals` | `kind`, `ref_id`, `justification`, `checks`, optional `concerns`, `ticket_id`, `margin_note` | prepares a payment; cash changes only after a human approves |

There is no `read_cash_accounts` (use `read_balance`) and no `write_cash_accounts` (cash changes only when a human approves a payment in the backend).

The approval logic lives in `approvals.py`, next to the server. The server uses it to *prepare*; the backend's approve route uses it to *decide*. Nothing in it is a tool, so agents can't approve anything.

## Read tools

The `read_*` tools take no arguments and return a list of rows, each row a dictionary keyed by column name.

### `read_desk`
- **Returns:** `date_today` (the shop's assumed date, used for everything that is "today"; never the real date), `notes`
- **Helpful for:** every agent
- **Tickets:** any and all (what is overdue, how long until something is due)

### `read_inventory`
- **Returns:** `sku`, `size` (together the key), `name`, `qty`, `location`
- **Helpful for:** Inventory agent
- **Ticket:** 101 (is there stock to fill the customer's order?)

### `read_invoices`
- **Returns:** `id` (key), `vendor_id`, `amount`, `due_date`, `status`, `description`
- **Helpful for:** Boss, Inventory, and Accounting agents
- **Tickets:** 101, 103 (is a purchase of new inventory already in process?)

### `read_balance`
- **Returns:** `name`, `balance`, `date` (from `cash_accounts`)
- **Helpful for:** Accounting agent
- **Tickets:** 101, 102, 103 (is there enough cash before any payment?)

### `read_lease`
- **Returns:** `id` (key), `space_name`, `landlord`, `monthly_rent`, `next_due`, `notes`
- **Helpful for:** Facilities agent
- **Tickets:** 102, and future rent payments

### `read_vendor`
- **Returns:** `id` (key), `name`, `specialty`, `lead_days`
- **Helpful for:** Inventory, Boss and Customer Service agents
- **Tickets:** 101, 103 (lead times come from here, never guessed)

### `read_pricing`
- **Returns:** `sku` (key), `unit_cost`, `list_price`
- **Helpful for:** Accounting, Boss and Customer Service agents
- **Tickets:** 103 (and 101) (judge a bulk discount against margin)

### `read_payments`
- **Returns:** `id` (key), `kind`, `ref_id`, `amount`, `account`, `paid_at`, `approved_by`
- **Helpful for:** Accounting and Boss agents
- **Tickets:** 101, 102, 103 (see what's already paid and who approved it)

### `read_approvals`
- **Returns:** `id`, `kind` (`payment`, `purchase` or `message`), `payload`, `summary`, `status` (`pending`, `approved`, `declined`, `failed`), `created_at`, `decided_at`, `decided_by`, `result`, and on pending payments and purchases `blocked` and `block_reason` (true when approving would overdraw checking)
- **Helpful for:** Boss and Accounting agents
- **Tickets:** 101, 102, 103 (what is still waiting for a human)
- The `pending_approvals` table is created in the working database the first time it is needed, and a database reset removes it.

### `read_ticket`
- **Returns:** all fields: `id` (key), `type`, `requester`, `subject`, `sku`, `size`, `qty`, `lease_id`, `invoice_id`, `status`, `notes`, `created_at`
- **Helpful for:** Boss agent
- **Tickets:** any and all (the boss reviews the shop's open needs, plans, then delegates)

## Write tools

### `write_ticket`
- **Arguments:** `ticket_id`, `status` (`open` or `closed`), `notes`
- **Writes:** `tickets`, only the `status` and `notes` fields
- **Behavior:** The new notes are appended to the existing notes (the original request is kept). When closing a ticket, the shop date from `desk.date_today` is stamped on the front of the new notes automatically. Returns the updated ticket row.
- **Helpful for:** Boss agent
- **Tickets:** any and all (closing a ticket stops further delegation; notes record the date closed, actions taken including suppliers and the delegation path, and any exceptions a human had to handle)

### `write_inventory`
- **Arguments:** `sku`, `size`, `qty_change` (signed integer, not 0)
- **Writes:** `inventory`, only the `qty` field of one existing `sku` + `size` row
- **Behavior:** Adds `qty_change` to the current quantity (positive when stock arrives, negative when stock leaves). A change that would take stock below zero is rejected and nothing is written. Unknown `sku`/`size` pairs are rejected; rows can't be created. Returns the updated row.
- **Helpful for:** Inventory agent
- **Tickets:** 101, 103 (keep stock accurate after a vendor shipment arrives or an order is filled)

### `write_invoices`
- **Arguments:** `vendor_id`, `amount` (> 0), `due_date` (`YYYY-MM-DD`), `description`, `justification`, `checks`, `margin_note` (all required), optional `concerns`, `ticket_id`
- **Prepares** a purchase (a vendor order, i.e. a purchase order) as a pending approval. The open invoice is created in `invoices` only when a human approves it; approving it moves **no cash** (cash leaves only when that invoice is later paid by an approved payment). It never edits an existing invoice and never marks one paid. Unknown vendors, non-positive amounts and bad dates are rejected. An identical pending purchase isn't duplicated. It is prepared even when checking can't cover it, with a `Cash is short` warning, but the approval is blocked while the amount exceeds checking (see "Cash gate" below). Returns the pending approval.
- **Helpful for:** Accounting and Inventory agents
- **Tickets:** 101, 103 (the vendor order for a restock)

### `write_messages`
- **Arguments:** `ticket_id`, `subject`, `body` (up to 1500 characters), `justification`, `checks`, optional `concerns`
- **Prepares** a reply to a customer as a pending approval (kind `message`) and **sends nothing.** The recipient is the ticket's `requester`, read from the database. It refuses a `rent_notice` or closed ticket, and text that names a vendor or another customer, uses an internal term (margin, invoice, lease, rent, cash, balance, ...) or quotes a `$` amount that is not allowed (see "Customer message prices" below). When a human approves, the text is appended to the ticket's `notes` and nothing else changes. A pending message for the same ticket is returned instead of a second one.
- **Helpful for:** Boss agent only (after it has reviewed the draft)
- **Tickets:** 101, 103 (the customer replies)

### `write_payments`
- **Arguments:** `kind` (`invoice` or `rent`), `ref_id` (an `invoices.id` or `leases.id`), `justification`, `checks` (both required), optional `concerns`, `ticket_id`, `margin_note`
- **Prepares** a payment as a pending approval and **moves no money.** The amount is taken from the invoice or lease, never from the caller. It refuses only if the item isn't payable (an invoice must be `open`). If checking can't cover it, it is still prepared with a `Cash is short` warning, and the approval is blocked until cash covers it (see "Cash gate" below). The same payment isn't prepared twice.
- **When a human approves** (backend route `POST /api/approvals/{id}/approve`), one transaction records the payment in `payments` with the approver's name, deducts the cash, and marks the invoice `paid` (or moves the lease's `next_due` forward one month). Cash is re-checked at that moment. `paid_at` and the cash date use `desk.date_today`.
- **Helpful for:** Accounting agent
- **Tickets:** 101, 102, 103

See `output/harness.md` for the full rationale behind each tool and the shop rules agents must follow.

## Partner Review Problem 8

Written for Problem 8 and brought up to date through Problem 9 (`write_messages`, the cash gate, message price rules).

- **Tools:** 15 (10 read-only, 5 write). Read tools open SQLite with `mode=ro`. No tool changes cash, `payments`, `leases` or an invoice's status.
- **Writes performed by tools:** `write_ticket` (updates `tickets.status`/`notes` of one row; notes appended; closing date from `desk.date_today`), `write_inventory` (`qty = qty + n` on an existing sku+size, rejected if it would go below 0, `n != 0`), `write_invoices`, `write_payments` and `write_messages` (insert a `pending_approvals` row; identical pending rows are not duplicated; the check and insert run in `BEGIN IMMEDIATE`).
- **`pending_approvals`** (working DB only, created lazily; absent from the original): `id, kind ('payment'|'purchase'|'message'), payload (JSON), summary, status ('pending'|'approved'|'declined'|'failed'), created_at, decided_at, decided_by, result (JSON)`. Reading it never creates it.
- **Execution** is `approvals.decide(db, id, approve, name)`, called only by the backend route. It runs in one `BEGIN IMMEDIATE` transaction: payment = re-check the item is payable, `balance = ROUND(balance - amount, 2)` guarded by `balance >= amount`, insert `payments` (`approved_by` = name, `paid_at` = `desk.date_today`), set invoice `paid` or move `leases.next_due` forward one month; purchase = insert an `open` invoice. An execution failure sets `status = 'failed'` and the route returns 409. `decide` is not an MCP tool.
- **Permissions:** the server exposes all 15 tools; `backend/tools.py:PERMISSIONS` filters them per agent (matrix in `output/harness.md`). Team tools (`delegate`, `check_in`, `status_update`) are not on this server.
- **Paths:** `DB_PATH = data/campus_customs_new.db`, resolved relative to `server.py`. The backend starts the server with its own interpreter (`sys.executable`).
- **Reset:** `backend/db.py:reset_database()` replaces the working DB with a `sqlite3` backup of the original, which removes `pending_approvals`.

### Approval content (added after Problem 8 review)

Each pending approval's `payload` holds two extra objects besides the execution fields.
- `review`, written by the agent and validated by the tool (a missing field is a `ValueError` the agent must fix): `justification` (at least 20 characters), `checks` (at least one item), `concerns` (list; empty means none), `margin_note` (required for `write_invoices`), `ticket_id`.
- `facts`, computed by `approvals._facts` from the database, not supplied by an agent: `shop_date`, `cash_before`, `cash_after_this` (payments), `other_firm_obligations` (other open invoices and each lease's rent) and their total, `cash_after_all_firm`, `open_tickets`, `due`/`days_overdue`/`days_until_due`, `vendor`/`vendor_lead_days` (purchases), and `warnings`. Warnings are generated for: cash after all firm obligations below 0 (with the shortfall), cash left under 20% of today's balance, an overdue item, and a purchase from a vendor with an open invoice.
- Execution (`decide`) reads only `kind`, `ref_id`/vendor fields and `amount`; `review` and `facts` are display and audit data.
- **Cash gate:** `write_payments` refuses only a payment whose item isn't payable; a payment that cash can't cover is prepared with a `Cash is short` warning. `approvals.decide` raises `InsufficientCash` (HTTP 409, nothing written, approval stays `pending`) when approving a payment would take checking below zero or approving a purchase whose amount exceeds checking (the invoice it creates could not be paid), and `list_approvals` adds `blocked` and `block_reason` to each pending payment and purchase. `write_invoices` also prepares with a `Cash is short` warning.
- **Customer message prices:** only `pricing.list_price` values may be quoted, except on a `price_override` ticket, where a unit price above `unit_cost / 0.70` and below list (or a total in that band times the ticket's quantity) is also accepted, and such a ticket's reply must state one. Anything else with a `$` is refused, including unit cost, the floor and the order cost.
- **`write_messages`:** prepares kind `message`, payload `ticket_id`, `to` (the ticket's `requester`), `subject`, `body` (max 1500 characters), `review`, `context`. Refused for a `rent_notice` or closed ticket, and for text that names a vendor or another customer, uses an internal term, or quotes a `$` amount that is not a `list_price`. Approval (`decide`) appends the text to `tickets.notes` and returns `sent: false`; it changes no cash.
