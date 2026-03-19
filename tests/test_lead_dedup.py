"""Unit tests for lead deduplication (phone + fuzzy matching)."""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from phase1_leads.dedup import deduplicate, _normalize_phone, validate_indian_phone


class TestDeduplicate:
    """Tests for the ``deduplicate`` function."""

    def test_removes_exact_phone_duplicates(self):
        """Leads with same phone as existing should be removed."""
        existing = [{"Phone": "+919876543210", "Name": "Test Shop"}]
        new_leads = [
            {"phone": "9876543210", "name": "Test Shop", "address": "Mumbai"},
            {"phone": "9123456789", "name": "New Shop", "address": "Delhi"},
        ]
        result = deduplicate(new_leads, existing)
        assert len(result) == 1
        assert result[0]["name"] == "New Shop"

    def test_removes_intra_batch_duplicates(self):
        """Two leads in the same batch with same phone should deduplicate."""
        new_leads = [
            {"phone": "9876543210", "name": "Shop A", "address": "Mumbai"},
            {"phone": "9876543210", "name": "Shop A Copy", "address": "Mumbai"},
        ]
        result = deduplicate(new_leads, [])
        assert len(result) == 1

    def test_keeps_different_phones(self):
        """Leads with different phones should all be kept."""
        new_leads = [
            {"phone": "9876543210", "name": "Shop A"},
            {"phone": "9876543211", "name": "Shop B"},
            {"phone": "9876543212", "name": "Shop C"},
        ]
        result = deduplicate(new_leads, [])
        assert len(result) == 3

    def test_skips_leads_without_phone(self):
        """Leads with empty phone should be skipped."""
        new_leads = [
            {"phone": "", "name": "No Phone Shop"},
            {"phone": "9876543210", "name": "Has Phone Shop"},
        ]
        result = deduplicate(new_leads, [])
        assert len(result) == 1
        assert result[0]["name"] == "Has Phone Shop"

    def test_handles_country_code_variations(self):
        """Same phone with different formatting should be detected as duplicate."""
        existing = [{"Phone": "+919876543210"}]
        new_leads = [
            {"phone": "919876543210", "name": "Shop A"},  # 91 prefix
        ]
        result = deduplicate(new_leads, existing)
        assert len(result) == 0

    def test_empty_inputs(self):
        """Empty inputs should return empty results."""
        assert deduplicate([], []) == []
        assert deduplicate([], [{"Phone": "9876543210"}]) == []

    def test_existing_with_lowercase_keys(self):
        """Should handle both uppercase and lowercase key variants."""
        existing = [{"phone": "9876543210", "name": "Test"}]
        new_leads = [{"phone": "9876543210", "name": "Test Copy"}]
        result = deduplicate(new_leads, existing)
        assert len(result) == 0


class TestFuzzyDedup:
    """Tests for fuzzy name + address matching (requires rapidfuzz)."""

    def test_fuzzy_match_similar_names_and_addresses(self):
        """Very similar names + addresses should be caught as duplicates."""
        try:
            from rapidfuzz import fuzz
        except ImportError:
            return  # Skip if rapidfuzz not installed

        existing = [{"Phone": "+919000000001", "Name": "Mumbai Hair Salon", "Address": "123 Main St, Andheri"}]
        new_leads = [
            {
                "phone": "9111111111",
                "name": "Mumbai Hair Salon",  # Exact name match
                "address": "123 Main Street, Andheri",  # Very similar address
            },
        ]
        result = deduplicate(new_leads, existing)
        # Should be caught as fuzzy duplicate (same name, very similar address)
        assert len(result) == 0

    def test_different_businesses_not_matched(self):
        """Completely different businesses should NOT be caught."""
        try:
            from rapidfuzz import fuzz
        except ImportError:
            return

        existing = [{"Phone": "+919000000001", "Name": "Pizza Palace", "Address": "Bandra"}]
        new_leads = [
            {"phone": "9111111111", "name": "Tech Solutions", "address": "Powai"},
        ]
        result = deduplicate(new_leads, existing)
        assert len(result) == 1
