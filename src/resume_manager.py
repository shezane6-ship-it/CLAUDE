"""
Fetches and caches the user's resume via MCP tool.
Falls back to a local resume.txt if the MCP tool is unavailable.
"""

import logging
from pathlib import Path
from typing import Optional

import database
from config import DATA_DIR

logger = logging.getLogger(__name__)

LOCAL_RESUME_PATH = DATA_DIR / "resume.txt"


class ResumeManager:
    """
    Usage:
        rm = ResumeManager(mcp_get_resume_fn)
        resume_text = rm.get()
    """

    def __init__(self, mcp_get_resume_fn=None):
        """
        mcp_get_resume_fn: async callable that returns the resume text from MCP.
        If None, falls back to local file / cache.
        """
        self._mcp_fn = mcp_get_resume_fn

    def get(self, force_refresh: bool = False) -> str:
        """Return the resume as plain text, using cache when possible."""
        if not force_refresh:
            cached = database.get_cached_resume()
            if cached:
                logger.debug("Using cached resume.")
                return cached

        # Try MCP tool first
        if self._mcp_fn is not None:
            try:
                resume = self._mcp_fn()
                if resume:
                    database.cache_resume(resume)
                    logger.info("Resume loaded from MCP tool.")
                    return resume
            except Exception as exc:
                logger.warning(f"MCP resume fetch failed: {exc}")

        # Fallback: local file
        if LOCAL_RESUME_PATH.exists():
            resume = LOCAL_RESUME_PATH.read_text(encoding="utf-8")
            database.cache_resume(resume)
            logger.info("Resume loaded from local file.")
            return resume

        raise FileNotFoundError(
            "No resume found. Either:\n"
            "  1. Make sure the MCP resume tool is connected, OR\n"
            f"  2. Place your resume at {LOCAL_RESUME_PATH}"
        )

    def summary(self) -> str:
        """Return a condensed version of the resume (first 1500 chars)."""
        full = self.get()
        if len(full) <= 1500:
            return full
        return full[:1500] + "\n...[truncated]"
