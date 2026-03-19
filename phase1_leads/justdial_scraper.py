"""
JustDial scraper using Requests + BeautifulSoup.

JustDial listings are server-rendered HTML, so no headless browser is needed.
Phone numbers are obfuscated using CSS sprite tricks — this module includes
the decoding logic.
"""

from __future__ import annotations

import random
import re
import time
from typing import Any

import requests
from bs4 import BeautifulSoup

from utils.logger import get_logger
from utils.telegram_alert import send_alert

logger = get_logger(__name__)

# ── Constants ────────────────────────────────────────────────────
_BASE_URL = "https://www.justdial.com/{city}/{category}"

_HEADERS_LIST = [
    {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept-Language": "en-IN,en;q=0.9",
    },
    {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
        "Accept-Language": "en-US,en;q=0.9,hi;q=0.8",
    },
    {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
        "Accept-Language": "en-IN,en;q=0.9",
    },
]

# JustDial encodes digits into CSS class names. This maps class → digit.
_JD_PHONE_MAP = {
    "icon-acb": "0",
    "icon-igh": "1",
    "icon-dee": "2",
    "icon-fab": "3",
    "icon-dcb": "4",
    "icon-ehg": "5",
    "icon-gfe": "6",
    "icon-hgf": "7",
    "icon-fed": "8",
    "icon-bac": "9",
    # Alternate encoding (newer pages)
    "acb": "0",
    "igh": "1",
    "dee": "2",
    "fab": "3",
    "dcb": "4",
    "ehg": "5",
    "gfe": "6",
    "hgf": "7",
    "fed": "8",
    "bac": "9",
}

_MAX_PAGES = 10  # Max pages to scrape per category
_REQUEST_DELAY = (3.0, 5.0)  # Seconds between requests


def _decode_phone(phone_container: BeautifulSoup) -> str:
    """
    Decode an obfuscated JustDial phone number.

    JustDial hides digits using ``<span>`` tags with CSS class names
    that map to specific digits.
    """
    if phone_container is None:
        return ""

    spans = phone_container.find_all("span")
    digits: list[str] = []
    for span in spans:
        classes = span.get("class", [])
        for cls in classes:
            if cls in _JD_PHONE_MAP:
                digits.append(_JD_PHONE_MAP[cls])
                break

    phone = "".join(digits)
    return phone if len(phone) >= 10 else ""


def _parse_listing_page(html: str, city: str, category: str) -> list[dict[str, Any]]:
    """Parse a single page of JustDial listings."""
    soup = BeautifulSoup(html, "html.parser")
    listings: list[dict[str, Any]] = []

    # JustDial uses various container classes; try known patterns
    cards = soup.select("li.cntanr") or soup.select("div.store-details")

    for card in cards:
        try:
            # Name
            name_el = card.select_one("span.lng_cont_name, a.lng_cont_name, .store-name span")
            name = name_el.get_text(strip=True) if name_el else ""

            # Rating
            rating = 0.0
            rating_el = card.select_one("span.green-box, span.star_m, .green-box")
            if rating_el:
                try:
                    rating = float(rating_el.get_text(strip=True))
                except ValueError:
                    pass

            # Review count
            reviews = 0
            review_el = card.select_one("span.rt_count, .total-reviews")
            if review_el:
                text = review_el.get_text(strip=True)
                digits = re.sub(r"[^\d]", "", text)
                reviews = int(digits) if digits else 0

            # Address
            address = ""
            addr_el = card.select_one("span.cont_fl_addr, .address-info span")
            if addr_el:
                address = addr_el.get_text(strip=True)

            # Phone (obfuscated)
            phone_container = card.select_one("p.contact-info span.mobilesv, .contact-info")
            phone = _decode_phone(phone_container)

            # Skip if no name or phone
            if not name or not phone:
                continue

            # Classify phone type (consistent with google_maps_scraper)
            digits_only = re.sub(r"[^\d]", "", phone)
            if len(digits_only) == 10 and digits_only[0] in "6789":
                phone_type = "mobile"
            else:
                phone_type = "landline"

            listings.append({
                "name": name,
                "phone": phone,
                "phone_type": phone_type,
                "address": address,
                "rating": rating,
                "reviews": reviews,
                "website": "",  # JustDial listings typically don't have websites
                "category": category,
                "city": city,
                "type": category,
                "source": "justdial",
            })

        except Exception as exc:
            logger.debug("Error parsing JustDial card: %s", exc)
            continue

    return listings


def scrape(city: str, business_type: str) -> list[dict[str, Any]]:
    """
    Scrape JustDial for businesses in a given city and category.

    Args:
        city: Target city (e.g., ``"Delhi"``).
        business_type: Business category (e.g., ``"Restaurant"``).

    Returns:
        List of lead dicts.
    """
    # JustDial uses URL-friendly slugs
    city_slug = city.strip().capitalize()
    category_slug = business_type.strip().replace(" ", "-")

    logger.info("Scraping JustDial for: %s in %s", category_slug, city_slug)

    all_leads: list[dict[str, Any]] = []
    session = requests.Session()

    for page_num in range(1, _MAX_PAGES + 1):
        url = f"https://www.justdial.com/{city_slug}/{category_slug}"
        if page_num > 1:
            url += f"/page-{page_num}"

        headers = random.choice(_HEADERS_LIST)

        try:
            resp = session.get(url, headers=headers, timeout=15)
            if resp.status_code == 404:
                logger.info("JustDial: No more pages (404 on page %d).", page_num)
                break
            resp.raise_for_status()
        except requests.RequestException as exc:
            logger.warning("JustDial request failed (page %d): %s", page_num, exc)
            break

        page_leads = _parse_listing_page(resp.text, city_slug, business_type)

        if not page_leads:
            logger.info("JustDial: No listings found on page %d — stopping.", page_num)
            break

        all_leads.extend(page_leads)
        logger.debug("JustDial page %d: %d listings found.", page_num, len(page_leads))

        # Rate limiting
        time.sleep(random.uniform(*_REQUEST_DELAY))

    logger.info(
        "JustDial: scraped %d total leads for '%s in %s'.",
        len(all_leads), business_type, city,
    )

    if not all_leads:
        send_alert(
            f"JustDial scraper returned 0 results for <b>{business_type} in {city}</b>. "
            "The page structure may have changed.",
            level="warning",
        )

    return all_leads
