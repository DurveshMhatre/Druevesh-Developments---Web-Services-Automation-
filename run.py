"""
Entrypoint script for the AI Web Automation project.

Usage:
    python run.py                  Start the FastAPI server (normal mode)
    python run.py --scrape-test    Run a single test scrape (1 city, 1 type)
    python run.py --send-test      Send a test WhatsApp message to yourself
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

# Ensure project root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))


def main() -> None:
    parser = argparse.ArgumentParser(description="AI Web Automation Runner")
    parser.add_argument(
        "--scrape-test",
        action="store_true",
        help="Run a test scrape for the first city/type combo and print results.",
    )
    parser.add_argument(
        "--send-test",
        type=str,
        metavar="PHONE",
        help="Send a test WhatsApp message to the given phone number (e.g. 919876543210).",
    )
    args = parser.parse_args()

    if args.scrape_test:
        _run_scrape_test()
    elif args.send_test:
        _run_send_test(args.send_test)
    else:
        _run_server()


def _run_server() -> None:
    """Start the FastAPI server."""
    import uvicorn
    from config.settings import SERVER_HOST, SERVER_PORT

    print(f"🚀 Starting server on {SERVER_HOST}:{SERVER_PORT}...")
    uvicorn.run(
        "server.app:app",
        host=SERVER_HOST,
        port=SERVER_PORT,
        reload=False,
        log_level="info",
    )


def _run_scrape_test() -> None:
    """Run a quick test scrape with the first city and business type."""
    from config.settings import BUSINESS_TYPES, TARGET_CITIES
    from phase1_leads.google_maps_scraper import scrape as scrape_gmaps
    from phase1_leads.lead_scorer import score_lead_dict
    from utils.sheets_client import append_leads

    city = TARGET_CITIES[0] if TARGET_CITIES else "Mumbai"
    btype = BUSINESS_TYPES[0] if BUSINESS_TYPES else "Restaurant"

    print(f"🔍 Test scraping Google Maps for: {btype} in {city}...")
    leads = scrape_gmaps(city, btype)

    print(f"\n📋 Found {len(leads)} leads without a website:\n")
    for i, lead in enumerate(leads, 1):
        score_lead_dict(lead)
        print(
            f"  {i}. {lead['name']}"
            f"  📱 {lead.get('phone', 'N/A')}"
            f"  ⭐ {lead.get('rating', 0)}"
            f"  💯 Score: {lead.get('score', '?')}"
            f"  [{lead.get('status', '')}]"
        )

    if not leads:
        print("  (No leads found — this is normal if Google blocked the request)")
    else:
        print("\n💾 Saving leads to Google Sheets...")
        try:
            saved_count = append_leads(leads)
            print(f"✅ Successfully saved {saved_count} leads to Google Sheets!")
            print(f"🔗 Check your sheet here: https://docs.google.com/spreadsheets/d/{__import__('config.settings', fromlist=['GOOGLE_SHEETS_ID']).GOOGLE_SHEETS_ID}")
        except Exception as e:
            print(f"❌ Failed to save to Sheets: {e}")

    print(f"\n✅ Scrape test complete. {len(leads)} leads found.")


def _run_send_test(phone: str) -> None:
    """Send a test message via WhatsApp to verify the API setup."""
    from config.settings import WHATSAPP_MODE

    test_message = (
        "👋 This is a test message from AI Web Automation.\n"
        "If you received this, your WhatsApp setup is working! ✅"
    )

    print(f"📤 Sending test message to {phone} via {WHATSAPP_MODE}...")

    if WHATSAPP_MODE == "meta_cloud":
        from phase2_whatsapp.meta_cloud_api import send_text_message
        result = asyncio.run(send_text_message(phone, test_message))
        print(f"✅ Message sent! API response: {result}")
    else:
        from phase2_whatsapp.whatsapp_web_js.bridge import send_message
        result = asyncio.run(send_message(phone, test_message))
        print(f"✅ Message sent! Response: {result}")


if __name__ == "__main__":
    main()
