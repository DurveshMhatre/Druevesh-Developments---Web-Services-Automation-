"""
Centralized phone number validation and normalization for Indian numbers.

Used by: google_maps_scraper, sheets_client, dedup, bot.
All phone logic flows through this module to ensure consistency.
"""

from __future__ import annotations

import re
from typing import Literal


# ── Phone normalization ──────────────────────────────────────────

def normalize_phone(phone: str) -> str:
    """
    Normalize any phone string to ``+91XXXXXXXXXX`` format.

    Handles: ``9876543210``, ``919876543210``, ``+91 98765-43210``,
    ``(+91) 98765 43210``, ``098765 43210``, etc.

    Returns:
        Normalized phone string, or ``""`` if input has no digits.
    """
    digits = re.sub(r"[^\d]", "", str(phone))
    if not digits:
        return ""
    if digits.startswith("91") and len(digits) == 12:
        return f"+{digits}"
    if len(digits) == 10:
        return f"+91{digits}"
    return f"+{digits}"


# ── Indian phone validation ─────────────────────────────────────

def validate_indian_phone(phone: str) -> tuple[bool, str]:
    """
    Validate and normalize an Indian mobile phone number.

    Strips country codes (``+91``, ``91``, ``0``), whitespace, dashes,
    and parentheses, then checks for exactly 10 digits starting with
    ``6``, ``7``, ``8``, or ``9``.

    Args:
        phone: Raw phone string in any format.

    Returns:
        ``(True, "+91XXXXXXXXXX")`` if valid, or
        ``(False, "error message")`` if invalid.
    """
    clean = re.sub(r"[\s\-\(\)\+]", "", str(phone))

    # Strip country code
    if clean.startswith("91") and len(clean) == 12:
        clean = clean[2:]
    elif clean.startswith("0") and len(clean) == 11:
        clean = clean[1:]

    # Valid Indian mobile: 10 digits, starts with 6/7/8/9
    if len(clean) == 10 and clean[0] in "6789" and clean.isdigit():
        return True, f"+91{clean}"

    return False, "Invalid Indian mobile number"


# ── Phone type classification ───────────────────────────────────

def classify_phone_type(phone: str) -> Literal["mobile", "landline", "unknown"]:
    """
    Classify a phone number as mobile or landline.

    Indian mobile: 10 digits starting with 6/7/8/9.
    Everything else is classified as landline or unknown.

    Args:
        phone: Raw phone string.

    Returns:
        ``"mobile"``, ``"landline"``, or ``"unknown"``.
    """
    digits = re.sub(r"[^\d]", "", str(phone))

    # Strip leading 91 country code
    if digits.startswith("91") and len(digits) == 12:
        digits = digits[2:]

    if len(digits) == 10 and digits[0] in "6789":
        return "mobile"
    elif len(digits) >= 8:
        return "landline"
    return "unknown"
