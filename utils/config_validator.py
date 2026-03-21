"""
Startup environment variable validation.

Call ``validate_env()`` at server startup to fail fast with clear error
messages when required config is missing.
"""

from __future__ import annotations

import os
from typing import Any

from utils.logger import get_logger

logger = get_logger(__name__)


# ── Free-tier limits reference ───────────────────────────────────
FREE_TIER_LIMITS: dict[str, dict[str, Any]] = {
    "GEMINI_API_KEY": {
        "description": "Google Gemini AI API key",
        "limits": "1,500 requests/day, 15 RPM",
        "get_url": "https://aistudio.google.com/app/apikey",
        "required": True,
    },
    "GOOGLE_SHEETS_ID": {
        "description": "Google Sheets spreadsheet ID",
        "limits": "300 reads/min, 60 writes/min per user",
        "get_url": "Create at sheets.google.com → use ID from URL",
        "required": True,
    },
    "TELEGRAM_BOT_TOKEN": {
        "description": "Telegram Bot API token for admin alerts",
        "limits": "Unlimited (Telegram Bot API is free)",
        "get_url": "Chat with @BotFather on Telegram",
        "required": False,
    },
    "TELEGRAM_CHAT_ID": {
        "description": "Telegram chat ID for admin alerts",
        "limits": "N/A",
        "get_url": "Chat with @userinfobot on Telegram",
        "required": False,
    },
    "META_ACCESS_TOKEN": {
        "description": "Meta WhatsApp Cloud API access token",
        "limits": "1,000 service conversations/month",
        "get_url": "https://developers.facebook.com/apps/",
        "required": False,
    },
    "META_PHONE_NUMBER_ID": {
        "description": "Meta WhatsApp phone number ID",
        "limits": "N/A (tied to META_ACCESS_TOKEN)",
        "get_url": "https://developers.facebook.com/apps/ → WhatsApp → API Setup",
        "required": False,
    },
}


def validate_env(strict: bool = False) -> list[str]:
    """
    Validate that required environment variables are set.

    Args:
        strict: If ``True``, raise ``ValueError`` on any missing *required* var.
                If ``False``, just log warnings and return the list of issues.

    Returns:
        List of warning/error messages for missing or empty variables.

    Raises:
        ValueError: If ``strict=True`` and a required variable is missing.
    """
    from config.settings import (
        GEMINI_API_KEY,
        GOOGLE_SHEETS_ID,
        TELEGRAM_BOT_TOKEN,
        TELEGRAM_CHAT_ID,
        META_ACCESS_TOKEN,
        META_PHONE_NUMBER_ID,
        WHATSAPP_MODE,
    )

    # Map config names to their current values
    values = {
        "GEMINI_API_KEY": GEMINI_API_KEY,
        "GOOGLE_SHEETS_ID": GOOGLE_SHEETS_ID,
        "TELEGRAM_BOT_TOKEN": TELEGRAM_BOT_TOKEN,
        "TELEGRAM_CHAT_ID": TELEGRAM_CHAT_ID,
        "META_ACCESS_TOKEN": META_ACCESS_TOKEN,
        "META_PHONE_NUMBER_ID": META_PHONE_NUMBER_ID,
    }

    issues: list[str] = []

    for var_name, info in FREE_TIER_LIMITS.items():
        value = values.get(var_name, "")

        if not value or value in ("your_gemini_api_key_here", "your_google_sheets_id_here"):
            msg = (
                f"{'❌ REQUIRED' if info['required'] else '⚠️  Optional'}: "
                f"{var_name} is not set.\n"
                f"    → {info['description']}\n"
                f"    → Free-tier limits: {info['limits']}\n"
                f"    → Get it: {info['get_url']}"
            )
            if info["required"]:
                logger.error(msg)
            else:
                logger.warning(msg)
            issues.append(msg)
        else:
            logger.info(
                "✅ %s configured (free-tier: %s)", var_name, info["limits"]
            )

    # WhatsApp mode-specific checks
    if WHATSAPP_MODE == "meta_cloud":
        if not META_ACCESS_TOKEN or not META_PHONE_NUMBER_ID:
            msg = (
                "⚠️  WHATSAPP_MODE=meta_cloud but META_ACCESS_TOKEN or "
                "META_PHONE_NUMBER_ID is missing. WhatsApp sending will fail."
            )
            logger.warning(msg)
            issues.append(msg)
    elif WHATSAPP_MODE == "whatsapp_web_js":
        wjs_url = os.getenv("WHATSAPP_WEB_JS_URL", "http://localhost:3001")
        logger.info(
            "WhatsApp mode: whatsapp_web_js — Node server expected at %s", wjs_url
        )

    if strict:
        required_missing = [
            i for i in issues if i.startswith("❌ REQUIRED")
        ]
        if required_missing:
            raise ValueError(
                "Missing required environment variables:\n\n"
                + "\n\n".join(required_missing)
                + "\n\nCopy config/.env.example to config/.env and fill in the values."
            )

    return issues
