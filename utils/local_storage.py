"""
Local fallback storage for when Google Sheets API quota is exhausted.

Writes leads, conversations, and other data to local JSON files.
Provides a sync function to push pending data to Sheets when quota resets.
Ensures zero data loss during free-tier limits.
"""

from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from utils.logger import get_logger

logger = get_logger(__name__)

# ── Storage directory ────────────────────────────────────────────
_STORAGE_DIR = Path(__file__).resolve().parent.parent / "data" / "local_fallback"
_STORAGE_DIR.mkdir(parents=True, exist_ok=True)

_lock = threading.Lock()


def _get_file(name: str) -> Path:
    """Return the path of a local storage JSON file."""
    return _STORAGE_DIR / f"{name}.json"


def _load(name: str) -> list[dict[str, Any]]:
    """Load all records from a local JSON file."""
    path = _get_file(name)
    if not path.exists():
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, IOError) as exc:
        logger.error("Failed to read local storage %s: %s", path, exc)
        return []


def _save(name: str, records: list[dict[str, Any]]) -> None:
    """Save records to a local JSON file (overwrites)."""
    path = _get_file(name)
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(records, f, ensure_ascii=False, indent=2)
    except IOError as exc:
        logger.error("Failed to write local storage %s: %s", path, exc)


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


# ══════════════════════════════════════════════════════════════════
#  PUBLIC API
# ══════════════════════════════════════════════════════════════════

def store_leads(leads: list[dict[str, Any]]) -> int:
    """
    Store leads locally when Google Sheets is unavailable.

    Returns:
        Number of leads stored.
    """
    with _lock:
        existing = _load("pending_leads")
        for lead in leads:
            lead["_stored_at"] = _now_iso()
        existing.extend(leads)
        _save("pending_leads", existing)
    logger.info("Stored %d leads to local fallback.", len(leads))
    return len(leads)


def store_conversation(
    phone: str,
    direction: str,
    message: str,
    stage: str,
) -> None:
    """Store a conversation row locally."""
    record = {
        "phone": phone,
        "direction": direction,
        "message": message,
        "stage": stage,
        "timestamp": _now_iso(),
    }
    with _lock:
        existing = _load("pending_conversations")
        existing.append(record)
        _save("pending_conversations", existing)


def get_pending_leads() -> list[dict[str, Any]]:
    """Return all locally stored leads pending sync."""
    with _lock:
        return _load("pending_leads")


def get_pending_conversations() -> list[dict[str, Any]]:
    """Return all locally stored conversations pending sync."""
    with _lock:
        return _load("pending_conversations")


def clear_pending(name: str) -> None:
    """Clear all pending data for a given type after successful sync."""
    with _lock:
        _save(name, [])
    logger.info("Cleared local fallback for '%s'.", name)


def sync_to_sheets() -> dict[str, int]:
    """
    Attempt to push all pending local data to Google Sheets.

    Should be called when Sheets quota has reset (e.g., at midnight).

    Returns:
        Dict with counts of synced items per category.
    """
    result = {"leads": 0, "conversations": 0}

    try:
        from utils.sheets_client import append_leads, append_conversation

        # Sync pending leads
        pending_leads = get_pending_leads()
        if pending_leads:
            saved = append_leads(pending_leads)
            if saved > 0:
                clear_pending("pending_leads")
                result["leads"] = saved
                logger.info("Synced %d pending leads to Sheets.", saved)

        # Sync pending conversations
        pending_convos = get_pending_conversations()
        if pending_convos:
            for conv in pending_convos:
                append_conversation(
                    conv["phone"], conv["direction"],
                    conv["message"], conv["stage"],
                )
            clear_pending("pending_conversations")
            result["conversations"] = len(pending_convos)
            logger.info("Synced %d pending conversations to Sheets.", len(pending_convos))

    except Exception as exc:
        logger.error("Local storage sync failed: %s", exc)

    return result


def get_status() -> dict[str, Any]:
    """Return local storage status for monitoring."""
    return {
        "pending_leads": len(get_pending_leads()),
        "pending_conversations": len(get_pending_conversations()),
        "storage_dir": str(_STORAGE_DIR),
    }
