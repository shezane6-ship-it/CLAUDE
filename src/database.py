"""
SQLite database layer — tracks jobs seen, applications sent, and cover letters generated.
"""

import sqlite3
import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from config import DATA_DIR


DB_PATH = DATA_DIR / "jobs.db"


def get_connection() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db() -> None:
    """Create tables if they don't exist yet."""
    with get_connection() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS jobs (
                id              TEXT PRIMARY KEY,
                title           TEXT NOT NULL,
                company         TEXT,
                location        TEXT,
                job_type        TEXT,
                salary          TEXT,
                description     TEXT,
                apply_url       TEXT,
                source          TEXT DEFAULT 'indeed',
                match_score     INTEGER DEFAULT 0,
                found_at        TEXT NOT NULL,
                status          TEXT DEFAULT 'new'
                                    CHECK(status IN ('new','reviewed','applied',
                                                     'interview','rejected','ignored'))
            );

            CREATE TABLE IF NOT EXISTS applications (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id          TEXT NOT NULL REFERENCES jobs(id),
                applied_at      TEXT NOT NULL,
                method          TEXT,          -- 'email' | 'url' | 'manual'
                cover_letter    TEXT,
                notes           TEXT
            );

            CREATE TABLE IF NOT EXISTS resume_cache (
                id              INTEGER PRIMARY KEY CHECK(id = 1),
                content         TEXT NOT NULL,
                cached_at       TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
            CREATE INDEX IF NOT EXISTS idx_jobs_found_at ON jobs(found_at);
        """)


# ── Job helpers ────────────────────────────────────────────────────────────────

def job_exists(job_id: str) -> bool:
    with get_connection() as conn:
        row = conn.execute("SELECT 1 FROM jobs WHERE id = ?", (job_id,)).fetchone()
    return row is not None


def save_job(job: dict) -> bool:
    """Insert a new job. Returns True if inserted, False if already exists."""
    if job_exists(job["id"]):
        return False
    with get_connection() as conn:
        conn.execute("""
            INSERT INTO jobs (id, title, company, location, job_type, salary,
                              description, apply_url, match_score, found_at, status)
            VALUES (:id, :title, :company, :location, :job_type, :salary,
                    :description, :apply_url, :match_score, :found_at, :status)
        """, {
            "id": job["id"],
            "title": job.get("title", ""),
            "company": job.get("company", ""),
            "location": job.get("location", ""),
            "job_type": job.get("job_type", ""),
            "salary": job.get("salary", ""),
            "description": job.get("description", ""),
            "apply_url": job.get("apply_url", ""),
            "match_score": job.get("match_score", 0),
            "found_at": datetime.utcnow().isoformat(),
            "status": "new",
        })
    return True


def update_job_status(job_id: str, status: str) -> None:
    with get_connection() as conn:
        conn.execute("UPDATE jobs SET status = ? WHERE id = ?", (status, job_id))


def get_jobs(status: Optional[str] = None, limit: int = 100) -> list[dict]:
    with get_connection() as conn:
        if status:
            rows = conn.execute(
                "SELECT * FROM jobs WHERE status = ? ORDER BY match_score DESC LIMIT ?",
                (status, limit)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM jobs ORDER BY match_score DESC, found_at DESC LIMIT ?",
                (limit,)
            ).fetchall()
    return [dict(r) for r in rows]


def count_applications_today() -> int:
    today = datetime.utcnow().date().isoformat()
    with get_connection() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS cnt FROM applications WHERE applied_at LIKE ?",
            (f"{today}%",)
        ).fetchone()
    return row["cnt"]


def save_application(job_id: str, method: str, cover_letter: str = "", notes: str = "") -> None:
    with get_connection() as conn:
        conn.execute("""
            INSERT INTO applications (job_id, applied_at, method, cover_letter, notes)
            VALUES (?, ?, ?, ?, ?)
        """, (job_id, datetime.utcnow().isoformat(), method, cover_letter, notes))
    update_job_status(job_id, "applied")


# ── Resume cache ───────────────────────────────────────────────────────────────

def get_cached_resume() -> Optional[str]:
    with get_connection() as conn:
        row = conn.execute("SELECT content FROM resume_cache WHERE id = 1").fetchone()
    return row["content"] if row else None


def cache_resume(content: str) -> None:
    with get_connection() as conn:
        conn.execute("""
            INSERT INTO resume_cache (id, content, cached_at)
            VALUES (1, ?, ?)
            ON CONFLICT(id) DO UPDATE SET content = excluded.content,
                                          cached_at = excluded.cached_at
        """, (content, datetime.utcnow().isoformat()))


# ── Stats ──────────────────────────────────────────────────────────────────────

def get_stats() -> dict:
    with get_connection() as conn:
        total     = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
        new       = conn.execute("SELECT COUNT(*) FROM jobs WHERE status='new'").fetchone()[0]
        applied   = conn.execute("SELECT COUNT(*) FROM jobs WHERE status='applied'").fetchone()[0]
        interview = conn.execute("SELECT COUNT(*) FROM jobs WHERE status='interview'").fetchone()[0]
        today_app = count_applications_today()
    return {
        "total_jobs_seen": total,
        "new_jobs": new,
        "total_applied": applied,
        "interviews": interview,
        "applied_today": today_app,
    }
