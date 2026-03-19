"""
Rule-based lead scoring (no AI required).

Assigns an integer score 1-100 based on attributes such as whether the
business already has a website, its Google rating, review count, and
business type.
"""

from __future__ import annotations

from config.settings import HIGH_VALUE_TYPES
from utils.logger import get_logger

logger = get_logger(__name__)


def score_lead(
    has_website: bool,
    rating: float,
    reviews: int,
    business_type: str,
    source: str,
) -> int:
    """
    Calculate a lead quality score.

    Args:
        has_website: ``True`` if the business already has a website.
        rating: Average star rating (0-5).
        reviews: Total review count.
        business_type: Category string (e.g., ``"Salon"``).
        source: Data source (``"google_maps"`` or ``"justdial"``).

    Returns:
        Integer score in the range 1-100.
    """
    score = 50

    # No website → high need for our service
    if not has_website:
        score += 25

    # Good rating → established, can likely afford a website
    if rating >= 4.0:
        score += 10
    elif rating >= 3.0:
        score += 5

    # Active business with reviews → more likely to invest
    if reviews >= 50:
        score += 15
    elif reviews >= 20:
        score += 10
    elif reviews >= 5:
        score += 5

    # High-value business types → historically higher conversion
    if business_type.strip().title() in HIGH_VALUE_TYPES:
        score += 5

    # Google Maps source tends to provide higher-quality data
    if source == "google_maps":
        score += 5

    final = max(1, min(score, 100))
    logger.debug(
        "Scored lead: website=%s rating=%.1f reviews=%d type=%s source=%s → %d",
        has_website, rating, reviews, business_type, source, final,
    )
    return final


def score_lead_dict(lead: dict) -> int:
    """
    Convenience wrapper that accepts a lead dict (as returned by scrapers).

    Adds the computed score to the dict under the ``"score"`` key and
    returns it.
    """
    has_website = bool(lead.get("website"))
    rating = float(lead.get("rating", 0) or 0)
    reviews = int(lead.get("reviews", 0) or 0)
    business_type = str(lead.get("type", "") or lead.get("category", ""))
    source = str(lead.get("source", ""))

    s = score_lead(has_website, rating, reviews, business_type, source)
    lead["score"] = s

    # Set status based on score
    if s >= 60:
        lead["status"] = "Ready for Outreach"
    else:
        lead["status"] = "Low Priority"

    return s
