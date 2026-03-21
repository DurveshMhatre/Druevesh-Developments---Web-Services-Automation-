"""
Google Sheets API wrapper using gspread with OAuth 2.0 Desktop credentials.

Service-account key creation is blocked on free-tier GCP projects by the
``iam.disableServiceAccountKeyCreation`` organization policy, so we use
``gspread.oauth()`` instead.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
import time
from typing import Any

import gspread

from config.settings import (
    GOOGLE_SHEETS_ID,
    OAUTH_CREDENTIALS_FILE,
    OAUTH_TOKEN_FILE,
)
from utils.logger import get_logger

logger = get_logger(__name__)


# ── Sheets API retry decorator ───────────────────────────────────

def retry_sheets_api(max_retries: int = 3, initial_delay: float = 1.0, multiplier: float = 2.0):
    """
    Decorator that retries Google Sheets API calls on transient errors.

    Retries on: HTTP 429 (rate limit), 503 (service unavailable),
    and connection/timeout errors.

    Args:
        max_retries: Maximum number of retry attempts.
        initial_delay: Initial delay in seconds before first retry.
        multiplier: Delay multiplier for exponential backoff.
    """
    import functools

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            delay = initial_delay
            last_exc: Exception | None = None
            for attempt in range(1, max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as exc:
                    last_exc = exc
                    err_str = str(exc).lower()
                    retryable = (
                        "429" in err_str
                        or "503" in err_str
                        or "rate" in err_str
                        or "quota" in err_str
                        or "connection" in err_str
                        or "timeout" in err_str
                    )
                    if retryable and attempt < max_retries:
                        logger.debug(
                            "Sheets API retry %d/%d for %s: %s — waiting %.1fs",
                            attempt, max_retries, func.__name__, exc, delay,
                        )
                        time.sleep(delay)
                        delay *= multiplier
                    else:
                        raise
            raise last_exc  # type: ignore[misc]
        return wrapper
    return decorator


# ── Connection cache (created once per process) ─────────────────
_gspread_client: gspread.Client | None = None
_spreadsheet: gspread.Spreadsheet | None = None

# ── In-memory cache for leads (reduces Sheets API calls) ─────────
_leads_cache: list[dict[str, Any]] = []
_leads_cache_time: float = 0.0
_CACHE_TTL = 300  # 5 minutes


def _get_client() -> gspread.Client:
    """
    Authenticate and return a gspread client using OAuth 2.0 Desktop flow.

    Connection is cached per process — OAuth handshake only happens once.
    """
    global _gspread_client
    if _gspread_client is None:
        _gspread_client = gspread.oauth(
            credentials_filename=str(OAUTH_CREDENTIALS_FILE),
            authorized_user_filename=str(OAUTH_TOKEN_FILE),
            scopes=[
                "https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive",
            ],
        )
    return _gspread_client


def _get_spreadsheet() -> gspread.Spreadsheet:
    """Return the master spreadsheet by ID (cached per process)."""
    global _spreadsheet
    if _spreadsheet is None:
        _spreadsheet = _get_client().open_by_key(GOOGLE_SHEETS_ID)
    return _spreadsheet


def _ensure_worksheet(
    spreadsheet: gspread.Spreadsheet,
    title: str,
    headers: list[str],
) -> gspread.Worksheet:
    """Get or create a worksheet with the given headers in row 1."""
    try:
        ws = spreadsheet.worksheet(title)
    except gspread.WorksheetNotFound:
        ws = spreadsheet.add_worksheet(title=title, rows=1000, cols=len(headers))
        ws.append_row(headers, value_input_option="RAW")
        logger.info("Created worksheet '%s' with headers.", title)
    return ws


# ── Column definitions ───────────────────────────────────────────
LEAD_HEADERS = [
    "Name", "Phone", "PhoneType", "Type", "City", "Rating", "Reviews",
    "Score", "Website", "Source", "Status", "DateAdded",
    "CurrentStage", "LastMessageAt",
]

CONVERSATION_HEADERS = [
    "LeadPhone", "Timestamp", "Direction", "Message", "Stage",
]

REQUIREMENTS_HEADERS = [
    "LeadPhone", "BusinessName", "ServicesDescription",
    "PagesNeeded", "Features", "Budget", "DesignPreferences",
]

PACKAGE_HEADERS = [
    "LeadPhone", "PackageName", "Price", "Timestamp", "Status",
]


# ── Helpers ──────────────────────────────────────────────────────
def _normalize_phone(phone: str) -> str:
    """Strip spaces, dashes, and ensure +91 prefix."""
    digits = re.sub(r"[^\d]", "", phone)
    if digits.startswith("91") and len(digits) == 12:
        return f"+{digits}"
    if len(digits) == 10:
        return f"+91{digits}"
    return f"+{digits}" if not digits.startswith("+") else digits


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


# ══════════════════════════════════════════════════════════════════
#  PUBLIC API — Leads
# ══════════════════════════════════════════════════════════════════

def get_all_leads(force_refresh: bool = False) -> list[dict[str, Any]]:
    """Return every row from the *Leads* worksheet as a list of dicts.

    Uses an in-memory cache with 5-minute TTL to reduce API calls.
    """
    global _leads_cache, _leads_cache_time

    now = time.time()
    if not force_refresh and _leads_cache and (now - _leads_cache_time) < _CACHE_TTL:
        logger.debug("Returning %d cached leads (%.0f s old).", len(_leads_cache), now - _leads_cache_time)
        return _leads_cache

    ss = _get_spreadsheet()
    ws = _ensure_worksheet(ss, "Leads", LEAD_HEADERS)
    records = ws.get_all_records()
    _leads_cache = records
    _leads_cache_time = now
    logger.debug("Fetched %d leads from Sheets (cache refreshed).", len(records))
    return records


def append_leads(leads: list[dict[str, Any]]) -> int:
    """Append new lead rows and return the count of rows added.

    Falls back to local storage if Sheets API fails.
    """
    global _leads_cache_time
    if not leads:
        return 0

    rows = []
    for lead in leads:
        rows.append([
            lead.get("name", ""),
            _normalize_phone(lead.get("phone", "")),
            lead.get("phone_type", "mobile"),
            lead.get("type", ""),
            lead.get("city", ""),
            lead.get("rating", ""),
            lead.get("reviews", ""),
            lead.get("score", ""),
            lead.get("website", ""),
            lead.get("source", ""),
            lead.get("status", "New"),
            lead.get("date_added", _now_iso()),
            lead.get("current_stage", ""),
            lead.get("last_message_at", ""),
        ])

    try:
        ss = _get_spreadsheet()
        ws = _ensure_worksheet(ss, "Leads", LEAD_HEADERS)
        ws.append_rows(rows, value_input_option="USER_ENTERED")
        _leads_cache_time = 0  # Invalidate cache
        logger.info("Appended %d new leads to Sheets.", len(rows))
        return len(rows)
    except Exception as exc:
        logger.error("Failed to append leads to Sheets: %s — falling back to local storage.", exc)
        from utils.local_storage import store_leads
        return store_leads(leads)


def _find_lead_row(ws, phone: str) -> int | None:
    """Find the row number for a lead by phone — robust against formatting issues."""
    # First try ws.find (fast)
    try:
        cell = ws.find(phone, in_column=2)
        if cell is not None:
            return cell.row
    except Exception:
        pass

    # Fallback: scan rows manually (handles Google Sheets number formatting)
    all_values = ws.col_values(2)  # Get all Phone column values
    for i, val in enumerate(all_values):
        if _normalize_phone(str(val)) == phone:
            return i + 1  # 1-indexed rows
    return None


def update_lead_status(phone: str, status: str) -> bool:
    """Update the Status column for a lead matched by phone number."""
    phone = _normalize_phone(phone)
    ss = _get_spreadsheet()
    ws = _ensure_worksheet(ss, "Leads", LEAD_HEADERS)

    row = _find_lead_row(ws, phone)
    if row is None:
        logger.warning("Lead with phone %s not found.", phone)
        return False

    status_col = LEAD_HEADERS.index("Status") + 1
    ws.update_cell(row, status_col, status)
    logger.info("Updated lead %s → status=%s", phone, status)
    return True


def update_lead_field(phone: str, field: str, value: str) -> bool:
    """Update an arbitrary column for a lead matched by phone number."""
    phone = _normalize_phone(phone)
    if field not in LEAD_HEADERS:
        logger.error("Unknown lead field: %s", field)
        return False

    ss = _get_spreadsheet()
    ws = _ensure_worksheet(ss, "Leads", LEAD_HEADERS)

    row = _find_lead_row(ws, phone)
    if row is None:
        logger.warning("Lead with phone %s not found.", phone)
        return False

    col = LEAD_HEADERS.index(field) + 1
    ws.update_cell(row, col, value)
    logger.debug("Updated lead %s → %s=%s", phone, field, value)
    return True


def get_lead_by_phone(phone: str) -> dict[str, Any] | None:
    """Return a single lead dict or ``None``."""
    phone = _normalize_phone(phone)
    for lead in get_all_leads():
        if _normalize_phone(str(lead.get("Phone", ""))) == phone:
            return lead
    return None


def get_leads_by_status(status: str) -> list[dict[str, Any]]:
    """Return all leads with the given status."""
    return [l for l in get_all_leads() if l.get("Status") == status]


# ══════════════════════════════════════════════════════════════════
#  PUBLIC API — Conversations
# ══════════════════════════════════════════════════════════════════

def append_conversation(
    phone: str,
    direction: str,
    message: str,
    stage: str,
) -> None:
    """Append a single conversation row."""
    ss = _get_spreadsheet()
    ws = _ensure_worksheet(ss, "Conversations", CONVERSATION_HEADERS)
    ws.append_row(
        [_normalize_phone(phone), _now_iso(), direction, message, stage],
        value_input_option="USER_ENTERED",
    )


def get_conversation_history(phone: str, limit: int = 10) -> list[dict[str, Any]]:
    """Return the last *limit* messages for a lead."""
    phone = _normalize_phone(phone)
    ss = _get_spreadsheet()
    ws = _ensure_worksheet(ss, "Conversations", CONVERSATION_HEADERS)
    records = ws.get_all_records()
    history = [r for r in records if _normalize_phone(str(r.get("LeadPhone", ""))) == phone]
    return history[-limit:]


# ══════════════════════════════════════════════════════════════════
#  PUBLIC API — Requirements
# ══════════════════════════════════════════════════════════════════

def save_requirements(phone: str, data: dict[str, Any]) -> None:
    """Save collected requirements for a lead."""
    ss = _get_spreadsheet()
    ws = _ensure_worksheet(ss, "Requirements", REQUIREMENTS_HEADERS)
    ws.append_row(
        [
            _normalize_phone(phone),
            data.get("business_name", ""),
            data.get("services_description", ""),
            data.get("pages_needed", ""),
            data.get("features", ""),
            data.get("budget", ""),
            data.get("design_preferences", ""),
        ],
        value_input_option="USER_ENTERED",
    )
    logger.info("Saved requirements for %s.", phone)


def get_requirements(phone: str) -> dict[str, Any] | None:
    """Return saved requirements for a lead, or ``None``."""
    phone = _normalize_phone(phone)
    ss = _get_spreadsheet()
    ws = _ensure_worksheet(ss, "Requirements", REQUIREMENTS_HEADERS)
    records = ws.get_all_records()
    for r in reversed(records):  # latest first
        if _normalize_phone(str(r.get("LeadPhone", ""))) == phone:
            return r
    return None


# ══════════════════════════════════════════════════════════════════
#  PUBLIC API — Package Recommendations
# ══════════════════════════════════════════════════════════════════

def save_package_recommendation(
    phone: str,
    package_name: str,
    price: int,
    status: str = "pending",
) -> None:
    """Save a package recommendation."""
    ss = _get_spreadsheet()
    ws = _ensure_worksheet(ss, "PackageRecommendations", PACKAGE_HEADERS)
    ws.append_row(
        [_normalize_phone(phone), package_name, price, _now_iso(), status],
        value_input_option="USER_ENTERED",
    )
    logger.info("Saved package recommendation: %s → %s", phone, package_name)
