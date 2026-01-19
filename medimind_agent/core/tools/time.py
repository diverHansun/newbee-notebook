"""Current time tool for agents.

Provides a simple function tool that returns the current local date and time
in a concise, agent-friendly format.
"""

from __future__ import annotations

from datetime import datetime
from llama_index.core.tools import FunctionTool


def get_current_datetime() -> str:
    """Get the current local date and time.

    Returns a human-readable string like:
    "2026-01-17 15:04 local (UTC+0800)"
    """
    now = datetime.now().astimezone()
    return now.strftime("%Y-%m-%d %H:%M local (UTC%z)")


def build_current_time_tool() -> FunctionTool:
    """Build a FunctionTool for retrieving current date and time."""
    return FunctionTool.from_defaults(
        fn=get_current_datetime,
        name="get_current_datetime",
        description=(
            "Get the current local date and time in 'YYYY-MM-DD HH:MM' format. "
            "Use this whenever you need up-to-date time information."
        ),
    )

__all__ = ["get_current_datetime", "build_current_time_tool"]


