"""Fallback Chain — try primary MCP servers, fall back to backups on failure.

Example chain:
  Primary: GitHub MCP
  Backup 1: GitLab MCP
  Backup 2: Local git operations

The chain executes an operation against each server in priority order,
tracking success/failure rates and automatically reordering servers
based on observed reliability.

Example::
    chain = FallbackChain(primaries=["github"], backups=["gitlab", "local_git"])
    result = await chain.execute("create_issue", {"title": "Bug"}, executor_fn)
    log = chain.get_execution_log()
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Callable, Coroutine, Dict, List, Optional

logger = logging.getLogger(__name__)


class FallbackExhaustedError(Exception):
    """Raised when every server in the fallback chain has failed.

    Attributes:
        operation -- the operation that was requested
        attempts -- list of (server, error) tuples describing each failure
    """

    def __init__(
        self,
        operation: str,
        attempts: List[Dict[str, Any]],
        message: str = "",
    ) -> None:
        self.operation = operation
        self.attempts = attempts
        default_msg = (
            f"Fallback chain exhausted for operation '{operation}': "
            f"tried {len(attempts)} server(s), all failed."
        )
        super().__init__(message or default_msg)


@dataclass
class ExecutionRecord:
    """A single attempt to execute an operation on a specific server."""

    server: str
    operation: str
    success: bool
    latency_ms: float
    timestamp: float
    error: Optional[str] = None
    result_summary: Optional[str] = None


class FallbackChain:
    """Execute operations through a chain of MCP servers with automatic fallback.

    The chain maintains two ordered lists:
    * **primaries** — preferred servers tried first.
    * **backups** — fallback servers tried when all primaries fail.

    After each execution the internal log is updated.  The log drives
    :meth:`get_server_ranking`, which can be used to dynamically
    reorder primaries based on observed success rates.
    """

    def __init__(
        self,
        primaries: List[str],
        backups: List[str],
        max_log_entries: int = 1000,
        success_window_size: int = 50,
    ) -> None:
        self.primaries = list(primaries)
        self.backups = list(backups)
        self._all_servers = self.primaries + self.backups
        self._execution_log: List[ExecutionRecord] = []
        self._max_log_entries = max_log_entries
        self._success_window_size = success_window_size
        self._server_stats: Dict[str, Dict[str, Any]] = defaultdict(
            lambda: {
                "attempts": 0,
                "successes": 0,
                "failures": 0,
                "total_latency_ms": 0.0,
                "last_used": 0.0,
            }
        )

    async def execute(
        self,
        operation: str,
        args: Dict[str, Any],
        executor: Callable[[str, str, Dict[str, Any]], Coroutine[Any, Any, Any]],
        timeout_per_server: Optional[float] = None,
    ) -> Any:
        """Execute an operation, trying each server in order until one succeeds.

        Args:
            operation: The operation name (e.g. ``"create_issue"``).
            args: Operation arguments forwarded to *executor*.
            executor: Async callable with signature
                ``async fn(server_name, operation, args) -> result``.
            timeout_per_server: Optional timeout in seconds for each
                individual server attempt.

        Returns:
            The result from the first successful server.

        Raises:
            FallbackExhaustedError: If every server in the chain fails.
        """
        servers = self._all_servers
        attempts: List[Dict[str, Any]] = []
        result: Any = None

        logger.info(
            "FallbackChain executing '%s' against %d server(s)",
            operation,
            len(servers),
        )

        for idx, server in enumerate(servers):
            is_backup = idx >= len(self.primaries)
            role = "backup" if is_backup else "primary"
            start = time.perf_counter()

            try:
                if timeout_per_server is not None:
                    result = await asyncio.wait_for(
                        executor(server, operation, args),
                        timeout=timeout_per_server,
                    )
                else:
                    result = await executor(server, operation, args)

                latency_ms = (time.perf_counter() - start) * 1000

                record = ExecutionRecord(
                    server=server,
                    operation=operation,
                    success=True,
                    latency_ms=latency_ms,
                    timestamp=time.time(),
                    result_summary=self._summarize_result(result),
                )
                self._append_record(record)

                if is_backup:
                    logger.info(
                        "Operation '%s' succeeded on backup %s (%.2fms)",
                        operation,
                        server,
                        latency_ms,
                    )
                else:
                    logger.debug(
                        "Operation '%s' succeeded on primary %s (%.2fms)",
                        operation,
                        server,
                        latency_ms,
                    )
                return result

            except asyncio.TimeoutError:
                latency_ms = (time.perf_counter() - start) * 1000
                error_msg = f"Timeout after {timeout_per_server}s"
                record = ExecutionRecord(
                    server=server,
                    operation=operation,
                    success=False,
                    latency_ms=latency_ms,
                    timestamp=time.time(),
                    error=error_msg,
                )
                self._append_record(record)
                attempts.append({"server": server, "error": error_msg})
                logger.warning(
                    "%s %s timed out for '%s' (%.2fms)",
                    role.capitalize(),
                    server,
                    operation,
                    latency_ms,
                )

            except Exception as exc:
                latency_ms = (time.perf_counter() - start) * 1000
                error_msg = f"{type(exc).__name__}: {exc}"
                record = ExecutionRecord(
                    server=server,
                    operation=operation,
                    success=False,
                    latency_ms=latency_ms,
                    timestamp=time.time(),
                    error=error_msg,
                )
                self._append_record(record)
                attempts.append({"server": server, "error": error_msg})
                logger.warning(
                    "%s %s failed for '%s': %s (%.2fms)",
                    role.capitalize(),
                    server,
                    operation,
                    error_msg,
                    latency_ms,
                )

        # All servers exhausted
        logger.error(
            "FallbackChain exhausted for '%s' — all %d servers failed",
            operation,
            len(servers),
        )
        raise FallbackExhaustedError(operation=operation, attempts=attempts)

    def _append_record(self, record: ExecutionRecord) -> None:
        """Append a record to the execution log and update per-server stats."""
        self._execution_log.append(record)

        # Trim log if it exceeds max size
        if len(self._execution_log) > self._max_log_entries:
            self._execution_log = self._execution_log[-self._max_log_entries:]

        # Update per-server stats
        stats = self._server_stats[record.server]
        stats["attempts"] += 1
        stats["last_used"] = record.timestamp
        stats["total_latency_ms"] += record.latency_ms
        if record.success:
            stats["successes"] += 1
        else:
            stats["failures"] += 1

    def get_execution_log(
        self,
        server: Optional[str] = None,
        operation: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Return the log of recent execution attempts.

        Args:
            server: If given, filter to this server only.
            operation: If given, filter to this operation only.
            limit: Maximum number of entries to return.

        Returns:
            List of execution record dicts, most recent first.
        """
        records = self._execution_log
        if server:
            records = [r for r in records if r.server == server]
        if operation:
            records = [r for r in records if r.operation == operation]

        return [
            {
                "server": r.server,
                "operation": r.operation,
                "success": r.success,
                "latency_ms": round(r.latency_ms, 2),
                "timestamp": r.timestamp,
                "error": r.error,
                "result_summary": r.result_summary,
            }
            for r in reversed(records[-limit:])
        ]

    def get_server_ranking(self) -> List[str]:
        """Return servers ordered by recent success rate (best first).

        The ranking is computed from a sliding window of the most
        recent *success_window_size* attempts per server.  Servers
        with no recent data are penalized to the end of the list.

        Returns:
            Ordered list of server names.
        """
        scores: Dict[str, float] = {}

        for server in self._all_servers:
            recent = [
                r for r in self._execution_log
                if r.server == server
            ][-self._success_window_size:]

            if not recent:
                # No data — penalize slightly but keep in list
                scores[server] = -1.0
                continue

            successes = sum(1 for r in recent if r.success)
            success_rate = successes / len(recent)
            avg_latency = sum(r.latency_ms for r in recent) / len(recent)

            # Score = success_rate weighted by recency, minus latency penalty
            # Lower latency improves the score
            latency_penalty = min(avg_latency / 1000.0, 0.3)  # cap at 0.3
            scores[server] = success_rate - latency_penalty

        # Sort by score descending; primaries with equal scores come first
        def sort_key(server: str) -> Tuple[float, bool, int]:
            is_primary = server in self.primaries
            primary_idx = self.primaries.index(server) if is_primary else 9999
            return (-scores.get(server, 0.0), not is_primary, primary_idx)

        return sorted(self._all_servers, key=sort_key)

    def get_server_stats(self) -> Dict[str, Dict[str, Any]]:
        """Return aggregate statistics for every server.

        Returns:
            Mapping of server name -> stats dict with keys:
            ``attempts``, ``successes``, ``failures``, ``success_rate``,
            ``avg_latency_ms``, ``last_used``.
        """
        result: Dict[str, Dict[str, Any]] = {}
        for server, stats in self._server_stats.items():
            attempts = stats["attempts"]
            result[server] = {
                "attempts": attempts,
                "successes": stats["successes"],
                "failures": stats["failures"],
                "success_rate": stats["successes"] / attempts if attempts else 0.0,
                "avg_latency_ms": (
                    stats["total_latency_ms"] / attempts if attempts else 0.0
                ),
                "last_used": stats["last_used"],
            }
        return result

    def reorder_primaries(self) -> None:
        """Reorder :attr:`primaries` based on recent success rates.

        After calling this method the primary list is sorted so that
        the most reliable servers (highest success rate, lowest latency)
        are tried first on the next :meth:`execute` call.

        Backup servers are never promoted to primary; only the order
        within the existing primary set is changed.
        """
        if len(self.primaries) <= 1:
            return

        ranked = self.get_server_ranking()
        # Keep only primaries, in ranked order
        new_primaries = [s for s in ranked if s in self.primaries]
        # Append any primaries that weren't in ranking (no data yet)
        for s in self.primaries:
            if s not in new_primaries:
                new_primaries.append(s)

        self.primaries = new_primaries
        self._all_servers = self.primaries + self.backups
        logger.info(
            "Primaries reordered: %s",
            " -> ".join(self.primaries),
        )

    def add_primary(self, server: str) -> None:
        """Add a new primary server to the chain.

        Args:
            server: The server identifier to add.
        """
        if server not in self.primaries:
            self.primaries.append(server)
            if server not in self._all_servers:
                self._all_servers.append(server)
            logger.info("Added primary server '%s' to fallback chain", server)

    def add_backup(self, server: str) -> None:
        """Add a new backup server to the chain.

        Args:
            server: The server identifier to add.
        """
        if server not in self.backups:
            self.backups.append(server)
            if server not in self._all_servers:
                self._all_servers.append(server)
            logger.info("Added backup server '%s' to fallback chain", server)

    def remove_server(self, server: str) -> None:
        """Remove a server from the chain entirely.

        Args:
            server: The server identifier to remove.
        """
        if server in self.primaries:
            self.primaries.remove(server)
        if server in self.backups:
            self.backups.remove(server)
        if server in self._all_servers:
            self._all_servers.remove(server)
        self._server_stats.pop(server, None)
        logger.info("Removed server '%s' from fallback chain", server)

    def _summarize_result(self, result: Any) -> Optional[str]:
        """Create a short string summary of a result for logging.

        Args:
            result: The raw result object.

        Returns:
            A short summary string, or ``None`` if the result
            cannot be meaningfully summarized.
        """
        try:
            if isinstance(result, dict):
                keys = list(result.keys())[:5]
                return f"dict(keys={keys})"
            if isinstance(result, list):
                return f"list(len={len(result)})"
            if isinstance(result, str):
                preview = result[:80]
                return f"str(len={len(result)}, preview={preview!r})"
            return f"{type(result).__name__}"
        except Exception:
            return None

    def __repr__(self) -> str:
        return (
            f"FallbackChain(primaries={self.primaries!r}, "
            f"backups={self.backups!r}, "
            f"log_entries={len(self._execution_log)})"
        )
