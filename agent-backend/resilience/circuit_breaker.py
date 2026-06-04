"""Circuit Breaker — prevents cascading failures when LLM providers fail.

States:
- CLOSED: Normal operation, requests pass through
- OPEN: Too many failures, reject requests fast
- HALF_OPEN: Testing if service recovered

The breaker wraps calls to an external service.  When the failure count in
CLOSED state reaches *failure_threshold* the breaker snaps OPEN.  After
*recovery_timeout* seconds it transitions to HALF_OPEN and allows a limited
number of probe calls.  If those succeed the breaker closes again; if any
fail it re-opens immediately.
"""

from __future__ import annotations

import asyncio
import logging
import time
from enum import Enum
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger(__name__)


class CircuitState(str, Enum):
    """Finite states for the circuit breaker."""

    CLOSED = "closed"       # Normal operation
    OPEN = "open"           # Failing fast
    HALF_OPEN = "half_open" # Testing recovery


class CircuitBreakerError(Exception):
    """Raised when a call is rejected because the circuit is OPEN."""

    def __init__(self, name: str, message: str = "") -> None:
        self.name = name
        self.msg = message or f"Circuit '{name}' is OPEN"
        super().__init__(self.msg)


class CircuitBreaker:
    """Circuit breaker for external service calls.

    Parameters
    ----------
    name:
        Human-readable identifier (e.g. ``"openai-gpt-4"``).
    failure_threshold:
        Number of consecutive failures before snapping OPEN (default 5).
    recovery_timeout:
        Seconds to wait before moving OPEN -> HALF_OPEN (default 60).
    half_open_max_calls:
        Max probe calls allowed in HALF_OPEN state (default 3).
    expected_exception:
        Exception type (or tuple) that counts as a *failure*.  Other
        exceptions are re-raised without affecting breaker state.
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        half_open_max_calls: int = 3,
        expected_exception: type | tuple = Exception,
    ) -> None:
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls
        self.expected_exception = expected_exception

        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[float] = None
        self.half_open_calls = 0
        self._total_calls = 0
        self._total_failures = 0

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def call(self, fn: Callable, *args: Any, **kwargs: Any) -> Any:
        """Execute *fn* with circuit-breaker protection (synchronous).

        Raises
        ------
        CircuitBreakerError
            If the circuit is OPEN and the recovery timeout has not yet
            elapsed.
        """
        self._enforce_state()

        # Guard HALF_OPEN call budget
        if self.state == CircuitState.HALF_OPEN:
            if self.half_open_calls >= self.half_open_max_calls:
                raise CircuitBreakerError(
                    self.name, f"Circuit '{self.name}' HALF_OPEN call budget exhausted"
                )
            self.half_open_calls += 1

        self._total_calls += 1
        try:
            result = fn(*args, **kwargs)
        except self.expected_exception as exc:
            self._on_failure()
            raise
        else:
            self._on_success()
            return result

    async def call_async(self, fn: Callable, *args: Any, **kwargs: Any) -> Any:
        """Execute async *fn* with circuit-breaker protection.

        Same semantics as :meth:`call` but awaits a coroutine.
        """
        self._enforce_state()

        if self.state == CircuitState.HALF_OPEN:
            if self.half_open_calls >= self.half_open_max_calls:
                raise CircuitBreakerError(
                    self.name, f"Circuit '{self.name}' HALF_OPEN call budget exhausted"
                )
            self.half_open_calls += 1

        self._total_calls += 1
        try:
            if asyncio.iscoroutinefunction(fn):
                result = await fn(*args, **kwargs)
            else:
                result = fn(*args, **kwargs)
        except self.expected_exception:
            self._on_failure()
            raise
        else:
            self._on_success()
            return result

    def get_state(self) -> Dict[str, Any]:
        """Return a JSON-serialisable snapshot of breaker state."""
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "last_failure": self.last_failure_time,
            "half_open_calls": self.half_open_calls,
            "total_calls": self._total_calls,
            "total_failures": self._total_failures,
            "failure_threshold": self.failure_threshold,
            "recovery_timeout": self.recovery_timeout,
        }

    def reset(self) -> None:
        """Manually reset the breaker to CLOSED (useful for tests)."""
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = None
        self.half_open_calls = 0
        logger.info("Circuit '%s' manually reset to CLOSED", self.name)

    # ------------------------------------------------------------------ #
    # State transitions
    # ------------------------------------------------------------------ #

    def _enforce_state(self) -> None:
        """Check whether enough time has passed to move OPEN -> HALF_OPEN."""
        if self.state == CircuitState.OPEN:
            if self.last_failure_time is None:
                # Should never happen, but be defensive
                self._transition_to_half_open()
                return

            elapsed = time.time() - self.last_failure_time
            if elapsed >= self.recovery_timeout:
                self._transition_to_half_open()
            else:
                remaining = self.recovery_timeout - elapsed
                raise CircuitBreakerError(
                    self.name,
                    f"Circuit '{self.name}' is OPEN — retry in {remaining:.1f}s",
                )

    def _on_success(self) -> None:
        """Record a successful call and potentially transition states."""
        self.success_count += 1
        if self.state == CircuitState.HALF_OPEN:
            # If we've seen enough successes in HALF_OPEN, close the circuit
            if self.success_count >= self.half_open_max_calls:
                self._transition_to_closed()

    def _on_failure(self) -> None:
        """Record a failed call and potentially snap OPEN."""
        self.failure_count += 1
        self._total_failures += 1
        self.last_failure_time = time.time()

        if self.state == CircuitState.HALF_OPEN:
            # Any failure in HALF_OPEN re-opens immediately
            self._transition_to_open()
        elif self.state == CircuitState.CLOSED and self.failure_count >= self.failure_threshold:
            self._transition_to_open()

    def _transition_to_open(self) -> None:
        """CLOSED/HALF_OPEN -> OPEN."""
        prev = self.state.value
        self.state = CircuitState.OPEN
        logger.warning(
            "Circuit '%s' transitioned %s -> OPEN (failures=%d)",
            self.name,
            prev,
            self.failure_count,
        )

    def _transition_to_half_open(self) -> None:
        """OPEN -> HALF_OPEN after recovery timeout."""
        self.state = CircuitState.HALF_OPEN
        self.half_open_calls = 0
        self.failure_count = 0
        self.success_count = 0
        logger.info(
            "Circuit '%s' transitioned OPEN -> HALF_OPEN (probing)",
            self.name,
        )

    def _transition_to_closed(self) -> None:
        """HALF_OPEN -> CLOSED after successful probes."""
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.half_open_calls = 0
        self.last_failure_time = None
        logger.info(
            "Circuit '%s' transitioned HALF_OPEN -> CLOSED (recovered)",
            self.name,
        )
