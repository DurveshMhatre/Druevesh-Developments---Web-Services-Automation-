"""Comprehensive unit tests for phone_utils (21 tests)."""

from utils.phone_utils import normalize_phone, validate_indian_phone, classify_phone_type


# ══════════════════════════════════════════════════════════════════
#  normalize_phone()
# ══════════════════════════════════════════════════════════════════


class TestNormalizePhone:
    """Tests for normalize_phone()."""

    def test_10_digit_gets_plus91(self):
        assert normalize_phone("9876543210") == "+919876543210"

    def test_12_digit_with_91_prefix(self):
        assert normalize_phone("919876543210") == "+919876543210"

    def test_already_formatted_plus91(self):
        assert normalize_phone("+919876543210") == "+919876543210"

    def test_with_spaces(self):
        assert normalize_phone("98765 43210") == "+919876543210"

    def test_with_dashes(self):
        assert normalize_phone("98-7654-3210") == "+919876543210"

    def test_with_parentheses_and_spaces(self):
        assert normalize_phone("(+91) 98765 43210") == "+919876543210"

    def test_empty_returns_empty(self):
        assert normalize_phone("") == ""

    def test_non_numeric_returns_empty(self):
        assert normalize_phone("abcdefghij") == ""

    def test_short_number(self):
        """Numbers shorter than 10 digits get + prefix only."""
        result = normalize_phone("12345")
        assert result == "+12345"


# ══════════════════════════════════════════════════════════════════
#  validate_indian_phone()
# ══════════════════════════════════════════════════════════════════


class TestValidateIndianPhone:
    """Tests for validate_indian_phone()."""

    def test_valid_10_digit_mobile(self):
        valid, result = validate_indian_phone("9876543210")
        assert valid is True
        assert result == "+919876543210"

    def test_valid_with_plus91(self):
        valid, result = validate_indian_phone("+919876543210")
        assert valid is True
        assert result == "+919876543210"

    def test_valid_with_91_no_plus(self):
        valid, result = validate_indian_phone("919876543210")
        assert valid is True
        assert result == "+919876543210"

    def test_valid_with_leading_zero(self):
        valid, result = validate_indian_phone("09876543210")
        assert valid is True
        assert result == "+919876543210"

    def test_valid_with_spaces_and_dashes(self):
        valid, result = validate_indian_phone("+91 98765-43210")
        assert valid is True
        assert result == "+919876543210"

    def test_valid_with_parentheses(self):
        valid, result = validate_indian_phone("(+91) 98765 43210")
        assert valid is True
        assert result == "+919876543210"

    def test_starts_with_6(self):
        valid, _ = validate_indian_phone("6123456789")
        assert valid is True

    def test_starts_with_7(self):
        valid, _ = validate_indian_phone("7123456789")
        assert valid is True

    def test_starts_with_8(self):
        valid, _ = validate_indian_phone("8123456789")
        assert valid is True

    def test_starts_with_9(self):
        valid, _ = validate_indian_phone("9123456789")
        assert valid is True

    def test_invalid_starts_with_5(self):
        valid, msg = validate_indian_phone("5123456789")
        assert valid is False
        assert "Invalid" in msg

    def test_invalid_starts_with_1(self):
        valid, _ = validate_indian_phone("1234567890")
        assert valid is False

    def test_invalid_too_short(self):
        valid, _ = validate_indian_phone("987654")
        assert valid is False

    def test_invalid_too_long(self):
        valid, _ = validate_indian_phone("98765432101234")
        assert valid is False

    def test_invalid_empty(self):
        valid, _ = validate_indian_phone("")
        assert valid is False

    def test_invalid_non_numeric(self):
        valid, _ = validate_indian_phone("abcdefghij")
        assert valid is False


# ══════════════════════════════════════════════════════════════════
#  classify_phone_type()
# ══════════════════════════════════════════════════════════════════


class TestClassifyPhoneType:
    """Tests for classify_phone_type()."""

    def test_mobile_10_digit(self):
        assert classify_phone_type("9876543210") == "mobile"

    def test_mobile_with_91_prefix(self):
        assert classify_phone_type("919876543210") == "mobile"

    def test_landline_8_digit(self):
        assert classify_phone_type("02212345678") == "landline"

    def test_unknown_short(self):
        assert classify_phone_type("12345") == "unknown"

    def test_empty_unknown(self):
        assert classify_phone_type("") == "unknown"
