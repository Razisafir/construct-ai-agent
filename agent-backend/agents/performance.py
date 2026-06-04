"""Performance Tracker — track agent effectiveness, auto-adjust assignments.

The tracker maintains a sliding window of task execution records per
agent.  It uses weighted scoring (favouring recency) to select the
best agent for a given task type and detects performance trends over
time.

Example::

    tracker = PerformanceTracker(window_size=100)
    tracker.record_success("agent-1", "code_review", 1200)
    tracker.record_failure("agent-2", "code_review", "timeout")
    best = tracker.get_best_agent("code_review", ["agent-1", "agent-2"])
"""

from __future__ import annotations

import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class TaskRecord:
    """A single observation of an agent executing a task.

    Attributes:
        agent_id: Identifier of the agent that performed the task.
        task_type: Category of task (e.g. ``"code"``, ``"test"``).
        success: Whether the task completed successfully.
        duration_ms: Wall-clock time from assignment to completion.
        timestamp: Unix epoch when the record was created.
        error: Error message if the task failed, else ``None``.
    """

    agent_id: str
    task_type: str
    success: bool
    duration_ms: int
    timestamp: float = field(default_factory=time.time)
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a dictionary."""
        return {
            "agent_id": self.agent_id,
            "task_type": self.task_type,
            "success": self.success,
            "duration_ms": self.duration_ms,
            "timestamp": self.timestamp,
            "error": self.error,
        }


@dataclass
class PerformanceReport:
    """Comprehensive performance summary for a single agent.

    Attributes:
        agent_id: The agent being reported on.
        total_tasks: Total number of recorded tasks.
        success_rate: Fraction of tasks that succeeded (0.0–1.0).
        avg_duration_ms: Mean task duration in milliseconds.
        error_rate: Fraction of tasks that failed (0.0–1.0).
        task_type_breakdown: Per-task-type statistics.
        trend: One of ``"improving"``, ``"stable"``, ``"declining"``.
    """

    agent_id: str
    total_tasks: int
    success_rate: float
    avg_duration_ms: float
    error_rate: float
    task_type_breakdown: Dict[str, Dict[str, float]]
    trend: str  # "improving", "stable", "declining"

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a dictionary."""
        return {
            "agent_id": self.agent_id,
            "total_tasks": self.total_tasks,
            "success_rate": round(self.success_rate, 4),
            "avg_duration_ms": round(self.avg_duration_ms, 2),
            "error_rate": round(self.error_rate, 4),
            "task_type_breakdown": self.task_type_breakdown,
            "trend": self.trend,
        }


class PerformanceTracker:
    """Tracks per-agent performance and optimizes task assignment.

    The tracker maintains a sliding window of the most recent
    :class:`TaskRecord` observations.  When the window is full, old
    records are discarded so that decisions are always based on fresh
    data.

    Attributes:
        records: Chronological list of task records (newest at end).
        window_size: Maximum number of records to retain.
    """

    def __init__(self, window_size: int = 100) -> None:
        self.records: List[TaskRecord] = []
        self.window_size = window_size
        logger.info(
            "PerformanceTracker initialized (window_size=%d)", window_size
        )

    # ------------------------------------------------------------------
    # Recording
    # ------------------------------------------------------------------

    def record_success(
        self,
        agent_id: str,
        task_type: str,
        duration_ms: int,
    ) -> None:
        """Record a successful task completion.

        Args:
            agent_id: The agent that completed the task.
            task_type: Category of the task.
            duration_ms: Wall-clock duration in milliseconds.
        """
        record = TaskRecord(
            agent_id=agent_id,
            task_type=task_type,
            success=True,
            duration_ms=duration_ms,
        )
        self._add_record(record)
        logger.debug(
            "Success recorded for %s on %s (%d ms)",
            agent_id,
            task_type,
            duration_ms,
        )

    def record_failure(
        self,
        agent_id: str,
        task_type: str,
        error: str,
    ) -> None:
        """Record a failed task.

        The duration is stored as ``-1`` to indicate the task did not
        complete.

        Args:
            agent_id: The agent that attempted the task.
            task_type: Category of the task.
            error: Error message describing why the task failed.
        """
        record = TaskRecord(
            agent_id=agent_id,
            task_type=task_type,
            success=False,
            duration_ms=-1,
            error=error,
        )
        self._add_record(record)
        logger.debug(
            "Failure recorded for %s on %s: %s",
            agent_id,
            task_type,
            error,
        )

    def _add_record(self, record: TaskRecord) -> None:
        """Append a record and enforce the sliding window."""
        self.records.append(record)
        if len(self.records) > self.window_size:
            removed = len(self.records) - self.window_size
            self.records = self.records[-self.window_size:]
            logger.debug("Sliding window dropped %d old records", removed)

    # ------------------------------------------------------------------
    # Agent selection
    # ------------------------------------------------------------------

    def get_best_agent(
        self,
        task_type: str,
        available_agents: List[str],
    ) -> Optional[str]:
        """Return the best agent for *task_type* based on history.

        The scoring formula balances:

        - **Success rate** (0–1): higher is better.
        - **Speed** (0–1): faster average completion is better.
        - **Recency**: more recent records contribute more weight.

        Agents with no historical data for the task type receive a
        neutral score of 0.5 so that exploration is still possible.

        Args:
            task_type: The category of task to be assigned.
            available_agents: Candidate agent IDs.

        Returns:
            The ID of the highest-scoring agent, or ``None`` if no
            candidates are provided.
        """
        if not available_agents:
            return None

        now = time.time()
        scores: Dict[str, float] = {}

        for agent_id in available_agents:
            agent_records = [
                r for r in self.records
                if r.agent_id == agent_id and r.task_type == task_type
            ]

            if not agent_records:
                # No data — assign neutral score to encourage exploration
                scores[agent_id] = 0.5
                continue

            # Weighted by recency (exponential decay)
            weighted_success = 0.0
            weighted_duration = 0.0
            total_weight = 0.0

            for rec in agent_records:
                age_seconds = now - rec.timestamp
                # Half-life of 1 hour
                weight = 0.5 ** (age_seconds / 3600.0)
                total_weight += weight
                if rec.success:
                    weighted_success += weight
                    # Normalize duration: assume 10s is "normal"
                    dur = rec.duration_ms if rec.duration_ms > 0 else 10000
                    speed_score = max(0.0, 1.0 - (dur / 10000.0))
                    weighted_duration += weight * speed_score

            if total_weight == 0:
                scores[agent_id] = 0.5
                continue

            success_rate = weighted_success / total_weight
            speed_rate = weighted_duration / total_weight

            # Combined score: 70% success, 30% speed
            scores[agent_id] = (0.7 * success_rate) + (0.3 * speed_rate)
            logger.debug(
                "Agent %s score for %s: %.3f (success=%.3f, speed=%.3f)",
                agent_id,
                task_type,
                scores[agent_id],
                success_rate,
                speed_rate,
            )

        if not scores:
            return None

        best_agent = max(scores, key=scores.get)  # type: ignore[arg-type]
        logger.info(
            "Best agent for %s: %s (score=%.3f)",
            task_type,
            best_agent,
            scores[best_agent],
        )
        return best_agent

    # ------------------------------------------------------------------
    # Reporting
    # ------------------------------------------------------------------

    def get_agent_report(self, agent_id: str) -> PerformanceReport:
        """Generate a detailed performance report for an agent.

        Args:
            agent_id: The agent to report on.

        Returns:
            A :class:`PerformanceReport` with aggregated statistics.
        """
        agent_records = [r for r in self.records if r.agent_id == agent_id]
        total = len(agent_records)

        if total == 0:
            return PerformanceReport(
                agent_id=agent_id,
                total_tasks=0,
                success_rate=0.0,
                avg_duration_ms=0.0,
                error_rate=0.0,
                task_type_breakdown={},
                trend="stable",
            )

        successes = [r for r in agent_records if r.success]
        success_rate = len(successes) / total
        durations = [r.duration_ms for r in successes if r.duration_ms > 0]
        avg_duration = sum(durations) / len(durations) if durations else 0.0

        # Per-task-type breakdown
        by_type: Dict[str, List[TaskRecord]] = defaultdict(list)
        for r in agent_records:
            by_type[r.task_type].append(r)

        breakdown: Dict[str, Dict[str, float]] = {}
        for ttype, recs in by_type.items():
            t_success = len([r for r in recs if r.success])
            t_durations = [r.duration_ms for r in recs if r.duration_ms > 0]
            breakdown[ttype] = {
                "total": float(len(recs)),
                "success_rate": round(t_success / len(recs), 4),
                "avg_duration_ms": round(
                    sum(t_durations) / len(t_durations) if t_durations else 0.0, 2
                ),
            }

        trend = self._detect_trend(agent_records)

        report = PerformanceReport(
            agent_id=agent_id,
            total_tasks=total,
            success_rate=round(success_rate, 4),
            avg_duration_ms=round(avg_duration, 2),
            error_rate=round(1.0 - success_rate, 4),
            task_type_breakdown=breakdown,
            trend=trend,
        )
        logger.debug("Generated report for %s: %s", agent_id, trend)
        return report

    def get_underperforming_agents(
        self,
        threshold: float = 0.5,
    ) -> List[str]:
        """Return agents with success rate below *threshold*.

        Only agents with at least 5 recorded tasks are considered,
        to avoid penalising agents that have just started.

        Args:
            threshold: Success-rate floor (default 0.5).

        Returns:
            List of agent IDs that are underperforming.
        """
        by_agent: Dict[str, List[TaskRecord]] = defaultdict(list)
        for r in self.records:
            by_agent[r.agent_id].append(r)

        underperformers: List[str] = []
        for agent_id, recs in by_agent.items():
            if len(recs) < 5:
                continue
            success_rate = len([r for r in recs if r.success]) / len(recs)
            if success_rate < threshold:
                underperformers.append(agent_id)
                logger.warning(
                    "Agent %s underperforming: %.2f success rate",
                    agent_id,
                    success_rate,
                )
        return underperformers

    def get_all_agents(self) -> List[str]:
        """Return a deduplicated list of all known agent IDs."""
        return sorted({r.agent_id for r in self.records})

    # ------------------------------------------------------------------
    # Trend detection
    # ------------------------------------------------------------------

    @staticmethod
    def _detect_trend(records: List[TaskRecord]) -> str:
        """Detect whether performance is improving, stable, or declining.

        Splits the records into two halves (chronological) and compares
        the success rates.  A difference of more than 10 percentage
        points is considered a trend.

        Args:
            records: Chronological list of task records for one agent.

        Returns:
            ``"improving"``, ``"stable"``, or ``"declining"``.
        """
        if len(records) < 6:
            return "stable"

        # Sort by timestamp to ensure chronological order
        sorted_records = sorted(records, key=lambda r: r.timestamp)
        mid = len(sorted_records) // 2
        first_half = sorted_records[:mid]
        second_half = sorted_records[mid:]

        def _rate(recs: List[TaskRecord]) -> float:
            if not recs:
                return 0.0
            return len([r for r in recs if r.success]) / len(recs)

        first_rate = _rate(first_half)
        second_rate = _rate(second_half)
        delta = second_rate - first_rate

        if delta > 0.1:
            return "improving"
        elif delta < -0.1:
            return "declining"
        return "stable"

    # ------------------------------------------------------------------
    # Window management
    # ------------------------------------------------------------------

    def trim_window(self, max_age_seconds: float = 86400.0) -> int:
        """Remove records older than *max_age_seconds*.

        Args:
            max_age_seconds: Maximum age in seconds (default 24 hours).

        Returns:
            Number of records removed.
        """
        cutoff = time.time() - max_age_seconds
        original_count = len(self.records)
        self.records = [r for r in self.records if r.timestamp >= cutoff]
        removed = original_count - len(self.records)
        if removed:
            logger.info("Trimmed %d old records from window", removed)
        return removed

    def clear(self) -> None:
        """Remove all records."""
        count = len(self.records)
        self.records.clear()
        logger.info("Cleared all %d performance records", count)

    # ------------------------------------------------------------------
    # Persistence helpers
    # ------------------------------------------------------------------

    def export_records(self) -> List[Dict[str, Any]]:
        """Export all records as JSON-serializable dictionaries."""
        return [r.to_dict() for r in self.records]

    def import_records(self, data: List[Dict[str, Any]]) -> int:
        """Import records from dictionaries.

        Args:
            data: List of record dictionaries.

        Returns:
            Number of records imported.
        """
        imported = 0
        for d in data:
            try:
                self._add_record(
                    TaskRecord(
                        agent_id=d["agent_id"],
                        task_type=d["task_type"],
                        success=d["success"],
                        duration_ms=d["duration_ms"],
                        timestamp=d.get("timestamp", time.time()),
                        error=d.get("error"),
                    )
                )
                imported += 1
            except (KeyError, TypeError):
                logger.warning("Skipping invalid record during import: %s", d)
        logger.info("Imported %d performance records", imported)
        return imported


# ---------------------------------------------------------------------------
# Demo
# ---------------------------------------------------------------------------

async def _async_demo() -> None:  # noqa: RUF029
    """Run the performance tracker demonstration."""
    tracker = PerformanceTracker(window_size=50)

    # Simulate recordings
    tracker.record_success("agent-1", "code", 1200)
    tracker.record_success("agent-1", "code", 1500)
    tracker.record_success("agent-1", "code", 1100)
    tracker.record_success("agent-1", "test", 800)
    tracker.record_failure("agent-1", "code", "timeout")

    tracker.record_success("agent-2", "code", 3000)
    tracker.record_success("agent-2", "code", 2800)
    tracker.record_failure("agent-2", "code", "memory_error")
    tracker.record_failure("agent-2", "code", "timeout")
    tracker.record_failure("agent-2", "test", "assertion_error")

    tracker.record_success("agent-3", "test", 600)
    tracker.record_success("agent-3", "test", 650)
    tracker.record_success("agent-3", "test", 700)
    tracker.record_success("agent-3", "code", 2000)

    # Best agent selection
    best = tracker.get_best_agent("code", ["agent-1", "agent-2", "agent-3"])
    print(f"Best agent for 'code': {best}")

    best_test = tracker.get_best_agent(
        "test", ["agent-1", "agent-2", "agent-3"]
    )
    print(f"Best agent for 'test': {best_test}")

    # Reports
    print("\n--- Agent Reports ---")
    for agent in tracker.get_all_agents():
        report = tracker.get_agent_report(agent)
        r = report.to_dict()
        print(
            f"{agent}: {r['total_tasks']} tasks, "
            f"{r['success_rate']:.0%} success, "
            f"avg {r['avg_duration_ms']:.0f}ms, "
            f"trend={r['trend']}"
        )

    # Underperformers
    under = tracker.get_underperforming_agents(threshold=0.5)
    print(f"\nUnderperforming agents: {under}")

    # Window stats
    print(f"\nTotal records in window: {len(tracker.records)}")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )
    print("=" * 60)
    print("PerformanceTracker Demo")
    print("=" * 60)
    import asyncio

    asyncio.run(_async_demo())
