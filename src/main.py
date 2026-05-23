#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════╗
║           JOB AUTOMATION BOT  —  main.py                ║
║  Powered by Claude AI + Indeed via MCP tools             ║
╚══════════════════════════════════════════════════════════╝

Modes
-----
  python src/main.py              → run once (great for testing)
  python src/main.py --loop       → run every N hours (24/7 mode)
  python src/main.py --dashboard  → show stats only
  python src/main.py --cover <id> → print cover letter for job <id>
  python src/main.py --setup      → interactive first-time setup
"""

import argparse
import logging
import os
import sys
import time
from pathlib import Path

# ── Path setup (so imports work from repo root or src/) ──────────────────────
SRC_DIR = Path(__file__).parent
sys.path.insert(0, str(SRC_DIR))

import database
import dashboard as dash
from config import load_config, save_config, LOGS_DIR
from resume_manager import ResumeManager
from job_searcher import JobSearcher
from job_analyzer import JobAnalyzer
from application_bot import ApplicationBot
from notifier import Notifier

# ── Logging ───────────────────────────────────────────────────────────────────
LOGS_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    handlers=[
        logging.FileHandler(LOGS_DIR / "automation.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("main")


# ── Claude client (optional — degrades gracefully) ────────────────────────────
def _build_claude_client(config: dict):
    api_key_env = config["claude"]["api_key_env"]
    api_key = os.environ.get(api_key_env, "")
    if not api_key:
        logger.warning(
            f"No Anthropic API key found in env var '{api_key_env}'. "
            "AI scoring/cover letters disabled — using heuristic fallback."
        )
        return None
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        logger.info("Claude AI client initialized ✓")
        return client
    except ImportError:
        logger.warning("anthropic package not installed — AI features disabled.")
        return None


# ── MCP tool stubs (real MCP calls injected by Claude Code env) ───────────────
def _mcp_search_jobs(search, location, country_code, job_type=None):
    """
    Bridge to the Indeed MCP search_jobs tool.
    In production, Claude Code injects the real MCP implementation.
    Falls back to a mock for unit-testing without MCP.
    """
    # Dynamically import the MCP bridge if available
    try:
        from mcp_bridge import search_jobs as _real
        return _real(search=search, location=location,
                     country_code=country_code, job_type=job_type)
    except ImportError:
        pass

    logger.warning("MCP bridge not available — returning mock data.")
    return _mock_search_results(search, location)


def _mcp_get_job_details(job_id: str):
    try:
        from mcp_bridge import get_job_details as _real
        return _real(job_id=job_id)
    except ImportError:
        return {"id": job_id, "description": "Details unavailable (no MCP bridge)."}


def _mcp_get_resume():
    try:
        from mcp_bridge import get_resume as _real
        return _real()
    except ImportError:
        return None


def _mock_search_results(keyword: str, location: str) -> str:
    """Returns fake markdown results so the system can be tested offline."""
    return (
        f"## Jobs for '{keyword}' in {location}\n\n"
        "1. [Senior Python Developer](https://www.indeed.com/viewjob?jk=abc123def456) "
        "at Acme Corp — Remote — $90k-$120k\n\n"
        "2. [Backend Engineer](https://www.indeed.com/viewjob?jk=def789ghi012) "
        "at StartupXYZ — Paris — €55k-€75k\n\n"
        "3. [Python Software Engineer](https://www.indeed.com/viewjob?jk=ghi345jkl678) "
        "at TechCorp — Remote — Competitive salary\n"
    )


# ── Core automation loop ──────────────────────────────────────────────────────

def run_once(config: dict) -> dict:
    """Execute one full search → analyze → apply cycle. Returns summary dict."""
    logger.info("=" * 55)
    logger.info("  Starting automation cycle…")
    logger.info("=" * 55)

    claude_client  = _build_claude_client(config)
    notifier       = Notifier(config)
    resume_mgr     = ResumeManager(mcp_get_resume_fn=_mcp_get_resume)
    searcher       = JobSearcher(_mcp_search_jobs, _mcp_get_job_details)
    analyzer       = JobAnalyzer(claude_client, config)
    bot            = ApplicationBot(analyzer, resume_mgr)

    # 1. Search
    jobs = searcher.search_all()

    # 2. Process each job
    results = {"applied": 0, "ignored": 0, "deferred": 0, "skipped": 0, "errors": 0}

    for job in jobs:
        try:
            outcome = bot.process_job(job)
            action  = outcome.get("action", "error")
            results[action] = results.get(action, 0) + 1

            if action == "applied":
                msg = (
                    f"Applied to {job.get('title')} @ {job.get('company')}\n"
                    f"Score: {outcome.get('score', '?')}/100\n"
                    f"Method: {outcome.get('method','?')}"
                )
                notifier.send("✅ New Application", msg)

            if action == "deferred" and outcome.get("reason") == "daily cap":
                logger.warning("Daily cap reached — stopping cycle early.")
                break
        except Exception as exc:
            logger.error(f"Error processing job {job.get('id','?')}: {exc}", exc_info=True)
            results["errors"] += 1

    # 3. Summary
    logger.info(
        f"Cycle complete — Applied: {results['applied']} | "
        f"Ignored: {results['ignored']} | "
        f"Deferred: {results['deferred']} | "
        f"Errors: {results['errors']}"
    )
    dash.print_dashboard()
    return results


def run_loop(config: dict) -> None:
    """Run forever, sleeping between cycles as configured."""
    interval_hours = config["search"]["search_interval_hours"]
    interval_secs  = interval_hours * 3600
    logger.info(f"Loop mode: running every {interval_hours}h")

    while True:
        try:
            run_once(config)
        except KeyboardInterrupt:
            logger.info("Interrupted by user — shutting down.")
            break
        except Exception as exc:
            logger.error(f"Unhandled error in cycle: {exc}", exc_info=True)

        logger.info(f"Sleeping {interval_hours}h until next cycle…")
        try:
            time.sleep(interval_secs)
        except KeyboardInterrupt:
            logger.info("Interrupted during sleep — shutting down.")
            break


# ── Interactive setup ─────────────────────────────────────────────────────────

def interactive_setup() -> None:
    """Guided first-time configuration."""
    print("\n" + "=" * 55)
    print("  🤖  Job Automation Bot — First-Time Setup")
    print("=" * 55)
    config = load_config()

    def ask(prompt: str, default: str = "") -> str:
        val = input(f"  {prompt} [{default}]: ").strip()
        return val if val else default

    print("\n── Job Search ────────────────────────────────────────")
    kw_input = ask("Job keywords (comma-separated)",
                   ", ".join(config["search"]["keywords"]))
    config["search"]["keywords"] = [k.strip() for k in kw_input.split(",")]
    config["search"]["location"]     = ask("Location (city or 'remote')",
                                           config["search"]["location"])
    config["search"]["country_code"] = ask("Country code (e.g. FR, US, GB)",
                                           config["search"]["country_code"])
    config["search"]["min_match_score"] = int(
        ask("Minimum match score (0-100)", str(config["search"]["min_match_score"]))
    )

    print("\n── Application ───────────────────────────────────────")
    config["application"]["max_applications_per_day"] = int(
        ask("Max applications per day",
            str(config["application"]["max_applications_per_day"]))
    )

    print("\n── Claude AI ─────────────────────────────────────────")
    print(f"  Set ANTHROPIC_API_KEY env var for AI-powered scoring.")
    print(f"  Get your key at: https://console.anthropic.com/")

    save_config(config)
    print("\n  ✅ Config saved to data/config.json")
    print("  Run: python src/main.py        (single run)")
    print("  Run: python src/main.py --loop (24/7 mode)\n")


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Job Automation Bot — powered by Claude AI + Indeed"
    )
    parser.add_argument("--loop",      action="store_true", help="Run 24/7 loop")
    parser.add_argument("--dashboard", action="store_true", help="Show dashboard only")
    parser.add_argument("--cover",     metavar="JOB_ID",   help="Print cover letter")
    parser.add_argument("--setup",     action="store_true", help="Interactive setup")
    args = parser.parse_args()

    database.init_db()

    if args.setup:
        interactive_setup()
        return

    if args.dashboard:
        dash.print_dashboard()
        return

    if args.cover:
        dash.print_cover_letter(args.cover)
        return

    config = load_config()

    if args.loop:
        run_loop(config)
    else:
        run_once(config)


if __name__ == "__main__":
    main()
