"""
Wrapper around the Google Gen AI SDK (Gemini).

Uses the new `google-genai` SDK with gemini-2.5-flash (latest stable fast model).
Plain API key from AI Studio — no service account required.

Thread-safe rate limiting with daily quota enforcement for free tier.
"""

from __future__ import annotations

import json
import threading
import time
from datetime import datetime, timezone, timedelta
from typing import Any

from google import genai
from google.genai import types

from config.settings import GEMINI_API_KEY
from utils.logger import get_logger

logger = get_logger(__name__)

# ── Configure SDK ────────────────────────────────────────────────
_client = genai.Client(api_key=GEMINI_API_KEY)

# ── Model selection ──────────────────────────────────────────────
_MODEL = "gemini-2.5-flash"  # Latest stable fast model (GA since June 2025)

# ── Rate-limit tracking (thread-safe) ────────────────────────────
_rate_limit_lock = threading.Lock()
_request_timestamps: list[float] = []
_RPM_LIMIT = 14  # stay just under the 15 RPM free-tier ceiling

# ── Daily quota tracking (Gemini free tier: 1,500 req/day) ──────
_DAILY_LIMIT = 1450  # safety margin below 1,500
_daily_count = 0
_daily_reset_date: str = ""  # ISO date string for last reset

# ── IST timezone ────────────────────────────────────────────────
_IST = timezone(timedelta(hours=5, minutes=30))

# ── Response cache for common queries ────────────────────────────
_response_cache: dict[str, tuple[str, float]] = {}
_CACHE_TTL = 3600  # 1 hour


def _get_today_ist() -> str:
    """Return today's date in IST as ISO string."""
    return datetime.now(_IST).strftime("%Y-%m-%d")


def _check_daily_quota() -> bool:
    """Check and enforce daily request quota. Returns True if quota available."""
    global _daily_count, _daily_reset_date

    today = _get_today_ist()
    if _daily_reset_date != today:
        _daily_count = 0
        _daily_reset_date = today
        logger.info("Gemini daily quota reset for %s.", today)

    if _daily_count >= _DAILY_LIMIT:
        logger.warning(
            "Gemini daily quota exhausted (%d/%d). Blocking request.",
            _daily_count, _DAILY_LIMIT,
        )
        return False
    return True


def _wait_for_rate_limit() -> None:
    """Sleep if we're approaching the per-minute request limit. Thread-safe."""
    with _rate_limit_lock:
        now = time.time()
        # Discard timestamps older than 60 s
        while _request_timestamps and _request_timestamps[0] < now - 60:
            _request_timestamps.pop(0)

        if len(_request_timestamps) >= _RPM_LIMIT:
            sleep_for = 60 - (now - _request_timestamps[0]) + 1
            logger.warning("Gemini rate limit approaching — sleeping %.1f s", sleep_for)
            time.sleep(sleep_for)

        _request_timestamps.append(time.time())


def _call_gemini(
    system_prompt: str,
    user_message: str,
    *,
    max_retries: int = 3,
) -> str:
    """
    Low-level helper: send a prompt to Gemini 2.5 Flash and return raw text.

    Includes exponential back-off on 429 / 500 errors.
    Enforces daily quota and per-minute rate limits (thread-safe).
    """
    global _daily_count

    # Check daily quota
    with _rate_limit_lock:
        if not _check_daily_quota():
            raise RuntimeError(
                f"Gemini daily quota exhausted ({_daily_count}/{_DAILY_LIMIT}). "
                "Try again after midnight IST."
            )
        _daily_count += 1

    _wait_for_rate_limit()

    config = types.GenerateContentConfig(
        system_instruction=system_prompt,
        temperature=0.7,
    )

    for attempt in range(1, max_retries + 1):
        try:
            response = _client.models.generate_content(
                model=_MODEL,
                contents=user_message,
                config=config,
            )
            return response.text
        except Exception as exc:
            err_str = str(exc).lower()
            retryable = "429" in err_str or "500" in err_str or "resource" in err_str or "quota" in err_str
            if retryable and attempt < max_retries:
                wait = 2 ** attempt
                logger.warning(
                    "Gemini request failed (attempt %d/%d): %s — retrying in %d s",
                    attempt, max_retries, exc, wait,
                )
                time.sleep(wait)
            else:
                logger.error("Gemini request failed permanently: %s", exc)
                raise

    # Should not reach here, but satisfy type-checker
    raise RuntimeError("Gemini request failed after all retries.")


# ══════════════════════════════════════════════════════════════════
#  PUBLIC API
# ══════════════════════════════════════════════════════════════════

def generate(system_prompt: str, user_message: str) -> str:
    """
    Generate a plain-text response from Gemini 2.5 Flash.

    Args:
        system_prompt: Instructions describing the AI's role / context.
        user_message: The user's current input.

    Returns:
        The model's text response.
    """
    return _call_gemini(system_prompt, user_message)


def generate_json(system_prompt: str, user_message: str) -> dict[str, Any]:
    """
    Generate a response and parse it as JSON.

    The system prompt should instruct Gemini to reply strictly in JSON.
    If parsing fails, returns ``{"raw": "<text>", "parse_error": True}``.
    """
    text = _call_gemini(system_prompt, user_message)

    # Strip markdown code fences if present
    cleaned = text.strip()
    if cleaned.startswith("```"):
        # Remove opening fence (```json or ```)
        cleaned = cleaned.split("\n", 1)[-1] if "\n" in cleaned else cleaned[3:]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    cleaned = cleaned.strip()

    try:
        # strict=False tolerates control characters (newlines/tabs) inside JSON strings
        # which Gemini sometimes produces in Hinglish/multilingual responses
        return json.loads(cleaned, strict=False)
    except json.JSONDecodeError as exc:
        logger.warning("Failed to parse Gemini JSON response: %s", exc)
        return {"raw": text, "parse_error": True}


def get_quota_status() -> dict[str, Any]:
    """Return current quota usage stats for monitoring."""
    with _rate_limit_lock:
        now = time.time()
        recent_rpm = sum(1 for ts in _request_timestamps if ts > now - 60)
    return {
        "daily_used": _daily_count,
        "daily_limit": _DAILY_LIMIT,
        "daily_remaining": max(0, _DAILY_LIMIT - _daily_count),
        "rpm_current": recent_rpm,
        "rpm_limit": _RPM_LIMIT,
        "reset_date": _daily_reset_date,
    }
