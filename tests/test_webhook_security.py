"""Unit tests for webhook signature verification security."""

import hashlib
import hmac


class TestVerifySignature:
    """Tests for _verify_signature in server/app.py."""

    def _make_signature(self, payload: bytes, secret: str) -> str:
        """Helper: compute valid HMAC-SHA256 signature."""
        return hmac.new(
            secret.encode("utf-8"), payload, hashlib.sha256
        ).hexdigest()

    def test_valid_sha256_prefixed_signature(self):
        """Standard Meta format: sha256=<hex>."""
        from server.app import _verify_signature

        payload = b'{"test": "data"}'
        secret = "test_secret_key"
        sig = f"sha256={self._make_signature(payload, secret)}"

        assert _verify_signature(payload, sig, secret) is True

    def test_valid_raw_hex_signature(self):
        """Raw hex format (no sha256= prefix)."""
        from server.app import _verify_signature

        payload = b'{"test": "data"}'
        secret = "test_secret_key"
        sig = self._make_signature(payload, secret)

        assert _verify_signature(payload, sig, secret) is True

    def test_invalid_signature(self):
        """Wrong signature should fail."""
        from server.app import _verify_signature

        payload = b'{"test": "data"}'
        secret = "test_secret_key"

        assert _verify_signature(payload, "sha256=deadbeef1234", secret) is False

    def test_empty_signature(self):
        """Empty signature should fail."""
        from server.app import _verify_signature

        assert _verify_signature(b"data", "", "secret") is False

    def test_empty_secret(self):
        """Empty secret should fail."""
        from server.app import _verify_signature

        assert _verify_signature(b"data", "sha256=abc", "") is False

    def test_tampered_payload(self):
        """Signature computed for different payload should fail."""
        from server.app import _verify_signature

        secret = "test_secret"
        original = b'{"amount": 100}'
        sig = f"sha256={self._make_signature(original, secret)}"

        tampered = b'{"amount": 999}'
        assert _verify_signature(tampered, sig, secret) is False

    def test_wrong_secret(self):
        """Signature computed with different secret should fail."""
        from server.app import _verify_signature

        payload = b'{"data": true}'
        sig = f"sha256={self._make_signature(payload, 'secret_a')}"

        assert _verify_signature(payload, sig, "secret_b") is False
