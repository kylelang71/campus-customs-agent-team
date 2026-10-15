"""Campus Customs backend (FastAPI).

Run from this folder:   uvicorn main:app --reload --port 8000

Routes
  GET  /api/tickets                 every ticket, open or resolved, and whether the team is working it
  GET  /api/tickets/{id}
  POST /api/tickets/{id}/run        run the agent team (Boss first) on one ticket, in the background
  GET  /api/runs                    every run started since the backend started (run id, ticket, status)
  GET  /api/runs/{run_id}           whether that run is still going, and how it ended
  GET  /api/events                  recent agent events (what each agent did, said, and which tools)
  GET  /api/heartbeats              what each running agent is doing now, and its last heartbeat (live only)
  GET  /api/balance                 current checking balance
  GET  /api/budget                  today's token allowance (limit, spent, percent, paused)
  POST /api/budget/reset            a person allows the team to continue; starts a fresh allowance
  GET  /api/approvals               payments, purchases and customer messages the agents prepared (?status=pending)
  POST /api/approvals/{id}/approve  a human approves; this is what actually changes cash
  POST /api/approvals/{id}/decline  a human declines

Resetting the database for a fresh run is a function, not a route: db.reset_database()
(or `python db.py reset`).
"""

from __future__ import annotations

import asyncio
import re
import sys
import uuid
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "mcp_server"))  # approvals.py is shared with the MCP server

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator

import approvals
import audit
import db
import team

app = FastAPI(title="Campus Customs backend")
# The board is the Vite page at http://localhost:5173. Browsers only let it call these routes
# because this allows exactly that origin (and nothing else). Run this on localhost only.
BOARD_ORIGIN = "http://localhost:5173"
app.add_middleware(
    CORSMiddleware,
    allow_origins=[BOARD_ORIGIN],
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type"],
)

# runs started through POST /api/tickets/{id}/run (the audit trail is the permanent record; see _restore_runs)
RUNS: dict[str, dict[str, Any]] = {}


def _restore_runs() -> None:
    """Rebuild the finished runs since the last database reset from the audit trail, so a backend restart
    or code reload doesn't make a ticket that was worked look untouched. A run that was still going when the
    backend stopped is shown as failed (it died with the process). With no recorded reset, nothing is restored."""
    since = db.last_reset()
    if since is None:
        return
    try:
        entries = audit.read_all()
    except audit.AuditError:
        return
    by_run: dict[str, list[dict[str, Any]]] = {}
    for e in entries:
        if e.get("time", "") >= since and not str(e.get("run_id", "")).startswith("approval-"):
            by_run.setdefault(e["run_id"], []).append(e)
    for run_id, es in by_run.items():
        first = es[0]
        m = re.match(r"Work ticket (\d+)", str(first.get("message", "")))
        if not (first.get("kind") == "received" and first.get("agent") == "Boss" and first.get("from") == "user" and m):
            continue
        run: dict[str, Any] = {"run_id": run_id, "ticket_id": int(m.group(1)), "status": "error", "result": None, "error": None}
        final = next((e for e in reversed(es) if e["agent"] == "Boss" and e["kind"] == "message" and e.get("to") == "user"), None)
        failure = next((e for e in reversed(es) if e["agent"] == "Boss" and e["kind"] == "error"), None)
        if final is not None:
            run["status"], run["result"] = "done", final.get("message")
        elif failure is not None:
            run["error"] = str(failure.get("message"))
        else:
            run["error"] = "The backend stopped or reloaded before this run finished."
        RUNS[run_id] = run


_restore_runs()


# --- tickets ---------------------------------------------------------------------------


def _ticket_view(row: dict[str, Any]) -> dict[str, Any]:
    running = any(r["ticket_id"] == row["id"] and r["status"] == "running" for r in RUNS.values())
    return {**row, "state": "resolved" if row["status"] == "closed" else "open", "team_working": running}


@app.get("/api/tickets")
def tickets() -> dict[str, Any]:
    rows = [_ticket_view(t) for t in db.list_tickets()]
    return {
        "tickets": rows,
        "open": sum(t["state"] == "open" for t in rows),
        "resolved": sum(t["state"] == "resolved" for t in rows),
    }


@app.get("/api/tickets/{ticket_id}")
def ticket(ticket_id: int) -> dict[str, Any]:
    row = db.get_ticket(ticket_id)
    if row is None:
        raise HTTPException(404, f"No ticket with id {ticket_id}")
    return _ticket_view(row)


async def _work_ticket(run_id: str, ticket_id: int) -> None:
    run = RUNS[run_id]
    prompt = (
        f"Work ticket {ticket_id}, and only ticket {ticket_id}. Read it with read_ticket; the other tickets are "
        "background and are not your assignment in this run. Keep the user informed with status_update, in plain "
        "English. Plan only the steps this ticket needs, and ask only "
        "the teammates it needs, one focused question each. If a payment or purchase is needed, run the payment "
        "review, have Accounting prepare it, and then stop: a human approves it in the dashboard. Prepare every payment or purchase the "
        "ticket needs even if cash can't cover it: a shortfall is stated in the plan, and the board blocks approving "
        "a payment the balance can't cover. A customer reply, "
        "once you have approved the draft, is prepared with write_messages and also waits for a human. Pass what each "
        "teammate told you to the next one in `known`, so nothing is fetched twice. Finish by "
        "reporting what was done and what is waiting on a human. Don't wait for or chase the approval, don't "
        "close the ticket while an approval is pending, and don't start work on any other ticket. If this ticket "
        f"already has a pending approval (read_approvals), just report that and stop."
    )
    try:
        deps = team.TeamDeps(agent_name="Boss", run_id=run_id)
        run["result"] = await team.run_agent("Boss", prompt, deps, sender="user")
        run["status"] = "done"
    except audit.BudgetExceeded as exc:
        run["status"], run["error"] = "stopped", str(exc)
    except Exception as exc:  # noqa: BLE001 - report to the caller instead of losing it in a background task
        run["status"], run["error"] = "error", f"{type(exc).__name__}: {exc}"


@app.post("/api/tickets/{ticket_id}/run", status_code=202)
async def run_ticket(ticket_id: int) -> dict[str, Any]:
    row = db.get_ticket(ticket_id)
    if row is None:
        raise HTTPException(404, f"No ticket with id {ticket_id}")
    if row["status"] == "closed":
        raise HTTPException(409, f"Ticket {ticket_id} is already resolved")
    if audit.budget_status()["paused"]:
        raise HTTPException(409, "The daily token allowance has been used. A person must allow the team to continue first.")
    busy = next((r for r in RUNS.values() if r["status"] == "running"), None)
    if busy is not None:  # the team works one ticket at a time
        raise HTTPException(409, f"The team is busy with ticket {busy['ticket_id']}. Wait for it to finish before starting another.")
    run_id = uuid.uuid4().hex[:12]
    RUNS[run_id] = {"run_id": run_id, "ticket_id": ticket_id, "status": "running", "result": None, "error": None}
    RUNS[run_id]["task"] = asyncio.create_task(_work_ticket(run_id, ticket_id))
    return {"run_id": run_id, "ticket_id": ticket_id, "status": "running"}


@app.get("/api/runs")
def list_runs() -> dict[str, Any]:
    """Every run started since the backend started, so the board can tie events to tickets."""
    return {"runs": [{k: v for k, v in r.items() if k != "task"} for r in RUNS.values()]}


@app.get("/api/runs/{run_id}")
def run_status(run_id: str) -> dict[str, Any]:
    run = RUNS.get(run_id)
    if run is None:
        raise HTTPException(404, f"No run with id {run_id}")
    return {k: v for k, v in run.items() if k != "task"}


# --- agent events ------------------------------------------------------------------------


def _describe(e: dict[str, Any]) -> str:
    who, kind = e.get("agent", "?"), e.get("kind")
    if kind == "received":
        return f"{who} received a task from {e.get('from')}"
    if kind == "tool_call":
        if e.get("tool") == "delegate":
            return f"{who} delegated to {e.get('to')}"
        return f"{who} used {e.get('tool')} ({e.get('to')})"
    if kind == "message":
        return f"{who} replied to {e.get('to')}"
    if kind == "approval":
        return f"{e.get('returned')}: {e.get('message')}"
    if kind == "status":
        return f"{who} to you: {e.get('message')}"
    if kind == "budget_reset":
        return str(e.get("message"))
    if kind == "usage":
        return f"{who} used {e.get('input_tokens')} input and {e.get('output_tokens')} output tokens (${e.get('cost_usd')})"
    return f"{who}: {e.get('message')}"


@app.get("/api/events")
def events(
    after: int | None = Query(None, ge=0, description="return events from this index on (use the previous 'next')"),
    limit: int = Query(200, ge=1, le=1000),
    run_id: str | None = None,
    agent: str | None = None,
    include_usage: bool = False,
) -> dict[str, Any]:
    """What each agent did, said, and which tools it used. Poll with after=<next> to refresh."""
    rows = audit.read_all()
    start = after if after is not None else max(len(rows) - limit, 0)
    window = rows[start : start + limit]
    out = []
    for offset, e in enumerate(window):
        if run_id and e.get("run_id") != run_id:
            continue
        if agent and e.get("agent") != agent:
            continue
        if e.get("kind") == "usage" and not include_usage:
            continue
        out.append({"index": start + offset, "summary": _describe(e), **e})
    return {"events": out, "next": start + len(window), "total": len(rows)}


# --- cash --------------------------------------------------------------------------------


@app.get("/api/heartbeats")
async def get_heartbeats() -> dict[str, Any]:
    """What each running agent is doing right now, and how long since its last heartbeat (live only, not stored)."""
    return {"interval": team.HEARTBEAT_SECONDS, "agents": team.heartbeats()}


@app.get("/api/balance")
def balance() -> dict[str, Any]:
    return db.checking_balance()


class Decision(BaseModel):
    name: str = Field(min_length=1, max_length=100, description="the person approving or declining")

    @field_validator("name")
    @classmethod
    def _not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("a name is required")
        return v.strip()


# --- daily token allowance ----------------------------------------------------------------


@app.get("/api/budget")
def budget() -> dict[str, Any]:
    """Today's token allowance: limit, spent, remaining, percent, and whether the team is paused."""
    return audit.budget_status()


@app.post("/api/budget/reset")
def reset_budget(body: Decision) -> dict[str, Any]:
    """A person gives permission to continue after the allowance was used. Starts a fresh allowance."""
    return audit.reset_allowance(body.name)


# --- approvals ---------------------------------------------------------------------------


@app.get("/api/approvals")
def list_approvals(status: str | None = Query(None, pattern="^(pending|approved|declined|failed)$")) -> dict[str, Any]:
    return {"approvals": approvals.list_approvals(db.WORKING_DB, status)}


def _decide(approval_id: int, approve: bool, name: str) -> dict[str, Any]:
    try:
        result = approvals.decide(db.WORKING_DB, approval_id, approve, name)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from None
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from None
    warning = None
    try:
        audit.append(
            run_id=f"approval-{approval_id}",
            agent="Human",
            kind="approval",
            message=result["summary"],
            returned=f"{result['status']} by {name}",
            to=db.WORKING_DB.name,
        )
    except audit.AuditError as exc:  # the decision already happened; don't hide it
        warning = f"Decision recorded but not written to the audit trail: {exc}"
    return {**result, "audit_warning": warning} if warning else result


@app.post("/api/approvals/{approval_id}/approve")
def approve(approval_id: int, body: Decision) -> dict[str, Any]:
    """A human clicked approve. This is the only thing that changes cash."""
    result = _decide(approval_id, True, body.name)
    if result["status"] == "failed":
        raise HTTPException(409, result["result"]["error"])
    return result


@app.post("/api/approvals/{approval_id}/decline")
def decline(approval_id: int, body: Decision) -> dict[str, Any]:
    return _decide(approval_id, False, body.name)
