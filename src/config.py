"""
Configuration management for the Job Automation System.
Edit data/config.json to customize your search preferences.
"""

import json
import os
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
LOGS_DIR = BASE_DIR / "logs"
TEMPLATES_DIR = BASE_DIR / "templates"

DEFAULT_CONFIG = {
    # ── Job Search ─────────────────────────────────────────────────────────────
    "search": {
        "keywords": ["Software Engineer", "Python Developer", "Backend Engineer"],
        "location": "remote",
        "country_code": "FR",
        "job_type": "fulltime",          # fulltime | parttime | contract | internship
        "max_results_per_keyword": 20,
        "min_match_score": 60,           # 0-100 — skip jobs below this threshold
        "search_interval_hours": 4       # how often to re-run the search loop
    },

    # ── Application ────────────────────────────────────────────────────────────
    "application": {
        "auto_apply_email": False,       # send email applications automatically
        "sender_email": "",              # your Gmail / SMTP email
        "sender_password": "",           # app password (not your real password)
        "smtp_host": "smtp.gmail.com",
        "smtp_port": 587,
        "max_applications_per_day": 10,  # safety cap
        "blacklisted_companies": [],     # e.g. ["CompanyX", "CompanyY"]
        "required_keywords": [],         # job must contain these (OR logic)
        "excluded_keywords": ["unpaid", "non rémunéré"]
    },

    # ── Claude AI ──────────────────────────────────────────────────────────────
    "claude": {
        "model": "claude-opus-4-7",
        "api_key_env": "ANTHROPIC_API_KEY",  # env var name
        "cover_letter_language": "auto",     # auto | fr | en
        "cover_letter_max_words": 300
    },

    # ── Notifications ──────────────────────────────────────────────────────────
    "notifications": {
        "enabled": False,
        "webhook_url": ""                # Slack/Discord/ntfy webhook
    }
}


def load_config() -> dict[str, Any]:
    """Load config from data/config.json, filling missing keys with defaults."""
    config_path = DATA_DIR / "config.json"
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    if not config_path.exists():
        save_config(DEFAULT_CONFIG)
        return DEFAULT_CONFIG

    with open(config_path, "r", encoding="utf-8") as f:
        user_config = json.load(f)

    # Deep merge: user values override defaults
    merged = _deep_merge(DEFAULT_CONFIG, user_config)
    return merged


def save_config(config: dict[str, Any]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(DATA_DIR / "config.json", "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)


def _deep_merge(base: dict, override: dict) -> dict:
    result = dict(base)
    for key, val in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(val, dict):
            result[key] = _deep_merge(result[key], val)
        else:
            result[key] = val
    return result
