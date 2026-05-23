"""
Job search layer — wraps the Indeed MCP tools and applies local filters.
"""

import logging
import re
from typing import Optional
from config import load_config

logger = logging.getLogger(__name__)


class JobSearcher:
    """
    Usage:
        searcher = JobSearcher(
            search_jobs_fn=mcp_search_jobs,
            get_job_details_fn=mcp_get_job_details,
        )
        jobs = searcher.search_all()
    """

    def __init__(self, search_jobs_fn, get_job_details_fn):
        self._search = search_jobs_fn
        self._details = get_job_details_fn
        self._config = load_config()

    # ── Public ─────────────────────────────────────────────────────────────────

    def search_all(self) -> list[dict]:
        """Search all configured keywords and return de-duplicated job list."""
        search_cfg = self._config["search"]
        app_cfg    = self._config["application"]

        seen_ids: set[str] = set()
        results: list[dict] = []

        for keyword in search_cfg["keywords"]:
            logger.info(f"Searching: '{keyword}' @ {search_cfg['location']}")
            raw = self._search_keyword(keyword, search_cfg, app_cfg)
            for job in raw:
                if job["id"] not in seen_ids:
                    seen_ids.add(job["id"])
                    results.append(job)

        logger.info(f"Total unique jobs found: {len(results)}")
        return results

    def get_details(self, job_id: str) -> dict:
        """Fetch full job details from Indeed."""
        try:
            raw = self._details(job_id)
            return self._parse_job_details(raw, job_id)
        except Exception as exc:
            logger.warning(f"Could not fetch details for job {job_id}: {exc}")
            return {}

    # ── Private ────────────────────────────────────────────────────────────────

    def _search_keyword(self, keyword: str, search_cfg: dict, app_cfg: dict) -> list[dict]:
        try:
            raw = self._search(
                search=keyword,
                location=search_cfg["location"],
                country_code=search_cfg["country_code"],
                job_type=search_cfg.get("job_type"),
            )
            jobs = self._parse_search_results(raw)
            jobs = [j for j in jobs if self._passes_filters(j, app_cfg)]
            return jobs[: search_cfg.get("max_results_per_keyword", 20)]
        except Exception as exc:
            logger.error(f"Search failed for '{keyword}': {exc}")
            return []

    def _parse_search_results(self, raw) -> list[dict]:
        """
        Parse whatever the MCP tool returns (string or list) into a list of dicts.
        Indeed MCP returns a markdown string — we extract job IDs and metadata.
        """
        if isinstance(raw, list):
            return raw  # already parsed

        if not isinstance(raw, str):
            return []

        jobs = []
        # Extract job_id from Indeed apply links, e.g. jk=abc123
        for match in re.finditer(
            r"\[([^\]]+)\]\(https?://[^\)]*(?:jk=|jobs/view/)([a-f0-9]+)[^\)]*\)",
            raw, re.IGNORECASE
        ):
            title = match.group(1).strip()
            job_id = match.group(2)
            apply_url = re.search(
                rf"jk={re.escape(job_id)}[^\s\)\"]*", raw
            )
            jobs.append({
                "id": job_id,
                "title": title,
                "company": self._extract_after(raw, title, "company"),
                "location": "",
                "salary": "",
                "apply_url": apply_url.group(0) if apply_url else "",
                "description": "",
            })

        if not jobs:
            # Fallback: treat entire response as one "job" so we don't lose data
            logger.debug("Could not parse job list — storing raw response for review.")

        return jobs

    def _parse_job_details(self, raw, job_id: str) -> dict:
        """Parse detailed job response."""
        if isinstance(raw, dict):
            return raw

        if not isinstance(raw, str):
            return {"id": job_id, "description": str(raw)}

        result = {"id": job_id, "raw_details": raw}
        # Extract salary
        salary_match = re.search(r"\$[\d,]+(?:\s*[-–]\s*\$[\d,]+)?(?:\s*/\s*\w+)?", raw)
        if salary_match:
            result["salary"] = salary_match.group(0)
        return result

    @staticmethod
    def _extract_after(text: str, anchor: str, field: str) -> str:
        """Best-effort extraction of a field that appears near an anchor."""
        idx = text.find(anchor)
        if idx == -1:
            return ""
        snippet = text[idx: idx + 400]
        patterns = {
            "company": r"(?:at|chez|by)\s+([A-Z][^\n\|•]+?)(?:\n|\|)",
        }
        m = re.search(patterns.get(field, ""), snippet)
        return m.group(1).strip() if m else ""

    @staticmethod
    def _passes_filters(job: dict, app_cfg: dict) -> bool:
        """Return True if the job passes all configured filters."""
        title_desc = (job.get("title", "") + " " + job.get("description", "")).lower()

        # Blacklisted companies
        company = job.get("company", "").lower()
        for bl in app_cfg.get("blacklisted_companies", []):
            if bl.lower() in company:
                return False

        # Excluded keywords
        for kw in app_cfg.get("excluded_keywords", []):
            if kw.lower() in title_desc:
                return False

        return True
