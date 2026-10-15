"""Runtime for the Campus Customs agent team.

Every agent (Boss, Inventory, Accounting, Facilities, Customer Service) gets
the `delegate` tool, so any agent can hand work to any other agent. Agents are
looked up by name at call time, so the agent modules never import each other.

Every run goes through `run_agent`, which writes each loop-step to the audit
trail (audit.py) and stops the whole team when the daily spending cap is hit.
Each agent's instructions come from its own file in prompts/ and nothing else.
"""

from __future__ import annotations

import asyncio
import importlib
import json
import os
import time
import typing
import uuid
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from openai import AsyncOpenAI
from pydantic import BaseModel, ValidationError
from pydantic_ai import Agent, RunContext
from pydantic_ai.exceptions import ModelAPIError, ModelHTTPError, UnexpectedModelBehavior, UsageLimitExceeded
from pydantic_ai.messages import RetryPromptPart, ToolCallPart, ToolReturnPart
from pydantic_ai.models.openai import OpenAIResponsesModel
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.usage import UsageLimits

import audit
from models import CUSTOMER_SAFE_TYPES, MESSAGE_TYPES, AgentName
from tools import toolset_for

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent  # HW5/
load_dotenv(ROOT / ".env")
load_dotenv(ROOT.parent / ".env")

# Every agent on the team ALWAYS uses this model. It is deliberately not read
# from the environment, so a stray PORTKEY_MODEL value can't change it.
MODEL_NAME = "gpt-6-luna"
PORTKEY_BASE_URL = os.getenv("PORTKEY_BASE_URL", "https://api.portkey.ai/v1").rstrip("/")

# Stops two agents from handing a task back and forth forever.
MAX_DELEGATION_DEPTH = 4
# Total handoffs (all agents combined) allowed in response to one prompt.
MAX_DELEGATIONS_PER_PROMPT = 20

# Check-in loop. `delegate` waits this long for a teammate, then hands the caller a progress report
# instead of a reply; the caller calls `check_in` to wait another round, or to give up.
CHECKIN_SECONDS = 60
MAX_CHECKINS = 8  # after this many check-ins on one task, it is stopped
QUIET_WARNING_SECONDS = 60  # a normal step takes under 30 s, so this long without activity is flagged as probably stuck
MAX_RUN_STEPS = 40  # model requests in one agent run, so a loop can't go on forever
HEARTBEAT_SECONDS = 2  # every working agent beats this often; the board shows it and flags a missed beat
MAX_KNOWN_CHARS = 8000  # most gathered facts one delegate call may carry
MODEL_TIMEOUT_SECONDS = 30  # one model call that takes longer than this is abandoned and retried (the gateway sometimes stalls)

# agent name -> (module name, prompt file)
ROSTER: dict[str, tuple[str, str]] = {
    "Boss": ("boss", "boss.md"),
    "Inventory": ("inventory", "inventory.md"),
    "Accounting": ("accounting", "accounting.md"),
    "Facilities": ("facilities", "facilities.md"),
    "Customer Service": ("customer_service", "customer_service.md"),
}
assert set(ROSTER) == set(typing.get_args(AgentName)), "ROSTER and models.AgentName are out of sync"

DB_NAME = "campus_customs_new.db"


@dataclass
class Pulse:
    """When a delegated task last showed any sign of life, and what it did lately.

    Activity by the teammate, or by anyone it asked in turn, counts for everyone above it,
    so a caller can tell "still busy" from "stuck" when it checks in.
    """

    parent: "Pulse | None" = None
    started: float = field(default_factory=time.monotonic)
    last: float = field(default_factory=time.monotonic)
    recent: deque[str] = field(default_factory=lambda: deque(maxlen=5))

    def touch(self, note: str | None = None) -> None:
        self.last = time.monotonic()
        if note:
            self.recent.append(note)
        if self.parent is not None:
            self.parent.touch(note)


@dataclass
class PendingTask:
    """A task this agent handed to a teammate that has not finished yet."""

    to_agent: str
    task: "asyncio.Task[str]"
    pulse: Pulse
    entry: dict[str, Any]
    reply_type: str | None
    restart: "typing.Callable[[], asyncio.Task[str]] | None" = None  # starts the same task again
    retried: bool = False  # a failed model call is retried automatically once
    checkins: int = 0


@dataclass
class Beat:
    """Liveness of one running agent: what it is doing now and when its heartbeat last ticked.

    A background task per run advances `last` every HEARTBEAT_SECONDS, so a fresh beat means the agent's
    process is alive even while it waits on the model service or a teammate. Live state only: not stored.
    """

    agent: str
    run_id: str
    started: float
    changed: float  # when `doing` last changed
    last: float  # last heartbeat tick
    doing: str = "starting"
    beats: int = 0

    def set(self, doing: str) -> None:
        if doing != self.doing:
            self.doing, self.changed = doing, time.monotonic()

    def note(self, doing: "typing.Callable[[], str]") -> None:
        """Set `doing` from a function; liveness reporting must never be able to break a run, so errors are dropped."""
        try:
            self.set(doing())
        except Exception:  # noqa: BLE001
            pass


HEARTBEATS: dict[int, Beat] = {}  # one entry per agent run in progress


def heartbeats() -> list[dict[str, Any]]:
    """What every running agent is doing right now, for GET /api/heartbeats."""
    now = time.monotonic()
    return [
        {
            "agent": b.agent,
            "run_id": b.run_id,
            "doing": b.doing,
            "seconds_running": round(now - b.started, 1),
            "seconds_in_step": round(now - b.changed, 1),
            "beat_age": round(now - b.last, 1),
            "beats": b.beats,
        }
        for b in list(HEARTBEATS.values())  # a copy: runs start and end while this is read
    ]


async def _tick(beat: Beat) -> None:
    while True:
        await asyncio.sleep(HEARTBEAT_SECONDS)
        beat.last = time.monotonic()
        beat.beats += 1


def _doing(parts: list[ToolCallPart]) -> str:
    """A few plain words for what a batch of tool calls is doing."""
    waits, tools = [], []
    for part in parts:
        args = _as_dict(part.args)
        if part.tool_name in ("delegate", "check_in") and args.get("to_agent"):
            waits.append(str(args["to_agent"]))
        elif part.tool_name != "status_update":
            tools.append(part.tool_name)
    out = []
    if waits:
        out.append("waiting for " + " and ".join(dict.fromkeys(waits)))
    if tools:
        out.append("using " + ", ".join(dict.fromkeys(tools)))
    return "; ".join(out) or "posting an update"


@dataclass
class TeamDeps:
    """Per-run context passed to every agent."""

    agent_name: str
    run_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])  # one id per prompt
    depth: int = 0
    trace: list[dict[str, Any]] = field(default_factory=list)  # shared across the whole prompt
    pulse: Pulse | None = None  # set when this run was started by a delegate call
    chain: tuple[str, ...] = ()  # the agents above this one, each waiting for its answer
    pending: dict[str, PendingTask] = field(default_factory=dict)  # teammates this agent is waiting on


def build_model(agent_name: str) -> OpenAIResponsesModel:
    """Build one agent's own model session on Portkey's OpenAI-compatible gateway.

    Every agent gets its own client and connection pool (never shared), and every request it makes is
    tagged with its name, so the gateway shows five separate sessions, one per agent.
    """
    api_key = os.getenv("PORTKEY_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("PORTKEY_API_KEY is not set. Add it to HW5/.env (see .env.example).")
    client = AsyncOpenAI(
        api_key=api_key,
        base_url=PORTKEY_BASE_URL,
        default_headers={
            "x-portkey-api-key": api_key,
            "x-portkey-metadata": json.dumps({"agent": agent_name, "project": "campus-customs-hw5"}),
        },
        max_retries=4,  # ride out brief gateway errors (500s, rate limits)
        timeout=MODEL_TIMEOUT_SECONDS,
    )
    return OpenAIResponsesModel(MODEL_NAME, provider=OpenAIProvider(openai_client=client))


async def status_update(ctx: RunContext[TeamDeps], message: str) -> str:
    """Tell the person watching the board, in plain English, what is going on right now.

    Write one or two short sentences as you would to a shop owner: what you are doing or just
    learned, and what (if anything) they need to do. No ticket jargon, ids, JSON or tool names.

    Args:
        message: The update, at most about 300 characters.
    """
    text = " ".join(message.split())
    if not text:
        return "Nothing to post. Write a short plain-English update."
    me = ctx.deps
    audit.append(run_id=me.run_id, agent=me.agent_name, kind="status", message=text[:400], to="user")
    if me.pulse is not None:
        me.pulse.touch()
    return "Posted to the user."


def build_agent(name: str) -> Agent[TeamDeps, str]:
    """Build one team member from its own prompt file, the delegate tool, and its allowed MCP tools."""
    instructions = (HERE / "prompts" / ROSTER[name][1]).read_text(encoding="utf-8")
    return Agent(
        build_model(name),
        deps_type=TeamDeps,
        instructions=instructions,
        output_type=str,
        retries=3,  # room to fix a typed reply or a tool call that fails validation
        tools=[delegate, check_in, *([status_update] if name == "Boss" else [])],
        toolsets=[toolset_for(name)],
    )


def get_agent(name: str) -> Agent[TeamDeps, str]:
    """Return the named agent (built once, on first use)."""
    return importlib.import_module(ROSTER[name][0]).get_agent()


def _destination(tool: str, args: dict[str, Any]) -> str:
    """Who or what a tool call goes to, for the audit trail."""
    return str(args.get("to_agent")) if tool in ("delegate", "check_in") else DB_NAME


def _as_dict(args: Any) -> dict[str, Any]:
    if isinstance(args, dict):
        return args
    try:
        return json.loads(args) if isinstance(args, str) else {}
    except ValueError:
        return {}


async def run_agent(
    name: str, task: str, deps: TeamDeps, sender: str = "user", output_type: type[BaseModel] | None = None
) -> str:
    """Run one agent on a task, logging every loop-step. Returns its reply.

    With output_type, the agent must answer with a valid object of that type (it is
    asked to fix an invalid one), and the reply is that object as JSON.

    Raises audit.BudgetExceeded when the daily cap is reached (checked before the
    run and after every step), which stops the whole team.
    """
    agent = get_agent(name)
    pulse = deps.pulse

    def log(**fields: Any) -> None:
        audit.append(run_id=deps.run_id, agent=name, **fields)
        if pulse is not None:  # any logged activity counts as a sign of life for whoever is waiting
            pulse.touch(_note(name, fields))

    audit.check_budget()
    log(kind="received", from_=sender, message=task)

    now = time.monotonic()
    beat = Beat(name, deps.run_id, started=now, changed=now, last=now)
    HEARTBEATS[id(beat)] = beat
    ticker = asyncio.create_task(_tick(beat))

    calls: dict[str, ToolCallPart] = {}
    step = 0
    run = None
    try:
        async with agent.iter(
            task, deps=deps, output_type=output_type, usage_limits=UsageLimits(request_limit=MAX_RUN_STEPS)
        ) as run:
            async for node in run:
                if pulse is not None:
                    pulse.touch()
                u = run.usage
                audit.check_budget(audit.price(u.input_tokens, u.output_tokens, u.cache_read_tokens))
                if Agent.is_call_tools_node(node):
                    step += 1
                    tool_parts = [p for p in node.model_response.parts if isinstance(p, ToolCallPart)]
                    for part in tool_parts:
                        calls[part.tool_call_id] = part
                    beat.note(lambda: _doing(tool_parts) if tool_parts else "writing its answer")
                elif Agent.is_model_request_node(node):
                    beat.note(lambda: "waiting for the model")
                    for part in node.request.parts:
                        if isinstance(part, ToolReturnPart | RetryPromptPart):
                            call = calls.pop(part.tool_call_id, None)
                            tool = part.tool_name or (call.tool_name if call else "unknown")
                            args = _as_dict(call.args) if call else {}
                            returned = part.content if isinstance(part, ToolReturnPart) else f"ERROR: {part.content}"
                            log(
                                kind="tool_call",
                                step=step,
                                tool=tool,
                                arguments=args,
                                returned=returned,
                                to=_destination(tool, args),
                            )
        output = run.result.output
        reply = output.model_dump_json() if isinstance(output, BaseModel) else str(output).strip()
        log(kind="message", step=step, message=reply, to=sender)
        return reply
    except asyncio.CancelledError:  # the caller finished or gave up; this is a normal stop, not an error
        log(kind="message", step=step, message="(stopped: the agent that asked for this finished or stopped waiting)", to=sender)
        raise
    except Exception as exc:
        log(kind="error", step=step, message=f"{type(exc).__name__}: {exc}")
        raise
    finally:
        ticker.cancel()
        HEARTBEATS.pop(id(beat), None)
        _cancel_pending(deps)  # never leave a teammate running after this agent is done
        if run is not None:
            u = run.usage
            log(
                kind="usage",
                input_tokens=u.input_tokens,
                output_tokens=u.output_tokens,
                cached_tokens=u.cache_read_tokens,
                requests=u.requests,
                cost_usd=round(audit.price(u.input_tokens, u.output_tokens, u.cache_read_tokens), 6),
            )


def _note(agent: str, fields: dict[str, Any]) -> str | None:
    """A few words for a check-in report about what an agent just did."""
    kind = fields.get("kind")
    if kind == "received":
        return f"{agent} received a task from {fields.get('from_')}"
    if kind == "tool_call":
        return f"{agent} {'asked ' + str(fields.get('to')) if fields.get('tool') == 'delegate' else 'used ' + str(fields.get('tool'))}"
    if kind == "message":
        return f"{agent} replied to {fields.get('to')}"
    if kind == "error":
        return f"{agent} hit an error"
    return None


def _cancel_pending(deps: TeamDeps) -> None:
    for p in deps.pending.values():
        if not p.task.done():
            p.task.cancel()
        else:  # retrieve any exception so nothing is reported as "never retrieved"
            p.task.exception() if not p.task.cancelled() else None
    deps.pending.clear()


async def delegate(
    ctx: RunContext[TeamDeps],
    to_agent: str,
    task: str,
    payload_type: str | None = None,
    payload: dict[str, Any] | None = None,
    reply_type: str | None = None,
    known: str | None = None,
) -> str:
    """Hand a task to another agent on the team and return their reply.

    Describe the task fully; the other agent can't see this conversation. Anything
    pulled from the database, or likely to be written into it, should travel as a
    validated type, not as free text.

    Args:
        to_agent: One of: Boss, Inventory, Accounting, Facilities, Customer Service.
        task: What you need, in plain words. Keep it short and free of restricted details when writing to Customer Service.
        payload_type: Name of the type of `payload` (sent together with `payload`). Types: @TYPES@
        payload: Data to send, as an object with that type's fields. It is checked before it is sent; if it is invalid you get the errors back so you can fix and resend.
        reply_type: Name of the type you need back (same list). The teammate's answer is checked against it and returned as JSON.
        known: Everything already gathered for this ticket that the teammate could need, copied in full (replies and tool results, not a summary), so they don't fetch it again. Not accepted for Customer Service.
    """
    me = ctx.deps
    if to_agent not in ROSTER:
        return f"Unknown agent '{to_agent}'. Choose one of: {', '.join(ROSTER)}."
    if to_agent == me.agent_name:
        return "You can't delegate to yourself; do the task or pick a teammate."
    if to_agent in me.chain:
        return (
            f"Refused: {to_agent} asked for your work and is waiting for your answer. Don't delegate to them; "
            "finish the task yourself and give your answer as your reply. If you truly can't, say what is missing in your reply."
        )
    if len(me.trace) >= MAX_DELEGATIONS_PER_PROMPT:
        return f"Communication limit ({MAX_DELEGATIONS_PER_PROMPT} delegations per prompt) reached. Report what is done and what is still open."
    if me.depth >= MAX_DELEGATION_DEPTH:
        return f"Delegation depth limit ({MAX_DELEGATION_DEPTH}) reached. Handle this yourself or report back."

    # Customer Service is the front door: it only gets, and only asks for, customer-safe types.
    safe = ", ".join(sorted(CUSTOMER_SAFE_TYPES))
    if to_agent == "Customer Service" and (payload_type not in CUSTOMER_SAFE_TYPES or payload is None):
        return f"Refused: anything sent to Customer Service must carry a payload of one of these types: {safe}."
    if me.agent_name == "Customer Service" and reply_type not in CUSTOMER_SAFE_TYPES:
        return f"Refused: Customer Service must set reply_type to one of: {safe}."

    if known is not None and known.strip():
        if to_agent == "Customer Service":
            return "Refused: don't send gathered facts to Customer Service; send a customer-safe payload instead."
        if len(known) > MAX_KNOWN_CHARS:
            return f"Not sent. `known` is {len(known)} characters; the limit is {MAX_KNOWN_CHARS}. Pass only the facts this teammate needs."

    # Check the payload before it is sent.
    if (payload_type is None) != (payload is None):
        return "Send payload_type and payload together, or neither."
    text = task
    if payload_type is not None:
        model = MESSAGE_TYPES.get(payload_type)
        if model is None:
            return f"Unknown payload_type '{payload_type}'. Choose one of: {', '.join(sorted(MESSAGE_TYPES))}."
        try:
            checked = model.model_validate(payload)
        except ValidationError as exc:
            problems = "; ".join(f"{'.'.join(map(str, e['loc'])) or 'payload'}: {e['msg']}" for e in exc.errors())
            return f"Not sent. Your payload isn't a valid {payload_type}: {problems}"
        text += f"\n\nPAYLOAD ({payload_type}): {checked.model_dump_json()}"
    reply_model = None
    if reply_type is not None:
        reply_model = MESSAGE_TYPES.get(reply_type)
        if reply_model is None:
            return f"Unknown reply_type '{reply_type}'. Choose one of: {', '.join(sorted(MESSAGE_TYPES))}."
        text += f"\n\nReply as a {reply_type}."
    if known is not None and known.strip():
        text += (
            "\n\nALREADY GATHERED FOR THIS TICKET (use as given; don't call a tool or ask a teammate for anything in it):\n"
            + known.strip()
        )

    # The same question to the same teammate is answered once per prompt: hand back the earlier reply.
    key = (to_agent, task, payload_type, json.dumps(payload, sort_keys=True, default=str), reply_type, (known or "").strip())
    for old in me.trace:
        if old.get("key") == key and old["reply"] is not None and not old.get("failed"):
            return f"You already asked {to_agent} exactly this, so it was not asked again. Their earlier reply:\n{old['reply']}"

    if to_agent in me.pending:
        return (
            f"You already have a task running with {to_agent}. Call check_in('{to_agent}') to see how it is going, "
            "or check_in with give_up=true to stop it. Don't send them the same task twice."
        )

    entry: dict[str, Any] = {
        "from": me.agent_name,
        "to": to_agent,
        "task": task,
        "payload_type": payload_type,
        "reply_type": reply_type,
        "reply": None,
        "key": key,
    }
    me.trace.append(entry)
    pulse = Pulse(parent=me.pulse)
    child = TeamDeps(
        agent_name=to_agent,
        run_id=me.run_id,
        depth=me.depth + 1,
        trace=me.trace,
        pulse=pulse,
        chain=(*me.chain, me.agent_name),
    )
    def start() -> "asyncio.Task[str]":
        return asyncio.create_task(run_agent(to_agent, text, child, sender=me.agent_name, output_type=reply_model))

    me.pending[to_agent] = PendingTask(to_agent, start(), pulse, entry, reply_type, restart=start)
    return await _wait(me, to_agent)


def _others(me: TeamDeps, skip: str | None = None) -> str:
    """One line naming the other teammates this agent is still waiting on, so none is forgotten."""
    now = time.monotonic()
    waiting = [
        f"{p.to_agent} ({_fmt(now - p.pulse.started)} so far, last activity {_fmt(now - p.pulse.last)} ago"
        + (", probably stuck: check in now" if now - p.pulse.last >= QUIET_WARNING_SECONDS else "")
        + ")"
        for name, p in me.pending.items()
        if name != skip
    ]
    return ("\n\nSTILL WAITING ON: " + "; ".join(waiting) + ". Check in on any that are quiet before doing anything else.") if waiting else ""


def _fmt(seconds: float) -> str:
    seconds = int(seconds)
    return f"{seconds // 60}m {seconds % 60:02d}s" if seconds >= 60 else f"{seconds}s"


async def _wait(me: TeamDeps, to_agent: str) -> str:
    """Wait one round for a teammate. Returns their reply, or a progress report if they are still working."""
    p = me.pending[to_agent]
    done, _ = await asyncio.wait({p.task}, timeout=CHECKIN_SECONDS)
    if done:
        try:
            p.entry["reply"] = p.task.result()
        except audit.BudgetExceeded:
            del me.pending[to_agent]
            raise  # the whole team stops
        except UnexpectedModelBehavior as exc:
            p.entry["reply"], p.entry["failed"] = f"{to_agent} couldn't produce a valid {p.reply_type}: {exc}", True
        except ModelAPIError as exc:  # the model service failed or timed out for this teammate
            if not p.retried and p.restart is not None:  # try the same task once more before bothering the caller
                p.retried = True
                p.pulse.touch(f"{to_agent} is retrying after a model timeout")
                p.task = p.restart()
                return await _wait(me, to_agent)
            status = f" (status {exc.status_code})" if isinstance(exc, ModelHTTPError) else " (it timed out)"
            p.entry["failed"] = True
            p.entry["reply"] = f"{to_agent} could not answer because the model service failed{status}, even after one automatic retry. Carry on without it and say so, or try once more with a simpler task."
        except UsageLimitExceeded:
            p.entry["failed"] = True
            p.entry["reply"] = f"{to_agent} stopped after too many steps without finishing. Try a simpler, more specific task, or carry on without it."
        me.pending.pop(to_agent, None)
        return p.entry["reply"] + _others(me)

    p.checkins += 1
    if p.checkins >= MAX_CHECKINS:
        return await _stop(me, to_agent, f"It was still not done after {MAX_CHECKINS} check-ins, so it was stopped.")
    elapsed = time.monotonic() - p.pulse.started
    quiet = time.monotonic() - p.pulse.last
    recent = "; ".join(p.pulse.recent) or "nothing yet"
    stuck = " It has shown no activity for a while and may be stuck." if quiet >= QUIET_WARNING_SECONDS else ""
    return (
        f"CHECK-IN {p.checkins} of {MAX_CHECKINS}: {to_agent} is still working on your task "
        f"({_fmt(elapsed)} so far; last activity {_fmt(quiet)} ago).{stuck} Recent steps: {recent}. "
        f"Call check_in('{to_agent}') to wait another round, or check_in('{to_agent}', give_up=true) to stop it. "
        "If there is no activity across two check-ins, give up and either re-send a simpler, more specific task once, "
        "or carry on without them and say so." + _others(me, skip=to_agent)
    )


async def _stop(me: TeamDeps, to_agent: str, why: str) -> str:
    p = me.pending.pop(to_agent)
    p.task.cancel()
    await asyncio.gather(p.task, return_exceptions=True)  # let it log that it stopped
    p.entry["reply"], p.entry["failed"] = f"(stopped: {why})", True
    return (
        f"Stopped {to_agent}'s task. {why} Carry on without it, retry once with a simpler, more specific task, "
        "or report the problem to the Boss (or a human)." + _others(me)
    )


async def check_in(ctx: RunContext[TeamDeps], to_agent: str, give_up: bool = False) -> str:
    """Check on a teammate you handed a task to that is taking a while.

    `delegate` waits about a minute and then returns a CHECK-IN report instead of a reply when the
    teammate isn't finished. Call this to wait another round (you get their reply as soon as it is
    ready, or another progress report), or set give_up to stop the task and carry on without it.

    Args:
        to_agent: The teammate you are waiting on.
        give_up: True to stop their task now.
    """
    me = ctx.deps
    if to_agent not in me.pending:
        return f"You have no task running with {to_agent}."
    if give_up:
        return await _stop(me, to_agent, "You gave up waiting for it.")
    return await _wait(me, to_agent)


delegate.__doc__ = delegate.__doc__.replace("@TYPES@", ", ".join(sorted(MESSAGE_TYPES)))


async def run_team(agent_name: str, prompt: str, sender: str = "user") -> str:
    """Entry point: send a prompt to one agent (usually Boss) and run the whole team."""
    return await run_agent(agent_name, prompt, TeamDeps(agent_name=agent_name), sender=sender)
