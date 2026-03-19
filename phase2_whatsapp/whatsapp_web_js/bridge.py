"""
Python ↔ Node.js bridge for whatsapp-web.js (Option B).

Communicates with the Node.js server via HTTP with:
- Retry logic with exponential backoff and jitter
- QR code status polling for initial auth
- Message queue for offline handling
"""

from __future__ import annotations

import asyncio
import random
from typing import Any

import httpx

from config.settings import WHATSAPP_WEB_JS_URL
from utils.logger import get_logger

logger = get_logger(__name__)

# ── Retry configuration ─────────────────────────────────────────
_MAX_RETRIES = 3
_BASE_DELAY = 1.0  # seconds
_MAX_DELAY = 15.0  # seconds

# ── Offline message queue ────────────────────────────────────────
_offline_queue: list[dict[str, str]] = []


async def _request_with_retry(
    method: str,
    url: str,
    *,
    json_data: dict | None = None,
    timeout: float = 15.0,
    max_retries: int = _MAX_RETRIES,
) -> dict[str, Any]:
    """
    Make an HTTP request with exponential backoff + jitter.

    Raises httpx.HTTPStatusError after all retries exhausted.
    """
    last_exc: Exception | None = None

    for attempt in range(1, max_retries + 1):
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                if method == "GET":
                    resp = await client.get(url)
                else:
                    resp = await client.post(url, json=json_data)
                resp.raise_for_status()
                return resp.json()
        except (httpx.HTTPStatusError, httpx.ConnectError, httpx.TimeoutException) as exc:
            last_exc = exc
            if attempt < max_retries:
                # Exponential backoff with jitter
                delay = min(_BASE_DELAY * (2 ** (attempt - 1)), _MAX_DELAY)
                jitter = random.uniform(0, delay * 0.5)
                total_delay = delay + jitter
                logger.warning(
                    "whatsapp-web.js bridge: attempt %d/%d failed (%s) — "
                    "retrying in %.1f s",
                    attempt, max_retries, exc, total_delay,
                )
                await asyncio.sleep(total_delay)
            else:
                logger.error(
                    "whatsapp-web.js bridge: all %d attempts failed: %s",
                    max_retries, exc,
                )

    raise last_exc  # type: ignore[misc]


async def send_message(phone: str, text: str) -> dict:
    """
    Send a WhatsApp message via the Node.js whatsapp-web.js server.

    Falls back to queuing the message if the server is unreachable.

    Args:
        phone: Recipient phone (e.g., ``"919876543210"``).
        text: Message body.

    Returns:
        Response dict from the Node server.
    """
    url = f"{WHATSAPP_WEB_JS_URL}/send"
    payload = {"phone": phone, "message": text}

    try:
        data = await _request_with_retry("POST", url, json_data=payload)
        logger.info("whatsapp-web.js: message sent to %s", phone)
        return data
    except Exception as exc:
        logger.error(
            "whatsapp-web.js: failed to send to %s after retries — queueing: %s",
            phone, exc,
        )
        _offline_queue.append(payload)
        return {"status": "queued", "error": str(exc)}


async def is_ready() -> bool:
    """Check whether the Node.js WhatsApp client is connected."""
    url = f"{WHATSAPP_WEB_JS_URL}/health"
    try:
        data = await _request_with_retry("GET", url, max_retries=1, timeout=5.0)
        return data.get("status") == "ready"
    except Exception:
        return False


async def get_qr_status() -> dict[str, Any]:
    """
    Poll the Node.js server for QR code authentication status.

    Returns:
        Dict with ``status`` (e.g. "qr_pending", "authenticated", "disconnected")
        and optionally ``qr`` (base64 QR image data).
    """
    url = f"{WHATSAPP_WEB_JS_URL}/qr-status"
    try:
        return await _request_with_retry("GET", url, max_retries=2, timeout=10.0)
    except Exception as exc:
        logger.error("Failed to get QR status: %s", exc)
        return {"status": "unavailable", "error": str(exc)}


async def flush_offline_queue() -> int:
    """
    Attempt to send all queued messages that failed while server was offline.

    Returns:
        Number of messages successfully sent.
    """
    if not _offline_queue:
        return 0

    sent = 0
    remaining: list[dict[str, str]] = []

    for msg in _offline_queue:
        try:
            url = f"{WHATSAPP_WEB_JS_URL}/send"
            await _request_with_retry("POST", url, json_data=msg)
            sent += 1
            logger.info("Flushed queued message to %s", msg.get("phone"))
        except Exception:
            remaining.append(msg)

    _offline_queue.clear()
    _offline_queue.extend(remaining)

    if sent:
        logger.info(
            "Offline queue flush: %d sent, %d still pending.", sent, len(remaining)
        )
    return sent


def get_queue_size() -> int:
    """Return the number of messages in the offline queue."""
    return len(_offline_queue)
