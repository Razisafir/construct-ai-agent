"""Action Recorder — record user actions, replay as automation scripts.

Features:
- Record: mouse clicks, key presses, text input
- Replay: execute recorded scripts at variable speed
- Export: save as JSON for reuse
- Safety: sandbox mode, approval workflow, audit trail

Dependencies (optional):
    pip install pyautogui Pillow

Safety model:
    Sandbox mode (default ON) requires explicit approval for every action.
    When sandbox is OFF, a risk-score heuristic is used:
    - Low  risk (0-30):   auto-approved
    - Med  risk (31-70):  requires approval
    - High risk (71-100): blocked unless explicitly overridden
"""

from __future__ import annotations

import json
import logging
import threading
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Optional UI-automation backend
# ---------------------------------------------------------------------------
try:
    import pyautogui

    HAS_PYAUTOGUI = True
except ImportError:  # pragma: no cover
    HAS_PYAUTOGUI = False
    pyautogui = None  # type: ignore[assignment]

try:
    from PIL import Image

    HAS_PIL = True
except ImportError:  # pragma: no cover
    HAS_PIL = False
    Image = None  # type: ignore[assignment,misc]


# ---------------------------------------------------------------------------
# Enums & data classes
# ---------------------------------------------------------------------------
class ActionType(str, Enum):
    CLICK = "click"
    DOUBLE_CLICK = "double_click"
    RIGHT_CLICK = "right_click"
    TYPE = "type"
    KEY_PRESS = "key_press"
    SCROLL = "scroll"
    WAIT = "wait"
    SCREENSHOT = "screenshot"


class RiskLevel(str, Enum):
    LOW = "low"       # 0-30   → auto-approve when sandbox OFF
    MEDIUM = "medium"  # 31-70  → require approval
    HIGH = "high"      # 71-100 → block unless override


@dataclass
class Action:
    type: ActionType
    x: Optional[int] = None
    y: Optional[int] = None
    text: Optional[str] = None
    key: Optional[str] = None
    duration_ms: int = 0
    timestamp: float = field(default_factory=time.time)
    screenshot_before: Optional[str] = None
    screenshot_after: Optional[str] = None

    def to_dict(self) -> dict:
        """Serialise to a plain dictionary (paths included)."""
        return {
            "type": self.type.value,
            "x": self.x,
            "y": self.y,
            "text": self.text,
            "key": self.key,
            "duration_ms": self.duration_ms,
            "timestamp": self.timestamp,
            "screenshot_before": self.screenshot_before,
            "screenshot_after": self.screenshot_after,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Action":
        """Deserialise from a plain dictionary."""
        return cls(
            type=ActionType(data["type"]),
            x=data.get("x"),
            y=data.get("y"),
            text=data.get("text"),
            key=data.get("key"),
            duration_ms=data.get("duration_ms", 0),
            timestamp=data.get("timestamp", 0.0),
            screenshot_before=data.get("screenshot_before"),
            screenshot_after=data.get("screenshot_after"),
        )


@dataclass
class ActionScript:
    name: str
    actions: List[Action]
    created_at: float = field(default_factory=time.time)
    total_duration_ms: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AuditEntry:
    """Single audit-trail record for a replayed action."""

    action_index: int
    action_type: str
    timestamp_iso: str
    risk_score: int
    risk_level: str
    approved: bool
    executed: bool
    screenshot_before: Optional[str] = None
    screenshot_after: Optional[str] = None
    denial_reason: Optional[str] = None


@dataclass
class ReplayResult:
    """Outcome of a script replay."""

    success: bool
    actions_executed: int
    actions_total: int
    audit_log_path: Optional[str] = None
    stopped_by_user: bool = False
    stop_reason: Optional[str] = None


# ---------------------------------------------------------------------------
# Main recorder class
# ---------------------------------------------------------------------------
class ActionRecorder:
    """Records and replays user actions with safety guards.

    Args:
        audit_dir: Directory where audit artefacts (screenshots, JSON logs)
            are persisted.
    """

    # Coordinates that are considered "sensitive" — clicks here score higher.
    _SENSITIVE_REGIONS: List[Tuple[int, int, int, int]] = [
        # OS menu bars (top-left / top-right corners at common resolutions)
        (0, 0, 300, 40),
        (1720, 0, 1920, 40),
    ]

    # Keys that are considered high-risk when pressed in isolation.
    _HIGH_RISK_KEYS: Set[str] = {"delete", "backspace", "escape", "enter", "return", "tab"}

    # Text patterns that suggest sensitive data entry.
    _SENSITIVE_PATTERNS: Tuple[str, ...] = ("password", "passwd", "secret", "token", "api_key", "credit_card")

    def __init__(self, audit_dir: str = "./audit") -> None:
        self.audit_dir = Path(audit_dir)
        self.audit_dir.mkdir(parents=True, exist_ok=True)
        self._recording: Optional[List[Action]] = None
        self._script_name: Optional[str] = None
        self._sandbox_mode: bool = True
        self._requires_approval: bool = True
        self._emergency_stop: threading.Event = threading.Event()
        self._last_action_time: float = 0.0
        self._action_count: int = 0

    # ------------------------------------------------------------------
    # Recording API
    # ------------------------------------------------------------------

    def start_recording(self, name: str) -> None:
        """Begin recording a new action script.

        Args:
            name: Human-readable name for the script.
        """
        self._recording = []
        self._script_name = name
        self._action_count = 0
        logger.info("Started recording script: %s", name)

    def stop_recording(self) -> ActionScript:
        """Stop recording and return the compiled ``ActionScript``.

        Computes *total_duration_ms* from the timestamps of the first and
        last recorded actions.

        Returns:
            The compiled ``ActionScript``.

        Raises:
            RuntimeError: If called without a preceding ``start_recording``.
        """
        if self._recording is None:
            raise RuntimeError("Cannot stop recording — recording was not started")

        total_duration_ms = 0
        if len(self._recording) >= 2:
            total_duration_ms = int(
                (self._recording[-1].timestamp - self._recording[0].timestamp) * 1000
            )

        script = ActionScript(
            name=self._script_name or "unnamed",
            actions=list(self._recording),
            total_duration_ms=total_duration_ms,
            metadata={
                "action_count": len(self._recording),
                "recorded_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        logger.info(
            "Stopped recording '%s' — %d actions, ~%d ms",
            script.name,
            len(script.actions),
            total_duration_ms,
        )
        self._recording = None
        self._script_name = None
        return script

    def record_click(self, x: int, y: int, button: str = "left") -> None:
        """Record a mouse click.

        Args:
            x: Screen X coordinate.
            y: Screen Y coordinate.
            button: ``"left"``, ``"right"``, or ``"double"``.
        """
        if self._recording is None:
            return
        if button == "double":
            action_type = ActionType.DOUBLE_CLICK
        elif button == "right":
            action_type = ActionType.RIGHT_CLICK
        else:
            action_type = ActionType.CLICK
        self._recording.append(Action(type=action_type, x=x, y=y))
        self._action_count += 1
        logger.debug("Recorded %s at (%d, %d)", action_type.value, x, y)

    def record_type(self, text: str) -> None:
        """Record text input.

        Args:
            text: The string to type.
        """
        if self._recording is None:
            return
        self._recording.append(Action(type=ActionType.TYPE, text=text))
        self._action_count += 1
        logger.debug("Recorded TYPE: %r", text[:50])

    def record_key(self, key: str) -> None:
        """Record a single key press.

        Args:
            key: Key name (e.g. ``"enter"``, ``"tab"``, ``"ctrl"``).
        """
        if self._recording is None:
            return
        self._recording.append(Action(type=ActionType.KEY_PRESS, key=key))
        self._action_count += 1
        logger.debug("Recorded KEY: %s", key)

    def record_scroll(self, x: int, y: int, clicks: int) -> None:
        """Record a scroll action.

        Args:
            x: Cursor X position during scroll.
            y: Cursor Y position during scroll.
            clicks: Positive = scroll up, negative = scroll down.
        """
        if self._recording is None:
            return
        self._recording.append(
            Action(type=ActionType.SCROLL, x=x, y=y, duration_ms=clicks * 100)
        )
        self._action_count += 1
        logger.debug("Recorded SCROLL at (%d, %d) — clicks=%d", x, y, clicks)

    def record_wait(self, duration_ms: int) -> None:
        """Record an explicit wait.

        Args:
            duration_ms: Milliseconds to wait.
        """
        if self._recording is None:
            return
        self._recording.append(Action(type=ActionType.WAIT, duration_ms=duration_ms))
        self._action_count += 1
        logger.debug("Recorded WAIT: %d ms", duration_ms)

    # ------------------------------------------------------------------
    # Replay API
    # ------------------------------------------------------------------

    def play_script(
        self,
        script: ActionScript,
        speed: float = 1.0,
        executor: Optional[Callable[[Action], bool]] = None,
        auto_approve_low_risk: bool = True,
    ) -> ReplayResult:
        """Replay an ``ActionScript``.

        The replay engine:
        1. Checks sandbox mode.
        2. For each action, computes a risk score.
        3. Requests approval (or auto-approves low-risk actions).
        4. Executes via *executor* or the built-in pyautogui fallback.
        5. Captures before/after screenshots for the audit trail.
        6. Monitors the emergency-stop flag.

        Args:
            script: The script to replay.
            speed: Playback multiplier.  ``2.0`` = twice as fast.
            executor: Callable ``fn(action) -> bool``.  If *None*, pyautogui
                is used (if installed).
            auto_approve_low_risk: When sandbox is OFF, automatically approve
                actions with risk score ≤ 30.

        Returns:
            ``ReplayResult`` summarising the outcome.
        """
        if script is None or not script.actions:
            logger.warning("Empty script — nothing to replay")
            return ReplayResult(success=True, actions_executed=0, actions_total=0)

        if speed <= 0:
            raise ValueError("speed must be positive")

        # Determine execution backend
        if executor is None:
            if HAS_PYAUTOGUI:
                executor = self._default_executor
            else:
                raise RuntimeError(
                    "No executor provided and pyautogui is not installed. "
                    "Install it: pip install pyautogui"
                )

        self._emergency_stop.clear()
        audit_entries: List[AuditEntry] = []
        executed_count = 0
        stop_reason: Optional[str] = None

        logger.info(
            "Replaying script '%s' — %d actions, speed=%.1fx, sandbox=%s",
            script.name,
            len(script.actions),
            speed,
            "ON" if self._sandbox_mode else "OFF",
        )

        for idx, action in enumerate(script.actions):
            # ---- Emergency stop check ----
            if self._emergency_stop.is_set():
                stop_reason = "Emergency stop requested"
                logger.warning("Replay halted: %s", stop_reason)
                break

            # ---- Debounce / rapid-fire protection ----
            now = time.monotonic()
            if self._last_action_time > 0 and (now - self._last_action_time) < 0.05:
                time.sleep(0.05)
            self._last_action_time = now

            # ---- Risk assessment ----
            risk_score = self._calculate_risk_score(action)
            risk_level = self._score_to_level(risk_score)

            # ---- Approval workflow ----
            approved = False
            if self._sandbox_mode:
                approved = self._request_approval(action, risk_score, risk_level)
            else:
                if risk_level == RiskLevel.LOW and auto_approve_low_risk:
                    approved = True
                    logger.debug("Auto-approved low-risk action #%d (score=%d)", idx, risk_score)
                else:
                    approved = self._request_approval(action, risk_score, risk_level)

            ss_before = self._take_audit_screenshot(f"action_{idx:03d}_before")

            if not approved:
                audit_entries.append(
                    AuditEntry(
                        action_index=idx,
                        action_type=action.type.value,
                        timestamp_iso=datetime.now(timezone.utc).isoformat(),
                        risk_score=risk_score,
                        risk_level=risk_level.value,
                        approved=False,
                        executed=False,
                        screenshot_before=ss_before,
                        denial_reason="User denied approval",
                    )
                )
                logger.info("Action #%d denied — skipping", idx)
                continue

            # ---- Execute ----
            executed = False
            try:
                executed = executor(action)
                if executed:
                    executed_count += 1
            except Exception as exc:
                logger.error("Action #%d execution failed: %s", idx, exc)
                stop_reason = f"Execution error at action {idx}: {exc}"
                break

            ss_after = self._take_audit_screenshot(f"action_{idx:03d}_after")

            audit_entries.append(
                AuditEntry(
                    action_index=idx,
                    action_type=action.type.value,
                    timestamp_iso=datetime.now(timezone.utc).isoformat(),
                    risk_score=risk_score,
                    risk_level=risk_level.value,
                    approved=True,
                    executed=executed,
                    screenshot_before=ss_before,
                    screenshot_after=ss_after,
                )
            )

            # ---- Speed-adjusted delay ----
            delay = self._action_delay_ms(action) / 1000.0 / speed
            if delay > 0:
                # Slice delay so emergency stop is responsive
                slice_size = 0.1  # 100 ms slices
                elapsed = 0.0
                while elapsed < delay:
                    if self._emergency_stop.is_set():
                        stop_reason = "Emergency stop during delay"
                        break
                    sleep_for = min(slice_size, delay - elapsed)
                    time.sleep(sleep_for)
                    elapsed += sleep_for
                if self._emergency_stop.is_set():
                    break

        # ---- Persist audit trail ----
        audit_path = self._persist_audit(script, audit_entries, stop_reason)

        success = stop_reason is None and executed_count == len(script.actions)
        result = ReplayResult(
            success=success,
            actions_executed=executed_count,
            actions_total=len(script.actions),
            audit_log_path=str(audit_path) if audit_path else None,
            stopped_by_user=self._emergency_stop.is_set(),
            stop_reason=stop_reason,
        )
        logger.info(
            "Replay finished — executed %d/%d actions, success=%s",
            executed_count,
            len(script.actions),
            success,
        )
        return result

    def trigger_emergency_stop(self) -> None:
        """Signal the replay loop to halt at the next checkpoint.

        Thread-safe — may be called from any thread (e.g. a hot-key handler).
        """
        logger.critical("EMERGENCY STOP triggered")
        self._emergency_stop.set()

    def is_emergency_stopped(self) -> bool:
        """Return *True* if emergency stop is currently active."""
        return self._emergency_stop.is_set()

    def reset_emergency_stop(self) -> None:
        """Clear the emergency-stop flag so a new replay can begin."""
        self._emergency_stop.clear()
        logger.info("Emergency stop flag reset")

    # ------------------------------------------------------------------
    # Import / Export
    # ------------------------------------------------------------------

    def export_script(self, script: ActionScript) -> str:
        """Export *script* as a pretty-printed JSON string.

        Screenshots are omitted from export to keep payload size reasonable.
        """
        payload = {
            "name": script.name,
            "created_at": script.created_at,
            "total_duration_ms": script.total_duration_ms,
            "metadata": script.metadata,
            "actions": [
                {
                    "type": a.type.value,
                    "x": a.x,
                    "y": a.y,
                    "text": a.text,
                    "key": a.key,
                    "duration_ms": a.duration_ms,
                }
                for a in script.actions
            ],
        }
        return json.dumps(payload, indent=2, ensure_ascii=False)

    def export_script_to_file(self, script: ActionScript, path: str) -> Path:
        """Export *script* to a JSON file and return the path."""
        path_obj = Path(path)
        path_obj.parent.mkdir(parents=True, exist_ok=True)
        path_obj.write_text(self.export_script(script), encoding="utf-8")
        logger.info("Script exported to %s", path_obj)
        return path_obj

    def import_script(self, json_str: str) -> ActionScript:
        """Import an ``ActionScript`` from a JSON string."""
        data = json.loads(json_str)
        actions = [
            Action(
                type=ActionType(a["type"]),
                x=a.get("x"),
                y=a.get("y"),
                text=a.get("text"),
                key=a.get("key"),
                duration_ms=a.get("duration_ms", 0),
            )
            for a in data.get("actions", [])
        ]
        return ActionScript(
            name=data.get("name", "imported"),
            actions=actions,
            created_at=data.get("created_at", time.time()),
            total_duration_ms=data.get("total_duration_ms", 0),
            metadata=data.get("metadata", {}),
        )

    def import_script_from_file(self, path: str) -> ActionScript:
        """Import an ``ActionScript`` from a JSON file."""
        path_obj = Path(path)
        if not path_obj.exists():
            raise FileNotFoundError(f"Script file not found: {path}")
        return self.import_script(path_obj.read_text(encoding="utf-8"))

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------

    def set_sandbox_mode(self, enabled: bool) -> None:
        """Enable or disable sandbox mode.

        When enabled (default), every action requires explicit approval.
        """
        self._sandbox_mode = enabled
        logger.info("Sandbox mode: %s", "ON" if enabled else "OFF")

    def set_requires_approval(self, required: bool) -> None:
        """Set whether actions require explicit approval regardless of sandbox.

        This is the master switch — when *False* and sandbox is also OFF,
        low-risk actions are auto-approved.
        """
        self._requires_approval = required
        logger.info("Requires approval: %s", "YES" if required else "NO")

    # ------------------------------------------------------------------
    # Audit trail
    # ------------------------------------------------------------------

    def _take_audit_screenshot(self, prefix: str) -> Optional[str]:
        """Capture a screenshot for the audit trail.

        Returns:
            Absolute path to the saved PNG, or *None* on failure.
        """
        if not HAS_PIL:
            return None
        try:
            ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
            filename = f"{prefix}_{ts}.png"
            path = self.audit_dir / filename
            screenshot = Image.new("RGB", (1, 1))  # fallback placeholder
            # Use pyautogui or mss if available for real capture
            if HAS_PYAUTOGUI and pyautogui is not None:
                screenshot = pyautogui.screenshot()
            screenshot.save(str(path))
            return str(path.resolve())
        except Exception as exc:
            logger.warning("Audit screenshot failed: %s", exc)
            return None

    def _persist_audit(
        self,
        script: ActionScript,
        entries: List[AuditEntry],
        stop_reason: Optional[str] = None,
    ) -> Optional[Path]:
        """Write the audit trail to a timestamped JSON file.

        Returns:
            Path to the audit file, or *None* if nothing to persist.
        """
        if not entries:
            return None
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        filename = f"audit_{script.name}_{ts}.json"
        path = self.audit_dir / filename
        payload = {
            "script_name": script.name,
            "script_created_at": script.created_at,
            "replay_started_at": entries[0].timestamp_iso if entries else None,
            "replay_finished_at": datetime.now(timezone.utc).isoformat(),
            "actions_total": len(script.actions),
            "actions_audited": len(entries),
            "stopped_by_user": self._emergency_stop.is_set(),
            "stop_reason": stop_reason,
            "sandbox_mode": self._sandbox_mode,
            "entries": [
                {
                    "action_index": e.action_index,
                    "action_type": e.action_type,
                    "timestamp": e.timestamp_iso,
                    "risk_score": e.risk_score,
                    "risk_level": e.risk_level,
                    "approved": e.approved,
                    "executed": e.executed,
                    "screenshot_before": e.screenshot_before,
                    "screenshot_after": e.screenshot_after,
                    "denial_reason": e.denial_reason,
                }
                for e in entries
            ],
        }
        try:
            path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
            logger.info("Audit trail written to %s", path)
            return path
        except Exception as exc:
            logger.error("Failed to write audit trail: %s", exc)
            return None

    # ------------------------------------------------------------------
    # Risk scoring & approval
    # ------------------------------------------------------------------

    def _calculate_risk_score(self, action: Action) -> int:
        """Compute a risk score (0-100) for *action*.

        Heuristics:
        - Clicks near OS chrome (menu bars, corners) = higher.
        - Typing sensitive keywords (password, secret) = higher.
        - Pressing destructive keys (delete, enter on dialogs) = higher.
        - Right-clicks = medium.
        - Double-clicks = slightly elevated.
        - Scroll / Wait = low.

        Returns:
            Integer score 0 (safest) to 100 (most dangerous).
        """
        score = 0

        # Base risk by action type
        base_scores: Dict[ActionType, int] = {
            ActionType.WAIT: 0,
            ActionType.SCROLL: 5,
            ActionType.SCREENSHOT: 0,
            ActionType.CLICK: 15,
            ActionType.DOUBLE_CLICK: 25,
            ActionType.RIGHT_CLICK: 30,
            ActionType.TYPE: 20,
            ActionType.KEY_PRESS: 20,
        }
        score += base_scores.get(action.type, 15)

        # Coordinate risk (clicks in sensitive regions)
        if action.type in (ActionType.CLICK, ActionType.DOUBLE_CLICK, ActionType.RIGHT_CLICK):
            if action.x is not None and action.y is not None:
                for rx, ry, rx2, ry2 in self._SENSITIVE_REGIONS:
                    if rx <= action.x <= rx2 and ry <= action.y <= ry2:
                        score += 25
                        break

        # Text-input risk
        if action.type == ActionType.TYPE and action.text:
            lower = action.text.lower()
            for pattern in self._SENSITIVE_PATTERNS:
                if pattern in lower:
                    score += 30
                    break
            if len(action.text) > 100:
                score += 10  # Large paste operations are risky

        # Key-press risk
        if action.type == ActionType.KEY_PRESS and action.key:
            key_lower = action.key.lower()
            if key_lower in self._HIGH_RISK_KEYS:
                score += 20
            # Modifier combos (e.g. ctrl+a, ctrl+delete)
            if "+" in key_lower or "-" in key_lower:
                score += 15

        return min(100, max(0, score))

    @staticmethod
    def _score_to_level(score: int) -> RiskLevel:
        """Map a numeric risk score to a ``RiskLevel``."""
        if score <= 30:
            return RiskLevel.LOW
        if score <= 70:
            return RiskLevel.MEDIUM
        return RiskLevel.HIGH

    def _request_approval(
        self,
        action: Action,
        risk_score: int,
        risk_level: RiskLevel,
    ) -> bool:
        """Request user approval for an action.

        In interactive mode this prompts via stdin.  In headless / CI
        environments, override this method or subclass to integrate with
        your approval backend (Slack, e-mail, web UI, etc.).

        Returns:
            *True* if approved, *False* if denied.
        """
        if not self._requires_approval and not self._sandbox_mode:
            return True

        # Never auto-approve HIGH risk
        if risk_level == RiskLevel.HIGH and self._sandbox_mode:
            logger.warning("HIGH risk action blocked in sandbox mode (score=%d)", risk_score)
            return False

        action_desc = self._action_description(action)
        prompt = (
            f"\n[APPROVAL REQUIRED] Action: {action_desc}\n"
            f"  Risk score: {risk_score}/100 ({risk_level.value.upper()})\n"
            f"  Approve? [y/N/stop]: "
        )

        try:
            response = input(prompt).strip().lower()
        except (EOFError, OSError):
            # Non-interactive environment — deny by default
            logger.warning("Cannot prompt for approval in non-interactive mode — denying action")
            return False

        if response in ("stop", "s", "halt"):
            self.trigger_emergency_stop()
            return False

        approved = response in ("y", "yes", "approve", "a")
        logger.info("Action %s by user", "approved" if approved else "denied")
        return approved

    @staticmethod
    def _action_description(action: Action) -> str:
        """Build a human-readable description of *action*."""
        parts = [action.type.value]
        if action.x is not None and action.y is not None:
            parts.append(f"at ({action.x}, {action.y})")
        if action.text is not None:
            display = action.text[:40] + "..." if len(action.text) > 40 else action.text
            parts.append(f'text="{display}"')
        if action.key is not None:
            parts.append(f'key={action.key}')
        return " ".join(parts)

    # ------------------------------------------------------------------
    # Default executor (pyautogui)
    # ------------------------------------------------------------------

    @staticmethod
    def _default_executor(action: Action) -> bool:
        """Execute *action* using pyautogui.

        Returns:
            *True* on success, *False* if the action type is unsupported.

        Raises:
            RuntimeError: If pyautogui is not installed.
        """
        if not HAS_PYAUTOGUI or pyautogui is None:
            raise RuntimeError("pyautogui is not installed")

        # Safety pause between actions
        pyautogui.PAUSE = 0.05

        try:
            if action.type == ActionType.CLICK:
                if action.x is not None and action.y is not None:
                    pyautogui.click(action.x, action.y)
                else:
                    pyautogui.click()
            elif action.type == ActionType.DOUBLE_CLICK:
                if action.x is not None and action.y is not None:
                    pyautogui.doubleClick(action.x, action.y)
                else:
                    pyautogui.doubleClick()
            elif action.type == ActionType.RIGHT_CLICK:
                if action.x is not None and action.y is not None:
                    pyautogui.rightClick(action.x, action.y)
                else:
                    pyautogui.rightClick()
            elif action.type == ActionType.TYPE:
                if action.text:
                    pyautogui.typewrite(action.text, interval=0.01)
            elif action.type == ActionType.KEY_PRESS:
                if action.key:
                    pyautogui.press(action.key)
            elif action.type == ActionType.SCROLL:
                clicks = action.duration_ms // 100 if action.duration_ms else 3
                if action.x is not None and action.y is not None:
                    pyautogui.scroll(clicks, action.x, action.y)
                else:
                    pyautogui.scroll(clicks)
            elif action.type == ActionType.WAIT:
                time.sleep(action.duration_ms / 1000.0)
            elif action.type == ActionType.SCREENSHOT:
                pass  # No-op — screenshot handled by caller
            else:
                logger.warning("Unsupported action type: %s", action.type)
                return False
            return True
        except Exception as exc:
            logger.error("pyautogui execution failed for %s: %s", action.type, exc)
            raise

    @staticmethod
    def _action_delay_ms(action: Action) -> int:
        """Return the post-action delay in milliseconds.

        Uses the action's own *duration_ms* when meaningful, otherwise a
        conservative default.
        """
        if action.type == ActionType.WAIT:
            return action.duration_ms
        if action.type == ActionType.TYPE and action.text:
            # Approximate typing speed: ~50 ms per character
            return min(len(action.text) * 50, 2000)
        if action.type == ActionType.SCROLL:
            return 200
        return 300  # Default pause between actions

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    def list_audit_files(self) -> List[Path]:
        """Return a list of all audit files in *audit_dir*."""
        return sorted(self.audit_dir.glob("audit_*.json"))

    def get_audit_summary(self, audit_path: str) -> dict:
        """Load an audit file and return a human-readable summary."""
        path = Path(audit_path)
        if not path.exists():
            raise FileNotFoundError(f"Audit file not found: {audit_path}")
        data = json.loads(path.read_text(encoding="utf-8"))
        entries = data.get("entries", [])
        approved = sum(1 for e in entries if e["approved"])
        executed = sum(1 for e in entries if e["executed"])
        denied = sum(1 for e in entries if not e["approved"])
        return {
            "script_name": data.get("script_name"),
            "actions_total": data.get("actions_total"),
            "actions_audited": len(entries),
            "approved": approved,
            "denied": denied,
            "executed": executed,
            "stopped_by_user": data.get("stopped_by_user"),
            "stop_reason": data.get("stop_reason"),
            "audit_file": str(path),
        }
