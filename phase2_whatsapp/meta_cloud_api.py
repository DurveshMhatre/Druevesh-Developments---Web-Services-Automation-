"""
Meta WhatsApp Cloud API integration (Option A).

Handles sending and receiving messages through the official Meta API.
"""

from __future__ import annotations

from typing import Any

import httpx

from config.settings import META_ACCESS_TOKEN, META_PHONE_NUMBER_ID
from utils.logger import get_logger

logger = get_logger(__name__)

_API_VERSION = "v21.0"
_BASE_URL = f"https://graph.facebook.com/{_API_VERSION}"


async def send_text_message(to: str, text: str) -> dict[str, Any]:
    """
    Send a text message via the Meta WhatsApp Cloud API.

    Args:
        to: Recipient phone number in international format (e.g., ``"919876543210"``).
        text: Message body.

    Returns:
        API response dict.
    """
    url = f"{_BASE_URL}/{META_PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {META_ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to,
        "type": "text",
        "text": {"body": text},
    }

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(url, json=payload, headers=headers)
        resp.raise_for_status()
        data = resp.json()
        logger.info("Meta API: message sent to %s", to)
        return data


async def send_template_message(
    to: str,
    template_name: str,
    language_code: str = "en",
    components: list[dict] | None = None,
) -> dict[str, Any]:
    """
    Send a template message (required for first contact within 24-hr window).

    Args:
        to: Recipient phone number.
        template_name: Approved template name.
        language_code: Language code (default ``"en"``).
        components: Optional template components (header, body parameters).

    Returns:
        API response dict.
    """
    url = f"{_BASE_URL}/{META_PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {META_ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }
    template_obj: dict[str, Any] = {
        "name": template_name,
        "language": {"code": language_code},
    }
    if components:
        template_obj["components"] = components

    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to,
        "type": "template",
        "template": template_obj,
    }

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(url, json=payload, headers=headers)
        resp.raise_for_status()
        data = resp.json()
        logger.info("Meta API: template '%s' sent to %s", template_name, to)
        return data


async def send_media_message(
    to: str,
    media_type: str,
    media_url: str,
    caption: str = "",
) -> dict[str, Any]:
    """
    Send a media message (image, document, video).

    Args:
        to: Recipient phone number.
        media_type: ``"image"`` | ``"document"`` | ``"video"``.
        media_url: Public URL of the media file.
        caption: Optional caption.

    Returns:
        API response dict.
    """
    url = f"{_BASE_URL}/{META_PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {META_ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }
    media_obj: dict[str, str] = {"link": media_url}
    if caption:
        media_obj["caption"] = caption

    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to,
        "type": media_type,
        media_type: media_obj,
    }

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(url, json=payload, headers=headers)
        resp.raise_for_status()
        data = resp.json()
        logger.info("Meta API: %s sent to %s", media_type, to)
        return data


def parse_webhook_message(body: dict[str, Any]) -> dict[str, Any] | None:
    """
    Extract sender phone and message text from a Meta webhook payload.

    Returns ``None`` if the payload doesn't contain a user message.
    """
    try:
        entry = body["entry"][0]
        changes = entry["changes"][0]
        value = changes["value"]

        if "messages" not in value:
            return None  # status update, not a message

        msg = value["messages"][0]
        contact = value["contacts"][0]

        return {
            "phone": msg["from"],
            "message": msg.get("text", {}).get("body", ""),
            "message_id": msg["id"],
            "timestamp": msg["timestamp"],
            "name": contact.get("profile", {}).get("name", ""),
            "type": msg["type"],
        }

    except (KeyError, IndexError) as exc:
        logger.debug("Could not parse webhook payload: %s", exc)
        return None
