"""
Circuit breaker pattern for external API calls.

Tracks failure counts per service (Gemini, WhatsApp, Google Sheets) and
automatically stops calling a service after N consecutive failures.
After a configurable cooldown, allows a test request through (half-open state).

States:
    CLOSED   → Normal operation, all calls go through
    OPEN     → Service is failing, all calls are blocked
    HALF_OPEN → Cooldown expired, allow ONE test call to see if service recovered
"""

from __future__ import annotations

import threading
import time
from enum import Enum
from typing import Any, Callable

from utils.logger import get_logger

logger = get_logger(__name__)


class CircuitState(Enum):
    CLOSED = "closed"       # Normal — all calls pass through
    OPEN = "open"           # Failing — all calls blocked
    HALF_OPEN = "half_open"  # Testing — allow one call


class CircuitBreaker:
    """
    Thread-safe circuit breaker for an external service.

    Args:
        name: Human-readable service name (for logging).
        failure_threshold: Consecutive failures before opening the circuit.
        recovery_timeout: Seconds to wait in OPEN state before trying HALF_OPEN.
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
    ) -> None:
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_time: float = 0.0
        self._lock = threading.Lock()

    @property
    def state(self) -> CircuitState:
        with self._lock:
            if self._state == CircuitState.OPEN:
                # Check if cooldown has elapsed → transition to HALF_OPEN
                if time.time() - self._last_failure_time >= self.recovery_timeout:
                    self._state = CircuitState.HALF_OPEN
                    logger.info(
                        "Circuit breaker [%s]: OPEN → HALF_OPEN (cooldown elapsed).",
                        self.name,
                    )
            return self._state

    def is_call_allowed(self) -> bool:
        """Return True if a call should be allowed through."""
        return self.state in (CircuitState.CLOSED, CircuitState.HALF_OPEN)

    def record_success(self) -> None:
        """Record a successful call — reset failure count and close circuit."""
        with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                logger.info(
                    "Circuit breaker [%s]: HALF_OPEN → CLOSED (test call succeeded).",
                    self.name,
                )
            self._failure_count = 0
            self._state = CircuitState.CLOSED

    def record_failure(self) -> None:
        """Record a failed call — increment counter and potentially open circuit."""
        with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.time()

            if self._state == CircuitState.HALF_OPEN:
                # Test call failed — re-open
                self._state = CircuitState.OPEN
                logger.warning(
                    "Circuit breaker [%s]: HALF_OPEN → OPEN (test call failed).",
                    self.name,
                )
            elif self._failure_count >= self.failure_threshold:
                self._state = CircuitState.OPEN
                logger.warning(
                    "Circuit breaker [%s]: CLOSED → OPEN after %d consecutive failures.",
                    self.name, self._failure_count,
                )

    def call(self, func: Callable, *args: Any, **kwargs: Any) -> Any:
        """
        Execute a function through the circuit breaker.

        Raises:
            CircuitOpenError: If the circuit is open and calls are blocked.
        """
        if not self.is_call_allowed():
            raise CircuitOpenError(
                f"Circuit breaker [{self.name}] is OPEN — "
                f"calls blocked for {self.recovery_timeout}s after "
                f"{self._failure_count} failures."
            )

        try:
            result = func(*args, **kwargs)
            self.record_success()
            return result
        except Exception as exc:
            self.record_failure()
            raise exc

    async def async_call(self, func: Callable, *args: Any, **kwargs: Any) -> Any:
        """Execute an async function through the circuit breaker."""
        if not self.is_call_allowed():
            raise CircuitOpenError(
                f"Circuit breaker [{self.name}] is OPEN — "
                f"calls blocked for {self.recovery_timeout}s."
            )

        try:
            result = await func(*args, **kwargs)
            self.record_success()
            return result
        except Exception as exc:
            self.record_failure()
            raise exc

    def get_status(self) -> dict[str, Any]:
        """Return current circuit breaker status for monitoring."""
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self._failure_count,
            "failure_threshold": self.failure_threshold,
            "recovery_timeout": self.recovery_timeout,
        }


class CircuitOpenError(Exception):
    """Raised when a call is attempted through an open circuit breaker."""
    pass


# ══════════════════════════════════════════════════════════════════
#  Pre-configured breakers for external services
# ══════════════════════════════════════════════════════════════════

gemini_breaker = CircuitBreaker("Gemini API", failure_threshold=5, recovery_timeout=120)
whatsapp_breaker = CircuitBreaker("WhatsApp API", failure_threshold=3, recovery_timeout=60)
sheets_breaker = CircuitBreaker("Google Sheets", failure_threshold=5, recovery_timeout=90)
