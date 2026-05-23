"""
AI-powered job analyzer — uses Claude to score job-resume fit and detect key info.
"""

import logging
import json
import re
from typing import Optional

logger = logging.getLogger(__name__)


SCORING_PROMPT = """You are a professional career coach and recruiter.

## Resume
{resume}

## Job Posting
Title: {title}
Company: {company}
Location: {location}
Description:
{description}

## Task
Analyze the fit between the candidate's resume and this job posting.

Return a JSON object (no markdown) with:
{{
  "match_score": <0-100 integer>,
  "strengths": ["...", "..."],
  "gaps": ["...", "..."],
  "email_contact": "<email if found in description, else null>",
  "recruiter_name": "<recruiter/hiring manager name if found, else null>",
  "key_requirements": ["...", "..."],
  "recommended_apply": <true|false>,
  "reason": "<one sentence summary>"
}}
"""

COVER_LETTER_PROMPT = """You are an expert career coach who writes compelling, concise cover letters.

## Candidate Resume
{resume}

## Job
Title: {title}
Company: {company}
Location: {location}
Key Requirements: {requirements}
Job Description (excerpt):
{description}

## Instructions
Write a {language} cover letter (max {max_words} words) that:
1. Opens with a strong hook specific to this company/role
2. Highlights 2-3 specific achievements from the resume that match the job
3. Explains why the candidate is excited about THIS company
4. Closes with a clear call to action

Return ONLY the cover letter text, no subject line, no "Dear Sir/Madam" template opener —
start directly with an engaging first sentence.
"""


class JobAnalyzer:
    """
    Usage:
        analyzer = JobAnalyzer(claude_client, config)
        result = analyzer.analyze(job, resume_text)
        letter = analyzer.generate_cover_letter(job, resume_text, analysis)
    """

    def __init__(self, claude_client, config: dict):
        self._client = claude_client
        self._config = config

    # ── Public ─────────────────────────────────────────────────────────────────

    def analyze(self, job: dict, resume: str) -> dict:
        """Score job-resume fit. Returns analysis dict."""
        if not self._client:
            return self._heuristic_score(job, resume)

        prompt = SCORING_PROMPT.format(
            resume=resume[:3000],
            title=job.get("title", "Unknown"),
            company=job.get("company", "Unknown"),
            location=job.get("location", ""),
            description=(job.get("description") or job.get("raw_details", ""))[:2000],
        )

        try:
            response = self._client.messages.create(
                model=self._config["claude"]["model"],
                max_tokens=512,
                messages=[{"role": "user", "content": prompt}],
            )
            text = response.content[0].text
            return json.loads(text)
        except json.JSONDecodeError:
            logger.warning("Claude returned invalid JSON for scoring — using heuristic.")
            return self._heuristic_score(job, resume)
        except Exception as exc:
            logger.error(f"Claude API error during analysis: {exc}")
            return self._heuristic_score(job, resume)

    def generate_cover_letter(
        self,
        job: dict,
        resume: str,
        analysis: Optional[dict] = None,
    ) -> str:
        """Generate a customized cover letter using Claude."""
        if not self._client:
            return self._template_cover_letter(job)

        lang_cfg = self._config["claude"]["cover_letter_language"]
        language = self._detect_language(job) if lang_cfg == "auto" else lang_cfg.upper()
        max_words = self._config["claude"]["cover_letter_max_words"]
        requirements = ", ".join((analysis or {}).get("key_requirements", [])[:5])

        prompt = COVER_LETTER_PROMPT.format(
            resume=resume[:2500],
            title=job.get("title", ""),
            company=job.get("company", ""),
            location=job.get("location", ""),
            requirements=requirements or "Not specified",
            description=(job.get("description") or job.get("raw_details", ""))[:1500],
            language=language,
            max_words=max_words,
        )

        try:
            response = self._client.messages.create(
                model=self._config["claude"]["model"],
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}],
            )
            return response.content[0].text.strip()
        except Exception as exc:
            logger.error(f"Cover letter generation failed: {exc}")
            return self._template_cover_letter(job)

    # ── Private ────────────────────────────────────────────────────────────────

    @staticmethod
    def _heuristic_score(job: dict, resume: str) -> dict:
        """Simple keyword-based scoring when Claude is unavailable."""
        title = job.get("title", "").lower()
        desc  = (job.get("description") or job.get("raw_details", "")).lower()
        resume_lower = resume.lower()

        tech_keywords = [
            "python", "javascript", "typescript", "react", "node", "sql",
            "django", "fastapi", "docker", "kubernetes", "aws", "gcp", "azure",
            "git", "ci/cd", "agile", "scrum", "machine learning", "data science",
        ]
        matches = sum(1 for kw in tech_keywords if kw in resume_lower and kw in desc)
        score = min(100, int(matches * 12 + 20))

        return {
            "match_score": score,
            "strengths": [],
            "gaps": [],
            "email_contact": None,
            "recruiter_name": None,
            "key_requirements": [],
            "recommended_apply": score >= 50,
            "reason": f"Heuristic score based on {matches} keyword matches.",
        }

    @staticmethod
    def _detect_language(job: dict) -> str:
        french_signals = ["fr", "france", "paris", "lyon", "marseille", "cdi", "cdd", "stage"]
        text = " ".join([
            job.get("location", ""),
            job.get("description", ""),
        ]).lower()
        return "French" if any(s in text for s in french_signals) else "English"

    @staticmethod
    def _template_cover_letter(job: dict) -> str:
        return (
            f"Dear Hiring Team at {job.get('company', 'your company')},\n\n"
            f"I am excited to apply for the {job.get('title', 'position')} role. "
            f"My background aligns well with the requirements, and I am eager to "
            f"contribute to your team.\n\n"
            f"I look forward to discussing this opportunity further.\n\n"
            f"Best regards,"
        )
