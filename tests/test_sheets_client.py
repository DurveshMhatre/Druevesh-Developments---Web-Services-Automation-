"""
Integration test for Google Sheets client.

These tests require valid OAuth credentials and a configured spreadsheet.
They are skipped by default — run with: pytest tests/test_sheets_client.py -v --runintegration
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Skip all tests in this module unless --runintegration is passed
pytestmark = pytest.mark.skipif(
    "not config.getoption('--runintegration')",
    reason="Integration tests require --runintegration flag and valid credentials",
)


class TestSheetsClient:
    """Integration tests for sheets_client.py."""

    def test_get_all_leads_returns_list(self):
        from utils.sheets_client import get_all_leads
        result = get_all_leads()
        assert isinstance(result, list)

    def test_phone_normalization(self):
        from utils.sheets_client import _normalize_phone
        assert _normalize_phone("9876543210") == "+919876543210"
        assert _normalize_phone("919876543210") == "+919876543210"
        assert _normalize_phone("+919876543210") == "+919876543210"
        assert _normalize_phone("98-7654-3210") == "+919876543210"

    def test_append_and_retrieve_lead(self):
        from utils.sheets_client import append_leads, get_lead_by_phone

        test_lead = {
            "name": "TEST_AUTOMATED",
            "phone": "9999999999",
            "type": "Test",
            "city": "TestCity",
            "rating": 5.0,
            "reviews": 100,
            "score": 95,
            "website": "",
            "source": "test",
            "status": "Test",
        }

        count = append_leads([test_lead])
        assert count == 1

        retrieved = get_lead_by_phone("9999999999")
        assert retrieved is not None
        assert retrieved["Name"] == "TEST_AUTOMATED"
