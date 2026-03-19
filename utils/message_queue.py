"""
Message queue for outgoing WhatsApp messages.

Provides:
- Priority queue (new leads > follow-ups)
- Rate-limiting to respect WhatsApp's 1 msg/sec limit
- Retry failed sends up to 3x with jittered delays
- Logging of all send attempts
"""

from __future__ import annotations

import asyncio
import random
import time
import threading
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any, Callable, Awaitable

from utils.logger import get_logger

logger = get_logger(__name__)


class MessagePriority(IntEnum):
    """Priority levels for outgoing messages (lower = higher priority)."""
    URGENT = 0       # Admin alerts, error notifications
    NEW_LEAD = 1     # First cold message to a new lead
    FOLLOW_UP = 2    # Follow-up messages
    BULK = 3         # Bulk / scheduled messages


@dataclass(order=True)
class QueuedMessage:
    """A message queued for sending."""
    priority: int
    phone: str = field(compare=False)
    text: str = field(compare=False)
    retries: int = field(default=0, compare=False)
    max_retries: int = field(default=3, compare=False)
    created_at: float = field(default_factory=time.time, compare=False)


class MessageQueue:
    """
    Thread-safe priority queue for outgoing WhatsApp messages.

    Rate-limits sending to 1 message per second and retries failures
    with jittered exponential backoff.
    """

    def __init__(self, rate_limit_delay: float = 1.0) -> None:
        self._queue: list[QueuedMessage] = []
        self._lock = threading.Lock()
        self._rate_limit_delay = rate_limit_delay
        self._last_send_time: float = 0.0
        self._total_sent = 0
        self._total_failed = 0

    def enqueue(
        self,
        phone: str,
        text: str,
        priority: MessagePriority = MessagePriority.NEW_LEAD,
    ) -> None:
        """Add a message to the queue."""
        msg = QueuedMessage(
            priority=priority.value,
            phone=phone,
            text=text,
        )
        with self._lock:
            self._queue.append(msg)
            self._queue.sort()  # sort by priority
        logger.debug(
            "Message queued for %s (priority=%s, queue_size=%d)",
            phone, priority.name, len(self._queue),
        )

    def _pop_next(self) -> QueuedMessage | None:
        """Pop the highest-priority message from the queue."""
        with self._lock:
            if self._queue:
                return self._queue.pop(0)
        return None

    async def process_queue(
        self,
        send_func: Callable[[str, str], Awaitable[Any]],
        max_messages: int = 50,
    ) -> dict[str, int]:
        """
        Process queued messages using the provided async send function.

        Args:
            send_func: Async function(phone, text) to send a message.
            max_messages: Maximum messages to process in one batch.

        Returns:
            Dict with ``sent``, ``failed``, ``requeued`` counts.
        """
        sent = 0
        failed = 0
        requeued = 0

        for _ in range(max_messages):
            msg = self._pop_next()
            if msg is None:
                break

            # Rate limiting — wait if we sent too recently
            now = time.time()
            elapsed = now - self._last_send_time
            if elapsed < self._rate_limit_delay:
                await asyncio.sleep(self._rate_limit_delay - elapsed)

            try:
                await send_func(msg.phone, msg.text)
                self._last_send_time = time.time()
                self._total_sent += 1
                sent += 1
                logger.info("Message sent to %s (attempt %d).", msg.phone, msg.retries + 1)
            except Exception as exc:
                msg.retries += 1
                if msg.retries < msg.max_retries:
                    # Requeue with jittered delay
                    jitter = random.uniform(0.5, 2.0)
                    await asyncio.sleep(jitter)
                    with self._lock:
                        self._queue.append(msg)
                        self._queue.sort()
                    requeued += 1
                    logger.warning(
                        "Send to %s failed (attempt %d/%d): %s — requeued.",
                        msg.phone, msg.retries, msg.max_retries, exc,
                    )
                else:
                    self._total_failed += 1
                    failed += 1
                    logger.error(
                        "Send to %s permanently failed after %d attempts: %s",
                        msg.phone, msg.max_retries, exc,
                    )

        result = {"sent": sent, "failed": failed, "requeued": requeued}
        logger.info("Queue batch result: %s", result)
        return result

    def get_status(self) -> dict[str, int]:
        """Return queue stats for monitoring."""
        with self._lock:
            pending = len(self._queue)
        return {
            "pending": pending,
            "total_sent": self._total_sent,
            "total_failed": self._total_failed,
        }

    @property
    def size(self) -> int:
        with self._lock:
            return len(self._queue)


# ── Singleton instance ───────────────────────────────────────────
outgoing_queue = MessageQueue(rate_limit_delay=1.0)
