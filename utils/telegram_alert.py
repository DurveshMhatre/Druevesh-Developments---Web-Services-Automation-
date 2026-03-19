"""
Telegram Bot API helper for sending admin alerts and notifications.
"""

from __future__ import annotations

import httpx

from config.settings import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
from utils.logger import get_logger

logger = get_logger(__name__)

_BASE_URL = "https://api.telegram.org/bot{token}/sendMessage"


async def _send_async(text: str) -> bool:
    """Send a message asynchronously via the Telegram Bot API."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logger.warning("Telegram credentials not configured — skipping alert.")
        return False

    url = _BASE_URL.format(token=TELEGRAM_BOT_TOKEN)
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            logger.debug("Telegram alert sent successfully.")
            return True
    except Exception as exc:
        logger.error("Failed to send Telegram alert: %s", exc)
        return False


def send_sync(text: str) -> bool:
    """Send a message synchronously (blocking) via the Telegram Bot API."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logger.warning("Telegram credentials not configured — skipping alert.")
        return False

    url = _BASE_URL.format(token=TELEGRAM_BOT_TOKEN)
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }

    try:
        with httpx.Client(timeout=10) as client:
            resp = client.post(url, json=payload)
            resp.raise_for_status()
            logger.debug("Telegram alert sent successfully.")
            return True
    except Exception as exc:
        logger.error("Failed to send Telegram alert: %s", exc)
        return False


# ══════════════════════════════════════════════════════════════════
#  PUBLIC API
# ══════════════════════════════════════════════════════════════════

def send_alert(message: str, level: str = "info") -> bool:
    """
    Send an alert to the admin's Telegram chat (synchronous).

    Args:
        message: Alert body text (HTML allowed).
        level: ``"info"`` | ``"warning"`` | ``"error"`` | ``"critical"``

    Returns:
        ``True`` if the message was sent successfully.
    """
    emoji_map = {
        "info": "ℹ️",
        "warning": "⚠️",
        "error": "🔴",
        "critical": "🚨",
    }
    emoji = emoji_map.get(level, "ℹ️")
    formatted = f"{emoji} <b>[{level.upper()}]</b>\n\n{message}"
    return send_sync(formatted)


async def send_alert_async(message: str, level: str = "info") -> bool:
    """Async version of :func:`send_alert`."""
    emoji_map = {
        "info": "ℹ️",
        "warning": "⚠️",
        "error": "🔴",
        "critical": "🚨",
    }
    emoji = emoji_map.get(level, "ℹ️")
    formatted = f"{emoji} <b>[{level.upper()}]</b>\n\n{message}"
    return await _send_async(formatted)
