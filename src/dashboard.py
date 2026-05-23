"""
Terminal dashboard — pretty-prints stats and recent activity.
"""

from datetime import datetime
from typing import Optional
import database


def _bar(value: int, total: int, width: int = 20, char: str = "█") -> str:
    if total == 0:
        return "─" * width
    filled = round(value / total * width)
    return char * filled + "░" * (width - filled)


def print_dashboard() -> None:
    stats = database.get_stats()
    recent_applied = database.get_jobs(status="applied", limit=5)
    recent_new     = database.get_jobs(status="new",     limit=5)

    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    print("\n" + "═" * 60)
    print(f"  🤖  JOB AUTOMATION DASHBOARD  —  {now}")
    print("═" * 60)

    total = stats["total_jobs_seen"] or 1
    print(f"\n  📊 Overview")
    print(f"     Jobs scanned   : {stats['total_jobs_seen']:>5}")
    print(f"     Applied        : {stats['total_applied']:>5}  {_bar(stats['total_applied'], total)}")
    print(f"     Interviews 🎉  : {stats['interviews']:>5}  {_bar(stats['interviews'], total)}")
    print(f"     Applied today  : {stats['applied_today']:>5}")
    print(f"     Queue (new)    : {stats['new_jobs']:>5}")

    if recent_applied:
        print(f"\n  ✅ Recently Applied")
        for j in recent_applied:
            score = j.get("match_score", 0)
            print(f"     [{score:3d}] {j['title'][:35]:<35} @ {(j['company'] or '?')[:20]}")

    if recent_new:
        print(f"\n  🔍 New Jobs (pending review)")
        for j in recent_new:
            score = j.get("match_score", 0)
            url   = j.get("apply_url", "")
            print(f"     [{score:3d}] {j['title'][:35]:<35}  {url[:40]}")

    print("\n" + "═" * 60 + "\n")


def print_cover_letter(job_id: str) -> None:
    """Print the cover letter generated for a specific job."""
    from database import get_connection
    with get_connection() as conn:
        row = conn.execute(
            "SELECT a.cover_letter, j.title, j.company "
            "FROM applications a JOIN jobs j ON a.job_id = j.id "
            "WHERE a.job_id = ? ORDER BY a.id DESC LIMIT 1",
            (job_id,)
        ).fetchone()

    if not row:
        print(f"No application found for job {job_id}")
        return

    print(f"\n── Cover Letter: {row['title']} @ {row['company']} ──\n")
    print(row["cover_letter"])
    print()
