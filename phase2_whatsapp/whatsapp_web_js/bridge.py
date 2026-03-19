"""
Python ↔ Node.js bridge for whatsapp-web.js (Option B).

Communicates with the Node.js server via HTTP.
"""

from __future__ import annotations

import httpx

from config.settings import WHATSAPP_WEB_JS_URL
from utils.logger import get_logger

logger = get_logger(__name__)


async def send_message(phone: str, text: str) -> dict:
    """
    Send a WhatsApp message via the Node.js whatsapp-web.js server.

    Args:
        phone: Recipient phone (e.g., ``"919876543210"``).
        text: Message body.

    Returns:
        Response dict from the Node server.
    """
    url = f"{WHATSAPP_WEB_JS_URL}/send"
    payload = {"phone": phone, "message": text}

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(url, json=payload)
        resp.raise_for_status()
        data = resp.json()
        logger.info("whatsapp-web.js: message sent to %s", phone)
        return data


async def is_ready() -> bool:
    """Check whether the Node.js WhatsApp client is connected."""
    url = f"{WHATSAPP_WEB_JS_URL}/health"
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(url)
            data = resp.json()
            return data.get("status") == "ready"
    except Exception:
        return False
