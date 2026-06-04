"""Performance Monitor — track metrics, detect degradation, trigger alerts.

Metrics:
- LLM latency per provider
- Token throughput
- Error rates
- Memory usage
- Active agent count

The monitor stores a bounded history of scalar metric points and evaluates
configurable thresholds.  When a threshold is breached an :class:`Alert` is
issued to every registered handler.
"""

from __future__ import annotations

import logging
import statistics
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Callable, Deque, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class MetricPoint:
    """A single timestamped observation."""

    timestamp: float
    value: float
    labels: Dict[str, str] = field(default_factory=dict)


@dataclass
class Alert:
    """An alert fired when a metric breaches a threshold."""

    severity: str          # "warning" or "critical"
    metric: str            # metric name
    message: str           # human-readable description
    timestamp: float       # when the alert fired
    threshold: float       # the breached threshold value
    actual_value: float    # the observed value


class PerformanceMonitor:
    """Records and monitors performance metrics with alerting.

    Parameters
    ----------
    history_size:
        Maximum number of :class:`MetricPoint` objects retained per metric
        name (default 10_000).
    """

    def __init__(self, history_size: int = 10000) -> None:
        self._history_size = history_size
        self._metrics: Dict[str, Deque[MetricPoint]] = {}
        self._thresholds: Dict[str, Tuple[float, float]] = {}  # metric -> (warning, critical)
        self._alert_handlers: List[Callable[[Alert], None]] = []
        self._alerts: Deque[Alert] = deque(maxlen=1000)
        self._alert_cooldowns: Dict[str, float] = {}  # metric -> last_alert_timestamp
        self._cooldown_sec = 60.0  # minimum seconds between repeat alerts

    # ------------------------------------------------------------------ #
    # Recording
    # ------------------------------------------------------------------ #

    def record_latency(self, operation: str, duration_ms: float, **labels: str) -> None:
        """Record operation latency in milliseconds.

        Parameters
        ----------
        operation:
            Identifier for the operation (e.g. ``"llm_chat"``).
        duration_ms:
            Observed latency.
        **labels:
            Additional dimension labels (e.g. ``provider="openai"``).
        """
        self._record(f"latency_{operation}", duration_ms, labels)

    def record_throughput(self, operation: str, tokens_per_sec: float, **labels: str) -> None:
        """Record token throughput.

        Parameters
        ----------
        operation:
            Identifier for the operation.
        tokens_per_sec:
            Observed throughput.
        **labels:
            Additional dimension labels.
        """
        self._record(f"throughput_{operation}", tokens_per_sec, labels)

    def record_error(self, operation: str, error: str, **labels: str) -> None:
        """Record an error occurrence.

        The value is always ``1.0``; analysis code should count points.

        Parameters
        ----------
        operation:
            Identifier for the operation.
        error:
            Error type or message.
        **labels:
            Additional dimension labels.
        """
        self._record(f"error_{operation}", 1.0, {**labels, "error": error})

    def record_gauge(self, name: str, value: float, **labels: str) -> None:
        """Record an arbitrary gauge metric.

        Parameters
        ----------
        name:
            Metric name (no prefix is added).
        value:
            Current value.
        **labels:
            Additional dimension labels.
        """
        self._record(name, value, labels)

    # ------------------------------------------------------------------ #
    # Thresholds & alerting
    # ------------------------------------------------------------------ #

    def set_threshold(self, metric: str, warning: float, critical: float) -> None:
        """Set alert thresholds for a metric.

        For latency metrics *warning* should be less than *critical* (alert
        when value **exceeds** the threshold).  For throughput metrics you
        may want to invert the logic via :meth:`alert_if_degraded`.

        Parameters
        ----------
        metric:
            Full metric name including prefix (e.g. ``"latency_llm_chat"``).
        warning:
            Value that triggers a ``"warning"`` alert.
        critical:
            Value that triggers a ``"critical"`` alert.
        """
        self._thresholds[metric] = (warning, critical)

    def add_alert_handler(self, handler: Callable[[Alert], None]) -> None:
        """Register a callback invoked for every fired alert.

        Handlers are called synchronously on the recording thread; for async
        handlers wrap them in ``asyncio.create_task`` inside your callback.
        """
        self._alert_handlers.append(handler)

    def get_recent_alerts(self, count: int = 50) -> List[Alert]:
        """Return the *count* most recent alerts (newest first)."""
        return list(self._alerts)[-count:][::-1]

    # ------------------------------------------------------------------ #
    # Dashboard & analysis
    # ------------------------------------------------------------------ #

    def get_dashboard(self) -> Dict[str, Any]:
        """Return a JSON-serialisable performance summary.

        The dashboard contains per-metric aggregates (count, min, max, mean,
        p95, p99) and the current circuit state for every metric that has
        data.
        """
        summary: Dict[str, Any] = {}
        for name, points in self._metrics.items():
            if not points:
                continue
            values = [p.value for p in points]
            stats: Dict[str, Any] = {
                "count": len(values),
                "min": min(values),
                "max": max(values),
                "mean": statistics.mean(values),
            }
            if len(values) >= 2:
                stats["stdev"] = statistics.stdev(values)
                sorted_vals = sorted(values)
                stats["p95"] = sorted_vals[int(len(sorted_vals) * 0.95)]
                stats["p99"] = sorted_vals[int(len(sorted_vals) * 0.99)]
            else:
                stats["stdev"] = 0.0
                stats["p95"] = values[0]
                stats["p99"] = values[0]

            # Include threshold configuration if present
            if name in self._thresholds:
                warn_thr, crit_thr = self._thresholds[name]
                stats["threshold_warning"] = warn_thr
                stats["threshold_critical"] = crit_thr
                stats["breached_warning"] = stats["max"] > warn_thr
                stats["breached_critical"] = stats["max"] > crit_thr

            summary[name] = stats

        return {
            "timestamp": time.time(),
            "metrics": summary,
            "total_metrics": len(summary),
            "alert_count": len(self._alerts),
        }

    def get_metric_stats(self, metric: str, window: Optional[int] = None) -> Dict[str, Any]:
        """Return statistics for a single metric.

        Parameters
        ----------
        metric:
            Full metric name.
        window:
            If given, only consider the last *window* points.

        Returns
        -------
        dict with keys ``count``, ``min``, ``max``, ``mean``, ``p95``, ``p99``.
        """
        if metric not in self._metrics:
            return {"count": 0, "min": 0.0, "max": 0.0, "mean": 0.0, "p95": 0.0, "p99": 0.0}

        pts = self._metrics[metric]
        if window:
            pts = deque(pts, maxlen=window) if window < len(pts) else pts
        values = [p.value for p in pts]
        if not values:
            return {"count": 0, "min": 0.0, "max": 0.0, "mean": 0.0, "p95": 0.0, "p99": 0.0}

        sorted_vals = sorted(values)
        return {
            "count": len(values),
            "min": sorted_vals[0],
            "max": sorted_vals[-1],
            "mean": statistics.mean(values),
            "p95": sorted_vals[int(len(sorted_vals) * 0.95)],
            "p99": sorted_vals[int(len(sorted_vals) * 0.99)],
        }

    def alert_if_degraded(
        self,
        metric: str,
        threshold: float = 0.8,
        lookback: int = 100,
    ) -> Optional[Alert]:
        """Check whether a metric has degraded below a ratio threshold.

        Compares the mean of the most recent *lookback//2* points against
        the mean of the preceding *lookback//2* points.  If the ratio is
        below *threshold* an :class:`Alert` is returned.

        This is useful for throughput metrics where a sudden drop indicates
        degradation.

        Parameters
        ----------
        metric:
            Metric name to analyse.
        threshold:
            Ratio below which degradation is flagged (default 0.8 = 20% drop).
        lookback:
            Number of historical points to consider (default 100).

        Returns
        -------
        Alert or None
        """
        if metric not in self._metrics or len(self._metrics[metric]) < lookback:
            return None

        points = list(self._metrics[metric])[-lookback:]
        half = len(points) // 2
        recent = [p.value for p in points[half:]]
        historical = [p.value for p in points[:half]]

        recent_mean = statistics.mean(recent)
        historical_mean = statistics.mean(historical)

        if historical_mean <= 0:
            return None

        ratio = recent_mean / historical_mean
        if ratio < threshold:
            alert = Alert(
                severity="warning" if ratio > threshold * 0.5 else "critical",
                metric=metric,
                message=(
                    f"Metric '{metric}' degraded: "
                    f"recent mean={recent_mean:.2f} vs "
                    f"historical mean={historical_mean:.2f} "
                    f"(ratio={ratio:.2f})"
                ),
                timestamp=time.time(),
                threshold=threshold,
                actual_value=ratio,
            )
            self._alerts.append(alert)
            self._dispatch_alert(alert)
            return alert
        return None

    def error_rate(self, operation: str, window_sec: float = 60.0) -> float:
        """Return the error rate for an operation over the last *window_sec*.

        The rate is ``errors / total_calls`` in the window.  Returns ``0.0``
        when there are no data points.
        """
        error_metric = f"error_{operation}"
        latency_metric = f"latency_{operation}"
        now = time.time()
        cutoff = now - window_sec

        error_count = sum(
            1 for p in self._metrics.get(error_metric, [])
            if p.timestamp >= cutoff
        )
        total_calls = sum(
            1 for p in self._metrics.get(latency_metric, [])
            if p.timestamp >= cutoff
        )
        if total_calls == 0:
            return 0.0
        return error_count / total_calls

    # ------------------------------------------------------------------ #
    # Internal
    # ------------------------------------------------------------------ #

    def _record(self, name: str, value: float, labels: Dict[str, str]) -> None:
        """Append a :class:`MetricPoint` and evaluate thresholds."""
        if name not in self._metrics:
            self._metrics[name] = deque(maxlen=self._history_size)
        point = MetricPoint(timestamp=time.time(), value=value, labels=labels)
        self._metrics[name].append(point)
        self._check_thresholds(name, value)

    def _check_thresholds(self, name: str, value: float) -> None:
        """Fire alerts when *value* breaches a configured threshold."""
        if name not in self._thresholds:
            return
        warning_thr, critical_thr = self._thresholds[name]

        # Cooldown check
        now = time.time()
        last_alert = self._alert_cooldowns.get(name, 0)
        if now - last_alert < self._cooldown_sec:
            return

        if value > critical_thr:
            alert = Alert(
                severity="critical",
                metric=name,
                message=f"Metric '{name}' = {value:.2f} exceeds critical threshold {critical_thr:.2f}",
                timestamp=now,
                threshold=critical_thr,
                actual_value=value,
            )
            self._alerts.append(alert)
            self._alert_cooldowns[name] = now
            self._dispatch_alert(alert)
        elif value > warning_thr:
            alert = Alert(
                severity="warning",
                metric=name,
                message=f"Metric '{name}' = {value:.2f} exceeds warning threshold {warning_thr:.2f}",
                timestamp=now,
                threshold=warning_thr,
                actual_value=value,
            )
            self._alerts.append(alert)
            self._alert_cooldowns[name] = now
            self._dispatch_alert(alert)

    def _dispatch_alert(self, alert: Alert) -> None:
        """Send *alert* to every registered handler, logging failures."""
        for handler in self._alert_handlers:
            try:
                handler(alert)
            except Exception:
                logger.exception("Alert handler failed for metric=%s", alert.metric)
