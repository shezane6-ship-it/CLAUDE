"""
Lightweight notification support — Slack, Discord, or ntfy webhooks.
"""

import json
import logging
import urllib.request
from typing import Optional

logger = logging.getLogger(__name__)


class Notifier:
    def __init__(self, config: dict):
        self._cfg = config.get("notifications", {})

    def is_enabled(self) -> bool:
        return bool(self._cfg.get("enabled") and self._cfg.get("webhook_url"))

    def send(self, title: str, message: str) -> bool:
        if not self.is_enabled():
            return False
        url = self._cfg["webhook_url"]
        try:
            if "hooks.slack.com" in url:
                return self._slack(url, title, message)
            elif "discord.com" in url:
                return self._discord(url, title, message)
            else:
                return self._ntfy(url, title, message)
        except Exception as exc:
            logger.warning(f"Notification failed: {exc}")
            return False

    # ── Backends ───────────────────────────────────────────────────────────────

    @staticmethod
    def _slack(url: str, title: str, body: str) -> bool:
        payload = json.dumps({"text": f"*{title}*\n{body}"}).encode()
        req = urllib.request.Request(url, data=payload,
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status == 200

    @staticmethod
    def _discord(url: str, title: str, body: str) -> bool:
        payload = json.dumps({"content": f"**{title}**\n{body}"}).encode()
        req = urllib.request.Request(url, data=payload,
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status in (200, 204)

    @staticmethod
    def _ntfy(url: str, title: str, body: str) -> bool:
        req = urllib.request.Request(url, data=body.encode(),
                                     headers={"Title": title})
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status == 200
