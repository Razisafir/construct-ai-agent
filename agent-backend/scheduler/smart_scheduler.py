"""Smart Scheduler — activity-aware background task scheduling.

Adjusts agent workload based on user activity, time of day, and power state.

Platform Support:
- Linux: /proc/interrupts, /dev/input, psutil, upower (battery)
- macOS: IOKit (activity), pmset (battery), IOKit power sources
- Windows: GetLastInputInfo (activity), GetSystemPowerStatus (battery)
- Fallback: time-based heuristics when platform detection unavailable
"""

from __future__ import annotations

import asyncio
import logging
import os
import platform
import struct
import subprocess
import sys
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Coroutine, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class ActivityLevel(str, Enum):
    """User activity level classification."""

    ACTIVE = "active"  # User is typing/mousing
    IDLE = "idle"  # No input for 5+ minutes
    AWAY = "away"  # No input for 30+ minutes
    SLEEP = "sleep"  # System is sleeping


class PowerState(str, Enum):
    """System power source classification."""

    AC_POWER = "ac"
    BATTERY = "battery"
    UNKNOWN = "unknown"


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


@dataclass
class ScheduleConfig:
    """Configuration for the SmartScheduler.

    All throttle percentages are CPU-utilisation targets (0–100).
    Quiet hours use the *most restrictive* of the applicable rules.
    """

    active_throttle_percent: int = 10  # CPU % when user active
    idle_throttle_percent: int = 50  # CPU % when user idle
    away_throttle_percent: int = 100  # Full speed when away
    battery_throttle_percent: int = 25  # CPU % on battery
    quiet_hours_start: int = 22  # 22:00 inclusive
    quiet_hours_end: int = 8  # 08:00 exclusive
    checkpoint_interval_sec: int = 120  # Save every 2 minutes
    activity_check_interval_sec: float = 30.0  # How often to poll
    idle_threshold_sec: float = 300.0  # 5 min → IDLE
    away_threshold_sec: float = 1800.0  # 30 min → AWAY


# ---------------------------------------------------------------------------
# Scheduler
# ---------------------------------------------------------------------------


class SmartScheduler:
    """Schedules background agent work based on system state.

    The scheduler runs an asyncio loop that periodically samples:
    1. User activity level (keyboard / mouse / active window)
    2. Power state (AC vs battery)
    3. Quiet hours

    It exposes a ``current_throttle`` property (0–100) that other
    components should respect when deciding how much work to do.
    """

    def __init__(self, config: Optional[ScheduleConfig] = None) -> None:
        self.config = config or ScheduleConfig()
        self._running: bool = False
        self._activity_level: ActivityLevel = ActivityLevel.IDLE
        self._power_state: PowerState = PowerState.UNKNOWN
        self._current_throttle: int = 100
        self._last_activity_time: float = time.time()
        self._sleep_detected_at: Optional[float] = None
        self._task: Optional[asyncio.Task[None]] = None
        self._listeners: list[Callable[[int], Coroutine[Any, Any, None]]] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Start the scheduler monitoring loop.

        Spawns a background asyncio task that polls system state and
        updates ``current_throttle`` every ``activity_check_interval_sec``.
        """
        if self._running:
            logger.warning("SmartScheduler already running")
            return
        self._running = True
        self._task = asyncio.create_task(self._monitor_loop())
        logger.info("SmartScheduler started")

    def stop(self) -> None:
        """Stop the scheduler and cancel the background task."""
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
        logger.info("SmartScheduler stopped")

    @property
    def current_throttle(self) -> int:
        """Current CPU throttle percentage (0–100).

        Consumers should treat this as a target utilisation ceiling.
        """
        return self._current_throttle

    @property
    def activity_level(self) -> ActivityLevel:
        """Most recently detected user activity level."""
        return self._activity_level

    @property
    def power_state(self) -> PowerState:
        """Most recently detected power state."""
        return self._power_state

    def should_run_task(self, task_priority: str = "normal") -> bool:
        """Check if a task should be executed now.

        Args:
            task_priority: One of ``"low"``, ``"normal"``, ``"high"``.
                High-priority tasks always run. Low-priority tasks are
                deferred during active hours.

        Returns:
            ``True`` if the task may proceed.
        """
        if task_priority == "high":
            return True
        if self._activity_level == ActivityLevel.ACTIVE and task_priority == "low":
            return False
        if self._activity_level == ActivityLevel.SLEEP:
            return task_priority == "high"
        return True

    def get_checkpoint_interval(self) -> int:
        """Return current checkpoint interval in seconds.

        The interval is shortened when the user is active (more frequent
        saves) and lengthened when away (fewer saves needed).
        """
        base = self.config.checkpoint_interval_sec
        if self._activity_level == ActivityLevel.ACTIVE:
            return max(30, base // 4)
        if self._activity_level == ActivityLevel.IDLE:
            return base
        if self._activity_level == ActivityLevel.AWAY:
            return base * 2
        # SLEEP — checkpoint already handled by sleep detection
        return base

    def add_listener(
        self, callback: Callable[[int], Coroutine[Any, Any, None]]
    ) -> None:
        """Register an async callback invoked whenever throttle changes.

        The callback receives the new throttle percentage (0–100).
        """
        self._listeners.append(callback)

    # ------------------------------------------------------------------
    # Monitoring loop
    # ------------------------------------------------------------------

    async def _monitor_loop(self) -> None:
        """Main monitoring loop — runs until ``stop()`` is called."""
        while self._running:
            try:
                await self._tick()
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("Scheduler tick failed")
            try:
                await asyncio.sleep(self.config.activity_check_interval_sec)
            except asyncio.CancelledError:
                break

    async def _tick(self) -> None:
        """Single scheduler tick: sample state, update throttle, notify."""
        prev_throttle = self._current_throttle

        self._activity_level = self._detect_activity()
        self._power_state = self._detect_power_state()
        self._current_throttle = self._calculate_throttle()

        logger.debug(
            "tick: activity=%s power=%s throttle=%d%%",
            self._activity_level.value,
            self._power_state.value,
            self._current_throttle,
        )

        if self._current_throttle != prev_throttle:
            logger.info(
                "Throttle changed %d%% → %d%% (activity=%s, power=%s)",
                prev_throttle,
                self._current_throttle,
                self._activity_level.value,
                self._power_state.value,
            )
            await self._notify_listeners()

    async def _notify_listeners(self) -> None:
        """Notify all registered listeners of a throttle change."""
        for cb in self._listeners:
            try:
                await cb(self._current_throttle)
            except Exception:
                logger.exception("Throttle listener failed")

    # ------------------------------------------------------------------
    # Activity detection — platform-specific
    # ------------------------------------------------------------------

    def _detect_activity(self) -> ActivityLevel:
        """Detect current user activity level.

        Tries platform-specific APIs in order:
        1. Windows: ``GetLastInputInfo``
        2. macOS: ``IOKit`` (via ctypes)
        3. Linux: ``X11``/``Wayland`` idle time via ``XScreenSaverInfo`` or ``loginctl``
        4. Linux: ``/proc/interrupts`` heuristic
        5. Fallback: time-based (last time *this* process saw activity)

        Returns:
            The detected :class:`ActivityLevel`.
        """
        system = platform.system()
        idle_seconds: Optional[float] = None

        if system == "Windows":
            idle_seconds = self._detect_idle_windows()
        elif system == "Darwin":
            idle_seconds = self._detect_idle_macos()
        elif system == "Linux":
            idle_seconds = self._detect_idle_linux()

        if idle_seconds is None:
            # Fallback — use our own session's last-activity timestamp
            idle_seconds = time.time() - self._last_activity_time

        # Sleep detection: if idle time jumped by a large amount,
        # the system may have been asleep.
        if self._detect_sleep_transition(idle_seconds):
            return ActivityLevel.SLEEP

        if idle_seconds >= self.config.away_threshold_sec:
            return ActivityLevel.AWAY
        if idle_seconds >= self.config.idle_threshold_sec:
            return ActivityLevel.IDLE
        return ActivityLevel.ACTIVE

    # -- Windows -------------------------------------------------------

    def _detect_idle_windows(self) -> Optional[float]:
        """Return idle seconds on Windows using ``GetLastInputInfo``."""
        try:
            import ctypes
            from ctypes import wintypes

            class LASTINPUTINFO(ctypes.Structure):
                _fields_ = [
                    ("cbSize", wintypes.UINT),
                    ("dwTime", wintypes.DWORD),
                ]

            user32 = ctypes.windll.user32
            lii = LASTINPUTINFO()
            lii.cbSize = ctypes.sizeof(LASTINPUTINFO)
            if user32.GetLastInputInfo(ctypes.byref(lii)):
                millis = ctypes.windll.kernel32.GetTickCount() - lii.dwTime
                return millis / 1000.0
        except Exception as exc:
            logger.debug("Windows idle detection failed: %s", exc)
        return None

    # -- macOS ---------------------------------------------------------

    def _detect_idle_macos(self) -> Optional[float]:
        """Return idle seconds on macOS using IOKit."""
        try:
            import ctypes
            from ctypes import c_double, c_void_p, cdll

            iokit = cdll.LoadLibrary("/System/Library/Frameworks/IOKit.framework/IOKit")
            cf = cdll.LoadLibrary("/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation")

            kIOHIDSystem = ctypes.c_void_p.in_dll(iokit, "kIOHIDSystem")
            iokit.IOServiceMatching.restype = c_void_p
            iokit.IOServiceGetMatchingService.argtypes = [c_void_p, c_void_p]
            iokit.IOServiceGetMatchingService.restype = c_void_p
            iokit.IOServiceOpen.argtypes = [c_void_p, c_void_p, ctypes.c_uint32, ctypes.POINTER(c_void_p)]

            hid_system = iokit.IOServiceGetMatchingService(
                0, iokit.IOServiceMatching(b"IOHIDSystem")
            )
            if not hid_system:
                return None

            port = c_void_p()
            if iokit.IOServiceOpen(hid_system, 0, 0, ctypes.byref(port)) != 0:
                return None

            # Get HIDIdleTime property
            iokit.IORegistryEntryCreateCFProperties.argtypes = [
                c_void_p, ctypes.POINTER(c_void_p), c_void_p, ctypes.c_uint32
            ]
            props = c_void_p()
            if iokit.IORegistryEntryCreateCFProperties(hid_system, ctypes.byref(props), 0, 0) == 0:
                cf.CFDictionaryGetValue.restype = c_void_p
                cf.CFNumberGetValue.argtypes = [c_void_p, ctypes.c_int, ctypes.c_void_p]

                key = cf.CFStringCreateWithCString(0, b"HIDIdleTime", 0)
                value = cf.CFDictionaryGetValue(props, key)
                if value:
                    nano = ctypes.c_uint64()
                    cf.CFNumberGetValue(value, 4, ctypes.byref(nano))  # kCFNumberSInt64Type = 4
                    idle_seconds = nano.value / 1e9
                    cf.CFRelease(props)
                    cf.CFRelease(key)
                    iokit.IOServiceClose(port)
                    return idle_seconds
                cf.CFRelease(key)
                cf.CFRelease(props)
            iokit.IOServiceClose(port)
        except Exception as exc:
            logger.debug("macOS idle detection failed: %s", exc)
        return None

    # -- Linux ---------------------------------------------------------

    def _detect_idle_linux(self) -> Optional[float]:
        """Return idle seconds on Linux via multiple methods."""
        # Try X11 idle time via xprintidle
        idle = self._detect_idle_linux_x11()
        if idle is not None:
            return idle

        # Try loginctl show-session
        idle = self._detect_idle_linux_loginctl()
        if idle is not None:
            return idle

        # Fallback: /proc/interrupts heuristic
        return self._detect_idle_linux_proc()

    def _detect_idle_linux_x11(self) -> Optional[float]:
        """Use xprintidle (if available) to get idle milliseconds."""
        try:
            result = subprocess.run(
                ["xprintidle"],
                capture_output=True,
                text=True,
                timeout=2,
            )
            if result.returncode == 0:
                millis = int(result.stdout.strip())
                return millis / 1000.0
        except (FileNotFoundError, subprocess.TimeoutExpired, ValueError):
            pass
        return None

    def _detect_idle_linux_loginctl(self) -> Optional[float]:
        """Use loginctl to check session idle status."""
        try:
            result = subprocess.run(
                ["loginctl", "show-session", "self", "-p", "IdleSinceHint"],
                capture_output=True,
                text=True,
                timeout=2,
            )
            if result.returncode == 0 and result.stdout.strip():
                line = result.stdout.strip()
                if "IdleSinceHint=" in line:
                    value = line.split("=", 1)[1].strip()
                    if value and value != "0":
                        idle_since_usec = int(value)
                        idle_since = idle_since_usec / 1e6
                        return time.time() - idle_since
        except (FileNotFoundError, subprocess.TimeoutExpired, ValueError):
            pass
        return None

    def _detect_idle_linux_proc(self) -> Optional[float]:
        """Estimate idle time by watching keyboard interrupt count changes.

        Compares current /proc/interrupts against a cached snapshot.
        If keyboard interrupts haven't changed, the user may be idle.
        """
        try:
            proc_path = Path("/proc/interrupts")
            if not proc_path.exists():
                return None

            data = proc_path.read_text()
            # Look for i8042 (keyboard controller) lines
            kb_lines = [ln for ln in data.splitlines() if "i8042" in ln or "KeyBoard" in ln]
            if not kb_lines:
                return None

            current_hash = hash("".join(kb_lines))
            now = time.time()

            cached = getattr(self, "_proc_cache", None)
            if cached is None:
                self._proc_cache = (current_hash, now)
                return 0.0

            prev_hash, prev_time = cached
            if current_hash != prev_hash:
                # Activity detected — update cache
                self._proc_cache = (current_hash, now)
                self._last_activity_time = now
                return 0.0

            # No change — return elapsed since last activity
            return now - prev_time
        except Exception as exc:
            logger.debug("/proc/interrupts idle detection failed: %s", exc)
        return None

    # -- Sleep detection -----------------------------------------------

    def _detect_sleep_transition(self, idle_seconds: float) -> bool:
        """Detect if the system just woke from sleep.

        Heuristic: if our own monotonic clock shows a large gap compared
        to the expected poll interval, the system was likely asleep.
        """
        now = time.time()
        if self._sleep_detected_at is not None:
            # We already detected sleep; clear it after a short grace period
            if now - self._sleep_detected_at > 60:
                self._sleep_detected_at = None
            return True

        # If idle_seconds is huge (e.g., > 2 hours) but we were polling
        # every 30s, the system was probably asleep.
        expected_max_idle = self.config.activity_check_interval_sec * 2
        if idle_seconds > expected_max_idle and idle_seconds > 3600:
            logger.info("Sleep transition detected (idle=%.0fs)", idle_seconds)
            self._sleep_detected_at = now
            return True
        return False

    # ------------------------------------------------------------------
    # Power detection — platform-specific
    # ------------------------------------------------------------------

    def _detect_power_state(self) -> PowerState:
        """Detect whether the system is on AC or battery power.

        Tries platform-specific APIs in order, falling back to
        :data:`PowerState.UNKNOWN`.
        """
        system = platform.system()

        if system == "Linux":
            return self._detect_power_linux()
        if system == "Darwin":
            return self._detect_power_macos()
        if system == "Windows":
            return self._detect_power_windows()

        return PowerState.UNKNOWN

    def _detect_power_linux(self) -> PowerState:
        """Check ``/sys/class/power_supply`` for battery status."""
        try:
            power_supply = Path("/sys/class/power_supply")
            if not power_supply.exists():
                return PowerState.UNKNOWN

            for entry in power_supply.iterdir():
                type_file = entry / "type"
                if not type_file.exists():
                    continue
                dev_type = type_file.read_text().strip()
                if dev_type == "Battery":
                    status_file = entry / "status"
                    if status_file.exists():
                        status = status_file.read_text().strip()
                        if status in ("Discharging", "Not charging"):
                            return PowerState.BATTERY
                        if status in ("Charging", "Full", "Unknown"):
                            return PowerState.AC_POWER
            # No battery found → assume AC
            return PowerState.AC_POWER
        except Exception as exc:
            logger.debug("Linux power detection failed: %s", exc)
        return PowerState.UNKNOWN

    def _detect_power_macos(self) -> PowerState:
        """Use ``pmset`` to detect power source on macOS."""
        try:
            result = subprocess.run(
                ["pmset", "-g", "ps"],
                capture_output=True,
                text=True,
                timeout=2,
            )
            if result.returncode == 0:
                output = result.stdout.lower()
                if "ac power" in output or "attached" in output:
                    return PowerState.AC_POWER
                if "battery" in output:
                    return PowerState.BATTERY
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
        return PowerState.UNKNOWN

    def _detect_power_windows(self) -> PowerState:
        """Use ``GetSystemPowerStatus`` on Windows."""
        try:
            import ctypes
            from ctypes import wintypes

            class SYSTEM_POWER_STATUS(ctypes.Structure):
                _fields_ = [
                    ("ACLineStatus", wintypes.BYTE),
                    ("BatteryFlag", wintypes.BYTE),
                    ("BatteryLifePercent", wintypes.BYTE),
                    ("SystemStatusFlag", wintypes.BYTE),
                    ("BatteryLifeTime", wintypes.DWORD),
                    ("BatteryFullLifeTime", wintypes.DWORD),
                ]

            sps = SYSTEM_POWER_STATUS()
            if ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(sps)):
                if sps.ACLineStatus == 1:
                    return PowerState.AC_POWER
                if sps.ACLineStatus == 0:
                    return PowerState.BATTERY
        except Exception as exc:
            logger.debug("Windows power detection failed: %s", exc)
        return PowerState.UNKNOWN

    # ------------------------------------------------------------------
    # Quiet hours
    # ------------------------------------------------------------------

    def _is_quiet_hours(self) -> bool:
        """Check if current local time falls within quiet hours.

        Quiet hours are inclusive of ``quiet_hours_start`` and exclusive
        of ``quiet_hours_end``.  Handles the overnight wrap-around
        (e.g., 22:00 → 08:00).
        """
        current_hour = time.localtime().tm_hour
        start = self.config.quiet_hours_start
        end = self.config.quiet_hours_end

        if start <= end:
            return start <= current_hour < end
        # Wrap-around (e.g., 22:00 → 08:00)
        return current_hour >= start or current_hour < end

    # ------------------------------------------------------------------
    # Throttle calculation
    # ------------------------------------------------------------------

    def _calculate_throttle(self) -> int:
        """Calculate CPU throttle percentage based on all factors.

        Takes the *minimum* of:
        - Activity-based throttle
        - Power-based throttle (if on battery)
        - Quiet-hours throttle (if in quiet hours)

        Returns:
            An integer 0–100 representing the maximum allowed CPU %.
        """
        # Activity-based
        activity_map = {
            ActivityLevel.ACTIVE: self.config.active_throttle_percent,
            ActivityLevel.IDLE: self.config.idle_throttle_percent,
            ActivityLevel.AWAY: self.config.away_throttle_percent,
            ActivityLevel.SLEEP: 0,
        }
        throttle = activity_map.get(self._activity_level, 100)

        # Power-based
        if self._power_state == PowerState.BATTERY:
            throttle = min(throttle, self.config.battery_throttle_percent)

        # Quiet hours
        if self._is_quiet_hours():
            throttle = min(throttle, self.config.active_throttle_percent)

        return max(0, min(100, throttle))

    # ------------------------------------------------------------------
    # Context-manager / async-context-manager support
    # ------------------------------------------------------------------

    async def __aenter__(self) -> SmartScheduler:
        await self.start()
        return self

    async def __aexit__(self, *exc: Any) -> None:
        self.stop()
