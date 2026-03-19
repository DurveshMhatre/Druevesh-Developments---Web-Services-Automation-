from __future__ import annotations

import datetime

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from config.settings import (
    BUSINESS_TYPES,
    SCRAPE_SCHEDULE_HOUR,
    TARGET_CITIES,
)
from utils.logger import get_logger
from utils.telegram_alert import send_alert

logger = get_logger(__name__)

_scheduler: BackgroundScheduler | None = None


# ══════════════════════════════════════════════════════════════════
#  JOB FUNCTIONS
# ══════════════════════════════════════════════════════════════════

def _run_daily_scrape():
    """Daily scraping job: Google Maps + JustDial → score → dedup → save."""
    logger.info("═══ Daily scrape job started ═══")

    from phase1_leads.google_maps_scraper import scrape as scrape_gmaps
    from phase1_leads.lead_scorer import score_lead_dict
    from utils.sheets_client import append_leads, get_all_leads

    all_new_leads = []

    for city in TARGET_CITIES:
        for btype in BUSINESS_TYPES:
            try:
                # Google Maps
                gmaps_leads = scrape_gmaps(city, btype)
                all_new_leads.extend(gmaps_leads)
            except Exception as exc:
                logger.error("Google Maps scraper error (%s/%s): %s", city, btype, exc)

            except Exception as exc:
                logger.error("Google Maps scraper error (%s/%s): %s", city, btype, exc)

    # Score all leads
    for lead in all_new_leads:
        score_lead_dict(lead)

    # Dedup against existing data (simple phone check since dedup.py is missing)
    existing = get_all_leads()
    existing_phones = {str(row.get("Phone", "")).strip() for row in existing if row.get("Phone")}
    
    unique = []
    for lead in all_new_leads:
        phone = str(lead.get("phone", "")).strip()
        if phone and phone not in existing_phones:
            unique.append(lead)
            existing_phones.add(phone)

    # Save to Sheets
    saved = append_leads(unique)

    logger.info(
        "═══ Daily scrape complete: %d scraped, %d unique, %d saved ═══",
        len(all_new_leads), len(unique), saved,
    )

    send_alert(
        f"🔍 <b>Daily Scrape Complete</b>\n\n"
        f"  • Total scraped: {len(all_new_leads)}\n"
        f"  • After dedup: {len(unique)}\n"
        f"  • Saved to Sheets: {saved}",
        level="info",
    )


def _run_outreach_cycle():
    """Outreach job: send cold messages and follow-ups."""
    logger.info("═══ Outreach cycle started ═══")
    from phase2_whatsapp.outreach_scheduler import run_outreach_cycle
    run_outreach_cycle()


def _run_daily_summary():
    """Send a daily summary to the admin via Telegram."""
    logger.info("Sending daily summary...")
    from utils.sheets_client import get_all_leads
    from phase2_whatsapp.templates import ADMIN_DAILY_SUMMARY, format_template

    leads = get_all_leads()
    today_leads = [l for l in leads if str(l.get("DateAdded", "")).startswith(
        datetime.date.today().isoformat()
    )]

    msg = format_template(
        ADMIN_DAILY_SUMMARY,
        leads_scraped=len(today_leads),
        messages_sent=sum(1 for l in leads if l.get("Status") in (
            "First Message Sent", "Follow-Up 1 Sent", "Follow-Up 2 Sent"
        )),
        replies_received=sum(1 for l in leads if l.get("Status") == "In Conversation"),
        interested_count=sum(1 for l in leads if l.get("Status") == "Interested - Handoff"),
        not_interested_count=sum(1 for l in leads if l.get("Status") == "Not Interested"),
    )
    send_alert(msg, level="info")


# ══════════════════════════════════════════════════════════════════
#  SCHEDULER CONTROL
# ══════════════════════════════════════════════════════════════════

def start_scheduler() -> None:
    """Create and start all scheduled jobs."""
    global _scheduler

    _scheduler = BackgroundScheduler()

    # Daily scrape at configured hour (default 6 AM)
    _scheduler.add_job(
        _run_daily_scrape,
        trigger=CronTrigger(hour=SCRAPE_SCHEDULE_HOUR, minute=0),
        id="daily_scrape",
        name="Daily Lead Scraper",
        replace_existing=True,
    )

    # Outreach every 2 hours during 9 AM - 8 PM
    _scheduler.add_job(
        _run_outreach_cycle,
        trigger=CronTrigger(hour="9-20/2", minute=0),
        id="outreach_cycle",
        name="Cold Outreach & Follow-ups",
        replace_existing=True,
    )

    # Daily summary at 9 PM
    _scheduler.add_job(
        _run_daily_summary,
        trigger=CronTrigger(hour=21, minute=0),
        id="daily_summary",
        name="Daily Telegram Summary",
        replace_existing=True,
    )

    _scheduler.start()
    logger.info(
        "Scheduler started with jobs: daily_scrape (@ %d:00), "
        "outreach (9-20 every 2h), daily_summary (@ 21:00).",
        SCRAPE_SCHEDULE_HOUR,
    )


def shutdown_scheduler() -> None:
    """Gracefully shut down the scheduler."""
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("Scheduler shut down.")
