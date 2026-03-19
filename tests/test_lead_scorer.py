"""Unit tests for the lead scorer."""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from phase1_leads.lead_scorer import score_lead, score_lead_dict


class TestScoreLead:
    """Tests for the ``score_lead`` function."""

    def test_no_website_gets_high_score(self):
        """Business without a website should score >= 75."""
        s = score_lead(
            has_website=False, rating=4.0, reviews=20,
            business_type="Restaurant", source="google_maps",
        )
        assert s >= 75

    def test_with_website_gets_lower_score(self):
        """Business with a website should score lower than one without."""
        with_site = score_lead(
            has_website=True, rating=4.0, reviews=20,
            business_type="Restaurant", source="google_maps",
        )
        without_site = score_lead(
            has_website=False, rating=4.0, reviews=20,
            business_type="Restaurant", source="google_maps",
        )
        assert without_site > with_site

    def test_score_never_exceeds_100(self):
        """Score must never go above 100."""
        s = score_lead(
            has_website=False, rating=5.0, reviews=1000,
            business_type="Salon", source="google_maps",
        )
        assert s <= 100

    def test_score_never_below_1(self):
        """Score must never go below 1."""
        s = score_lead(
            has_website=True, rating=0.0, reviews=0,
            business_type="Other", source="unknown",
        )
        assert s >= 1

    def test_high_value_business_bonus(self):
        """High-value types (Salon, Clinic) should score higher."""
        high = score_lead(
            has_website=False, rating=3.5, reviews=10,
            business_type="Salon", source="justdial",
        )
        low = score_lead(
            has_website=False, rating=3.5, reviews=10,
            business_type="Other", source="justdial",
        )
        assert high > low

    def test_google_maps_source_bonus(self):
        """Google Maps source should add a bonus."""
        gmaps = score_lead(
            has_website=False, rating=3.0, reviews=3,
            business_type="Other", source="google_maps",
        )
        jd = score_lead(
            has_website=False, rating=3.0, reviews=3,
            business_type="Other", source="justdial",
        )
        assert gmaps > jd

    def test_high_review_count_bonus(self):
        """50+ reviews should get the maximum review bonus."""
        many = score_lead(
            has_website=False, rating=4.0, reviews=100,
            business_type="Restaurant", source="google_maps",
        )
        few = score_lead(
            has_website=False, rating=4.0, reviews=3,
            business_type="Restaurant", source="google_maps",
        )
        assert many > few


class TestScoreLeadDict:
    """Tests for the ``score_lead_dict`` convenience wrapper."""

    def test_adds_score_to_dict(self):
        lead = {"name": "Test", "phone": "9876543210", "rating": 4.5, "reviews": 30}
        score_lead_dict(lead)
        assert "score" in lead
        assert isinstance(lead["score"], int)

    def test_sets_status_ready(self):
        """Lead with no website + good rating → status should be 'Ready for Outreach'."""
        lead = {"rating": 4.5, "reviews": 30, "website": "", "type": "Salon", "source": "google_maps"}
        score_lead_dict(lead)
        assert lead["status"] == "Ready for Outreach"

    def test_sets_status_low_priority(self):
        """Lead with website → lower score → 'Low Priority'."""
        lead = {"rating": 2.0, "reviews": 0, "website": "https://example.com", "type": "Other", "source": "unknown"}
        score_lead_dict(lead)
        assert lead["status"] == "Low Priority"
