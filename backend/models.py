"""Data types the Campus Customs agents pass to each other.

Agents hand these around as JSON objects inside their delegate() messages and
replies; this file is the single source of truth for their fields. Anything
derived (margin, balances after a payment, due dates) is a computed field, so
two agents can never disagree about the arithmetic.

Dates are the shop's dates (desk.date_today), never the real calendar date.
"""

from __future__ import annotations

import math
from datetime import date, datetime, timedelta
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, computed_field, create_model, field_validator, model_validator

AgentName = Literal["Boss", "Inventory", "Accounting", "Facilities", "Customer Service"]

# Business rules shared by several agents (see prompts/shared_rules.md).
MIN_MARGIN = 0.30  # gross margin floor: (price - unit_cost) / price
RENT_TICKET_LEAD_DAYS = 20  # a rent payment ticket is created this many days before it is due


def margin(price: float, unit_cost: float) -> float:
    """Gross margin as a fraction of the selling price."""
    return (price - unit_cost) / price if price > 0 else float("-inf")


def min_price_for_margin(unit_cost: float, floor: float = MIN_MARGIN) -> float:
    """Lowest unit price (rounded UP to the cent) that still meets the margin floor."""
    return math.ceil(unit_cost / (1 - floor) * 100) / 100


# --- Database rows ---------------------------------------------------------


class Ticket(BaseModel):
    """One row of the tickets table (what Boss reads with read_ticket)."""

    id: int
    type: str  # customer_order, rent_notice, price_override, ...
    requester: str
    subject: str
    sku: str | None = None
    size: str | None = None
    qty: int | None = None
    lease_id: int | None = None
    invoice_id: int | None = None
    status: Literal["open", "closed"]
    notes: str | None = None
    created_at: datetime


class StockLevel(BaseModel):
    """One row of the inventory table (sku + size is the key)."""

    sku: str
    size: str
    name: str
    qty: int = Field(ge=0)
    location: str


# --- Boss: tickets and coordination ------------------------------------------


class TicketRequest(BaseModel):
    """A teammate asking Boss to open and track a ticket.

    Only Boss writes tickets; every other agent sends one of these instead.
    """

    requested_by: AgentName
    type: str  # e.g. restock_order, rent_payment, payment_approval, customer_update
    subject: str
    details: str
    sku: str | None = None
    size: str | None = None
    qty: int | None = None
    lease_id: int | None = None
    invoice_id: int | None = None
    related_ticket_id: int | None = None
    priority: Literal["low", "normal", "high"] = "normal"
    needs_human: bool = False  # e.g. a payment that only a person can approve


class StatusCheck(BaseModel):
    """Boss's status line for one ticket at a scheduled check (8am, noon, 4pm) or a human prompt."""

    ticket_id: int
    slot: Literal["08:00", "12:00", "16:00", "on_request"]
    as_of: date
    state: Literal[
        "not_started",
        "in_progress",
        "waiting_on_vendor",
        "waiting_on_human",
        "ready_to_close",
        "closed",
    ]
    waiting_on: str | None = None  # agent, vendor, or "human approval"
    summary: str
    next_action: str | None = None


class TicketClosure(BaseModel):
    """What Boss records when closing a ticket (becomes the ticket's notes via write_ticket)."""

    ticket_id: int
    actions_taken: list[str]
    suppliers: list[str] = Field(default_factory=list)
    delegation_path: list[str] = Field(
        default_factory=list, description="e.g. 'Boss -> Inventory', 'Inventory -> Accounting'"
    )
    human_exceptions: list[str] = Field(
        default_factory=list, description="anything a human had to approve or handle"
    )

    def to_notes(self) -> str:
        """Notes text for write_ticket. The tool stamps the closing date itself, so none is added here."""
        parts = [
            "Actions: " + "; ".join(self.actions_taken),
            "Suppliers: " + (", ".join(self.suppliers) or "none"),
            "Delegation: " + (", ".join(self.delegation_path) or "none"),
            "Human exceptions: " + ("; ".join(self.human_exceptions) or "none"),
        ]
        return ". ".join(parts) + "."


# --- Inventory ---------------------------------------------------------------


class RestockRecommendation(BaseModel):
    """Inventory's recommendation to reorder one item.

    The database has no minimum order quantity. Inventory still recommends the units
    needed (demand minus stock); when the minimum is unknown it sets needs_human_input
    and says so in `reason`, so a person can adjust the quantity.
    """

    sku: str
    size: str
    current_qty: int = Field(ge=0)
    demand_qty: int | None = None  # how many open tickets are asking for
    recommended_order_qty: int | None = Field(default=None, gt=0)
    vendor_id: int
    vendor_name: str
    lead_days: int = Field(ge=0)  # from the vendors table, never guessed
    as_of: date
    blocking_invoice_ids: list[int] = Field(
        default_factory=list,
        description="open invoices with this vendor; the vendor won't ship until they're paid",
    )
    needs_human_input: bool = False
    reason: str

    @computed_field
    @property
    def expected_arrival(self) -> date:
        """If ordered on as_of, the earliest the goods could arrive."""
        return self.as_of + timedelta(days=self.lead_days)

    @computed_field
    @property
    def ready_to_order(self) -> bool:
        return (
            not self.blocking_invoice_ids
            and not self.needs_human_input
            and self.recommended_order_qty is not None
        )


# --- Accounting --------------------------------------------------------------


class PaymentRequest(BaseModel):
    """Accounting's prepared payment. Accounting never approves it; a human does."""

    kind: Literal["invoice", "rent"]
    ref_id: int  # invoices.id or leases.id
    payee: str
    amount: float = Field(gt=0)
    due_date: date | None = None
    as_of: date
    cash_available: float  # checking balance when prepared
    ticket_id: int | None = None
    status: Literal[
        "proposed",
        "held_insufficient_funds",
        "awaiting_human_approval",
        "paid",
        "refused",
    ] = "proposed"
    note: str | None = None

    @computed_field
    @property
    def sufficient_funds(self) -> bool:
        return self.cash_available >= self.amount

    @computed_field
    @property
    def cash_after(self) -> float:
        """Balance if paid. Negative means the payment must be held, never made."""
        return round(self.cash_available - self.amount, 2)

    @computed_field
    @property
    def days_overdue(self) -> int:
        if self.due_date is None:
            return 0
        return max((self.as_of - self.due_date).days, 0)


class DiscountAnalysis(BaseModel):
    """Accounting's call on a price (e.g. a bulk discount): the one price it commits to.

    Margin is (price - unit_cost) / price. The price must outperform the floor (a margin above
    MIN_MARGIN, so above the lowest allowed price) and be below the list price, and the
    reasoning goes in `note`. Within that band the choice is Accounting's. Boss re-checks these
    numbers before making the final call.
    """

    ticket_id: int | None = None
    sku: str
    size: str | None = None
    qty: int = Field(gt=0)
    list_price: float = Field(gt=0)
    unit_cost: float = Field(ge=0)
    proposed_unit_price: float = Field(gt=0)
    note: str | None = None

    @model_validator(mode="after")
    def _a_real_call(self) -> "DiscountAnalysis":
        low = min_price_for_margin(self.unit_cost)
        if self.proposed_unit_price <= low:
            raise ValueError(f"commit to a price above the minimum margin target: {self.proposed_unit_price} is at or below the lowest allowed price {low}")
        if self.proposed_unit_price >= self.list_price:
            raise ValueError(f"a discount price must be below the list price {self.list_price}")
        if not self.note or len(self.note.strip()) < 40:
            raise ValueError("note is required: explain in a few sentences why you chose this price")
        return self

    @computed_field
    @property
    def margin_pct(self) -> float:
        return round(margin(self.proposed_unit_price, self.unit_cost) * 100, 2)

    @computed_field
    @property
    def discount_pct(self) -> float:
        return round((1 - self.proposed_unit_price / self.list_price) * 100, 2)

    @computed_field
    @property
    def lowest_allowed_unit_price(self) -> float:
        return min_price_for_margin(self.unit_cost)

    @computed_field
    @property
    def meets_margin_floor(self) -> bool:
        return self.proposed_unit_price >= self.lowest_allowed_unit_price

    @computed_field
    @property
    def total_revenue(self) -> float:
        return round(self.proposed_unit_price * self.qty, 2)

    @computed_field
    @property
    def total_profit(self) -> float:
        return round((self.proposed_unit_price - self.unit_cost) * self.qty, 2)


class PendingOutflow(BaseModel):
    """One amount of money the shop still has to pay out, for the Boss's cash outlook."""

    kind: Literal["invoice", "rent", "restock_estimate"]
    ref_id: int | None = None  # invoices.id or leases.id (none for an estimate)
    ticket_id: int | None = None
    payee: str
    amount: float = Field(gt=0)
    due_date: date | None = None
    estimated: bool = False  # True when the amount is an estimate (e.g. unit cost x units still to order)
    is_proposed: bool = False  # True for the payment under review
    note: str | None = None


class TicketBrief(BaseModel):
    """Just enough of a ticket for Accounting to work out what it will cost (so the Boss has little to copy)."""

    id: int
    type: str
    subject: str | None = None
    sku: str | None = None
    size: str | None = None
    qty: int | None = None
    lease_id: int | None = None
    invoice_id: int | None = None


class OutlookRequest(BaseModel):
    """The Boss asking Accounting for a CashOutlook: every open ticket, plus the payment being reviewed."""

    open_tickets: list[TicketBrief]
    proposed: PaymentOrder


class CashOutlook(BaseModel):
    """Accounting's answer: what the checking account would look like if the open obligations were paid.

    The totals are computed here, so Accounting and the Boss can't disagree about the arithmetic.
    Each obligation is listed once (an invoice linked to a ticket isn't counted twice).
    """

    as_of: date
    cash_available: float = Field(ge=0)
    outflows: list[PendingOutflow]

    @computed_field
    @property
    def total_outflows(self) -> float:
        return round(sum(o.amount for o in self.outflows), 2)

    @computed_field
    @property
    def cash_after_proposed(self) -> float:
        """Balance after only the payment under review. Negative means it must be refused."""
        return round(self.cash_available - sum(o.amount for o in self.outflows if o.is_proposed), 2)

    @computed_field
    @property
    def cash_after_all(self) -> float:
        """Balance if every open obligation were paid."""
        return round(self.cash_available - self.total_outflows, 2)

    @computed_field
    @property
    def cash_after_firm(self) -> float:
        """Balance if only the firm obligations (open invoices, rent) were paid. Estimates are not yet owed."""
        return round(self.cash_available - sum(o.amount for o in self.outflows if not o.estimated), 2)

    @computed_field
    @property
    def covers_all(self) -> bool:
        return self.cash_after_all >= 0

    @computed_field
    @property
    def shortfall(self) -> float:
        return round(max(-self.cash_after_all, 0), 2)


class PaymentReview(BaseModel):
    """The Boss's answer to a proposed payment, after checking it against the other open tickets.

    "proceed" or "pay_other_first" only clears Accounting to call write_payments for `pay_now`.
    It is NOT an approval: a human still approves every payment.
    """

    ticket_id: int | None = None
    round: int = Field(ge=1, le=3)
    reviewed: PaymentOrder  # the payment that was proposed
    verdict: Literal["proceed", "hold", "pay_other_first", "escalate"]
    pay_now: PaymentOrder | None = Field(
        default=None, description="the one payment Accounting may now submit; set only for proceed or pay_other_first"
    )
    cash_after_proposed: float
    cash_after_firm: float  # after every open invoice and rent payment (not estimates)
    cash_after_all: float  # after firm obligations and estimates
    shortfall: float = Field(ge=0)  # how far cash_after_all is below zero
    reasons: list[str]
    needs_human: bool = False

    @model_validator(mode="after")
    def _pay_now_matches_verdict(self) -> "PaymentReview":
        if self.verdict in ("proceed", "pay_other_first") and self.pay_now is None:
            raise ValueError("pay_now is required when the verdict is proceed or pay_other_first")
        if self.verdict in ("hold", "escalate") and self.pay_now is not None:
            raise ValueError("pay_now must be empty when the verdict is hold or escalate")
        if self.verdict == "proceed" and self.pay_now != self.reviewed:
            raise ValueError("for proceed, pay_now must be the payment that was reviewed")
        return self


# --- Facilities --------------------------------------------------------------


class RentDue(BaseModel):
    """Facilities' view of one lease and when its payment ticket is due to be created."""

    lease_id: int
    space_name: str
    landlord: str
    monthly_rent: float = Field(gt=0)
    next_due: date
    as_of: date

    @computed_field
    @property
    def days_until_due(self) -> int:
        return (self.next_due - self.as_of).days

    @computed_field
    @property
    def ticket_due_on(self) -> date:
        return self.next_due - timedelta(days=RENT_TICKET_LEAD_DAYS)

    @computed_field
    @property
    def ticket_needed_now(self) -> bool:
        return self.as_of >= self.ticket_due_on


# --- Customer Service --------------------------------------------------------


StockBand = Literal["out_of_stock", "5_or_fewer", "more_than_5"]


def stock_band(qty: int) -> StockBand:
    """The only stock information a customer gets: never the exact count."""
    if qty <= 0:
        return "out_of_stock"
    return "5_or_fewer" if qty <= 5 else "more_than_5"


class CustomerFacingInfo(BaseModel):
    """The ONLY facts about the shop that may reach a customer.

    extra="forbid" means a teammate can't slip in cost, vendor, invoice, lease,
    cash, or payment fields (or an exact stock count): they would fail validation.
    Teammates build this object for Customer Service; Customer Service must not
    ask for more.
    """

    model_config = ConfigDict(extra="forbid")

    sku: str
    size: str | None = None
    name: str
    stock: StockBand  # use stock_band(qty); a customer hears "more than 5" or "5 or fewer", never the number
    list_price: float  # the only price a customer may be told
    lead_days: int | None = Field(default=None, ge=0)  # the only vendor fact a customer may be told


class CustomerReply(BaseModel):
    """A customer message that is being drafted. Nothing is ever sent to a real customer.

    Customer Service writes it as a "draft"; only the Boss can mark it "approved"
    (after the sensitive-information check). Anything the team can't settle in
    three rounds becomes "needs_human".
    """

    ticket_id: int | None = None
    customer: str | None = None
    message: str
    status: Literal["draft", "approved", "needs_human"] = "draft"


class DraftReview(BaseModel):
    """The Boss's answer to a drafted customer or vendor message (the private draft chat)."""

    ticket_id: int | None = None
    audience: Literal["customer", "vendor"] = "customer"
    round: int = Field(ge=1, le=3)
    verdict: Literal["approved", "revise", "escalate"]
    issues: list[str] = Field(
        default_factory=list, description="each piece of sensitive or unconfirmed content, quoted from the draft"
    )
    approved_message: str | None = Field(
        default=None, description="the exact final text; set only when the verdict is 'approved'"
    )


# --- More database rows -------------------------------------------------------
# One model per table, so anything read from the database can travel between
# agents as a validated object.


class Invoice(BaseModel):
    id: int
    vendor_id: int
    amount: float = Field(gt=0)
    due_date: date
    status: Literal["open", "paid"]
    description: str | None = None


class Vendor(BaseModel):
    id: int
    name: str
    specialty: str
    lead_days: int = Field(ge=0)


class Pricing(BaseModel):
    sku: str
    unit_cost: float = Field(ge=0)
    list_price: float = Field(gt=0)


class Payment(BaseModel):
    id: int
    kind: Literal["invoice", "rent"]
    ref_id: int | None = None
    amount: float = Field(gt=0)
    account: str
    paid_at: date
    approved_by: str = Field(min_length=1)


class Lease(BaseModel):
    id: int
    space_name: str
    landlord: str
    monthly_rent: float = Field(gt=0)
    next_due: date
    notes: str | None = None


class CashAccount(BaseModel):
    name: str
    balance: float = Field(ge=0)  # cash can never go negative
    date: date


class ShopDate(BaseModel):
    """The desk table: the shop's assumed date. Never the real date."""

    date_today: date
    notes: str | None = None


def _rows(name: str, item: type[BaseModel]) -> type[BaseModel]:
    """A reply type for 'several rows of this kind'."""
    return create_model(name, items=(list[item], ...), __module__=__name__)


StockLevels = _rows("StockLevels", StockLevel)
Tickets = _rows("Tickets", Ticket)
Invoices = _rows("Invoices", Invoice)
Vendors = _rows("Vendors", Vendor)
PriceList = _rows("PriceList", Pricing)
Payments = _rows("Payments", Payment)
Leases = _rows("Leases", Lease)
CashAccounts = _rows("CashAccounts", CashAccount)


# --- Things that will be written to the database -------------------------------
# The same fields the write tools take, so a request can be checked before anyone calls the tool.


class NewInvoice(BaseModel):
    """An order to record with write_invoices."""

    vendor_id: int
    amount: float = Field(gt=0)
    due_date: date
    description: str = Field(min_length=1)
    ticket_id: int | None = None


class InventoryChange(BaseModel):
    """A stock change to record with write_inventory (positive = stock arrived, negative = stock left)."""

    sku: str
    size: str
    qty_change: int
    reason: str
    ticket_id: int | None = None

    @field_validator("qty_change")
    @classmethod
    def _not_zero(cls, v: int) -> int:
        if v == 0:
            raise ValueError("qty_change must not be 0")
        return v


class TicketUpdate(BaseModel):
    """A change to record with write_ticket."""

    ticket_id: int
    status: Literal["open", "closed"]
    notes: str


class PaymentOrder(BaseModel):
    """What write_payments takes. The amount always comes from the invoice or lease, never from here."""

    kind: Literal["invoice", "rent"]
    ref_id: int
    ticket_id: int | None = None


class Approval(BaseModel):
    """A payment, purchase or customer message an agent has prepared and a human has yet to approve (or already decided)."""

    id: int
    kind: Literal["payment", "purchase", "message"]
    summary: str
    status: Literal["pending", "approved", "declined", "failed"]
    created_at: str
    decided_at: str | None = None
    decided_by: str | None = None
    result: dict[str, Any] | None = None  # the payment or invoice row (or approved message) once approved, or the failure reason


Approvals = _rows("Approvals", Approval)


# --- Messages to vendors --------------------------------------------------------


class VendorMessage(BaseModel):
    """A message to a vendor that is being drafted. Nothing is ever sent to a real vendor.

    Inventory or Accounting drafts it; only the Boss can mark it "approved" (after the
    sensitive-information check), the same private draft chat as customer messages.
    """

    vendor_id: int
    vendor_name: str
    drafted_by: Literal["Inventory", "Accounting"]
    ticket_id: int | None = None
    subject: str
    message: str
    status: Literal["draft", "approved", "needs_human"] = "draft"


# --- Customer-safe types ---------------------------------------------------------
# The only types that may be sent to, or requested by, Customer Service (enforced by delegate).

CustomerFacts = _rows("CustomerFacts", CustomerFacingInfo)


class CustomerTicketStatus(BaseModel):
    """The Boss's answer to 'what is the status of this customer's ticket?'. Nothing internal."""

    model_config = ConfigDict(extra="forbid")

    ticket_id: int
    status_summary: str  # customer-safe wording only, e.g. "being processed"
    lead_days: int | None = Field(default=None, ge=0)


class CustomerUpdateRequest(BaseModel):
    """The Boss asking Customer Service to draft an update for a customer."""

    model_config = ConfigDict(extra="forbid")

    ticket_id: int | None = None
    customer: str | None = None
    status_summary: str  # customer-safe wording only
    lead_days: int | None = Field(default=None, ge=0)


# --- Audit trail -------------------------------------------------------------


class AuditEntry(BaseModel):
    """One line of output/audit_trail.json (append-only).

    kind says what happened:
      received  - an agent was given a task or message (from_ = who sent it)
      tool_call - an agent used a tool (tool, arguments, returned, to)
      message   - an agent's final reply (message, to = who asked)
      status    - the Boss telling the user, in plain English, what is going on (message)
      approval  - a human decided on a payment or purchase (agent = "Human", message = what it was, returned = their decision)
      usage     - tokens and dollars an agent run used (counts toward the daily budget)
      budget_reset - a human gave permission to continue after the daily allowance was used (agent = "Human"); spending counts from here
      error     - a run stopped with an error (message)
    """

    model_config = ConfigDict(populate_by_name=True)

    time: str  # real clock time, ISO 8601 with offset
    run_id: str  # shared by every entry caused by one prompt
    agent: AgentName | Literal["Human"]
    kind: Literal["received", "tool_call", "message", "status", "approval", "usage", "budget_reset", "error"]
    step: int | None = None  # the agent's loop-step number within this run
    from_: str | None = Field(default=None, alias="from")
    to: str | None = None  # a teammate, the user, or the database
    tool: str | None = None
    arguments: dict[str, Any] | None = None
    returned: Any = None  # data a tool returned
    message: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    cached_tokens: int | None = None
    requests: int | None = None
    cost_usd: float | None = None


# --- Registry used by the delegate tool ---------------------------------------------

MESSAGE_TYPES: dict[str, type[BaseModel]] = {
    name: obj
    for name, obj in list(globals().items())
    if isinstance(obj, type) and issubclass(obj, BaseModel) and obj is not BaseModel and name != "AuditEntry"
}

# Messages to Customer Service, and anything Customer Service asks for, must be one of these.
# Each rejects fields it doesn't define (or holds only safe fields), so restricted data can't ride along.
CUSTOMER_SAFE_TYPES: frozenset[str] = frozenset(
    {"CustomerFacingInfo", "CustomerFacts", "CustomerTicketStatus", "CustomerUpdateRequest", "DraftReview"}
)
