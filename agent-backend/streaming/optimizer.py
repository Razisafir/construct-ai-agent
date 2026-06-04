"""Streaming Optimizer — buffers, batches, and optimizes token delivery.

Targets:
- 100 tokens/s sustained streaming
- 50-token buffer before flush
- 50ms flush interval
- Reduces frontend render overhead

Adaptive buffer sizing grows the buffer under sustained load to reduce
context-switch overhead, and shrinks it when idle for lower latency.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Callable, Deque, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class StreamChunk:
    """A batch of tokens ready for delivery to the client."""

    tokens: str
    token_count: int
    latency_ms: float
    timestamp: float = field(default_factory=time.time)


@dataclass
class _BufferedToken:
    """Internal wrapper that records when a token entered the buffer."""

    text: str
    enqueued_at: float = field(default_factory=time.time)


class StreamingOptimizer:
    """Buffers tokens and flushes in optimal-sized chunks.

    The optimizer collects individual tokens from an LLM stream, buffers them,
    and emits them in batches.  Two triggers cause a flush:

    1. **Buffer-full**: when ``len(buffer) >= buffer_size``.
    2. **Time-based**: a background task flushes at least every
       ``flush_interval_ms`` milliseconds even if the buffer is not full.

    Adaptive sizing monitors the trailing token arrival rate.  Under sustained
    load the buffer grows (up to ``max_buffer_size``) so that fewer emits are
    performed, reducing frontend render overhead.  When the stream goes idle the
    buffer shrinks back to ``buffer_size`` for lower latency.

    Parameters
    ----------
    buffer_size:
        Number of tokens to accumulate before flushing (default 50).
    flush_interval_ms:
        Maximum milliseconds to hold tokens before flushing (default 50).
    max_buffer_size:
        Upper bound for adaptive buffer growth (default 200).
    adaptive_window:
        How many recent inter-token intervals to keep for rate estimation
        (default 20).
    """

    def __init__(
        self,
        buffer_size: int = 50,
        flush_interval_ms: float = 50.0,
        max_buffer_size: int = 200,
        adaptive_window: int = 20,
    ) -> None:
        self.buffer_size = buffer_size
        self.flush_interval_ms = flush_interval_ms
        self.max_buffer_size = max_buffer_size
        self._adaptive_window = adaptive_window

        self._buffer: List[_BufferedToken] = []
        self._emit_fn: Optional[Callable[[str], None]] = None
        self._flush_task: Optional[asyncio.Task[None]] = None
        self._lock = asyncio.Lock()

        # Adaptive sizing state
        self._inter_token_intervals: Deque[float] = deque(maxlen=adaptive_window)
        self._last_token_time: Optional[float] = None
        self._current_buffer_size = buffer_size

        # Metrics
        self._metrics: Dict[str, float] = {
            "tokens_emitted": 0.0,
            "chunks_emitted": 0.0,
            "avg_chunk_size": 0.0,
            "avg_latency_ms": 0.0,
            "total_latency_ms": 0.0,
            "flushes_due_to_size": 0.0,
            "flushes_due_to_time": 0.0,
            "adaptive_size_changes": 0.0,
        }

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def set_emit_handler(self, fn: Callable[[str], None]) -> None:
        """Set the synchronous function called when a chunk is ready.

        The callable receives a single ``str`` argument containing the
        concatenated tokens for that chunk.
        """
        self._emit_fn = fn

    def on_token(self, token: str) -> None:
        """Receive a single token from the LLM stream.

        The token is appended to the internal buffer.  If the buffer reaches
        the current (possibly adapted) size limit, it is flushed immediately.

        Parameters
        ----------
        token:
            A single token string (may contain multiple characters).
        """
        now = time.time()
        self._update_adaptive_sizing(now)
        self._buffer.append(_BufferedToken(text=token, enqueued_at=now))
        if len(self._buffer) >= self._current_buffer_size:
            self._flush(reason="size")

    def flush(self) -> Optional[StreamChunk]:
        """Manually flush the current buffer.

        Returns ``None`` when the buffer is empty.
        """
        return self._flush(reason="manual")

    async def flush_async(self) -> None:
        """Background coroutine that flushes periodically.

        Intended to be started as an ``asyncio.Task`` alongside the stream.
        The task runs until cancelled, flushing the buffer at least every
        ``flush_interval_ms``.

        Example::

            optimizer = StreamingOptimizer()
            task = asyncio.create_task(optimizer.flush_async())
            # ... feed tokens via on_token() ...
            task.cancel()
        """
        try:
            while True:
                await asyncio.sleep(self.flush_interval_ms / 1000.0)
                async with self._lock:
                    if self._buffer:
                        self._flush(reason="time")
        except asyncio.CancelledError:
            logger.debug("StreamingOptimizer flush_async cancelled")
            raise

    def start_background_flush(self, loop: Optional[asyncio.AbstractEventLoop] = None) -> None:
        """Convenience helper that starts :meth:`flush_async` as a task."""
        if self._flush_task is not None and not self._flush_task.done():
            logger.warning("Background flush task already running")
            return
        self._flush_task = asyncio.ensure_future(self.flush_async(), loop=loop)

    def stop_background_flush(self) -> None:
        """Cancel the background flush task if running."""
        if self._flush_task is not None and not self._flush_task.done():
            self._flush_task.cancel()
            self._flush_task = None

    def get_metrics(self) -> Dict[str, float]:
        """Return a snapshot of streaming performance metrics."""
        return self._metrics.copy()

    def reset_metrics(self) -> None:
        """Reset all performance counters to zero."""
        self._metrics = {
            "tokens_emitted": 0.0,
            "chunks_emitted": 0.0,
            "avg_chunk_size": 0.0,
            "avg_latency_ms": 0.0,
            "total_latency_ms": 0.0,
            "flushes_due_to_size": 0.0,
            "flushes_due_to_time": 0.0,
            "adaptive_size_changes": 0.0,
        }

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #

    def _update_adaptive_sizing(self, now: float) -> None:
        """Adjust buffer size based on trailing token arrival rate.

        If tokens are arriving very quickly (avg interval < 5 ms) we grow the
        buffer up to ``max_buffer_size``.  If they are slow (> 20 ms) we
        shrink back toward ``buffer_size``.  This reduces emit overhead during
        fast streams while keeping latency low during slow ones.
        """
        if self._last_token_time is not None:
            interval_ms = (now - self._last_token_time) * 1000.0
            self._inter_token_intervals.append(interval_ms)
        self._last_token_time = now

        if len(self._inter_token_intervals) < self._adaptive_window // 2:
            return  # Not enough data yet

        avg_interval = sum(self._inter_token_intervals) / len(self._inter_token_intervals)
        old_size = self._current_buffer_size

        if avg_interval < 5.0 and self._current_buffer_size < self.max_buffer_size:
            # Fast stream — grow buffer (step by 10)
            self._current_buffer_size = min(
                self._current_buffer_size + 10, self.max_buffer_size
            )
        elif avg_interval > 20.0 and self._current_buffer_size > self.buffer_size:
            # Slow stream — shrink buffer (step by 10)
            self._current_buffer_size = max(
                self._current_buffer_size - 10, self.buffer_size
            )

        if self._current_buffer_size != old_size:
            self._metrics["adaptive_size_changes"] += 1.0
            logger.debug(
                "Adaptive buffer size changed %d -> %d (avg_interval=%.2f ms)",
                old_size,
                self._current_buffer_size,
                avg_interval,
            )

    def _flush(self, reason: str = "manual") -> Optional[StreamChunk]:
        """Drain the buffer, emit a chunk, and update metrics.

        Parameters
        ----------
        reason:
            One of ``"size"``, ``"time"``, or ``"manual"`` — tracked in
            metrics for diagnostic purposes.

        Returns
        -------
        StreamChunk or None
        """
        if not self._buffer:
            return None

        now = time.time()
        tokens_text = "".join(t.text for t in self._buffer)
        count = len(self._buffer)

        # Latency = time from first token entering buffer to flush
        oldest_enqueued = self._buffer[0].enqueued_at
        latency_ms = (now - oldest_enqueued) * 1000.0

        chunk = StreamChunk(
            tokens=tokens_text,
            token_count=count,
            latency_ms=latency_ms,
            timestamp=now,
        )

        # Emit
        if self._emit_fn is not None:
            try:
                self._emit_fn(tokens_text)
            except Exception:
                logger.exception("Emit handler failed for chunk of %d tokens", count)

        # Update metrics
        self._buffer.clear()
        self._metrics["tokens_emitted"] += count
        self._metrics["chunks_emitted"] += 1.0
        self._metrics["total_latency_ms"] += latency_ms

        total_chunks = self._metrics["chunks_emitted"]
        self._metrics["avg_chunk_size"] = self._metrics["tokens_emitted"] / total_chunks
        self._metrics["avg_latency_ms"] = self._metrics["total_latency_ms"] / total_chunks

        if reason == "size":
            self._metrics["flushes_due_to_size"] += 1.0
        elif reason == "time":
            self._metrics["flushes_due_to_time"] += 1.0

        logger.debug(
            "Flushed %d tokens in %.2f ms (reason=%s)",
            count,
            latency_ms,
            reason,
        )
        return chunk
