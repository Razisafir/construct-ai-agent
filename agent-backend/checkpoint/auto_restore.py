"""Auto Restore — detect last checkpoint on startup, offer restore with conflict resolution.

Features:
- Detect if checkpoint exists from previous session
- Compare checkpoint age vs current session
- Handle conflicts (newer files exist that differ from checkpoint)
- Offer restore or continue fresh
- Age-based recommendation engine

Typical workflow::

    ar = AutoRestore(checkpoint_manager)
    suggestion = ar.check_for_checkpoint()
    if suggestion is None:
        print("No checkpoint found, starting fresh.")
    elif suggestion.recommendation == "auto_restore":
        state = ar.restore(suggestion.checkpoint_id)
    elif suggestion.recommendation == "ask_user":
        print(f"Conflicts detected: {suggestion.conflicts}")
        # ... prompt user ...
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class FileConflict:
    """Represents a single file that differs between checkpoint and disk."""

    relative_path: str
    checkpoint_hash: str  # SHA-256 of file content at checkpoint time
    current_hash: str  # SHA-256 of file content on disk now
    modification_time: float  # Current file mtime


@dataclass
class RestoreSuggestion:
    """Recommendation produced by :meth:`AutoRestore.check_for_checkpoint`."""

    checkpoint_id: str
    checkpoint_timestamp: float
    hours_ago: float
    state_summary: str  # Human-readable summary of the checkpoint
    conflicts: List[FileConflict]  # Files modified since checkpoint
    recommendation: str  # "auto_restore", "recommend_restore", "ask_user", "continue"
    checkpoint_is_full: bool = True  # False if incremental-only available


# ---------------------------------------------------------------------------
# AutoRestore
# ---------------------------------------------------------------------------


class AutoRestore:
    """Handles automatic checkpoint detection and restore on startup.

    Args:
        checkpoint_manager: A :class:`~checkpoint_v2.CheckpointManager`
            instance to query for available checkpoints.
        workspace_dir: Optional path to the workspace directory for
            conflict detection.  If ``None``, conflict detection is
            skipped.
        session_file: Path to a sentinel file used to track the most
            recent session.  Defaults to ``.last_session`` inside the
            checkpoint directory.
    """

    def __init__(
        self,
        checkpoint_manager: Any,
        workspace_dir: Optional[str] = None,
        session_file: Optional[str] = None,
    ) -> None:
        self.cm = checkpoint_manager
        self.workspace_dir = Path(workspace_dir) if workspace_dir else None
        self.session_start = time.time()

        if session_file is None:
            self.session_file = Path(self.cm.checkpoint_dir) / ".last_session"
        else:
            self.session_file = Path(session_file)

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    def check_for_checkpoint(self) -> Optional[RestoreSuggestion]:
        """Check if a restore-worthy checkpoint exists.

        This method:
        1. Reads the last-session sentinel file.
        2. Finds the most recent valid checkpoint.
        3. Detects file conflicts (if *workspace_dir* was provided).
        4. Generates a :class:`RestoreSuggestion` with a recommendation.

        Returns:
            A :class:`RestoreSuggestion` if a checkpoint exists and
            warrants attention, or ``None`` if no checkpoint is found
            or the checkpoint is older than the current session.
        """
        # Load last session info
        last_session = self._load_last_session()

        # Find latest checkpoint
        latest = self.cm.find_latest()
        if latest is None:
            logger.info("No checkpoints found — fresh start")
            return None

        hours_ago = (self.session_start - latest.timestamp) / 3600.0

        # If we have a last-session record, check if checkpoint predates it
        if last_session is not None:
            session_age_hours = (self.session_start - last_session) / 3600.0
            if hours_ago > session_age_hours + 0.5:  # 30 min tolerance
                logger.info(
                    "Checkpoint %.1fh old but current session is %.1fh old — "
                    "checkpoint predates this session, ignoring",
                    hours_ago,
                    session_age_hours,
                )
                return None

        # Detect conflicts
        conflicts: List[FileConflict] = []
        if self.workspace_dir is not None and self.workspace_dir.exists():
            try:
                conflicts = self.detect_conflicts(latest)
            except Exception as exc:
                logger.warning("Conflict detection failed: %s", exc)

        has_conflicts = len(conflicts) > 0
        recommendation = self.get_recommendation(hours_ago, has_conflicts)

        # Build state summary
        state_summary = self._build_state_summary(latest)

        suggestion = RestoreSuggestion(
            checkpoint_id=latest.id,
            checkpoint_timestamp=latest.timestamp,
            hours_ago=hours_ago,
            state_summary=state_summary,
            conflicts=conflicts,
            recommendation=recommendation,
            checkpoint_is_full=not latest.is_incremental,
        )

        logger.info(
            "Checkpoint %s (%.1fh ago) → recommendation=%s, conflicts=%d",
            latest.id,
            hours_ago,
            recommendation,
            len(conflicts),
        )
        return suggestion

    # ------------------------------------------------------------------
    # Conflict detection
    # ------------------------------------------------------------------

    def detect_conflicts(self, checkpoint: Any) -> List[FileConflict]:
        """Detect files modified since *checkpoint* was saved.

        Compares the file hashes stored in the checkpoint (if any)
        against the current files on disk.  Files not present in the
        checkpoint are ignored unless they appear in a ``_files``
        sub-dict.

        Args:
            checkpoint: The checkpoint metadata to compare against.

        Returns:
            List of :class:`FileConflict` objects for each changed file.
        """
        conflicts: List[FileConflict] = []
        if self.workspace_dir is None:
            return conflicts

        # Try to extract file hashes from checkpoint state
        try:
            state = self.cm.restore(checkpoint.id)
        except Exception as exc:
            logger.warning("Could not restore checkpoint for conflict scan: %s", exc)
            return conflicts

        # Look for file manifest embedded in state
        file_manifest = state.get("_file_manifest", {})
        if not file_manifest and "files" in state:
            # Alternative key name
            file_manifest = state.get("files", {})

        # If no embedded manifest, do a heuristic scan of workspace
        if not file_manifest:
            return self._heuristic_conflict_scan(checkpoint)

        for rel_path, saved_hash in file_manifest.items():
            full_path = self.workspace_dir / rel_path
            if not full_path.exists():
                # File deleted since checkpoint
                conflicts.append(
                    FileConflict(
                        relative_path=rel_path,
                        checkpoint_hash=saved_hash,
                        current_hash="",
                        modification_time=0.0,
                    )
                )
                continue

            current_hash = self._hash_file(full_path)
            if current_hash != saved_hash:
                conflicts.append(
                    FileConflict(
                        relative_path=rel_path,
                        checkpoint_hash=saved_hash,
                        current_hash=current_hash,
                        modification_time=full_path.stat().st_mtime,
                    )
                )

        return conflicts

    def _heuristic_conflict_scan(self, checkpoint: Any) -> List[FileConflict]:
        """Heuristic conflict scan when no file manifest is embedded.

        Flags any files in the workspace that were modified *after*
        the checkpoint timestamp.

        Args:
            checkpoint: The checkpoint metadata.

        Returns:
            List of potentially conflicting files.
        """
        conflicts: List[FileConflict] = []
        if self.workspace_dir is None:
            return conflicts

        checkpoint_time = checkpoint.timestamp
        ignore_patterns = {
            ".git",
            "__pycache__",
            ".pytest_cache",
            "*.pyc",
            "*.pyo",
            ".DS_Store",
            "node_modules",
            ".venv",
            "venv",
        }

        for root, _dirs, files in os.walk(self.workspace_dir):
            # Skip ignored directories
            rel_root = Path(root).relative_to(self.workspace_dir)
            if any(part in ignore_patterns for part in rel_root.parts):
                continue

            for filename in files:
                if any(filename.endswith(pat.lstrip("*")) for pat in ignore_patterns):
                    continue

                full_path = Path(root) / filename
                try:
                    mtime = full_path.stat().st_mtime
                except OSError:
                    continue

                if mtime > checkpoint_time:
                    rel_path = str(full_path.relative_to(self.workspace_dir))
                    file_hash = self._hash_file(full_path)
                    conflicts.append(
                        FileConflict(
                            relative_path=rel_path,
                            checkpoint_hash="",
                            current_hash=file_hash,
                            modification_time=mtime,
                        )
                    )

        # Sort by modification time (newest first), cap at 50
        conflicts.sort(key=lambda c: c.modification_time, reverse=True)
        return conflicts[:50]

    # ------------------------------------------------------------------
    # Restore / discard
    # ------------------------------------------------------------------

    def restore(self, checkpoint_id: str) -> Dict[str, Any]:
        """Restore from a checkpoint and record the session.

        After restoring, writes the current session timestamp to the
        sentinel file so future restarts know this checkpoint has
        been consumed.

        Args:
            checkpoint_id: ID of the checkpoint to restore.

        Returns:
            The restored state dict.
        """
        state = self.cm.restore(checkpoint_id)
        self._save_last_session()
        logger.info("Restored checkpoint %s and recorded session", checkpoint_id)
        return state

    def discard(self, checkpoint_id: str) -> None:
        """Discard a checkpoint and continue fresh.

        Records the session so the same checkpoint is not offered
        again on the next restart.

        Args:
            checkpoint_id: ID of the checkpoint to discard.  The
                checkpoint file itself is NOT deleted — only the
                session marker is updated.
        """
        self._save_last_session()
        logger.info("Discarded checkpoint %s, continuing fresh", checkpoint_id)

    def restore_and_merge(
        self, checkpoint_id: str, current_state: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Restore from checkpoint and merge with current state.

        Top-level keys from *current_state* take precedence over
        checkpoint keys, except for nested dicts which are merged.

        Args:
            checkpoint_id: ID of the checkpoint to restore.
            current_state: The current in-memory state.

        Returns:
            Merged state dict.
        """
        checkpoint_state = self.cm.restore(checkpoint_id)
        merged = self._deep_merge(checkpoint_state, current_state)
        self._save_last_session()
        logger.info("Restored and merged checkpoint %s", checkpoint_id)
        return merged

    # ------------------------------------------------------------------
    # Recommendation engine
    # ------------------------------------------------------------------

    def get_recommendation(self, hours_ago: float, has_conflicts: bool) -> str:
        """Get automated recommendation based on age and conflicts.

        Rules:
        - < 1 hour + no conflicts  → ``"auto_restore"``
        - 1–24 hours + no conflicts → ``"recommend_restore"``
        - any age + conflicts      → ``"ask_user"``
        - > 24 hours + no conflicts → ``"continue"``

        Args:
            hours_ago: How many hours ago the checkpoint was saved.
            has_conflicts: Whether file conflicts were detected.

        Returns:
            One of ``"auto_restore"``, ``"recommend_restore"``,
            ``"ask_user"``, ``"continue"``.
        """
        if has_conflicts:
            return "ask_user"
        if hours_ago < 1.0:
            return "auto_restore"
        if hours_ago <= 24.0:
            return "recommend_restore"
        return "continue"

    # ------------------------------------------------------------------
    # Session persistence
    # ------------------------------------------------------------------

    def _load_last_session(self) -> Optional[float]:
        """Load the timestamp of the last recorded session.

        Returns:
            Unix timestamp of the last session, or ``None`` if no
            session file exists.
        """
        if not self.session_file.exists():
            return None
        try:
            data = json.loads(self.session_file.read_text(encoding="utf-8"))
            return float(data.get("timestamp", 0))
        except (json.JSONDecodeError, ValueError, OSError) as exc:
            logger.debug("Failed to load last session: %s", exc)
            return None

    def _save_last_session(self) -> None:
        """Write the current session timestamp to disk."""
        try:
            self.session_file.write_text(
                json.dumps(
                    {"timestamp": self.session_start},
                    indent=2,
                ),
                encoding="utf-8",
            )
        except OSError as exc:
            logger.warning("Failed to save session marker: %s", exc)

    # ------------------------------------------------------------------
    # State summary
    # ------------------------------------------------------------------

    def _build_state_summary(self, checkpoint: Any) -> str:
        """Build a human-readable summary of a checkpoint's contents.

        Args:
            checkpoint: Checkpoint metadata.

        Returns:
            A short descriptive string (e.g., "Checkpoint from 2.3h ago
            with keys: agent_state, files, tasks (3 keys, 1.2 MB raw)").
        """
        try:
            # Try to get key list from checkpoint metadata
            keys = list(getattr(checkpoint, "content_keys", []))
            size_mb = getattr(checkpoint, "size_bytes", 0) / (1024 * 1024)

            time_str = self._format_duration((self.session_start - checkpoint.timestamp))

            if keys:
                key_list = ", ".join(keys[:5])
                if len(keys) > 5:
                    key_list += f" (+{len(keys) - 5} more)"
                return (
                    f"Checkpoint from {time_str} with keys: {key_list} "
                    f"({len(keys)} keys, {size_mb:.2f} MB compressed)"
                )
            return f"Checkpoint from {time_str} ({size_mb:.2f} MB compressed)"
        except Exception as exc:
            logger.debug("Failed to build state summary: %s", exc)
            return f"Checkpoint {checkpoint.id} (summary unavailable)"

    @staticmethod
    def _format_duration(seconds: float) -> str:
        """Format a duration in seconds to a human-readable string."""
        if seconds < 60:
            return f"{int(seconds)}s ago"
        if seconds < 3600:
            return f"{int(seconds / 60)}m ago"
        if seconds < 86400:
            return f"{seconds / 3600:.1f}h ago"
        return f"{seconds / 86400:.1f}d ago"

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    @staticmethod
    def _hash_file(path: Path) -> str:
        """Compute the SHA-256 hash of a file's contents."""
        h = hashlib.sha256()
        try:
            with open(path, "rb") as fh:
                while True:
                    chunk = fh.read(65536)
                    if not chunk:
                        break
                    h.update(chunk)
        except OSError:
            return ""
        return h.hexdigest()

    @staticmethod
    def _deep_merge(
        base: Dict[str, Any], override: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Recursively merge *override* into *base*.

        Dict values are merged recursively; all other values from
        *override* take precedence.
        """
        result = dict(base)
        for key, val in override.items():
            if (
                key in result
                and isinstance(result[key], dict)
                and isinstance(val, dict)
            ):
                result[key] = AutoRestore._deep_merge(result[key], val)
            else:
                result[key] = val
        return result
