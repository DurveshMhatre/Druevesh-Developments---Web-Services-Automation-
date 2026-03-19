"""
Google Maps scraper using Playwright (headless Chromium).

Searches for businesses of a given type in a city, extracts those
that do **not** have a website, and returns a list of lead dicts.
"""

from __future__ import annotations

import asyncio
import random
from typing import Any

from playwright.async_api import async_playwright, Page, TimeoutError as PwTimeout

from utils.logger import get_logger
from utils.telegram_alert import send_alert

logger = get_logger(__name__)

# ── Rotating user agents ─────────────────────────────────────────
_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
]


async def _random_delay(min_s: float = 2.0, max_s: float = 5.0) -> None:
    """Human-like random delay."""
    await asyncio.sleep(random.uniform(min_s, max_s))


async def _scroll_results(page: Page, panel_selector: str, max_scrolls: int = 20) -> None:
    """
    Scroll the Google Maps results panel to trigger lazy-loading.

    Stops when no new results appear after two consecutive scrolls.
    """
    prev_count = 0
    stale_rounds = 0

    for _ in range(max_scrolls):
        await page.evaluate(
            '(selector) => document.querySelector(selector)?.scrollBy(0, 800)',
            panel_selector,
        )
        await _random_delay(1.5, 3.0)

        current_count = await page.locator('[class*="Nv2PK"]').count()
        if current_count == prev_count:
            stale_rounds += 1
            if stale_rounds >= 2:
                break
        else:
            stale_rounds = 0
        prev_count = current_count


async def _extract_listings(page: Page) -> list[dict[str, Any]]:
    """
    Parse visible listing cards and extract structured data.

    Returns a list of dicts with keys:
    ``name``, ``phone``, ``address``, ``rating``, ``reviews``,
    ``website``, ``category``, ``maps_url``.
    """
    results: list[dict[str, Any]] = []
    cards = page.locator('[class*="Nv2PK"]')
    count = await cards.count()

    for i in range(count):
        card = cards.nth(i)
        try:
            # Click card to open side panel
            await card.click()
            await _random_delay(1.5, 2.5)

            name = ""
            phone = ""
            address = ""
            rating = 0.0
            reviews = 0
            website = ""
            category = ""
            maps_url = page.url

            # Name
            name_el = page.locator('h1[class*="DUwDvf"]')
            if await name_el.count():
                name = (await name_el.first.inner_text()).strip()

            # Rating
            rating_el = page.locator('div[class*="F7nice"] span[aria-hidden="true"]')
            if await rating_el.count():
                try:
                    rating = float((await rating_el.first.inner_text()).strip())
                except ValueError:
                    pass

            # Review count
            review_el = page.locator('div[class*="F7nice"] span[aria-label*="review"]')
            if await review_el.count():
                review_text = (await review_el.first.get_attribute("aria-label")) or ""
                digits = "".join(c for c in review_text if c.isdigit())
                reviews = int(digits) if digits else 0

            # Category
            cat_el = page.locator('button[class*="DkEaL"]')
            if await cat_el.count():
                category = (await cat_el.first.inner_text()).strip()

            # Address
            addr_el = page.locator('button[data-item-id="address"]')
            if await addr_el.count():
                address = (await addr_el.first.inner_text()).strip()

            # Phone
            phone_el = page.locator('button[data-item-id*="phone:tel:"]')
            if await phone_el.count():
                phone_attr = (await phone_el.first.get_attribute("data-item-id")) or ""
                phone = phone_attr.replace("phone:tel:", "").strip()

            # Website
            web_el = page.locator('a[data-item-id="authority"]')
            if await web_el.count():
                website = (await web_el.first.get_attribute("href")) or ""

            results.append({
                "name": name,
                "phone": phone,
                "address": address,
                "rating": rating,
                "reviews": reviews,
                "website": website,
                "category": category,
                "maps_url": maps_url,
            })

        except Exception as exc:
            logger.debug("Error extracting card %d: %s", i, exc)
            continue

    return results


async def _scrape_async(city: str, business_type: str) -> list[dict[str, Any]]:
    """Core async scraper implementation."""
    query = f"{business_type} in {city}"
    logger.info("Scraping Google Maps for: %s", query)

    leads: list[dict[str, Any]] = []

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True, args=["--disable-blink-features=AutomationControlled"])
        context = await browser.new_context(
            user_agent=random.choice(_USER_AGENTS),
            viewport={"width": 1280, "height": 800},
            locale="en-IN",
        )
        page = await context.new_page()

        try:
            # Navigate directly to search URL — bypasses search box and popups
            import urllib.parse
            search_url = f"https://www.google.com/maps/search/{urllib.parse.quote(query)}"
            await page.goto(search_url, timeout=60_000)
            await _random_delay(3, 5)

            # Dismiss "Use Google Maps in Chrome" promo if present
            try:
                no_thanks = page.locator('button:has-text("No thanks")')
                if await no_thanks.count() > 0:
                    await no_thanks.first.click()
                    await _random_delay(1, 2)
            except Exception:
                pass

            # Wait for results to load
            try:
                await page.wait_for_selector('[class*="Nv2PK"]', timeout=15_000)
            except PwTimeout:
                logger.warning("No results found for '%s'.", query)
                await browser.close()
                return []

            # Scroll to load more results
            results_panel = 'div[role="feed"]'
            await _scroll_results(page, results_panel)

            # Extract data
            all_listings = await _extract_listings(page)

            import re

            # Filter: keep only leads WITHOUT a website AND WITH a phone number
            for listing in all_listings:
                if not listing["website"] and listing["phone"]:
                    # Classify the phone number as mobile or landline
                    raw_phone = listing["phone"]
                    digits = re.sub(r"\D", "", raw_phone)

                    # Strip leading "91" country code if present
                    if digits.startswith("91") and len(digits) == 12:
                        digits = digits[2:]

                    # Indian mobile numbers: exactly 10 digits starting with 6, 7, 8, or 9
                    if len(digits) == 10 and digits[0] in "6789":
                        listing["phone_type"] = "mobile"
                    else:
                        listing["phone_type"] = "landline"

                    listing["city"] = city
                    listing["type"] = business_type
                    listing["source"] = "google_maps"
                    leads.append(listing)

            logger.info(
                "Google Maps: found %d total listings, %d without website for '%s'.",
                len(all_listings), len(leads), query,
            )

        except Exception as exc:
            logger.error("Google Maps scraper crashed for '%s': %s", query, exc)
            # Take screenshot for debugging
            try:
                screenshot_path = f"logs/gmaps_error_{city}_{business_type}.png"
                await page.screenshot(path=screenshot_path)
                logger.info("Error screenshot saved: %s", screenshot_path)
            except Exception:
                pass
            send_alert(
                f"Google Maps scraper crashed for <b>{query}</b>:\n<code>{exc}</code>",
                level="error",
            )
        finally:
            await browser.close()

    return leads


def scrape(city: str, business_type: str) -> list[dict[str, Any]]:
    """
    Scrape Google Maps for businesses without websites.

    Args:
        city: Target city (e.g., ``"Delhi"``).
        business_type: Business category (e.g., ``"Restaurant"``).

    Returns:
        List of lead dicts with keys: ``name``, ``phone``, ``address``,
        ``rating``, ``reviews``, ``website``, ``category``, ``maps_url``,
        ``city``, ``type``, ``source``.
    """
    # Handle case where event loop is already running (e.g. APScheduler thread)
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as pool:
            return pool.submit(asyncio.run, _scrape_async(city, business_type)).result()
    else:
        return asyncio.run(_scrape_async(city, business_type))
