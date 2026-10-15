"""Customer Service agent."""

from __future__ import annotations

from functools import cache

from pydantic_ai import Agent

from team import TeamDeps, build_agent

NAME = "Customer Service"


@cache
def get_agent() -> Agent[TeamDeps, str]:
    """Lazy singleton so importing this module never requires an API key."""
    return build_agent(NAME)
