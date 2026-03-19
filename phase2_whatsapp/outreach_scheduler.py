"""
Cold outreach scheduler.

Picks un-contacted high-score leads from Google Sheets and sends the
first WhatsApp message. Also handles follow-ups (24 / 48 / 72 hrs).
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any

from config.settings import MAX_COLD_MESSAGES_PER_DAY, WHATSAPP_MODE
from phase2_whatsapp import meta_cloud_api
from phase2_whatsapp.templates import (
    FOLLOW_UP_1,
    FOLLOW_UP_2,
    FOLLOW_UP_3,
    WELCOME_MESSAGE,
    format_template,
)
from phase2_whatsapp.whatsapp_web_js import bridge as wjs_bridge
from utils.logger import get_logger
from utils.sheets_client import (
    append_conversation,
    get_leads_by_status,
    update_lead_field,
    update_lead_status,
)
from utils.telegram_alert import send_alert

logger = get_logger(__name__)


async def _send(phone: str, text: str) -> None:
    """Send a message via the active WhatsApp handler."""
    if WHATSAPP_MODE == "meta_cloud":
        await meta_cloud_api.send_text_message(phone, text)
    else:
        await wjs_bridge.send_message(phone, text)


def _parse_datetime(dt_str: str) -> datetime | None:
    """Try to parse various ISO-ish datetime strings."""
    if not dt_str:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S.%f"):
        try:
            return datetime.strptime(dt_str, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


# ══════════════════════════════════════════════════════════════════
#  COLD OUTREACH
# ══════════════════════════════════════════════════════════════════

async def send_cold_outreach() -> int:
    """
    Send first cold outreach messages to high-scoring leads.

    Returns the number of messages sent.
    """
    leads = get_leads_by_status("Ready for Outreach")
    if not leads:
        logger.info("No leads ready for outreach.")
        return 0

    sent = 0
    for lead in leads:
        if sent >= MAX_COLD_MESSAGES_PER_DAY:
            logger.info("Daily cold message limit (%d) reached.", MAX_COLD_MESSAGES_PER_DAY)
            break

        phone = str(lead.get("Phone", ""))
        name = str(lead.get("Name", "Business"))

        if not phone:
            continue

        phone_type = str(lead.get("PhoneType", "mobile")).lower()

        # Landline numbers can't receive WhatsApp → mark for voice calling
        if phone_type == "landline":
            update_lead_status(phone, "Voice Calling Ready")
            logger.info("Skipped landline %s (%s) → marked Voice Calling Ready.", name, phone)
            continue

        msg = format_template(WELCOME_MESSAGE, business_name=name)

        try:
            await _send(phone, msg)
            append_conversation(phone, "out", msg, "WELCOME")
            update_lead_status(phone, "First Message Sent")
            update_lead_field(phone, "CurrentStage", "WELCOME")
            update_lead_field(phone, "LastMessageAt", datetime.now(timezone.utc).isoformat())
            sent += 1
            logger.info("Cold outreach sent to %s (%s).", name, phone)

            # Small delay between messages to appear natural
            await asyncio.sleep(5)

        except Exception as exc:
            logger.error("Failed to send outreach to %s: %s", phone, exc)
            # Meta API rejects with 400/131026 when number is not on WhatsApp
            exc_str = str(exc)
            if "400" in exc_str or "Bad Request" in exc_str or "131026" in exc_str:
                update_lead_status(phone, "Voice Calling Ready")
                logger.info("Marked %s as Voice Calling Ready (not on WhatsApp).", phone)

    logger.info("Cold outreach complete: %d messages sent.", sent)
    return sent


# ══════════════════════════════════════════════════════════════════
#  FOLLOW-UPS
# ══════════════════════════════════════════════════════════════════

async def send_follow_ups() -> int:
    """
    Send follow-up messages to leads who haven't replied.

    - Follow-up 1: after 24 hrs
    - Follow-up 2: after 48 hrs
    - Follow-up 3: after 72 hrs (then mark as "No Response")

    Returns the number of follow-ups sent.
    """
    follow_up_statuses = {
        "First Message Sent":  (FOLLOW_UP_1, "Follow-Up 1 Sent", timedelta(hours=24)),
        "Follow-Up 1 Sent":   (FOLLOW_UP_2, "Follow-Up 2 Sent", timedelta(hours=24)),
        "Follow-Up 2 Sent":   (FOLLOW_UP_3, "No Response",      timedelta(hours=24)),
    }

    sent = 0
    now = datetime.now(timezone.utc)

    for status, (template, next_status, wait_time) in follow_up_statuses.items():
        leads = get_leads_by_status(status)

        for lead in leads:
            phone = str(lead.get("Phone", ""))
            name = str(lead.get("Name", "Business"))
            last_msg_at = _parse_datetime(str(lead.get("LastMessageAt", "")))

            if not phone or not last_msg_at:
                continue

            # Check if enough time has passed
            if now - last_msg_at < wait_time:
                continue

            msg = format_template(template, business_name=name)

            try:
                await _send(phone, msg)
                append_conversation(phone, "out", msg, next_status)
                update_lead_status(phone, next_status)
                update_lead_field(phone, "LastMessageAt", now.isoformat())
                sent += 1
                logger.info("Follow-up (%s) sent to %s.", next_status, phone)
                await asyncio.sleep(5)
            except Exception as exc:
                logger.error("Failed to send follow-up to %s: %s", phone, exc)

    logger.info("Follow-ups complete: %d messages sent.", sent)
    return sent


# ══════════════════════════════════════════════════════════════════
#  COMBINED SCHEDULER ENTRY POINT
# ══════════════════════════════════════════════════════════════════

def run_outreach_cycle() -> None:
    """Run both cold outreach and follow-ups (sync wrapper)."""
    async def _run():
        cold = await send_cold_outreach()
        followups = await send_follow_ups()
        return cold, followups

    # APScheduler BackgroundScheduler runs jobs in threads.
    # If uvicorn's event loop is already running, asyncio.run() would crash.
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as pool:
            cold, followups = pool.submit(asyncio.run, _run()).result()
    else:
        cold, followups = asyncio.run(_run())

    logger.info("Outreach cycle done: %d cold, %d follow-ups.", cold, followups)

    if cold + followups > 0:
        send_alert(
            f"📤 Outreach cycle complete:\n"
            f"  • Cold messages: {cold}\n"
            f"  • Follow-ups: {followups}",
            level="info",
        )
