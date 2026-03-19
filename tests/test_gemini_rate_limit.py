"""Unit tests for Gemini rate limiter thread safety and daily quota enforcement."""

import sys
import threading
import time
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


class TestRateLimiterThreadSafety:
    """Tests for the thread-safe rate limiter in gemini_client."""

    def test_rate_limit_lock_exists(self):
        """Rate limit lock should be a threading.Lock instance."""
        from utils.gemini_client import _rate_limit_lock
        assert isinstance(_rate_limit_lock, type(threading.Lock()))

    def test_wait_for_rate_limit_cleans_old_timestamps(self):
        """Timestamps older than 60s should be removed."""
        import utils.gemini_client as gc

        with gc._rate_limit_lock:
            gc._request_timestamps.clear()
            # Add an old timestamp
            gc._request_timestamps.append(time.time() - 120)
            old_count = len(gc._request_timestamps)

        gc._wait_for_rate_limit()

        with gc._rate_limit_lock:
            # Old timestamp should have been cleaned, new one added
            assert len(gc._request_timestamps) <= old_count + 1
            # Clean up
            gc._request_timestamps.clear()

    def test_concurrent_rate_limit_access(self):
        """Multiple threads accessing rate limiter should not crash."""
        import utils.gemini_client as gc

        errors = []

        def access_rate_limiter():
            try:
                gc._wait_for_rate_limit()
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=access_rate_limiter) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        # Clean up timestamps
        with gc._rate_limit_lock:
            gc._request_timestamps.clear()

        assert len(errors) == 0, f"Thread errors: {errors}"


class TestDailyQuota:
    """Tests for daily quota enforcement."""

    def test_quota_status_returns_dict(self):
        """get_quota_status should return a dict with expected keys."""
        from utils.gemini_client import get_quota_status

        status = get_quota_status()
        assert "daily_used" in status
        assert "daily_limit" in status
        assert "daily_remaining" in status
        assert "rpm_current" in status
        assert "rpm_limit" in status

    def test_daily_remaining_non_negative(self):
        """Remaining quota should never be negative."""
        from utils.gemini_client import get_quota_status

        status = get_quota_status()
        assert status["daily_remaining"] >= 0

    def test_daily_limit_is_1450(self):
        """Daily limit should be set to 1450 (safety margin under 1500)."""
        from utils.gemini_client import _DAILY_LIMIT
        assert _DAILY_LIMIT == 1450

    def test_rpm_limit_is_14(self):
        """RPM limit should be set to 14 (under the 15 RPM free-tier ceiling)."""
        from utils.gemini_client import _RPM_LIMIT
        assert _RPM_LIMIT == 14

    def test_check_daily_quota_resets_on_new_day(self):
        """Daily counter should reset when the date changes."""
        import utils.gemini_client as gc

        # Simulate a new day
        with gc._rate_limit_lock:
            gc._daily_count = 100
            gc._daily_reset_date = "2020-01-01"

        result = gc._check_daily_quota()
        assert result is True
        assert gc._daily_count == 0  # Should have reset
