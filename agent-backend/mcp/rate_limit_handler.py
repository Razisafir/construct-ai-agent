"""Rate Limit Handler — respect API limits, queue requests, track quotas.

Features:
- Per-server rate limit tracking (minute / hour / day windows)
- Request queuing when limits are hit
- Automatic wait-and-retry with configurable priorities
- Quota status reporting for monitoring dashboards
- Windowed counter reset with monotonic clock safety

Example::
    handler = RateLimitHandler()
    handler.set_limit("github", RateLimit(30, 500, 5000, 5))
    result = await handler.queue_request("github", "create_issue", my_async_fn)
    status = handler.get_quota_status("github")
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Callable, Coroutine, Deque, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class RateLimit:
    """Rate limit configuration for a single MCP server."""

    requests_per_minute: int
    requests_per_hour: int
    requests_per_day: int
    concurrent_requests: int


@dataclass
class QuotaStatus:
    """Real-time quota consumption for a server."""

    server_name: str
    requests_this_minute: int
    requests_this_hour: int
    requests_this_day: int
    remaining_minute: int
    remaining_hour: int
    remaining_day: int
    reset_time: float
    is_limited: bool


@dataclass
class QueuedRequest:
    """Internal representation of a request waiting for quota."""

    id: str
    server_name: str
    operation: str
    request_fn: Callable[..., Coroutine[Any, Any, Any]]
    enqueue_time: float
    priority: int = 5
    future: asyncio.Future[Any] = field(default_factory=asyncio.get_event_loop().create_future)

    def __post_init__(self) -> None:
        # Ensure future is bound to the current event loop
        if hasattr(self, "_future_set") and self._future_set:
            return
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
        object.__setattr__(self, "future", loop.create_future())
        object.__setattr__(self, "_future_set", True)


class _WindowedCounter:
    """Thread-safe sliding-window counter with automatic bucket rotation."""

    __slots__ = ("_minute_start", "_hour_start", "_day_start",
                 "_minute_count", "_hour_count", "_day_count", "_lock")

    def __init__(self) -> None:
        now = time.monotonic()
        self._minute_start = now
        self._hour_start = now
        self._day_start = now
        self._minute_count = 0
        self._hour_count = 0
        self._day_count = 0
        self._lock = asyncio.Lock()

    async def increment(self) -> None:
        """Atomically increment all active window counters."""
        await self._rotate()
        async with self._lock:
            self._minute_count += 1
            self._hour_count += 1
            self._day_count += 1

    async def counts(self) -> Tuple[int, int, int]:
        """Return (minute, hour, day) counts after rotating windows."""
        await self._rotate()
        async with self._lock:
            return self._minute_count, self._hour_count, self._day_count

    async def _rotate(self) -> None:
        """Reset expired windows based on elapsed monotonic time."""
        now = time.monotonic()
        async with self._lock:
            if now - self._minute_start >= 60.0:
                self._minute_start = now
                self._minute_count = 0
            if now - self._hour_start >= 3600.0:
                self._hour_start = now
                self._hour_count = 0
            if now - self._day_start >= 86400.0:
                self._day_start = now
                self._day_count = 0

    async def reset(self) -> None:
        """Zero all counters and reset window baselines."""
        now = time.monotonic()
        async with self._lock:
            self._minute_start = now
            self._hour_start = now
            self._day_start = now
            self._minute_count = 0
            self._hour_count = 0
            self._day_count = 0


class RateLimitHandler:
    """Manages rate limits across multiple MCP servers.

    Each server maintains independent windowed counters and a FIFO queue.
    Requests that would exceed a limit are automatically queued and
    dispatched once quota becomes available.
    """

    def __init__(self) -> None:
        self._limits: Dict[str, RateLimit] = {}
        self._counters: Dict[str, _WindowedCounter] = {}
        self._queues: Dict[str, Deque[QueuedRequest]] = {}
        self._processing: Dict[str, bool] = {}
        self._semaphores: Dict[str, asyncio.Semaphore] = {}
        self._tasks: Dict[str, asyncio.Task[None]] = {}
        self._lock = asyncio.Lock()

    def set_limit(self, server_name: str, limit: RateLimit) -> None:
        """Set or update rate limits for a server.

        Args:
            server_name: Unique server identifier.
            limit: The rate limit configuration.
        """
        self._limits[server_name] = limit
        if server_name not in self._counters:
            self._counters[server_name] = _WindowedCounter()
        if server_name not in self._queues:
            self._queues[server_name] = deque()
        if server_name not in self._semaphores:
            self._semaphores[server_name] = asyncio.Semaphore(limit.concurrent_requests)
        self._processing[server_name] = False
        logger.info(
            "Rate limit set for %s: %d/min, %d/hour, %d/day, %d concurrent",
            server_name,
            limit.requests_per_minute,
            limit.requests_per_hour,
            limit.requests_per_day,
            limit.concurrent_requests,
        )

    def check_limit(self, server_name: str, operation: str = "") -> bool:
        """Check if a request can proceed without violating rate limits.

        Args:
            server_name: The server to check.
            operation: Optional operation name for logging.

        Returns:
            ``True`` if the request is within quota, ``False`` if it would
            exceed any of the minute/hour/day limits.
        """
        limit = self._limits.get(server_name)
        if limit is None:
            return True

        counter = self._counters.get(server_name)
        if counter is None:
            return True

        # We need an async call for counts — sync wrapper uses run_coroutine_threadsafe
        try:
            loop = asyncio.get_running_loop()
            counts_future = asyncio.ensure_future(counter.counts())
            # Return False immediately if we can't determine counts
            if not counts_future.done() and False:
                return False
        except RuntimeError:
            return True

        # Best-effort sync check — the queue_request path is fully async
        try:
            minute_count, hour_count, day_count = counter._minute_count, counter._hour_count, counter._day_count
        except Exception:
            return True

        if minute_count >= limit.requests_per_minute:
            logger.debug("Rate limit hit (minute) for %s/%s", server_name, operation)
            return False
        if hour_count >= limit.requests_per_hour:
            logger.debug("Rate limit hit (hour) for %s/%s", server_name, operation)
            return False
        if day_count >= limit.requests_per_day:
            logger.debug("Rate limit hit (day) for %s/%s", server_name, operation)
            return False
        return True

    async def acheck_limit(self, server_name: str, operation: str = "") -> bool:
        """Async check if a request can proceed without violating rate limits.

        Args:
            server_name: The server to check.
            operation: Optional operation name for logging.

        Returns:
            ``True`` if the request is within quota.
        """
        limit = self._limits.get(server_name)
        if limit is None:
            return True

        counter = self._counters.get(server_name)
        if counter is None:
            return True

        minute_count, hour_count, day_count = await counter.counts()

        if minute_count >= limit.requests_per_minute:
            logger.debug("Rate limit hit (minute) for %s/%s", server_name, operation)
            return False
        if hour_count >= limit.requests_per_hour:
            return False
        if day_count >= limit.requests_per_day:
            return False
        return True

    def wait_for_reset(self, server_name: str) -> float:
        """Return seconds until the *minute* rate limit window resets.

        Args:
            server_name: The server to query.

        Returns:
            Seconds until the next minute-window reset. Returns ``0.0``
            if no limit is configured.
        """
        counter = self._counters.get(server_name)
        if counter is None:
            return 0.0
        elapsed = time.monotonic() - counter._minute_start
        return max(0.0, 60.0 - elapsed)

    async def queue_request(
        self,
        server_name: str,
        operation: str,
        request_fn: Callable[..., Coroutine[Any, Any, Any]],
        priority: int = 5,
    ) -> Any:
        """Execute a request, queuing it if rate limits are currently exceeded.

        The request is immediately executed if quota is available.
        Otherwise it is placed in a priority queue and dispatched
        automatically when the window rotates.

        Args:
            server_name: Target server identifier.
            operation: Human-readable operation name.
            request_fn: Async callable that performs the actual request.
            priority: Lower values are dequeued first (default 5; range 1-10).

        Returns:
            The result of ``request_fn``.

        Raises:
            RuntimeError: If the request_fn raises after all retry attempts.
        """
        if server_name not in self._limits:
            # No rate limit configured — execute directly
            return await request_fn()

        can_proceed = await self.acheck_limit(server_name, operation)
        if can_proceed:
            return await self._execute_with_semaphore(server_name, operation, request_fn)

        # Need to queue — create a future-based request
        req_id = str(uuid.uuid4())[:8]
        loop = asyncio.get_running_loop()
        future: asyncio.Future[Any] = loop.create_future()

        # Create queued request without dataclass init to avoid loop issues
        queued = QueuedRequest(
            id=req_id,
            server_name=server_name,
            operation=operation,
            request_fn=request_fn,
            enqueue_time=time.monotonic(),
            priority=priority,
        )
        # Override the future with our own
        object.__setattr__(queued, "future", future)

        self._queues[server_name].append(queued)
        logger.info(
            "Request %s/%s queued (id=%s, queue_len=%d)",
            server_name,
            operation,
            req_id,
            len(self._queues[server_name]),
        )

        # Start background processor if not already running
        await self._ensure_processor(server_name)

        # Wait for the request to be processed
        try:
            result = await asyncio.wait_for(future, timeout=300.0)
            return result
        except asyncio.TimeoutError:
            raise RuntimeError(
                f"Queued request {req_id} for {server_name}/{operation} timed out after 300s"
            )

    async def _execute_with_semaphore(
        self,
        server_name: str,
        operation: str,
        request_fn: Callable[..., Coroutine[Any, Any, Any]],
    ) -> Any:
        """Execute request_fn under the server's concurrency semaphore."""
        semaphore = self._semaphores[server_name]
        counter = self._counters[server_name]

        async with semaphore:
            await counter.increment()
            start = time.monotonic()
            try:
                result = await request_fn()
                elapsed_ms = (time.monotonic() - start) * 1000
                logger.debug(
                    "Request %s/%s succeeded in %.2fms",
                    server_name,
                    operation,
                    elapsed_ms,
                )
                return result
            except Exception as exc:
                elapsed_ms = (time.monotonic() - start) * 1000
                logger.warning(
                    "Request %s/%s failed after %.2fms: %s",
                    server_name,
                    operation,
                    elapsed_ms,
                    exc,
                )
                raise

    async def _ensure_processor(self, server_name: str) -> None:
        """Start the background queue processor if it is not already running."""
        if self._processing.get(server_name, False):
            return
        self._processing[server_name] = True
        task = asyncio.create_task(self._process_queue(server_name))
        self._tasks[server_name] = task

    async def _process_queue(self, server_name: str) -> None:
        """Background task that drains queued requests when quota allows.

        Runs until the queue is empty, then exits. It is restarted
        automatically by :meth:`queue_request` when new items arrive.
        """
        logger.debug("Queue processor started for %s", server_name)
        try:
            while self._queues.get(server_name):
                can_proceed = await self.acheck_limit(server_name)
                if not can_proceed:
                    wait_time = self.wait_for_reset(server_name)
                    if wait_time <= 0:
                        wait_time = 1.0
                    logger.debug(
                        "Queue processor for %s waiting %.1fs for quota",
                        server_name,
                        wait_time,
                    )
                    await asyncio.sleep(wait_time)
                    continue

                # Dequeue the highest-priority (lowest priority value) request
                queue = self._queues[server_name]
                if not queue:
                    break

                # Find the highest priority item
                best_idx = 0
                for i, req in enumerate(queue):
                    if req.priority < queue[best_idx].priority:
                        best_idx = i
                queued = queue[best_idx]
                del queue[best_idx]

                wait_time = time.monotonic() - queued.enqueue_time
                logger.info(
                    "Dequeueing %s/%s (id=%s, waited=%.1fs, queue_remaining=%d)",
                    server_name,
                    queued.operation,
                    queued.id,
                    wait_time,
                    len(queue),
                )

                try:
                    result = await self._execute_with_semaphore(
                        server_name, queued.operation, queued.request_fn
                    )
                    if not queued.future.done():
                        queued.future.set_result(result)
                except Exception as exc:
                    if not queued.future.done():
                        queued.future.set_exception(exc)

                # Small yield to prevent starvation
                await asyncio.sleep(0)

        except asyncio.CancelledError:
            logger.debug("Queue processor for %s cancelled", server_name)
            # Fail all pending queued requests
            for req in self._queues.get(server_name, []):
                if not req.future.done():
                    req.future.set_exception(asyncio.CancelledError("Queue processor shut down"))
        except Exception as exc:
            logger.error(
                "Queue processor for %s crashed: %s", server_name, exc, exc_info=True
            )
        finally:
            self._processing[server_name] = False
            logger.debug("Queue processor stopped for %s", server_name)

    def get_quota_status(self, server_name: str) -> QuotaStatus:
        """Get current quota usage for a server.

        Args:
            server_name: The server to query.

        Returns:
            :class:`QuotaStatus` with current counts and remaining capacity.
            Returns a synthetic "unlimited" status if no limits are set.
        """
        limit = self._limits.get(server_name)
        counter = self._counters.get(server_name)

        if limit is None or counter is None:
            now = time.time()
            return QuotaStatus(
                server_name=server_name,
                requests_this_minute=0,
                requests_this_hour=0,
                requests_this_day=0,
                remaining_minute=999999,
                remaining_hour=999999,
                remaining_day=999999,
                reset_time=now + 60.0,
                is_limited=False,
            )

        # Best-effort sync read
        minute_count = counter._minute_count
        hour_count = counter._hour_count
        day_count = counter._day_count

        minute_reset = counter._minute_start + 60.0

        return QuotaStatus(
            server_name=server_name,
            requests_this_minute=minute_count,
            requests_this_hour=hour_count,
            requests_this_day=day_count,
            remaining_minute=max(0, limit.requests_per_minute - minute_count),
            remaining_hour=max(0, limit.requests_per_hour - hour_count),
            remaining_day=max(0, limit.requests_per_day - day_count),
            reset_time=minute_reset,
            is_limited=(
                minute_count >= limit.requests_per_minute
                or hour_count >= limit.requests_per_hour
                or day_count >= limit.requests_per_day
            ),
        )

    def get_all_quota_status(self) -> Dict[str, QuotaStatus]:
        """Return quota status for every configured server.

        Returns:
            Mapping of server name -> :class:`QuotaStatus`.
        """
        return {name: self.get_quota_status(name) for name in self._limits}

    async def reset_counters(self, server_name: str) -> None:
        """Reset rate limit counters for a server.

        Useful after recovering from a long outage or during testing.

        Args:
            server_name: The server whose counters should be zeroed.
        """
        counter = self._counters.get(server_name)
        if counter is not None:
            await counter.reset()
            logger.info("Rate limit counters reset for %s", server_name)

    async def shutdown(self) -> None:
        """Cancel all queue processors and fail pending queued requests.

        Should be called during application shutdown to ensure clean exit.
        """
        for server_name, task in list(self._tasks.items()):
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        for server_name, queue in self._queues.items():
            for req in queue:
                if not req.future.done():
                    req.future.set_exception(RuntimeError("RateLimitHandler shutting down"))
            queue.clear()

        self._tasks.clear()
        logger.info("RateLimitHandler shutdown complete")

    def get_queue_depth(self, server_name: str) -> int:
        """Return the number of requests waiting in a server's queue.

        Args:
            server_name: The server to query.

        Returns:
            Queue length (``0`` if the server has no queue).
        """
        return len(self._queues.get(server_name, ()))

    def get_all_queue_depths(self) -> Dict[str, int]:
        """Return queue depths for all servers.

        Returns:
            Mapping of server name -> queue length.
        """
        return {name: len(queue) for name, queue in self._queues.items()}
