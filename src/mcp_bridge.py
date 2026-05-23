"""
MCP Bridge — connects the Python automation code to the Claude Code MCP tools.

This file is auto-executed by Claude Code when the MCP tools are available.
In standalone mode (no Claude Code), it raises ImportError, and main.py
gracefully falls back to mock data.

Usage (from inside Claude Code):
    from mcp_bridge import search_jobs, get_job_details, get_resume
"""

# These symbols are injected by the Claude Code harness at runtime.
# If you're running outside Claude Code, mock them yourself:
#
#   import mcp_bridge
#   mcp_bridge.search_jobs = my_mock_fn
#

import logging
logger = logging.getLogger(__name__)


def search_jobs(search: str, location: str, country_code: str, job_type=None) -> str:
    """
    Calls the Indeed MCP search_jobs tool.
    Raises ImportError if not running inside Claude Code.
    """
    raise ImportError(
        "MCP bridge: search_jobs is not yet wired to a live MCP runtime.\n"
        "When running via Claude Code web/CLI, replace this with the real call.\n"
        "See README.md for instructions."
    )


def get_job_details(job_id: str) -> str:
    raise ImportError("MCP bridge: get_job_details not wired.")


def get_resume() -> str:
    raise ImportError("MCP bridge: get_resume not wired.")
