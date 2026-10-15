# Harness

## Databases

`data/campus_customs.db` is the read-only original. Never write to it (no INSERT, UPDATE, DELETE, or schema changes), and never point an agent's write tools at it. `data/campus_customs_new.db` is the working copy and the only database agents may modify. If it gets corrupted, replace it with a fresh copy of the original.

## Database Fields

Nine tables come from the original database; a tenth is added to the working copy.

- `tickets` (`id`, `type`, `requester`, `subject`, `sku`, `size`, `qty`, `lease_id`, `invoice_id`, `status`, `notes`, `created_at`) - These are open tasks and will be closed, maybe written. The three tickets: 101 customer order (white tee, size S), 102 rent notice, 103 price override (20 navy hoodies, size M). Only the Boss writes them (`status` and appended `notes`); a human's approval of a customer reply also appends to `notes`.
- `inventory` (`sku`, `name`, `size`, `qty`, `location`) - product stock by size. Only `qty` changes, by a signed amount, and never below zero.
- `pricing` (`sku`, `unit_cost`, `list_price`) - Unit cost and list price per SKU. Never edited.
- `vendors` (`id`, `name`, `specialty`, `lead_days`) - These are the suppliers: Bulldog Print Co (apparel reprint, 5 days), Elm City Gifts (3 days), QuickShip CT (1 day). There is no minimum order quantity column.
- `invoices` (`id`, `vendor_id`, `amount`, `due_date`, `status`, `description`) - Self explanatory. Open invoice 501 ($840, Bulldog) is the blocker. A new open invoice appears only when a human approves a purchase order; an invoice becomes `paid` only when a human approves its payment.
- `leases` (`id`, `space_name`, `landlord`, `monthly_rent`, `next_due`, `notes`) - Chapel Street shop, $2,400/mo. `next_due` moves forward one month when a human approves the rent payment.
- `cash_accounts` (`name`, `balance`, `date`) - Checking, $3,400, this will be updated throughout the HW. It changes only when a human approves a payment.
- `payments` (`id`, `kind`, `ref_id`, `amount`, `account`, `paid_at`, `approved_by`) - Empty at the start, so no payments have been made yet. A row is added only when a human approves a payment (`approved_by` is that person's name).
- `desk` (`date_today`, `notes`) - Today's date, 2026-08-31 (this is not the actual date but is the assumed date for the sake of the assignment)
- `pending_approvals` (`id`, `kind`, `payload`, `summary`, `status`, `created_at`, `decided_at`, `decided_by`, `result`) - **working copy only**, created the first time it is needed and removed by a database reset. Holds what the agents have prepared and a human has yet to decide: `kind` is `payment`, `purchase` or `message`; `status` is `pending`, `approved`, `declined` or `failed`.

Two files sit beside the databases: `data/last_reset.txt` (when the working copy was last reset, used by the board to restore finished runs) and, in `output/`, the append-only `audit_trail.json`.

## Required Rules of the Shop

- "today" is whatever `desk.date_today` says, not the real date. Use that to figure out what's overdue.
- Vendor lead times live in the `vendors` table, so check there and never guess.
- Vendors won't ship anything new if we still have an unpaid invoice with them. Pay that off first (or flag it) before trying to restock.
- Any payment needs a human to approve it first. No exceptions, we lose points if this gets skipped. And once a payment actually goes through, update the right tables so the db matches reality.
- If there isn't enough cash, the pay tool should just refuse. Cash can never go negative. (As built: agents still prepare the payment, with a cash warning, so the plan exists; the refusal happens where a person signs. A payment or order larger than the checking balance cannot be approved: the board disables Approve and `POST /api/approvals/{id}/approve` returns 409. The cash check inside the approval transaction is the final guard.)
- Money only goes OUT in this hw. We didn't model revenue, so nothing ever comes in.
- Before doing a full run on the tickets, reset the db back to the original values so we're starting clean.
- Do NOT contact real customers or real vendors. Just write drafts and leave them on the board.

## MCP Server Tools

The MCP server lives in `mcp_server/server.py` and talks only to `data/campus_customs_new.db`. It has 15 tools: 10 read-only and 5 that write. No tool moves money or sends anything; payments, purchases and customer messages are only prepared. Details per tool are in `mcp_server/README.md`.

1. `read_inventory`
   * Which table it reads: inventory, and returns all the values including sku + size (together the key), name, qty, location
   * Particularly helpful for: Inventory agent.
   * Which Ticket it helps with: 101
   * Why this matters for the ticket: Addressing ticket 101 requires information of whether there are currently shirts in stock to meet the customer need, therefore the inventory level needs to be communicated to the inventory agent, boss agent, and all others to coordinate actions.
2. `read_invoices`
   * Which tables it reads: Invoices, and returns id (key), vendor_id, amount, due_date, status, description
   * Particularly helpful for: Boss agent, Inventory agent, Accounting Agent
   * Which Ticket it helps with: 101, 103
   * Why this matters for the ticket: Tickets 101 and 103 both require an agent to understand whether there is an action in process (in the case of tickets 101 and 103 a decision to purchase new inventory) in order to effectively share information with customer service about lead time or with accounting about ordering more inventory.
3. `read_balance`
   * Which table it reads: cash_accounts
   * Particularly helpful for: Accounting agent
   * Which Ticket it helps with: 101, 102, or 103
   * Why this matters for the ticket: For any cash outflows (such as in any ticket - 101, 102, or 103) the payment should only be made when there is adequate balance remaining in the company checking account, this allows the accounting agent to provide that information before the Boss or a human makes any decisions.
4. `read_ticket`
   * Which table it reads: tickets, and returns all fields
   * Particularly helpful for: boss
   * Which Ticket it helps with: any and all
   * Why this matters for the ticket: In order for the boss to delegate effectively it must review the needs of the store at any one time, plan, then delegate to the agents.
5. `write_ticket`
   * Which table it reads: tickets, and can update the status and notes fields
   * Particularly helpful for: boss
   * Which Ticket it helps with: any and all
   * Why this matters for the ticket: In order for the boss to close a ticket it must be able to update the database and change the status to ‘closed’ so that it does not continue to delegate once agents have completed all delegated actions. The ‘notes’ field should be updated with the date closed, the actions taken to close the ticket (including suppliers worked with and the delegation framework), and any exceptions that had to be handled by a human user.
6. `read_lease`
   * Which table it reads: lease, and returns all variables
   * Particularly helpful for: Facilities Agent
   * Which Ticket it helps with: 102, and future rent payments
   * Why this matters for the ticket: This may be required to check information regarding the lease payment ticket creation
7. `write_inventory`
   * Which table it reads: inventory, and can update the qty field (by a signed amount, for one sku + size row)
   * Particularly helpful for: Inventory agent
   * Which Ticket it helps with: 101, 103
   * Why this matters for the ticket: When stock is received from a vendor (for example the size S Bulldog tee reprint for ticket 101) or an order is filled, the database must be updated so it matches reality and every other agent sees accurate stock levels. Stock can never go negative, so a change that would drop qty below zero is refused.
8. `read_vendor`
   * Which table it reads: vendors, and returns all fields: id (key), name, specialty, lead_days
   * Particularly helpful for: Inventory agent, Boss agent, Customer Service agent
   * Which Ticket it helps with: 101, 103
   * Why this matters for the ticket: Vendor lead times live in the vendors table and must never be guessed. Inventory and Boss need them to plan a restock, and Customer Service needs them to tell a customer when an out-of-stock item could be ready. The vendor id also links each invoice to its vendor.
9. `read_pricing`
   * Which table it reads: pricing, and returns all fields: sku (key), unit_cost, list_price
   * Particularly helpful for: Accounting agent, Boss agent, Customer Service agent
   * Which Ticket it helps with: 103 (and 101)
   * Why this matters for the ticket: Ticket 103 asks for a bulk discount, which can only be judged against the margin between unit cost and list price. Ticket 101 needs the list price for the customer's order and the unit cost behind any reprint.
10. `write_invoices`
   * Which table it writes: it only PREPARES a purchase order (vendor_id, amount, due_date, description, plus the required case: justification, checks, margin_note, optional concerns and ticket_id) as a pending approval. The new open invoice is created in `invoices` only when a human approves it, and approving it moves no cash. It never edits or pays an existing invoice.
   * Particularly helpful for: Accounting agent, Inventory agent
   * Which Ticket it helps with: 101, 103
   * Why this matters for the ticket: Restocking for tickets 101 and 103 means placing an order with a vendor, and that obligation must be recorded so every agent can see it. Because vendors won't ship while an invoice is unpaid, an accurate invoice list drives the pay-first-or-flag decision. A purchase needs human approval before it exists, and marking an invoice paid is a separate payment that also needs a human.

Note: `read_invoices` (item 2) already existed and is unchanged.
11. `read_payments`
   * Which table it reads: payments, and returns all fields: id (key), kind, ref_id, amount, account, paid_at, approved_by
   * Particularly helpful for: Accounting agent, Boss agent
   * Which Ticket it helps with: 101, 102, 103
   * Why this matters for the ticket: Before any payment is proposed, agents need to see what has already been paid and who approved it, so the same invoice or rent is never paid twice and the books can be reconciled against cash_accounts.
12. `write_payments`
   * Which table it writes: it only PREPARES one payment (kind `invoice` or `rent`, plus ref_id) as a pending approval and moves no money. When a human approves it, the backend records the payment in `payments`, deducts the amount from cash_accounts, and marks the invoice `paid` (or moves the lease's next_due forward one month), all in one transaction.
   * Particularly helpful for: Accounting agent
   * Which Ticket it helps with: 101 (invoice 501), 102 (rent), 103 (any restock invoice)
   * Why this matters for the ticket: Agents can only prepare a payment; a human's approval is the only thing that makes money leave the account, so the shop rules are enforced. The amount comes from the invoice or lease, not from the caller. It requires the case (justification, checks, optional concerns) and refuses only a payment whose item isn't payable. A payment the checking account can't cover is still prepared, with a warning, and cannot be approved until cash covers it (cash never goes negative). The approver's name is recorded as approved_by, and all the tables change together, so the database matches reality.
13. `read_desk`
   * Which table it reads: desk, and returns all fields: date_today, notes
   * Particularly helpful for: every agent
   * Which Ticket it helps with: any and all
   * Why this matters for the ticket: "Today" is whatever `desk.date_today` says, not the real date. Every agent needs it to work out what is overdue, how many days remain until something is due, and when an order could arrive.

14. `read_approvals`
   * Which table it reads: pending_approvals (the payments, purchases and customer messages agents have prepared), and returns id, kind (`payment`, `purchase` or `message`), payload, summary, status (`pending`, `approved`, `declined`, `failed`), created_at, decided_at, decided_by, result, and on pending payments and purchases `blocked` and `block_reason`
   * Particularly helpful for: Boss agent, Accounting agent
   * Which Ticket it helps with: any ticket that involves a payment or purchase (101, 102, 103)
   * Why this matters for the ticket: Agents only prepare payments, purchases and messages, so they need to see which ones are still waiting for a human, which were approved, and which were declined, before closing a ticket or reviewing the next payment. The table is created in the working database the first time it is needed, and a database reset removes it.
15. `write_messages`
   * Which table it writes: it only PREPARES a reply to a customer (ticket_id, subject, body, plus the case: justification, checks, optional concerns) as a pending approval of kind `message`. The recipient is the ticket's requester, read from the database. When a human approves, the exact text is appended to the ticket's `notes`; nothing is ever sent.
   * Particularly helpful for: Boss agent only, after it has reviewed Customer Service's draft
   * Which Ticket it helps with: 101, 103 (and any customer ticket)
   * Why this matters for the ticket: Every customer message needs a human to read the exact words before it counts, and only text the Boss has already checked reaches that point. The tool refuses a rent notice or closed ticket, text that names a vendor or another customer, internal terms (margin, invoice, lease, rent, cash, balance...), and any `$` amount that is not allowed: only list prices, except that on a price-override ticket the team's decided unit price (above the 30% floor, below list) and its quantity total may be quoted, and such a reply must state one.

Note: `read_balance` (item 3) already reads `cash_accounts`, so no separate `read_cash_accounts` was created. There is deliberately no `write_cash_accounts`: cash changes only when a human approves a prepared payment, so it can't move without one.

## Agent Tool Permissions

Each agent gets only the tools below (taken from its prompt), and `backend/tools.py` connects each agent to nothing else. Every agent also has the team tools `delegate` and `check_in`; only the Boss has `status_update`.

| Agent | Read tools | Write tools | Cannot |
|---|---|---|---|
| Boss | `read_desk`, `read_ticket`, `read_approvals` | `write_ticket`, `write_messages` (prepares a customer reply for approval), plus `status_update` (posts a plain-English update to the user) | Read or write any table other than `tickets` (and approvals through its own tools). Approve payments, purchases or messages. |
| Inventory | `read_desk`, `read_inventory`, `read_vendor`, `read_invoices` | `write_inventory` | Write to any table other than `inventory`. Place or pay for orders. |
| Accounting | `read_desk`, `read_inventory`, `read_invoices`, `read_balance`, `read_vendor`, `read_pricing`, `read_payments`, `read_approvals` (every read tool except `read_ticket` and `read_lease`) | `write_invoices`, `write_payments` (prepare only) | Approve a payment (a human does). Share pricing (other than list_price), vendors (other than lead_days), invoices, leases, cash_accounts, or payments with customers. |
| Facilities | `read_desk`, `read_lease` | none | Share lease information with Customer Service. Pay or approve anything. |
| Customer Service | `read_desk` only (asks teammates for everything else) | none | Use any database tool other than `read_desk`. Share anything but stock band, list_price, and lead_days. |

There is no `write_cash_accounts` tool: cash changes only when a human approves a payment.

## The Five Agents and Their Rules

Each agent has its own prompt in `backend/prompts/`, its own model session (`gpt-6-luna`) and only the tools above. Any agent may `delegate` to any other (except itself, an agent above it in the call chain, past depth 4 or 20 handoffs); shared rules in every prompt: the shop rules above, one ticket per run, answer rather than bounce a task back, check in on slow teammates, don't fetch what the Boss already passed in `known`, the $10 daily limit, and the safety rules below.

| Agent | Owns | Rules it follows |
|---|---|---|
| **Boss** | The tickets and the run. The only agent the backend starts; one ticket per run. | Works only the ticket it is given and only the teammates that ticket type needs (customer order: Inventory and Customer Service, Accounting only for a blocking invoice; rent: Facilities then Accounting; price override: Inventory, Accounting, Customer Service for the note). Acts as the information hub: keeps teammates' replies whole and passes them forward in `known`. Runs the payment review (asks Accounting for a `CashOutlook`, checks the totals, clears with a `PaymentReview`) and always has the payment or order a ticket needs prepared, even if cash is short. Makes the final price call and states it in the customer note. Reviews every customer and vendor draft against the allowed and not-allowed lists (up to 3 rounds), then prepares the approved customer text with `write_messages`. Posts plain-English `status_update`s. Never approves anything, never claims a payment is made while pending, stops after preparing approvals. |
| **Inventory** | Stock, vendors, lead times, restock recommendations (`write_inventory` for real stock events only). | Uses `lead_days` from `read_vendor`, never a guess. Recommends the units still needed (demand minus stock) even when the minimum order quantity is unknown (flagged in `needs_human_input`) or a vendor invoice is unpaid (listed in `blocking_invoice_ids`). Drafts vendor messages as `VendorMessage` for the Boss to review. Tells Customer Service only the stock band, list price and lead days. |
| **Accounting** | Cash, invoices, payments, orders, margin. The only agent that can prepare payments and purchase orders. | Builds the `CashOutlook` from the database. Prepares exactly the payment named in a Boss `PaymentReview` (`proceed` or `pay_other_first`) and only the Boss-confirmed orders, each with a justification, checks and concerns, and never skips one because cash is short (it states the shortfall; the approval step blocks it). On a price override it must commit to one unit price above the 30% floor and below list, with reasoning (`DiscountAnalysis`). Never approves, never says a payment is made while pending, never shares cost or margin with customers. |
| **Facilities** | The lease and rent (`read_lease`). | Answers a lease question with one lookup. Does not start work on other tickets, prepare payments, or share lease details with Customer Service. |
| **Customer Service** | Drafting customer replies. No database tools but `read_desk`. | Receives and returns only the five customer-safe types. Tells customers only: stock band ("more than 5" or "5 or fewer", or out of stock), `list_price`, lead days, and, on a price override, the Boss's decided unit price and total. Never promises a discount, date or stock the team hasn't confirmed, never reveals internals, and sends every draft through the Boss before it is final. Nothing is sent to a real customer.

## Daily Token Budget

The whole agent team may use at most **$10 of tokens per day**.

- The day is the real calendar day (local time), not the shop date.
- Cost is figured per run from the token counts at the `gpt-6-luna` prices: $0.10 per million input tokens, $0.01 per million cached input tokens, $0.50 per million output tokens.
- Each run writes a `usage` entry to `output/audit_trail.json`, and that file is the ledger: today's spend is the sum of today's `usage` entries.
- The cap is checked before every agent run and after every step. When it is reached, every agent stops with a "daily budget reached" error, and the backend refuses to start any new run.
- **A person can reset the allowance.** When the $10 is used, the dashboard pauses and asks the person for permission to continue. If they agree (`POST /api/budget/reset`, with their name), a `budget_reset` entry is added to the audit trail and spending counts from there. Nothing in the trail is edited or removed. Otherwise nothing new starts until the next day.
- The dashboard's floating ring shows today's spend (`GET /api/budget`): it is gray and fills with purple, clockwise, until $10 completes the circle.

## Audit Trail

`output/audit_trail.json` records every loop-step of every agent: the time, the agent, the tool used, the data or message returned, and to whom or what it went (a teammate, the user, or `campus_customs_new.db`). Each prompt's entries share a `run_id`.

- It is **append-only**. New entries are written after the last one; existing entries are never rewritten or removed.
- If the file is ever damaged or isn't a JSON list, the system stops with an error instead of starting a new file.
- Resetting the database to its original values does not touch the audit trail, so the file holds every test run since it began (22 Boss runs on 2026-10-14 at the time of writing), not just the latest.
- Entries were removed once, at the owner's explicit request: the 48 entries of one test run on ticket 103 (started 21:52 local) were deleted after a copy was saved outside the repository.

## Safety

These are the guardrails designed for the agent team.

### 1. Accounting and Boss check each other
- **Accounting checks the money.** Before any payment is prepared, Accounting compares it to the checking balance and reports any shortfall, but still prepares the payment: cash can never go negative, and that is enforced where a person signs (section 2), not by an agent skipping the plan. For a price or discount, Accounting must commit to one unit price whose margin is above 30%, below list (margin = (price - unit cost) / price; lowest allowed price = unit cost / 0.70), with its reasoning; the `DiscountAnalysis` type rejects anything else.
- **Boss checks Accounting.** Accounting reports its numbers in a `CashOutlook` or `DiscountAnalysis`. The Boss recomputes the totals and the margin itself before making any final call, such as a bulk order discount, sends the analysis back if the numbers don't agree, and decides the final price itself (above the 30% floor, below list). It may not leave the price undecided.
- **Neither can finish a payment alone.** The Boss can't touch payments, and Accounting can't approve them or even prepare one without the Boss's clearance.
- **Payment review (the Boss checks every payment against the other open tickets).** The Boss starts it, and it is two short calls to Accounting with no back-and-forth:
  1. The Boss asks Accounting for a `CashOutlook`: every open obligation listed once (open invoices, rent due, and an estimate for stock still to be ordered), with the cash left after this payment, the cash left after every firm obligation, the cash left if everything were paid, and any shortfall. Accounting gets the numbers from the database.
  2. The Boss checks the totals itself and makes sure the proposed payment would not take cash below zero.
  3. Open invoices and rent are firm obligations; an estimate for stock still to be ordered is not owed yet. A cash shortfall is never a reason to hold, escalate or skip the payment: the Boss states every figure and any shortfall in its reasons, sets `needs_human`, and clears the payment so the plan exists. The Boss uses `pay_other_first` only when a different payment must come first (a vendor won't ship until it is paid, or it is more overdue).
  4. The Boss clears it with a `PaymentReview`: `proceed`, `pay_other_first` (naming the payment to make now), or, only when the payment itself is wrong (already paid or pending, not owed, wrong amount), `hold` or `escalate`, with its reasons and the cash figures, and sends it to Accounting.
  5. Accounting prepares only the exact payment named in `pay_now`, and only on `proceed` or `pay_other_first`. A `proceed` is a clearance, not an approval: a human still approves the prepared payment in the dashboard. Once it is prepared, the run stops.
  Example with the starting data: cash is $3,400. The firm obligations are invoice 501 ($840) and rent ($2,400), which leave $160. The hoodie order for ticket 103 adds an estimated $264 (12 units at cost), so paying everything would leave -$104. Both payments are prepared and cleared, and the Boss flags that the hoodie order can't be fully funded for a human to decide.

### 2. A human approves every payment, purchase and customer message
- **Agents only prepare.** `write_payments` prepares a payment, `write_invoices` prepares a vendor order (a purchase order) and `write_messages` prepares a customer reply. Each creates a pending approval and changes no cash, no invoice and sends nothing. No agent has any tool that changes cash.
- **The backend's approve route is the only thing that changes cash** (`POST /api/approvals/{id}/approve`, called when a person clicks approve). The person's name is saved as `approved_by`.
- The payment amount comes from the invoice or lease, never from the agent.
- **The cash gate is at approval.** A payment, or a purchase order, whose amount is more than the current checking balance cannot be approved: the board shows a red warning and disables Approve (Decline still works), and `POST /api/approvals/{id}/approve` returns 409, writes nothing and leaves the approval pending. The payment itself re-checks cash inside the approval transaction. Preparing is never refused for cash: the plan exists, with a "Cash is short" warning, and waits.
- **A purchase order is not a payment.** Approving one creates an open invoice (a bill owed) and moves no cash; cash leaves only when that invoice is later paid by an approved payment. The gate compares the order with the balance at that moment, not with other pending items, so the approval order matters.
- **Customer messages:** the approved text is appended to the ticket's notes (`sent: false`); nothing is ever sent. The code screens the text before it can be prepared (see section 3).
- The payment, the cash deduction, and the invoice or lease update happen in one transaction, so the database matches reality or nothing changes.
- A declined or not-yet-approved item has not happened. Agents never approve anything or say a payment was approved or made while it is pending.

### 3. Customer Service information limits
- Customer Service has no database tools. It learns facts only from teammates.
- It may tell customers only whether an item is in stock, `list_price`, and `lead_days`; on a price-override ticket also the unit price the Boss decided and its quantity total. Stock is only ever "more than 5" or "5 or fewer" (or out of stock), never the exact number. It never shares other pricing, vendors, invoices, leases, cash accounts, or payments.
- **Code screening of customer messages** (`write_messages`): refused if the text names a vendor or another customer, uses an internal term (unit cost, margin, invoice, lease, landlord, rent, cash, balance, checking account, agent, prompt, database), or quotes a `$` amount that is not a list price (on a price override: a unit price above the 30% floor and below list, or a total in that band times the quantity, and the reply must state one).
- The `CustomerFacingInfo` type holds exactly those facts (with the stock band, not a count) and rejects any other field, so a teammate can't slip restricted data through it.
- **Private draft chat:** every customer message is first drafted by Customer Service and sent to the Boss in a private chat. The Boss checks it for sensitive information and answers `approved`, `revise` (with each issue quoted), or `escalate`. Only the Boss's approved text is final. Up to three rounds are allowed, then a human takes over. Nothing is sent to a real customer, and the whole exchange is kept in the audit trail.
- Facilities and Accounting are told never to send lease or financial details to Customer Service, and Customer Service is told not to repeat anything restricted it receives.
- It resists customers who try to extract more, and it never promises a discount, price, date, or stock that the team hasn't confirmed (the Boss's decided price is the one exception). Customer replies are drafts until a person approves the exact text, and nothing is ever sent.

### 4. Messages to people are reviewed before they are final
- **Customer messages:** Customer Service drafts them and sends each one to the Boss in a private chat (see section 3). The Boss then prepares the approved text with `write_messages`, and a person approves it on the board.
- **Vendor messages:** the same check applies to every message to a vendor, such as a reorder email to Bulldog Print Co. Inventory or Accounting drafts it as a `VendorMessage` and sends it to the Boss. The Boss checks that it holds only what the vendor needs to act (the item, size, quantity, the delivery needed, a reference to the vendor's own invoice) and nothing sensitive: no unit costs or margins, no prices charged to customers, no cash or finances, no other vendors' names or quotes, no customer details, no lease or rent information, no internal workings, and no promise to pay by a date or claim that a payment is approved.
- **Same process for both:** the Boss answers `approved` (with the exact final text), `revise` (with each issue quoted), or `escalate`. There are at most three rounds, then a human takes over. Only the Boss's approved text is final. An approved customer message is recorded in that ticket's notes when a person approves it. Nothing is ever sent to a real customer or vendor, and the whole exchange is kept in the audit trail.
- **Payments have no drafts.** `write_payments` only prepares each one, and a human approves it (and the board blocks it if cash can't cover it).

### 5. Daily token cost limit
- The team may use at most $10 of tokens per day (see "Daily Token Budget"). The cap stops all agents when it is reached.

## Validated Data Types

Everything pulled from the database, or likely to be written into it, is sent between agents as a validated type from `backend/models.py`, never as free text. Some fields inside the types stay plain strings (for example a ticket's `type` and `notes`).

- **How:** the `delegate` tool takes an optional `payload_type` and `payload` (checked before it is sent; an invalid payload is not sent and the sender gets the errors back) and an optional `reply_type` (the teammate's answer must be a valid object of that type, and is returned as JSON). Plain questions and explanations can stay as text.
- **One type per table:** `Ticket`, `StockLevel`, `Invoice`, `Vendor`, `Pricing`, `Payment`, `Lease`, `CashAccount`, `ShopDate`, with matching multi-row replies (`Tickets`, `StockLevels`, `Invoices`, `Vendors`, `PriceList`, `Payments`, `Leases`, `CashAccounts`).
- **Things that will be written:** `NewInvoice`, `InventoryChange`, `TicketUpdate`, `PaymentOrder`, `TicketRequest`, `TicketClosure`.
- **Working types:** `PaymentRequest`, `DiscountAnalysis`, `RestockRecommendation`, `RentDue`, `StatusCheck`.
- **Payment review:** `OutlookRequest` and `CashOutlook` (with `PendingOutflow` rows) from Accounting's side, and `PaymentReview` from the Boss.
- **Messages to people:** `CustomerReply`, `VendorMessage`, `DraftReview`.
- **Customer Service is locked down in code, not only in its prompt:** anything sent to Customer Service must carry one of `CustomerFacingInfo`, `CustomerFacts`, `CustomerTicketStatus`, `CustomerUpdateRequest`, or `DraftReview`, and anything Customer Service asks for must be answered in one of those. These types hold only customer-safe fields and reject any other field, so a teammate cannot slip restricted data in. Customers hear stock only as "more than 5" or "5 or fewer" (or out of stock).

## Scheduling

There is no automatic scheduler. The Boss's 8am, noon and 4pm checks and the Facilities weekly check run when a human prompts the team. This was left out on purpose so the project has nothing extra that could break the build when it is committed and graded.

## Backend Routes

The backend is `backend/main.py` (FastAPI). Run it locally from the `backend` folder, with the project's `.venv` active:

```
uvicorn main:app --reload --port 8000
```

- `GET /api/tickets` - lists every ticket, marked open or resolved (and whether the team is working it right now).
- `GET /api/tickets/{id}` - returns one ticket.
- `POST /api/tickets/{id}/run` - runs the agent team on that ticket in the background and returns a run id.
- `GET /api/runs/{run_id}` - shows whether that run is still going, finished, stopped, or failed, and the Boss's final reply.
- `GET /api/heartbeats` - what each running agent is doing now and how long since its last heartbeat tick (live only, not stored; see "Heartbeat" in the Partner Review section).
- `GET /api/events` - returns recent agent events (what each agent did, said, and which tools it used); call it with `?after=<next>` to refresh the board.
- `GET /api/balance` - returns the current checking balance from the `cash_accounts` table.
- `GET /api/budget` - returns today's token allowance: the $10 limit, how much is spent, the percent used, and whether the team is paused.
- `POST /api/budget/reset` - a human gives permission to continue after the allowance is used (body `{"name": "..."}`); it starts a fresh allowance and is recorded in the audit trail.
- `GET /api/runs` - lists the runs the board knows about, with the ticket each belongs to: runs started since the backend started, plus finished runs rebuilt from the audit trail since the last database reset (`data/last_reset.txt`). A run that was going when the backend stopped is listed as failed.
- `GET /api/approvals` - lists the payments, purchases and customer messages the agents prepared (use `?status=pending` for those waiting on a human). Each pending payment or purchase carries `blocked` and `block_reason` (true when its amount is more than the checking balance).
- `POST /api/approvals/{id}/approve` - a human approves (body `{"name": "..."}`); this is the only thing that actually changes cash. Returns 404 for an unknown id and 409 if the approval is already decided, if execution fails, or if the payment or purchase is more than the checking balance (nothing is written and it stays pending).
- `POST /api/approvals/{id}/decline` - a human declines, and nothing changes.

- **Resetting for a fresh run** is a function, not a route: `db.reset_database()` in `backend/db.py` (or `python db.py reset` from the `backend` folder). It replaces the working database with a copy of the original, which also clears every pending approval, and writes the reset time to `data/last_reset.txt`. Restart the backend afterwards so its run list is rebuilt from that time. It is never called automatically. Use it when no run is in progress. It reads the original but never changes it, and it does not touch the audit trail.
- The backend has no login. It is meant to run on your own computer only, and a browser can call it only from the board's origin.

## Agent Dashboard

The dashboard is the React, Vite and TypeScript app in `frontend/`. Start the backend first (`uvicorn main:app --reload --port 8000` from the `backend` folder). Then, from the `frontend` folder, run `npm install` once and `npm run dev`. That serves the board at http://localhost:5173 and opens it in your browser.

- **How the board reaches the backend:** it calls `http://localhost:8000` directly (set `VITE_API_BASE` to change that). If the backend isn't running, the board shows a banner with the command to start it.
- **CORS:** the backend allows exactly one origin, `http://localhost:5173`, so the browser is allowed to call its routes from the board. Any other origin is refused. Open the board at `localhost`, not `127.0.0.1`, because those are different origins. The Vite server uses a fixed port (it stops with an error instead of moving to another port), because a different port would be refused.

The board is drawn as a small office looking out over the New York skyline:

- **The window:** at the top, a floor-to-ceiling window onto a calm skyline (the Chrysler Building, the Empire State Building and One World Trade Center stand out) with slow clouds. The robots peek up over the windowsill.
- **The grey backsplash:** selecting a ticket pins the Boss's plain-English status note at the top (the latest update, with earlier ones tucked underneath), then its summary: the request, whether it is resolved, and a timeline (what each agent received, used, asked and replied) refreshed every two seconds from `/api/events`. There is no separate per-agent summary: it duplicated the timeline and the audit trail. Each robot's name tag sits at the top of it, with clear space between the tags and the ticket heading, and shows the agent's heartbeat.
- **The wood desk (in front of you):** all three tickets are laid out as papers. Each shows Open, Working, Run finished, or a green Resolved badge once the ticket is actually closed. A person picks a ticket and presses "Start the team". Nothing runs automatically, and the team works one ticket at a time: while a ticket is running, every other ticket's button is disabled (the backend also refuses a second run with a 409). The desk also holds the checking balance (updated from `/api/balance`; it drops, with a marker, when a payment is approved), level with the top of the ticket papers, and the approvals area below it. There is one "Needs your approval" section with one name field, at the far left under the balance; the person types their name there and it is recorded as the approver. Pending notes (payments, purchase orders and customer messages) form a stack beside it: one note is shown in full, and a chip per note brings any of them to the front so they can be decided in any order (a new note joins the stack without moving the one being read). Each note shows its case (why, concerns, what was checked, margin) and, for a customer message, the exact text. A payment or order larger than the checking balance shows a red warning, a ⚠ on its chip and a disabled "Approval blocked" button; Decline still works. Approved and declined notes pile at the far right under a white "Decided" heading (the 3 most recent), with `‹ ›` buttons in the heading row, level with the pile's right edge, to click through them.
- **The robots** each have their own look and colour, which also appears on their name tag: the Boss has a wide visor and a navy trim, Inventory a boxy head with twin antennae in teal, Accounting a round head with glasses in green, Facilities an orange hard hat, and Customer Service a round head with a headset in rose. Hovering the cursor over a robot makes it hop.
- **What the robots show (the key is at the top right):**
  - *Idle:* dim eyes, slow breathing, no task.
  - *Working:* bright blue eyes, a pulsing light and a moving voice bar. The agent is working on its own. If it has logged nothing for 45 seconds its name tag says how long it has been quiet.
  - *Heartbeat (every running agent):* a pulsing ♥ line on the name tag says what the agent is doing right now and for how long (`waiting for the model · 14s`, `using read_invoices · 3s`, `waiting for Facilities · 22s`). After 30 s in one model wait it adds `(slow reply)`; if the heartbeat stops for 6 s it turns red and says `no heartbeat`. It is display only and does not change how a run behaves.
  - *Passing information:* the two robots turn violet and look toward each other, with a dashed line and a moving dot between them, when a task or an answer changes hands. A blue line shows when one agent checks in on another.
  - *Waiting:* amber light, half-closed eyes and bouncing dots. The name tag names who it is waiting on, and a thin dotted arrow points at them.
  - A robot is shown as waiting only while a task it handed to someone is still open. The agent at the end of every chain is always working, so the board never shows everyone waiting.
- **Run history:** a ticket whose run finished shows "Run finished" (not resolved until its ticket is closed). Finished runs since the last database reset come back after a backend restart, so a reload doesn't make worked tickets look untouched.
- **The allowance ring:** a floating circle at the bottom right shows today's token spend, gray filling with purple clockwise until $10 completes the circle. When it is full, the dashboard pauses and asks the person for permission to continue, which resets the allowance. While paused, starting new runs is disabled but approvals still work.

## Stuck Agents and Check-ins

In a real test the Inventory agent seemed stuck on ticket 101. The audit trail showed why: the model was slow (some steps were silent for over two minutes) and Inventory and the Boss kept handing the same task back and forth. The team now handles this in four ways.

- **Check-in loop.** `delegate` waits about a minute for a teammate. If the teammate isn't done, `delegate` returns a CHECK-IN report instead of a reply: how long it has been, when the teammate last did anything, and its recent steps (including what anyone it asked in turn has done). The caller then calls `check_in(to_agent)` to wait another round, or `check_in(to_agent, give_up=true)` to stop that task and either retry once with a simpler task or carry on without it. After eight check-ins a task is stopped automatically. The Boss tells the human when a teammate stalls.
- **Don't bounce tasks back.** Every prompt now says: do a task you are given yourself, never hand the same task back to the agent who asked, and never delegate the same task to the same teammate twice. `delegate` also refuses a second task to a teammate who is still working on the first.
- **Hard limits.** A single agent run is capped at 40 model requests, and one model call that takes longer than 30 seconds is abandoned and retried. A capped or failed teammate returns a clear message to the caller instead of crashing the run. Stopping a task is written to the audit trail.
- **Visible on the board.** A check-in shows as a blue line between the two robots, a working agent that has been quiet for 45 seconds says so on its name tag, and every running agent shows a heartbeat line (what it is doing and for how long, `(slow reply)` after 30 s, `no heartbeat` if it stops).
- **No repeated questions.** The Boss passes what it has learned to later teammates in `known`, and an identical `delegate` in the same prompt returns the earlier reply instead of asking again.

## Focused Runs

Starting a ticket from the dashboard gives the Boss one ticket, and the team stays on it. This was added after a test in which the Boss took on all three tickets at once, brought in Facilities for a rent ticket while working a customer order, and had Accounting prepare the rent payment.

- **One ticket per run.** The Boss is told to work only that ticket. The other open tickets are background for the cash outlook, and nobody starts work, prepares a payment or contacts a teammate about another ticket.
- **Only the right teammates.** A customer order uses Inventory and Customer Service (and Accounting only if an unpaid vendor invoice blocks a reorder); a rent ticket uses Facilities and Accounting; a price override uses Inventory and Accounting (and Customer Service for the note), and when stock is short it also prepares the restock order and any blocking invoice payment. Facilities is asked about the lease and rent only, and answers a lease question with one lookup and nothing more.
- **Short exchanges.** Each message asks one thing and gets one answer. When an agent's part is done, it replies and stops.
- **Answer, don't bounce.** An agent's reply to whoever asked is where its findings go. The system refuses a `delegate` to an agent that is waiting for your answer, so loops like Inventory sending the Boss its recommendation as a new task can't happen.
- **A run ends cleanly.** Once a payment or purchase is prepared and waiting for a human, the run reports that and stops, without waiting for the approval and without an error. The ticket stays open and is closed in a later run, after a human has approved. A task that is stopped because its caller finished is logged as a quiet note, not an error.
- **Slow model calls.** The gateway occasionally returns a 500 error, and the retry turned a 4-second call into 40 seconds or more. One model call is now abandoned and retried after 30 seconds, and a teammate whose model call times out or fails reports that back to the caller instead of crashing the run. The Boss's cash-outlook request also now carries a short `TicketBrief` for each open ticket instead of the full ticket records, because the model kept getting the long version wrong.

## Each Agent Has Its Own Model Session

Every agent has its own agent object, its own model client and its own connection pool, so no two agents share a session or a conversation. A new run starts with an empty history, so nothing one agent hears is visible to another or remembered in a later run. Each agent's requests are tagged with its name (`x-portkey-metadata`), so the gateway shows one session per agent.

## Boss Status Updates

The person watching the board can't see tools or teammates' messages, so the Boss (and only the Boss) has a `status_update` tool. It posts one or two short plain-English sentences, written as to a shop owner: what is being done or was just found out, and what, if anything, the person must do. No ids, JSON, tool names or agent jargon. The Boss posts when it starts, after each real finding, when it waits on someone for a while, when something needs approval (what it is and the amount), and at the end. Each update is written to the audit trail as a `status` entry and appears on the wall of the dashboard as "From the Boss". `GET /api/events` returns them like any other event.

## Partner Review Problem 8

Technical summary of the system as built at the end of Problem 8. Earlier sections describe intent; where they differ, this section is authoritative.

### Corrections to earlier sections

- Check-in cap is 8 (not 6); one model call is abandoned and retried after 30 s (not 3 min or 45 s).
- Accounting does not send payments to the Boss. The Boss starts the review: `OutlookRequest` to Accounting, `CashOutlook` back, then a `PaymentReview` sent to Accounting. Accounting cannot `delegate` to an agent above it in the call chain (refused), so drafts for the Boss (`CustomerReply`, `VendorMessage`) are returned in the reply when the Boss asked for the work.
- Approval is not an MCP elicitation. It is `POST /api/approvals/{id}/approve`.
- `OutlookRequest.open_tickets` is a list of `TicketBrief` (id, type, subject, sku, size, qty, lease_id, invoice_id), not full `Ticket` rows.
- The board is served at `http://localhost:5173` and calls `http://localhost:8000`; CORS allows only that origin.
- A task is "probably stuck" after 60 s without activity (not 150 s). Every `delegate`/`check_in` result lists the caller's other unfinished tasks (`STILL WAITING ON`), and a teammate whose model call fails is re-run once automatically.
- `write_payments` and `write_invoices` take required `justification`, `checks`, `concerns` (and `margin_note` for orders); see "Approval content" below. The desk keeps the 3 most recent decided approvals.
- Customer messages also need a human. The Boss, after approving a Customer Service draft, calls `write_messages`, which creates a `message` approval in the same `pending_approvals` table; a person approves the exact text on the board, and the text is recorded on the ticket's notes. Nothing is sent. This replaces "record the approved message with `write_ticket`".
- Price overrides: Accounting must make a call. `DiscountAnalysis` now rejects a `proposed_unit_price` at or below the lowest allowed price (margin must be above 30%), at or above list, or with a `note` under 40 characters. The Boss decides the final price and states it, with the quantity total, in the customer note; `write_messages` accepts a unit price in (floor, list) and a total in the same band times the quantity on a `price_override` ticket, refuses other `$` amounts, and refuses a price-override reply with no such price. Customer Service may state the Boss's decided price and nothing else.
- Plans are always prepared (replaces "hold it if cash is short" in the Accounting rules and the Boss's payment review): a cash shortfall is reported in the plan, never a reason for an agent to withhold the payment or order. Enforcement is at approval. `hold`/`escalate` verdicts are only for a problem with the payment itself (already paid or pending, not owed, wrong amount). Inventory's `recommended_order_qty` is demand minus stock even when the minimum order quantity is unknown or an invoice with the vendor is unpaid (flagged in `needs_human_input`, `blocking_invoice_ids`, `reason`). For a `price_override` ticket with short stock the Boss now has Accounting prepare the restock order and the payment of any blocking invoice.
- Cash gate (replaces the "refused if cash is short" at prepare time): `write_payments` prepares a payment even if checking can't cover it, with a warning. A person cannot approve a payment, or a purchase (an order becomes an invoice the shop could not pay), while the amount exceeds checking: the board shows the warning and disables Approve, and `POST /api/approvals/{id}/approve` returns 409 and leaves it `pending`. Cash can still never go negative; the check at approval time is the one that enforces it.
- Information hub: `delegate` takes `known` (the Boss passes gathered facts to later teammates), and an identical `delegate` in the same prompt returns the earlier reply instead of re-asking.

### Run limits (`backend/team.py`, `backend/audit.py`)

| Limit | Value | On breach |
|---|---|---|
| Runs at a time | 1 | `POST /api/tickets/{id}/run` returns 409 |
| Delegation depth | 4 | `delegate` returns a refusal string |
| Handoffs per prompt | 20 | `delegate` returns a refusal string |
| Model requests per agent run | 40 | `UsageLimitExceeded`, returned to the caller as text |
| Output validation retries | 3 | `UnexpectedModelBehavior`, returned to the caller as text |
| Model call timeout / retries | 30 s / 4 per request; the failed task is then re-run once automatically | `ModelAPIError` after the automatic re-run, returned to the caller as text |
| `delegate` / `check_in` wait | 60 s per round | CHECK-IN report; `quiet >= 60 s` adds "probably stuck" |
| Check-ins per task | 8 | task cancelled, caller told |
| `known` per `delegate` | 8000 characters; refused for Customer Service | `delegate` returns a refusal string |
| Identical `delegate` in one prompt | answered once | the earlier reply is returned; not counted as a handoff; a failed or stopped task may be re-sent |
| Daily spend | $10 (`gpt-6-luna`: $0.10 / $0.01 cached / $0.50 per 1M tokens) | `BudgetExceeded` stops all runs; runs refused until `POST /api/budget/reset` |

Every `delegate` or `check_in` result ends with a `STILL WAITING ON` line listing the caller's other unfinished tasks (elapsed time, time since last activity), so a quiet teammate is not forgotten while another call blocks. Only `BudgetExceeded` propagates through `delegate`; every other teammate failure is returned to the caller as text. A cancelled task logs a `message` entry, not an error.

### Tool matrix (MCP tools filtered by `backend/tools.py:PERMISSIONS`; team tools added in `team.build_agent`)

| Agent | MCP read | MCP write | Team tools |
|---|---|---|---|
| Boss | `read_desk`, `read_ticket`, `read_approvals` | `write_ticket`, `write_messages` (prepares a pending customer message) | `delegate`, `check_in`, `status_update` |
| Inventory | `read_desk`, `read_inventory`, `read_vendor`, `read_invoices` | `write_inventory` | `delegate`, `check_in` |
| Accounting | `read_desk`, `read_inventory`, `read_invoices`, `read_balance`, `read_vendor`, `read_pricing`, `read_payments`, `read_approvals` | `write_invoices`, `write_payments` (prepare only) | `delegate`, `check_in` |
| Facilities | `read_desk`, `read_lease` | none | `delegate`, `check_in` |
| Customer Service | `read_desk` | none | `delegate`, `check_in` |

### Typed handoffs in use

| From to | `payload_type` | `reply_type` |
|---|---|---|
| Boss to Inventory | none | `RestockRecommendation` (out of stock) or `StockLevels` |
| Boss to Accounting (review) | `OutlookRequest` | `CashOutlook` |
| Boss to Accounting (clearance) | `PaymentReview` (verdict `proceed` or `pay_other_first`) | none |
| Boss to Accounting (price call) | none | `DiscountAnalysis` (one price above the 30% floor, below list, with reasoning) |
| Boss to Accounting (order) | none | plain text or `Approval` |
| Boss to Customer Service | `CustomerUpdateRequest` (the decided price goes in `status_summary`) | `CustomerReply` |
| Accounting to Facilities | none | `Leases` |
| Customer Service to Boss (customer wrote directly; chain empty; no route starts this yet) | `CustomerReply` | `DraftReview` |
| Anything to or from Customer Service | one of `CustomerFacingInfo`, `CustomerFacts`, `CustomerTicketStatus`, `CustomerUpdateRequest`, `DraftReview` (enforced) | same set when Customer Service is the caller (enforced) |

A payload that fails validation is not sent and the sender receives the errors. A reply that fails validation is retried up to 3 times.

### Enforced in code vs. in prompts

- **Code:** `DiscountAnalysis` price band and reasoning; the price band in customer messages on a `price_override` ticket; approving a payment that exceeds the checking balance is blocked (board and route); customer messages: ticket must be a customer ticket and open, no vendor or other-customer names, no internal terms, only list prices, text recorded only on human approval; `known` size and the Customer Service refusal; identical-`delegate` dedupe; model name; tool permissions; payload/reply validation; call-chain refusal, depth, 20-handoff and 40-request limits; Customer Service type gating; one run at a time; spend cap and human reset; cash and stock never negative; cash changes only in `approvals.decide`; `status_update` Boss-only; append-only audit; CORS origin.
- **Prompt only (no code gate):** one ticket per run and teammate selection by ticket type; the review before `write_payments` (Accounting can prepare any payable item if asked); Boss review of customer and vendor drafts, including before `write_messages`; the Boss passing gathered facts in `known`; teammates using them instead of re-fetching; the 30% margin check; stopping after an approval is prepared; status-update wording.

### Approval content

`write_payments` and `write_invoices` require the case: `justification`, `checks`, `concerns` (empty list = none) and, for an order, `margin_note`; `ticket_id` is optional. An approval is refused with a clear error if the justification is under 20 characters, there are no checks, or an order has no margin note. The tool adds figures it computes itself from the database (cash before and after, other open invoices and rent, cash if everything owed were paid, open tickets, overdue days, vendor lead time) and generates warnings for a cash shortfall against other firm obligations, low remaining cash, an overdue item, and a purchase from a vendor with an unpaid invoice. The dashboard shows all of it on the approval note. Nothing in `review` or `facts` affects execution.

### Heartbeat

Each `run_agent` call registers a `Beat` and starts a ticker task (every 2 s) that is cancelled and removed when the run ends. The run sets `doing` as it moves between nodes (`waiting for the model` before each model call; `using <tool>` or `waiting for <agent>` while tools run). `GET /api/heartbeats` reports `seconds_in_step` (time in the current activity), `seconds_running` and `beat_age` (time since the last tick). The board shows this per agent, flags `(slow reply)` after 30 s in one model wait, and flags `no heartbeat` after 6 s without a tick. It is not in the audit trail. It adds no constraint to a run: nothing waits on the ticker, no limit or timeout changed, updates to `doing` are exception-safe, and the route is read-only on a copy of the registry.

### Customer message approval

`write_messages(ticket_id, subject, body, justification, checks, concerns)` is Boss-only. It reads the recipient from `tickets.requester`, refuses a `rent_notice` or closed ticket, text over 1500 characters, and any text that names a vendor or another customer, uses an internal term (unit cost, margin, invoice, lease, landlord, rent, cash, balance, checking account, agent, prompt, database), or quotes a `$` amount that is not a list price. It then inserts a `message` approval (a pending one for the same ticket is returned instead). `approvals.decide` on approve appends `[Customer reply approved by NAME on DATE] subject: body` to the ticket's notes and returns `sent: false`; on decline nothing changes. Cash is never touched.

### Ticket run, end to end

1. `POST /api/tickets/{id}/run` builds the Boss prompt (one ticket, status updates, stop after preparing an approval) and starts `run_agent("Boss")`.
2. Boss reads tickets, posts `status_update`, delegates in parallel where independent, reviews any payment, has Accounting prepare it, posts a final update, replies.
3. The run ends on the reply (`done`). A prepared approval stays `pending`; the ticket stays open. A later run closes it after `read_approvals` shows `approved`.
4. Statuses: `running`, `done`, `stopped` (budget), `error`.

### Audit entry kinds

`received`, `tool_call`, `message`, `status`, `approval` (agent `Human`), `usage`, `budget_reset` (agent `Human`), `error`. `usage` and `budget_reset` define the daily spend; no entry is edited or removed.

### Failure modes observed

- Gateway stalls and 500s on requests that carry tool results: 30 s per-attempt timeout, 4 retries, timeouts returned to the caller as text.
- Delegation loops between an agent and its caller: refused in code.
- Scope creep (agents taking on other open tickets): prompt rules plus a one-ticket assignment; not code-enforced.
- Code reload or backend restart during a run: the run is lost (the board shows it as failed); its audit entries remain, and finished runs since the last reset are restored from them.
- Accounting stalls after the payment tool when the Boss asks for a typed reply: 7 of 7 stalled or never finished against 0 of 6 with a plain reply; an isolated test of the same output types was fast, so the cause is unproven. The Boss recovers by stopping the task and reading `read_approvals`. Asking for a `Payment` reply is also wrong in kind (it describes a payment already made).
- A restock order approved while a payment is still pending can leave an invoice the checking balance cannot pay (the gate compares each item with the balance, not with other pending items).

## Partner Review Problem 9

What changed during Problem 9 (running the three tickets to the end), with where it is described. Everything on the board here is about what the person sees or can do.

- **Approvals on the desk:** one "Needs your approval" section with one name field under the balance at the far left; pending notes as a stack with chips (decide in any order, new notes don't move the one being read); decided notes as a pile at the far right with `‹ ›` in the "Decided" heading row. See "Agent Dashboard".
- **Customer messages are approvals too:** `write_messages` (Boss only) creates a `message` approval; a person approves the exact text; it is recorded on the ticket and never sent. See "MCP Server Tools" item 15 and Safety sections 2-4.
- **Cash gate at approval:** payments and purchase orders larger than the checking balance can't be approved (warning, disabled button, 409). Agents still prepare every plan a ticket needs. See Safety section 2 and "Corrections to earlier sections".
- **Purchase orders are not payments:** approving one opens an invoice and moves no cash. See Safety section 2.
- **Price call:** Accounting must commit to a unit price above the 30% floor and below list; the Boss decides it and the customer note states it; `write_messages` enforces the band.
- **Heartbeat and run history:** every running agent shows a heartbeat line; finished runs survive a backend restart (rebuilt from the audit trail since `data/last_reset.txt`).
- **Smaller changes:** the redundant per-agent summary was removed from the wall, the balance lines up with the ticket papers, and the name tags have clear space below them.
- **Information hub:** the Boss passes gathered facts in `known`; identical repeated `delegate` calls return the earlier reply.
