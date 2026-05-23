"""
Application bot — decides whether and how to apply, then does it.
"""

import logging
import smtplib
import webbrowser
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

import database
from config import load_config

logger = logging.getLogger(__name__)


class ApplicationBot:
    """
    Usage:
        bot = ApplicationBot(analyzer, resume_manager)
        bot.process_job(job)
    """

    def __init__(self, analyzer, resume_manager):
        self._analyzer = analyzer
        self._resume  = resume_manager
        self._config  = load_config()

    # ── Public ─────────────────────────────────────────────────────────────────

    def process_job(self, job: dict) -> dict:
        """
        Full pipeline for one job:
          1. Score fit
          2. Decide to apply
          3. Generate cover letter
          4. Apply (email / URL / manual)
          5. Record everything
        """
        job_id = job["id"]
        resume = self._resume.get()

        # Score
        analysis = self._analyzer.analyze(job, resume)
        score = analysis.get("match_score", 0)
        job["match_score"] = score

        # Save/update job record
        new_job = database.save_job(job)
        if not new_job:
            logger.debug(f"Job {job_id} already in DB — skipping.")
            return {"action": "skipped", "reason": "already seen"}

        logger.info(
            f"[{score:3d}] {job.get('title','?')} @ {job.get('company','?')} "
            f"— {analysis.get('reason','')}"
        )

        min_score = self._config["search"]["min_match_score"]
        if score < min_score:
            database.update_job_status(job_id, "ignored")
            return {"action": "ignored", "score": score}

        if not analysis.get("recommended_apply", True):
            database.update_job_status(job_id, "ignored")
            return {"action": "ignored", "reason": "AI not recommended"}

        # Daily cap check
        max_daily = self._config["application"]["max_applications_per_day"]
        if database.count_applications_today() >= max_daily:
            logger.warning("Daily application cap reached — stopping for today.")
            database.update_job_status(job_id, "reviewed")
            return {"action": "deferred", "reason": "daily cap"}

        # Generate cover letter
        cover_letter = self._analyzer.generate_cover_letter(job, resume, analysis)

        # Choose application method
        email_contact = analysis.get("email_contact")
        if email_contact and self._config["application"]["auto_apply_email"]:
            action = self._apply_by_email(job, cover_letter, email_contact)
        else:
            action = self._apply_by_url(job, cover_letter)

        database.save_application(
            job_id=job_id,
            method=action["method"],
            cover_letter=cover_letter,
            notes=str(analysis.get("reason", "")),
        )

        return {**action, "score": score, "cover_letter": cover_letter}

    def get_pending_for_review(self) -> list[dict]:
        """Return jobs ready to apply but waiting for manual confirmation."""
        return database.get_jobs(status="reviewed")

    # ── Private ────────────────────────────────────────────────────────────────

    def _apply_by_email(self, job: dict, cover_letter: str, to_email: str) -> dict:
        """Send an email application."""
        cfg = self._config["application"]
        sender = cfg.get("sender_email", "")
        password = cfg.get("sender_password", "")

        if not sender or not password:
            logger.warning("Email credentials not configured — falling back to URL apply.")
            return self._apply_by_url(job, cover_letter)

        subject = f"Application: {job.get('title','')} — {job.get('company','')}"
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = sender
        msg["To"]      = to_email

        body = f"{cover_letter}\n\n---\nApplied via Job Automation Bot • {datetime.utcnow().date()}"
        msg.attach(MIMEText(body, "plain", "utf-8"))

        try:
            with smtplib.SMTP(cfg["smtp_host"], cfg["smtp_port"]) as server:
                server.starttls()
                server.login(sender, password)
                server.sendmail(sender, to_email, msg.as_string())

            logger.info(f"✉  Email sent to {to_email} for {job.get('title')}")
            return {"action": "applied", "method": "email", "to": to_email}
        except Exception as exc:
            logger.error(f"Email send failed: {exc}")
            return self._apply_by_url(job, cover_letter)

    def _apply_by_url(self, job: dict, cover_letter: str) -> dict:
        """
        Open the Indeed apply link in the browser and save the cover letter
        to the clipboard / a local file so the user can paste it.
        """
        apply_url = job.get("apply_url", "")
        if apply_url:
            # Save cover letter to a temp file for easy copy-paste
            out_path = f"/tmp/cover_letter_{job['id']}.txt"
            try:
                with open(out_path, "w", encoding="utf-8") as f:
                    f.write(cover_letter)
                logger.info(f"Cover letter saved → {out_path}")
            except OSError:
                pass

            logger.info(f"🔗 Apply URL: {apply_url}")
            database.update_job_status(job["id"], "applied")
            return {"action": "applied", "method": "url", "url": apply_url}
        else:
            database.update_job_status(job["id"], "reviewed")
            return {"action": "reviewed", "method": "manual"}
