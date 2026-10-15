"""Connects each agent to the MCP server, with only the tools its prompt allows.

One MCP connection (the campus-customs server over stdio) is shared by all
agents; each agent sees a filtered view of it. The permissions below are the
same table as in output/harness.md.

Agents only PREPARE payments, purchases and customer messages (write_payments, write_invoices,
write_messages).
Cash and invoices change only when a person approves in the backend
(POST /api/approvals/{id}/approve), so nothing here can move money.
"""

from __future__ import annotations

import sys
from pathlib import Path

from fastmcp.client.transports import StdioTransport
from pydantic_ai.mcp import MCPToolset

ROOT = Path(__file__).resolve().parent.parent  # HW5/
SERVER_SCRIPT = ROOT / "mcp_server" / "server.py"
PYTHON = sys.executable  # the backend's own interpreter, so no machine-specific path is needed

# agent -> the only MCP tools it may use (delegate is added separately, for everyone)
PERMISSIONS: dict[str, frozenset[str]] = {
    "Boss": frozenset({"read_desk", "read_ticket", "write_ticket", "read_approvals", "write_messages"}),
    "Inventory": frozenset({"read_desk", "read_inventory", "write_inventory", "read_vendor", "read_invoices"}),
    "Accounting": frozenset(
        {
            "read_desk",
            "read_inventory",
            "read_invoices",
            "read_balance",
            "read_vendor",
            "read_pricing",
            "read_payments",
            "read_approvals",
            "write_invoices",
            "write_payments",
        }
    ),
    "Facilities": frozenset({"read_desk", "read_lease"}),
    "Customer Service": frozenset({"read_desk"}),
}

_toolset: MCPToolset | None = None


def _shared_toolset() -> MCPToolset:
    global _toolset
    if _toolset is None:
        transport = StdioTransport(command=PYTHON, args=[str(SERVER_SCRIPT)])
        _toolset = MCPToolset(transport, prefer_tasks=False)
    return _toolset


def toolset_for(agent_name: str):
    """The MCP tools this agent may use, and nothing else."""
    allowed = PERMISSIONS[agent_name]
    return _shared_toolset().filtered(lambda ctx, tool_def: tool_def.name in allowed)
