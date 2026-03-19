"""Unit tests for Indian phone number validation and normalization."""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from phase1_leads.dedup import validate_indian_phone, _normalize_phone


class TestValidateIndianPhone:
    """Tests for the ``validate_indian_phone`` function."""

    def test_valid_10_digit_mobile(self):
        """Standard 10-digit Indian mobile number."""
        valid, result = validate_indian_phone("9876543210")
        assert valid is True
        assert result == "+919876543210"

    def test_valid_with_country_code_plus91(self):
        """Number with +91 prefix."""
        valid, result = validate_indian_phone("+919876543210")
        assert valid is True
        assert result == "+919876543210"

    def test_valid_with_country_code_91(self):
        """Number with 91 prefix (no +)."""
        valid, result = validate_indian_phone("919876543210")
        assert valid is True
        assert result == "+919876543210"

    def test_valid_with_leading_zero(self):
        """Number with leading 0 (trunk prefix)."""
        valid, result = validate_indian_phone("09876543210")
        assert valid is True
        assert result == "+919876543210"

    def test_valid_with_spaces_and_dashes(self):
        """Number with formatting characters."""
        valid, result = validate_indian_phone("+91 98765-43210")
        assert valid is True
        assert result == "+919876543210"

    def test_valid_with_parentheses(self):
        """Number with parentheses."""
        valid, result = validate_indian_phone("(+91) 98765 43210")
        assert valid is True
        assert result == "+919876543210"

    def test_starts_with_6(self):
        """Valid: starting with 6."""
        valid, _ = validate_indian_phone("6123456789")
        assert valid is True

    def test_starts_with_7(self):
        """Valid: starting with 7."""
        valid, _ = validate_indian_phone("7123456789")
        assert valid is True

    def test_starts_with_8(self):
        """Valid: starting with 8."""
        valid, _ = validate_indian_phone("8123456789")
        assert valid is True

    def test_starts_with_9(self):
        """Valid: starting with 9."""
        valid, _ = validate_indian_phone("9123456789")
        assert valid is True

    def test_invalid_starts_with_5(self):
        """Invalid: Indian mobiles don't start with 5."""
        valid, msg = validate_indian_phone("5123456789")
        assert valid is False
        assert "Invalid" in msg

    def test_invalid_starts_with_1(self):
        """Invalid: Indian mobiles don't start with 1."""
        valid, msg = validate_indian_phone("1234567890")
        assert valid is False

    def test_invalid_too_short(self):
        """Invalid: too few digits."""
        valid, msg = validate_indian_phone("987654")
        assert valid is False

    def test_invalid_too_long(self):
        """Invalid: too many digits."""
        valid, msg = validate_indian_phone("98765432101234")
        assert valid is False

    def test_invalid_empty(self):
        """Invalid: empty string."""
        valid, msg = validate_indian_phone("")
        assert valid is False

    def test_invalid_non_numeric(self):
        """Invalid: non-numeric input."""
        valid, msg = validate_indian_phone("abcdefghij")
        assert valid is False


class TestNormalizePhone:
    """Tests for the ``_normalize_phone`` helper."""

    def test_10_digit_gets_plus91(self):
        assert _normalize_phone("9876543210") == "+919876543210"

    def test_12_digit_with_91_prefix(self):
        assert _normalize_phone("919876543210") == "+919876543210"

    def test_already_formatted(self):
        assert _normalize_phone("+919876543210") == "+919876543210"

    def test_with_spaces(self):
        assert _normalize_phone("98765 43210") == "+919876543210"

    def test_empty_returns_empty(self):
        assert _normalize_phone("") == ""
