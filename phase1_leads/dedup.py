"""
Deduplication logic for leads before writing them to Google Sheets.

Compares new leads against existing ones by:
1. Normalized phone number (exact match)
2. Fuzzy matching on business name + address (using rapidfuzz)

This prevents duplicate leads from different scrapers or re-scrapes.
"""

from __future__ import annotations

import re
from typing import Any

from utils.logger import get_logger

logger = get_logger(__name__)

# Try to import rapidfuzz; fall back to basic matching if unavailable
try:
    from rapidfuzz import fuzz
    _HAS_RAPIDFUZZ = True
except ImportError:
    _HAS_RAPIDFUZZ = False
    logger.warning("rapidfuzz not installed — fuzzy dedup disabled, using phone-only matching.")


# ── Phone normalization ──────────────────────────────────────────

def _normalize_phone(phone: str) -> str:
    """Normalize a phone number to +91XXXXXXXXXX format."""
    digits = re.sub(r"[^\d]", "", str(phone))
    if digits.startswith("91") and len(digits) == 12:
        return f"+{digits}"
    if len(digits) == 10:
        return f"+91{digits}"
    return f"+{digits}" if digits else ""


# ── Indian phone validation ─────────────────────────────────────

def validate_indian_phone(phone: str) -> tuple[bool, str]:
    """
    Validate and normalize an Indian phone number.

    Returns:
        Tuple of (is_valid, normalized_number_or_error_message).
    """
    clean = re.sub(r"[\s\-\(\)]", "", str(phone))

    # Strip country code
    if clean.startswith("+91"):
        clean = clean[3:]
    elif clean.startswith("91") and len(clean) == 12:
        clean = clean[2:]
    elif clean.startswith("0"):
        clean = clean[1:]

    # Valid Indian mobile: 10 digits, starts with 6/7/8/9
    if len(clean) == 10 and clean[0] in "6789" and clean.isdigit():
        return True, f"+91{clean}"

    return False, "Invalid Indian mobile number"


# ── Fuzzy matching ───────────────────────────────────────────────

_NAME_THRESHOLD = 85   # % similarity for business names
_ADDR_THRESHOLD = 80   # % similarity for addresses


def _is_fuzzy_duplicate(
    new_name: str,
    new_addr: str,
    existing_name: str,
    existing_addr: str,
) -> bool:
    """Check if two leads are duplicates via fuzzy string matching."""
    if not _HAS_RAPIDFUZZ:
        return False

    if not new_name or not existing_name:
        return False

    name_score = fuzz.token_sort_ratio(new_name.lower(), existing_name.lower())

    if name_score >= _NAME_THRESHOLD:
        # If names are very similar, check address too (if available)
        if new_addr and existing_addr:
            addr_score = fuzz.token_sort_ratio(new_addr.lower(), existing_addr.lower())
            return addr_score >= _ADDR_THRESHOLD
        # If no address to compare but names are highly similar (>= 90%), mark as dup
        return name_score >= 90

    return False


# ── Main dedup function ──────────────────────────────────────────

def deduplicate(
    new_leads: list[dict[str, Any]],
    existing_leads: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Remove leads whose phone number already exists in the sheet,
    or whose business name + address closely match existing leads.

    Args:
        new_leads: Freshly scraped leads.
        existing_leads: Leads already in Google Sheets
            (as returned by :func:`utils.sheets_client.get_all_leads`).

    Returns:
        A filtered list containing only truly new leads.
    """
    # Build lookup structures from existing leads
    existing_phones: set[str] = set()
    existing_entries: list[tuple[str, str]] = []  # (name, address) pairs

    for lead in existing_leads:
        phone = _normalize_phone(lead.get("Phone", "") or lead.get("phone", ""))
        if phone:
            existing_phones.add(phone)

        name = str(lead.get("Name", "") or lead.get("name", "")).strip()
        addr = str(lead.get("Address", "") or lead.get("address", "")).strip()
        if name:
            existing_entries.append((name, addr))

    unique: list[dict[str, Any]] = []
    dup_count = 0
    fuzzy_dup_count = 0

    for lead in new_leads:
        phone = _normalize_phone(lead.get("phone", ""))
        if not phone:
            continue

        # Check 1: Exact phone match
        if phone in existing_phones:
            dup_count += 1
            continue

        # Check 2: Fuzzy name + address match
        new_name = str(lead.get("name", "")).strip()
        new_addr = str(lead.get("address", "")).strip()
        is_fuzzy_dup = False

        if _HAS_RAPIDFUZZ and new_name:
            for ex_name, ex_addr in existing_entries:
                if _is_fuzzy_duplicate(new_name, new_addr, ex_name, ex_addr):
                    is_fuzzy_dup = True
                    fuzzy_dup_count += 1
                    break

        if is_fuzzy_dup:
            continue

        # Not a duplicate — add to results and update lookup structures
        existing_phones.add(phone)
        if new_name:
            existing_entries.append((new_name, new_addr))
        unique.append(lead)

    logger.info(
        "Dedup: %d new leads in → %d unique out "
        "(%d phone duplicates, %d fuzzy duplicates removed).",
        len(new_leads), len(unique), dup_count, fuzzy_dup_count,
    )
    return unique
