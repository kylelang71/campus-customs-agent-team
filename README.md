# HW5: Campus Customs Agent Team

## Partner Review Problem 8

This section was written for Problem 8 and brought up to date through Problem 9 (customer-message approvals, the cash gate, price decisions, heartbeat, run history).

### Components

| Component | Path | Runtime |
|---|---|---|
| Agent team (5 pydantic-ai agents) | `backend/*.py`, `backend/prompts/*.md` | in the backend process |
| Backend (FastAPI) | `backend/main.py` | `uvicorn main:app --reload --port 8000`, run from `backend/` |
| MCP server (15 tools) | `mcp_server/server.py`, `mcp_server/approvals.py` | stdio subprocess started by the backend |
| Dashboard (React, Vite, TypeScript) | `frontend/` | `npm run dev` from `frontend/`, serves and opens `http://localhost:5173` |
| Working DB / original DB | `data/campus_customs_new.db` / `data/campus_customs.db` | SQLite; the original is only read by `db.reset_database()` |
| Audit trail | `output/audit_trail.json` | append-only JSON array |
| Reset marker | `data/last_reset.txt` | written by `db.reset_database()`; the board restores finished runs recorded after this time |
| Docs | `output/harness.md` (rules, permissions, safety), `output/design.md` (dashboard design), `mcp_server/README.md` (tools) | |

### Setup

```
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt   # Python 3.14
cp .env.example .env                                                  # set PORTKEY_API_KEY
cd frontend && npm install
```

### Running it

`data/` is not in the repository (it is git-ignored). Put the original database at `data/campus_customs.db`; the working copy `data/campus_customs_new.db` is made from it. The order is: clean database, MCP server, backend, board, then the tickets.

1. **Copy the original DB to the working copy when you need a clean run.** From `backend/`:

   ```
   ../.venv/bin/python db.py reset
   ```

   This replaces `data/campus_customs_new.db` with a copy of the original (`campus_customs.db` is only read, never changed), which also clears every pending approval, and stamps `data/last_reset.txt`. Copying the file by hand (`cp data/campus_customs.db data/campus_customs_new.db`) gives the same data but does not stamp the reset time. It is not a route, never touches the audit trail, and must not be run while a ticket is running.
2. **Start the MCP server.** The backend starts it for you as a stdio subprocess (see `backend/tools.py`), so the app needs nothing extra. To run it yourself, for example to check the tools or to use it from Claude Code (`.mcp.json` registers it as `campus-customs`):

   ```
   .venv/bin/python mcp_server/server.py
   ```
3. **Start the FastAPI backend** (needs `PORTKEY_API_KEY` in `.env`). From `backend/`:

   ```
   ../.venv/bin/uvicorn main:app --reload --port 8000
   ```

   Do not edit backend files or restart it while a ticket is running: that ends the run.
4. **Start the React board.** From `frontend/`:

   ```
   npm run dev
   ```

   It serves and opens `http://localhost:5173`. Open it as `localhost`, not `127.0.0.1`, because the backend only accepts that origin.
5. **Reset the DB before a full three-ticket run.** Repeat step 1, restart the backend (so its run list is rebuilt from the new reset time) and reload the board. Checking should read $3,400 with tickets 101, 102 and 103 open and nothing waiting for approval. Then start the tickets one at a time ("Start the team"; the team works one ticket at a time), type your name under "Needs your approval", and approve or decline each prepared payment, order or customer message in any order. A payment or order larger than the checking balance cannot be approved.

### Request path

1. `POST /api/tickets/{id}/run` starts `team.run_agent("Boss", ...)` as a background task. One run at a time (second start: 409). A run ends on the Boss's final reply; unfinished delegations are cancelled and logged as `message`.
2. Agents call MCP tools through one shared `MCPToolset`, filtered per agent by `backend/tools.py:PERMISSIONS`.
3. `write_payments` / `write_invoices` / `write_messages` only insert a row in `pending_approvals`. `POST /api/approvals/{id}/approve` (`approvals.decide`) is the only code path that changes cash, invoices, payments or leases.
4. Every step is appended to the audit trail; `GET /api/events` and the dashboard read it.

### Approvals

- `write_payments` / `write_invoices` require `justification`, `checks`, `concerns` (and `margin_note` for an order); the tool adds database-computed `facts` (cash before/after, other owed invoices and rent, cash if all were paid, open tickets, overdue days) and generated `warnings`. Execution ignores them; they are display and audit data.
- The board shows each pending approval's case, and keeps the 3 most recent decided approvals on the desk (older ones remain in `GET /api/approvals`).
- **Customer messages** use the same table, endpoints and panel (`kind = 'message'`). Only the Boss has `write_messages(ticket_id, subject, body, justification, checks, concerns)`; the recipient is the ticket's requester, read from the database. Preparation is refused if the ticket is a `rent_notice` or closed, or the text names a vendor or another customer, uses an internal term (margin, invoice, lease, rent, cash, balance, ...), or quotes a `$` amount that is not a `pricing.list_price`. A pending message for the same ticket is returned instead of a second one. Approving appends `[Customer reply approved by NAME on DATE] subject: body` to the ticket's notes and returns `sent: false`; nothing is sent anywhere. Declining records nothing. The Boss reviewing the draft first is prompt-only.
- **Plans are always prepared:** agents never hold, skip or shrink a payment or order because cash is short (the Boss's `hold`/`escalate` verdicts are for problems with the payment itself, and Inventory fills `recommended_order_qty` even if the minimum order quantity is unknown or a vendor invoice is unpaid). The shortfall is written into the plan's concerns and handled at approval, below. For a short item the Boss has Accounting prepare the order (`write_invoices`, due on the expected arrival) as well as the payment of any blocking invoice.
- **Cash gate on approval:** a pending payment or purchase whose amount exceeds the current checking balance cannot be approved (a payment would overdraw checking; an order becomes an invoice the shop could not pay). `GET /api/approvals` adds `blocked` and `block_reason` to every pending payment and purchase; the board shows the warning and disables Approve (Decline still works), and `POST /api/approvals/{id}/approve` returns 409 with the same message and writes nothing, so the approval stays pending. It is re-evaluated on each read, so it clears when cash covers the amount. `write_payments` no longer refuses a payment because cash is short: it prepares it, and `write_invoices` prepares an order, with a `Cash is short` warning. Customer messages involve no cash and are never blocked. The test is the amount against the balance on hand, not against other open obligations, so no restock order can be approved while cash is below its amount (nothing in the model brings cash in).
- **Board layout:** the approvals control panel (heading, name field) sits below the balance at the far left of the desk. Pending notes form a stack next to it: one note is shown in full, a chip per pending note (and a count) lets you bring any of them to the front, so they can be approved or declined in any order, and new notes join the stack without changing the one you are on; decided notes pile at the far right (the 3 most recent), and the `‹ ›` buttons above the pile click through them (they stay put however tall the note is).

### Heartbeat

- Every agent run (Boss, Inventory, Accounting, Facilities, Customer Service) has a heartbeat: a background task ticks every 2 s (`HEARTBEAT_SECONDS`) and the run records what it is doing now (`waiting for the model`, `using read_invoices`, `waiting for Facilities`, `writing its answer`) and since when. It is live state in `team.HEARTBEATS`, not written to the audit trail, and it disappears when the run ends.
- `GET /api/heartbeats` returns `{interval, agents: [{agent, run_id, doing, seconds_running, seconds_in_step, beat_age, beats}]}`. The board polls it with everything else and shows it on each name tag: `♥ waiting for the model · 14s`. After 30 s in one model wait the tag adds `(slow reply)`; if `beat_age` exceeds 6 s the tag shows `no heartbeat for Ns` in red. The heartbeat is informational only: nothing in a run waits on it, cancels on it or changes behaviour because of it (the 60 s check-in, 30 s model timeout and 8-check-in limits are unchanged); beat updates are wrapped so an error in them cannot fail a run, the endpoint is read-only and copies its state, and the board fetches it separately so if it fails only the heartbeat lines disappear. A fresh beat shows the agent's process is alive while it waits on the model service or a teammate; it does not mean the model will answer.

### Price decisions

- On a `price_override` ticket Accounting must commit to one `proposed_unit_price` in a `DiscountAnalysis`: above the lowest allowed price (`unit_cost / 0.70`, so a margin above 30%) and below the list price, with its reasoning in `note` (at least 40 characters). The type rejects a price at or below the floor, at or above list, or without reasoning. Within that band the choice is Accounting's judgement (quantity, stock versus units to reorder, lead time).
- The Boss makes the final call on the price and must state the decided unit price and the quantity total in the customer note. `write_messages` enforces the band for a `price_override` ticket: it accepts a unit price above the floor and below list (and a total within the same band times the quantity), refuses any other `$` amount (unit cost, the floor, the order cost), and refuses a reply that quotes no such price. For other tickets only list prices may be quoted, as before.
- That the Boss requires the call from Accounting, decides, and includes it is prompt-driven; the band and the note check are code.

### Information hub

- The Boss passes what the team has learned to later teammates. `delegate` takes `known` (max 8000 characters; refused for Customer Service), appended to the task as `ALREADY GATHERED FOR THIS TICKET`, so a teammate does not repeat a tool call or a question (for example Facilities' lease rows go to Accounting).
- An identical `delegate` (same teammate, task, payload, reply type, `known`) in the same prompt is not re-sent: the earlier reply is returned and the call does not count toward the 20-handoff limit. A failed or stopped task can be re-sent.
- Using `known` and keeping replies complete is prompt-only; the code enforces only the size limit, the Customer Service refusal and the identical-call rule. Paraphrased repeats are not caught.

### Agent graph

- Roster: **Boss** (reads and writes tickets, prepares customer messages, posts status updates), **Inventory** (stock, vendors, lead times, restock recommendations), **Accounting** (cash, invoices, payments, orders, margin and the price call), **Facilities** (lease and rent), **Customer Service** (customer-safe drafts only). Tools per agent are in `output/harness.md`.
- Any agent can `delegate` to any other, except: to itself, to an agent already above it in the call chain (refused), beyond depth 4, or past 20 handoffs per prompt.
- Messages into and out of Customer Service must be one of 5 customer-safe types (`models.CUSTOMER_SAFE_TYPES`).
- `delegate(task, payload_type, payload, reply_type)` validates the payload before sending and validates the reply against `reply_type` (3 retries). 42 types are registered in `models.MESSAGE_TYPES`.
- `delegate` waits 60 s, then returns a CHECK-IN report; `check_in(to_agent, give_up)` waits another 60 s. A task is stopped after 8 check-ins.
- A teammate whose model call fails is re-run once automatically; each delegate result lists the caller's other unfinished tasks (`STILL WAITING ON`).
- Per agent: own `Agent`, own `AsyncOpenAI` client and connection pool (30 s timeout, 4 retries), requests tagged `x-portkey-metadata {"agent": name}`, model fixed to `gpt-6-luna`, 40 model requests per run, empty history per run.

### Enforced in code vs. in prompts

| In code | In prompts only |
|---|---|
| model name; per-agent tool permissions; payload and reply validation; call-chain, depth and 20-handoff limits; Customer Service type gating; one run at a time; $10/day cap (pause, human reset); approval-only cash changes; no approval of a payment or order larger than the checking balance (board and route); the price band in `DiscountAnalysis` and in customer messages on a price override; customer-message screening (no vendor or other-customer names, no internal terms, only allowed prices); `known` size and the identical-`delegate` rule; cash and stock never negative; append-only audit; CORS limited to `http://localhost:5173` | one ticket per run and which teammates a ticket type uses; Boss-driven payment review before `write_payments`; Boss review of customer and vendor drafts (before `write_messages`); passing `known` facts to teammates; 30% margin; stop after preparing an approval; plain-English status wording |

### Warnings

- **Model gateway stalls (outside this project's control).** Requests to the model gateway occasionally stall or return 500. A stalled call is abandoned after 30 s and retried (4 retries); a teammate whose call still fails is re-run once; after that the caller is told. A run can still be slow while the gateway is degraded. Across observed runs, silent gaps over 30 s occurred for every agent (Boss most often); the full ~150 s timeouts landed on Accounting and Facilities because their retries stalled in sequence. No model setting tested (`reasoning_effort`, `send_reasoning_ids`, `store`) removed the stalls.
- **Servers do not survive the app.** The backend (`:8000`) and the board (`:5173`) were stopped by the desktop app once while idle. If the board shows "Cannot reach the backend", restart `uvicorn main:app --reload --port 8000` from `backend/`.
- **A reload or restart kills an in-flight run.** Do not edit backend files, or restart the backend, while a ticket is running. `--reload` restarts on any change in `backend/`.
- **A test leaves real state.** Approving a payment changes the working DB. Run `python db.py reset` from `backend/` before the next test; the audit trail is never reset, so it holds every test run (it is not a single-run file).
- **Accounting stalls after the payment tool when a typed reply is requested.** In the audit trail, Accounting's next model call after `write_payments` / `write_invoices` completed in 2-4 s all 6 times the Boss asked for a plain reply, and stalled (58-157 s, two `ModelAPIError` timeouts, some never finished) all 7 times a typed `reply_type` (`Payment`, `Approval`, `StatusCheck`) was requested. A short isolated test of the same typed outputs took 1-2 s, so the cause is not established. The Boss stops a stalled task and reads `read_approvals`, which is how the prepared approval is found. A `Payment` reply type also describes a payment already made (approver, paid date), which a pending approval cannot honestly fill.

### Known limits

- No scheduler: runs start only from the dashboard.
- No customer-chat route: Customer Service is reached only through the Boss (or `team.run_team`).
- An in-flight run is lost on a backend restart or code reload (the board then shows it as failed). Finished runs recorded after the last database reset are rebuilt from the audit trail when the backend starts; with no `data/last_reset.txt` nothing is restored.
- The model gateway occasionally returns 500s or stalls; a call is abandoned and retried after 30 s.
- `pending_approvals` ids restart at 1 after a reset, so `approval-N` run ids in the audit trail are not unique across resets.
- Payment review is not code-gated: `write_payments` checks only that the item is payable. Cash is enforced at approval, against the balance on hand only (not against other pending items), so approving a restock order first and then a payment can leave an invoice the shop cannot pay.
- The minimum order quantity of a vendor is not in the database and is not enforced: a restock quantity is demand minus stock and is flagged for a person to confirm.
