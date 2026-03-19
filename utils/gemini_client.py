"""
Wrapper around the Google Gen AI SDK (Gemini).

Uses the new `google-genai` SDK with gemini-2.5-flash (latest stable fast model).
Plain API key from AI Studio — no service account required.
"""

from __future__ import annotations

import json
import time
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

# ── Rate-limit tracking ─────────────────────────────────────────
_request_timestamps: list[float] = []
_RPM_LIMIT = 14  # stay just under the 15 RPM free-tier ceiling


def _wait_for_rate_limit() -> None:
    """Sleep if we're approaching the per-minute request limit."""
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
    """
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
