"""Load Tester — stress test the agent system.

Tests:
- Concurrent task execution (up to 30)
- Streaming speed (100 tokens/s target)
- Memory usage over time
- Recovery from failures

All tests are async and designed to be run inside an existing event loop.
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
import tracemalloc
from dataclasses import dataclass, field
from typing import Any, Callable, Coroutine, Deque, Dict, List, Optional

try:
    import psutil
except ImportError:  # pragma: no cover
    psutil = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)


@dataclass
class LoadReport:
    """Aggregated results from a concurrent-task load test."""

    tasks_completed: int
    tasks_failed: int
    avg_latency_ms: float
    max_latency_ms: float
    memory_peak_mb: float
    memory_end_mb: float
    throughput_tasks_per_sec: float
    errors: List[str] = field(default_factory=list)


@dataclass
class SpeedReport:
    """Results from a streaming-speed test."""

    tokens_per_second: float
    chunks_per_second: float
    avg_chunk_size: float
    total_tokens: int
    duration_sec: float


@dataclass
class RecoveryReport:
    """Results from a failure-recovery test."""

    recovery_time_ms: float
    data_loss: bool
    state_consistent: bool
    errors_during_recovery: List[str]


@dataclass
class _TaskResult:
    """Internal wrapper for a single task execution."""

    latency_ms: float
    error: Optional[str] = None


class LoadTester:
    """Load-testing framework for the Construct agent system.

    Each ``test_*`` coroutine runs a specific scenario and returns a
    dataclass report.  The tester optionally tracks process-level memory
    via *psutil*; if *psutil* is not installed memory fields will be ``0.0``.
    """

    def __init__(self) -> None:
        if psutil is not None:
            self.process = psutil.Process(os.getpid())
        else:
            self.process = None  # type: ignore[assignment]

    # ------------------------------------------------------------------ #
    # Concurrent tasks
    # ------------------------------------------------------------------ #

    async def test_concurrent_tasks(
        self,
        executor: Callable[..., Coroutine[Any, Any, Any]],
        count: int = 30,
        *args: Any,
        **kwargs: Any,
    ) -> LoadReport:
        """Launch *count* tasks concurrently and measure aggregate performance.

        Parameters
        ----------
        executor:
            Async callable representing one unit of work.
        count:
            Number of concurrent tasks (default 30).
        *args, **kwargs:
            Forwarded to *executor*.

        Returns
        -------
        LoadReport
        """
        logger.info("Starting concurrent task test: %d tasks", count)
        mem_start = self._sample_memory()
        mem_peak = mem_start

        semaphore = asyncio.Semaphore(count)
        results: List[_TaskResult] = []

        async def _run_one(task_id: int) -> _TaskResult:
            async with semaphore:
                t0 = time.perf_counter()
                try:
                    await executor(*args, **kwargs)
                except Exception as exc:
                    latency = (time.perf_counter() - t0) * 1000.0
                    return _TaskResult(latency_ms=latency, error=f"[{task_id}] {exc!r}")
                else:
                    latency = (time.perf_counter() - t0) * 1000.0
                    # Sample memory after each task
                    nonlocal mem_peak
                    mem = self._sample_memory()
                    if mem > mem_peak:
                        mem_peak = mem
                    return _TaskResult(latency_ms=latency)

        start = time.perf_counter()
        coros = [_run_one(i) for i in range(count)]
        raw_results = await asyncio.gather(*coros, return_exceptions=True)
        elapsed_sec = time.perf_counter() - start

        # Unwrap any exceptions returned by gather
        for r in raw_results:
            if isinstance(r, Exception):
                results.append(_TaskResult(latency_ms=0.0, error=repr(r)))
            else:
                results.append(r)

        errors = [r.error for r in results if r.error is not None]
        latencies = [r.latency_ms for r in results if r.error is None]

        report = LoadReport(
            tasks_completed=len(latencies),
            tasks_failed=len(errors),
            avg_latency_ms=sum(latencies) / len(latencies) if latencies else 0.0,
            max_latency_ms=max(latencies) if latencies else 0.0,
            memory_peak_mb=mem_peak,
            memory_end_mb=self._sample_memory(),
            throughput_tasks_per_sec=count / elapsed_sec if elapsed_sec > 0 else 0.0,
            errors=errors,
        )
        logger.info(
            "Concurrent test done: completed=%d failed=%d avg_latency=%.1f ms",
            report.tasks_completed,
            report.tasks_failed,
            report.avg_latency_ms,
        )
        return report

    # ------------------------------------------------------------------ #
    # Streaming speed
    # ------------------------------------------------------------------ #

    async def test_streaming_speed(
        self,
        stream_fn: Callable[..., Coroutine[Any, Any, None]],
        duration_sec: int = 60,
        *args: Any,
        **kwargs: Any,
    ) -> SpeedReport:
        """Run a streaming function for *duration_sec* and measure throughput.

        The *stream_fn* must accept a ``token_callback`` keyword argument.
        The callback receives each token (``str``) as it is produced.

        Parameters
        ----------
        stream_fn:
            Async callable that produces tokens.
        duration_sec:
            How long to collect tokens (default 60).
        *args, **kwargs:
            Forwarded to *stream_fn*.

        Returns
        -------
        SpeedReport
        """
        logger.info("Starting streaming speed test for %d s", duration_sec)
        tokens_collected: List[str] = []
        chunk_sizes: List[int] = []
        current_chunk: List[str] = []
        last_chunk_time = time.perf_counter()

        def _token_callback(token: str) -> None:
            nonlocal last_chunk_time
            tokens_collected.append(token)
            current_chunk.append(token)
            now = time.perf_counter()
            if (now - last_chunk_time) >= 0.05:  # 50 ms chunk boundary
                chunk_sizes.append(len(current_chunk))
                current_chunk.clear()
                last_chunk_time = now

        kwargs_with_cb = {**kwargs, "token_callback": _token_callback}
        start = time.perf_counter()

        try:
            await asyncio.wait_for(
                stream_fn(*args, **kwargs_with_cb),
                timeout=duration_sec + 5,
            )
        except asyncio.TimeoutError:
            pass  # Expected if stream_fn runs longer than duration
        except Exception as exc:
            logger.warning("Streaming function exited early: %s", exc)

        elapsed = time.perf_counter() - start
        if elapsed <= 0:
            elapsed = 0.001

        # Clamp to requested duration for fair measurement
        effective_duration = min(elapsed, duration_sec)
        total_tokens = len(tokens_collected)
        tokens_per_sec = total_tokens / effective_duration

        if current_chunk:
            chunk_sizes.append(len(current_chunk))

        avg_chunk = sum(chunk_sizes) / len(chunk_sizes) if chunk_sizes else 0.0
        chunks_per_sec = len(chunk_sizes) / effective_duration

        report = SpeedReport(
            tokens_per_second=tokens_per_sec,
            chunks_per_second=chunks_per_sec,
            avg_chunk_size=avg_chunk,
            total_tokens=total_tokens,
            duration_sec=effective_duration,
        )
        logger.info(
            "Streaming speed: %.1f tokens/s, %.1f chunks/s, avg_chunk=%.1f",
            report.tokens_per_second,
            report.chunks_per_second,
            report.avg_chunk_size,
        )
        return report

    # ------------------------------------------------------------------ #
    # Memory usage
    # ------------------------------------------------------------------ #

    async def test_memory_usage(
        self,
        executor: Callable[..., Coroutine[Any, Any, Any]],
        duration_sec: int = 300,
        sample_interval_sec: int = 10,
        *args: Any,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Run *executor* repeatedly and sample memory usage.

        Parameters
        ----------
        executor:
            Async callable to invoke repeatedly.
        duration_sec:
            Total test duration (default 300).
        sample_interval_sec:
            Seconds between memory samples (default 10).
        *args, **kwargs:
            Forwarded to *executor*.

        Returns
        -------
        dict with keys ``samples_mb``, ``peak_mb``, ``avg_mb``,
        ``leak_detected``, ``leak_rate_mb_per_min``.
        """
        logger.info(
            "Starting memory usage test: %d s, sampling every %d s",
            duration_sec,
            sample_interval_sec,
        )
        samples: List[Dict[str, float]] = []
        start = time.perf_counter()
        iteration = 0

        while True:
            elapsed = time.perf_counter() - start
            if elapsed >= duration_sec:
                break

            # Run one unit of work
            try:
                await executor(*args, **kwargs)
            except Exception as exc:
                logger.warning("Executor failed at iteration %d: %s", iteration, exc)

            # Sample memory at intervals
            if iteration % max(1, sample_interval_sec) == 0 or elapsed >= duration_sec - 1:
                mem_mb = self._sample_memory()
                samples.append({"elapsed_sec": elapsed, "memory_mb": mem_mb})
                logger.debug("Memory sample @ %.1f s: %.2f MB", elapsed, mem_mb)

            iteration += 1
            await asyncio.sleep(0)  # Yield control

        if not samples:
            return {
                "samples_mb": [],
                "peak_mb": 0.0,
                "avg_mb": 0.0,
                "leak_detected": False,
                "leak_rate_mb_per_min": 0.0,
            }

        mem_values = [s["memory_mb"] for s in samples]
        peak_mb = max(mem_values)
        avg_mb = sum(mem_values) / len(mem_values)

        # Simple linear regression on last 60% of samples for leak detection
        leak_detected = False
        leak_rate = 0.0
        if len(samples) >= 3:
            cutoff = int(len(samples) * 0.4)
            recent = samples[cutoff:]
            n = len(recent)
            if n >= 2:
                x = [r["elapsed_sec"] / 60.0 for r in recent]  # minutes
                y = [r["memory_mb"] for r in recent]
                x_mean = sum(x) / n
                y_mean = sum(y) / n
                numerator = sum((xi - x_mean) * (yi - y_mean) for xi, yi in zip(x, y))
                denominator = sum((xi - x_mean) ** 2 for xi in x)
                if denominator > 0:
                    leak_rate = numerator / denominator
                    leak_detected = leak_rate > 1.0  # > 1 MB/min is a leak

        report: Dict[str, Any] = {
            "samples_mb": samples,
            "peak_mb": peak_mb,
            "avg_mb": avg_mb,
            "leak_detected": leak_detected,
            "leak_rate_mb_per_min": leak_rate,
        }
        logger.info(
            "Memory test done: peak=%.2f MB avg=%.2f MB leak=%s rate=%.3f MB/min",
            peak_mb,
            avg_mb,
            leak_detected,
            leak_rate,
        )
        return report

    # ------------------------------------------------------------------ #
    # Recovery
    # ------------------------------------------------------------------ #

    async def test_recovery(
        self,
        kill_fn: Callable[..., Coroutine[Any, Any, Any]],
        recover_fn: Callable[..., Coroutine[Any, Any, Any]],
        verify_fn: Optional[Callable[..., Coroutine[Any, Any, bool]]] = None,
        *args: Any,
        **kwargs: Any,
    ) -> RecoveryReport:
        """Simulate a crash, trigger recovery, and verify state consistency.

        Parameters
        ----------
        kill_fn:
            Async callable that simulates a failure (e.g. raises or cancels
            in-flight work).
        recover_fn:
            Async callable that brings the system back to a working state.
        verify_fn:
            Optional async callable that returns ``True`` if state is
            consistent after recovery.
        *args, **kwargs:
            Forwarded to all three functions.

        Returns
        -------
        RecoveryReport
        """
        logger.info("Starting recovery test")
        errors: List[str] = []

        # Phase 1 — simulate failure
        t0 = time.perf_counter()
        try:
            await kill_fn(*args, **kwargs)
        except Exception as exc:
            logger.debug("kill_fn raised as expected: %s", exc)

        # Phase 2 — recover
        try:
            await recover_fn(*args, **kwargs)
        except Exception as exc:
            errors.append(f"Recovery failed: {exc!r}")
            logger.error("Recovery function failed: %s", exc)

        recovery_ms = (time.perf_counter() - t0) * 1000.0

        # Phase 3 — verify state
        state_consistent = True
        try:
            if verify_fn is not None:
                state_consistent = await verify_fn(*args, **kwargs)
        except Exception as exc:
            state_consistent = False
            errors.append(f"Verify failed: {exc!r}")

        # Heuristic: data loss is assumed false if recovery succeeded
        data_loss = len(errors) > 0 and not state_consistent

        report = RecoveryReport(
            recovery_time_ms=recovery_ms,
            data_loss=data_loss,
            state_consistent=state_consistent,
            errors_during_recovery=errors,
        )
        logger.info(
            "Recovery test done: time=%.1f ms consistent=%s errors=%d",
            report.recovery_time_ms,
            report.state_consistent,
            len(report.errors_during_recovery),
        )
        return report

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #

    def _sample_memory(self) -> float:
        """Return current RSS memory usage in MB."""
        if self.process is None:
            return 0.0
        try:
            return self.process.memory_info().rss / 1024 / 1024
        except Exception:
            return 0.0
