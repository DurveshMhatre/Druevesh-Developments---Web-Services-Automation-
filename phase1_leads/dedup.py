"""
Deduplication logic for leads before writing them to Google Sheets.

Compares new leads against existing ones by normalized phone number.
"""

from __future__ import annotations

import re
from typing import Any

from utils.logger import get_logger

logger = get_logger(__name__)


def _normalize_phone(phone: str) -> str:
    """Normalize a phone number to +91XXXXXXXXXX format."""
    digits = re.sub(r"[^\d]", "", str(phone))
    if digits.startswith("91") and len(digits) == 12:
        return f"+{digits}"
    if len(digits) == 10:
        return f"+91{digits}"
    return f"+{digits}" if digits else ""


def deduplicate(
    new_leads: list[dict[str, Any]],
    existing_leads: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Remove leads whose phone number already exists in the sheet.

    Args:
        new_leads: Freshly scraped leads.
        existing_leads: Leads already in Google Sheets
            (as returned by :func:`utils.sheets_client.get_all_leads`).

    Returns:
        A filtered list containing only truly new leads.
    """
    existing_phones: set[str] = set()
    for lead in existing_leads:
        phone = _normalize_phone(lead.get("Phone", "") or lead.get("phone", ""))
        if phone:
            existing_phones.add(phone)

    unique: list[dict[str, Any]] = []
    dup_count = 0

    for lead in new_leads:
        phone = _normalize_phone(lead.get("phone", ""))
        if not phone:
            continue
        if phone in existing_phones:
            dup_count += 1
        else:
            existing_phones.add(phone)  # prevent intra-batch duplicates
            unique.append(lead)

    logger.info(
        "Dedup: %d new leads in → %d unique out (%d duplicates removed).",
        len(new_leads), len(unique), dup_count,
    )
    return unique
