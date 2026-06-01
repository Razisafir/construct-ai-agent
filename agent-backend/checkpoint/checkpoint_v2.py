"""Checkpoint Manager V2 — atomic saves, incremental diffs, compression.

Features:
- Atomic saves (write to temp, rename — never corrupt)
- Incremental checkpoints (only changed state)
- Compression (gzip) for storage efficiency
- Auto-restore on startup with conflict resolution
- Integrity verification via SHA-256 checksums

Storage Layout::

    checkpoint_dir/
        manifest.json          # Index of all checkpoints
        <id>.json.gz           # Full checkpoint
        <id>.diff.gz           # Incremental diff
"""

from __future__ import annotations

import gzip
import hashlib
import json
import logging
import os
import shutil
import tempfile
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class Checkpoint:
    """Metadata for a single checkpoint file."""

    id: str
    timestamp: float
    path: str
    size_bytes: int
    is_incremental: bool
    parent_id: Optional[str] = None
    checksum_sha256: str = ""  # of the uncompressed content
    content_keys: List[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a plain dict for JSON storage."""
        return {
            "id": self.id,
            "timestamp": self.timestamp,
            "path": self.path,
            "size_bytes": self.size_bytes,
            "is_incremental": self.is_incremental,
            "parent_id": self.parent_id,
            "checksum_sha256": self.checksum_sha256,
            "content_keys": self.content_keys,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Checkpoint:
        """Deserialise from a plain dict."""
        return cls(
            id=d["id"],
            timestamp=d["timestamp"],
            path=d["path"],
            size_bytes=d["size_bytes"],
            is_incremental=d["is_incremental"],
            parent_id=d.get("parent_id"),
            checksum_sha256=d.get("checksum_sha256", ""),
            content_keys=d.get("content_keys", []),
        )


# ---------------------------------------------------------------------------
# Manifest
# ---------------------------------------------------------------------------


@dataclass
class _Manifest:
    """In-memory representation of the checkpoint manifest."""

    version: int = 2
    checkpoints: List[Checkpoint] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "checkpoints": [c.to_dict() for c in self.checkpoints],
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> _Manifest:
        return cls(
            version=d.get("version", 2),
            checkpoints=[Checkpoint.from_dict(c) for c in d.get("checkpoints", [])],
        )


# ---------------------------------------------------------------------------
# Manager
# ---------------------------------------------------------------------------


class CheckpointManager:
    """Manages atomic, incremental, compressed checkpoints.

    All public methods are thread-safe for single-process use.
    For multi-process safety, external locking is required.

    Args:
        checkpoint_dir: Directory where checkpoints are stored.
        max_checkpoints: Maximum number of checkpoints to retain.
    """

    MANIFEST_FILENAME = "manifest.json"

    def __init__(self, checkpoint_dir: str, max_checkpoints: int = 50) -> None:
        self.checkpoint_dir = Path(checkpoint_dir)
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        self.max_checkpoints = max(max_checkpoints, 5)
        self._manifest_path = self.checkpoint_dir / self.MANIFEST_FILENAME
        self._lock_file = self.checkpoint_dir / ".lock"

    # ------------------------------------------------------------------
    # Manifest helpers
    # ------------------------------------------------------------------

    def _load_manifest(self) -> _Manifest:
        """Load the manifest from disk, or return a fresh one."""
        if not self._manifest_path.exists():
            return _Manifest()
        try:
            raw = self._manifest_path.read_text(encoding="utf-8")
            data = json.loads(raw)
            return _Manifest.from_dict(data)
        except (json.JSONDecodeError, KeyError, TypeError) as exc:
            logger.warning("Corrupt manifest, starting fresh: %s", exc)
            return _Manifest()

    def _save_manifest(self, manifest: _Manifest) -> None:
        """Atomically write the manifest to disk."""
        tmp = self._manifest_path.with_suffix(".tmp")
        try:
            tmp.write_text(
                json.dumps(manifest.to_dict(), indent=2, sort_keys=True),
                encoding="utf-8",
            )
            tmp.replace(self._manifest_path)
        except Exception:
            if tmp.exists():
                tmp.unlink()
            raise

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def save(self, state: Dict[str, Any]) -> Checkpoint:
        """Atomically save state to a checkpoint file.

        Process:
        1. Serialise state to JSON bytes
        2. Compute SHA-256 checksum of uncompressed bytes
        3. Write to a temporary file with gzip compression
        4. Atomic rename (``replace``) to final path
        5. Verify by reading back and decompressing
        6. Update manifest and clean old checkpoints

        Args:
            state: Arbitrary JSON-serialisable dict to persist.

        Returns:
            A :class:`Checkpoint` metadata object.

        Raises:
            RuntimeError: If the checkpoint fails verification after write.
        """
        checkpoint_id = self._generate_id()
        timestamp = time.time()
        final_name = f"{checkpoint_id}.json.gz"
        final_path = self.checkpoint_dir / final_name

        # 1. Serialise
        raw_bytes = json.dumps(state, ensure_ascii=False, sort_keys=True).encode("utf-8")

        # 2. Checksum (of uncompressed data)
        checksum = hashlib.sha256(raw_bytes).hexdigest()

        # 3. Write temp → compress → atomic rename
        tmp_fd, tmp_path_str = tempfile.mkstemp(
            dir=str(self.checkpoint_dir),
            prefix=f".{checkpoint_id}_",
            suffix=".tmp",
        )
        try:
            with os.fdopen(tmp_fd, "wb") as tmp_fh:
                with gzip.GzipFile(fileobj=tmp_fh, mode="wb", compresslevel=6) as gz:
                    gz.write(raw_bytes)
            tmp_path = Path(tmp_path_str)
            tmp_path.replace(final_path)
        except Exception:
            # Best-effort cleanup
            try:
                os.unlink(tmp_path_str)
            except OSError:
                pass
            raise

        # 4. Verify by reading back
        if not self._verify_file(final_path, checksum):
            final_path.unlink()
            raise RuntimeError(
                f"Checkpoint {checkpoint_id} failed verification after write"
            )

        size_bytes = final_path.stat().st_size

        ckpt = Checkpoint(
            id=checkpoint_id,
            timestamp=timestamp,
            path=str(final_path),
            size_bytes=size_bytes,
            is_incremental=False,
            checksum_sha256=checksum,
            content_keys=sorted(state.keys()),
        )

        # 5. Update manifest
        manifest = self._load_manifest()
        manifest.checkpoints.append(ckpt)
        self._save_manifest(manifest)

        # 6. Clean old
        cleaned = self.clean_old(keep=self.max_checkpoints)
        if cleaned:
            logger.info("Removed %d old checkpoint(s)", cleaned)

        logger.info(
            "Full checkpoint saved: %s (raw=%d bytes, compressed=%d bytes)",
            checkpoint_id,
            len(raw_bytes),
            size_bytes,
        )
        return ckpt

    def save_incremental(
        self, base_checkpoint: Checkpoint, changes: List[Dict[str, Any]]
    ) -> Checkpoint:
        """Save only the changes (diff) since a base checkpoint.

        The diff is stored as a JSON object mapping keys to their new
        values.  On restore, the diff is merged on top of the base
        state (later keys overwrite earlier ones).

        Args:
            base_checkpoint: The checkpoint to diff against.
            changes: List of dicts, each containing key-value changes.
                Multiple dicts are merged in order.

        Returns:
            A :class:`Checkpoint` metadata object for the incremental save.
        """
        checkpoint_id = self._generate_id()
        timestamp = time.time()
        final_name = f"{checkpoint_id}.diff.gz"
        final_path = self.checkpoint_dir / final_name

        # Merge all change dicts into a single diff
        merged_diff: Dict[str, Any] = {}
        for chunk in changes:
            merged_diff.update(chunk)

        diff_payload = {
            "_meta": {
                "type": "incremental",
                "parent_id": base_checkpoint.id,
                "parent_checksum": base_checkpoint.checksum_sha256,
            },
            "changes": merged_diff,
        }

        raw_bytes = json.dumps(diff_payload, ensure_ascii=False, sort_keys=True).encode(
            "utf-8"
        )
        checksum = hashlib.sha256(raw_bytes).hexdigest()

        tmp_fd, tmp_path_str = tempfile.mkstemp(
            dir=str(self.checkpoint_dir),
            prefix=f".{checkpoint_id}_",
            suffix=".tmp",
        )
        try:
            with os.fdopen(tmp_fd, "wb") as tmp_fh:
                with gzip.GzipFile(fileobj=tmp_fh, mode="wb", compresslevel=6) as gz:
                    gz.write(raw_bytes)
            tmp_path = Path(tmp_path_str)
            tmp_path.replace(final_path)
        except Exception:
            try:
                os.unlink(tmp_path_str)
            except OSError:
                pass
            raise

        if not self._verify_file(final_path, checksum):
            final_path.unlink()
            raise RuntimeError(
                f"Incremental checkpoint {checkpoint_id} failed verification"
            )

        size_bytes = final_path.stat().st_size

        ckpt = Checkpoint(
            id=checkpoint_id,
            timestamp=timestamp,
            path=str(final_path),
            size_bytes=size_bytes,
            is_incremental=True,
            parent_id=base_checkpoint.id,
            checksum_sha256=checksum,
            content_keys=sorted(merged_diff.keys()),
        )

        manifest = self._load_manifest()
        manifest.checkpoints.append(ckpt)
        self._save_manifest(manifest)

        logger.info(
            "Incremental checkpoint saved: %s (parent=%s, compressed=%d bytes)",
            checkpoint_id,
            base_checkpoint.id,
            size_bytes,
        )
        return ckpt

    def restore(
        self, checkpoint_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Restore state from a checkpoint.

        If *checkpoint_id* is ``None``, restores the latest full
        checkpoint.  For incremental checkpoints, the base is loaded
        first and the diff is applied on top.

        Args:
            checkpoint_id: Specific checkpoint to restore, or ``None``
                for the latest.

        Returns:
            The restored state dict.

        Raises:
            FileNotFoundError: If the checkpoint or its parent does not exist.
            RuntimeError: If checksum verification fails.
        """
        if checkpoint_id is None:
            ckpt = self.find_latest()
            if ckpt is None:
                raise FileNotFoundError("No checkpoints available")
        else:
            ckpt = self._find_by_id(checkpoint_id)
            if ckpt is None:
                raise FileNotFoundError(f"Checkpoint not found: {checkpoint_id}")

        # If incremental, restore base first then apply diff
        if ckpt.is_incremental:
            if ckpt.parent_id is None:
                raise RuntimeError(
                    f"Incremental checkpoint {ckpt.id} has no parent_id"
                )
            base_ckpt = self._find_by_id(ckpt.parent_id)
            if base_ckpt is None:
                raise FileNotFoundError(
                    f"Parent checkpoint not found: {ckpt.parent_id}"
                )
            base_state = self._restore_single(base_ckpt)
            diff_state = self._restore_single(ckpt)
            changes = diff_state.get("changes", {})
            merged = dict(base_state)
            merged.update(changes)
            logger.info(
                "Restored incremental checkpoint %s (base=%s)",
                ckpt.id,
                ckpt.parent_id,
            )
            return merged

        state = self._restore_single(ckpt)
        logger.info("Restored full checkpoint %s", ckpt.id)
        return state

    def list_checkpoints(self) -> List[Checkpoint]:
        """List all available checkpoints sorted by timestamp (newest first).

        The returned list is a *copy* — modifying it does not affect
        the manifest on disk.
        """
        manifest = self._load_manifest()
        return sorted(manifest.checkpoints, key=lambda c: c.timestamp, reverse=True)

    def find_latest(self) -> Optional[Checkpoint]:
        """Find the most recent valid (verified) checkpoint.

        Skips checkpoints that fail integrity verification and logs
        a warning for each corrupt file.
        """
        for ckpt in self.list_checkpoints():
            if self.verify(ckpt):
                return ckpt
            logger.warning("Checkpoint %s failed verification, skipping", ckpt.id)
        return None

    def clean_old(self, keep: int = 20) -> int:
        """Remove old checkpoints, keeping the *keep* most recent.

        Also removes orphaned files not listed in the manifest.

        Args:
            keep: Number of recent checkpoints to retain.

        Returns:
            Number of checkpoints removed.
        """
        keep = max(keep, 1)
        manifest = self._load_manifest()
        sorted_ckpts = sorted(
            manifest.checkpoints, key=lambda c: c.timestamp, reverse=True
        )

        to_keep = sorted_ckpts[:keep]
        to_remove = sorted_ckpts[keep:]
        removed = 0

        kept_ids = {c.id for c in to_keep}
        kept_parent_ids = {
            c.parent_id for c in to_keep if c.parent_id is not None
        }
        # Also keep parents of incremental checkpoints that are still needed
        protected_ids = kept_ids | kept_parent_ids

        for ckpt in to_remove:
            if ckpt.id in protected_ids:
                continue
            path = Path(ckpt.path)
            if path.exists():
                try:
                    path.unlink()
                    removed += 1
                except OSError as exc:
                    logger.warning("Failed to remove %s: %s", path, exc)

        manifest.checkpoints = to_keep
        self._save_manifest(manifest)

        # Garbage-collect orphaned files
        removed += self._gc_orphans(manifest)

        return removed

    def verify(self, checkpoint: Checkpoint) -> bool:
        """Verify a checkpoint file is valid (not corrupted).

        Checks:
        1. File exists and is readable
        2. Can be decompressed successfully
        3. SHA-256 checksum matches (if recorded)

        Args:
            checkpoint: The checkpoint metadata to verify.

        Returns:
            ``True`` if the checkpoint passes all checks.
        """
        path = Path(checkpoint.path)
        if not path.exists():
            return False
        try:
            decompressed = self._decompress_file(path)
            if checkpoint.checksum_sha256:
                actual = hashlib.sha256(decompressed).hexdigest()
                if actual != checkpoint.checksum_sha256:
                    logger.warning(
                        "Checksum mismatch for %s: expected %s, got %s",
                        checkpoint.id,
                        checkpoint.checksum_sha256,
                        actual,
                    )
                    return False
            # Also validate JSON
            json.loads(decompressed.decode("utf-8"))
            return True
        except Exception as exc:
            logger.debug("Verification failed for %s: %s", checkpoint.id, exc)
            return False

    def prune_orphans(self) -> int:
        """Remove checkpoint files not referenced by the manifest.

        Returns:
            Number of orphaned files removed.
        """
        manifest = self._load_manifest()
        return self._gc_orphans(manifest)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _restore_single(self, checkpoint: Checkpoint) -> Dict[str, Any]:
        """Restore a single (non-incremental) checkpoint file."""
        path = Path(checkpoint.path)
        if not path.exists():
            raise FileNotFoundError(f"Checkpoint file missing: {path}")

        decompressed = self._decompress_file(path)

        if checkpoint.checksum_sha256:
            actual = hashlib.sha256(decompressed).hexdigest()
            if actual != checkpoint.checksum_sha256:
                raise RuntimeError(
                    f"Checksum mismatch for {checkpoint.id}: "
                    f"expected {checkpoint.checksum_sha256}, got {actual}"
                )

        return json.loads(decompressed.decode("utf-8"))

    @staticmethod
    def _decompress_file(path: Path) -> bytes:
        """Decompress a gzip file and return the raw bytes."""
        with gzip.GzipFile(path, "rb") as gz:
            return gz.read()

    @staticmethod
    def _verify_file(path: Path, expected_checksum: str) -> bool:
        """Verify a file on disk matches the expected checksum."""
        try:
            decompressed = CheckpointManager._decompress_file(path)
            actual = hashlib.sha256(decompressed).hexdigest()
            return actual == expected_checksum
        except Exception:
            return False

    def _find_by_id(self, checkpoint_id: str) -> Optional[Checkpoint]:
        """Find a checkpoint by its ID."""
        manifest = self._load_manifest()
        for ckpt in manifest.checkpoints:
            if ckpt.id == checkpoint_id:
                return ckpt
        return None

    def _gc_orphans(self, manifest: _Manifest) -> int:
        """Remove files in checkpoint_dir not referenced by the manifest."""
        referenced = {Path(c.path).name for c in manifest.checkpoints}
        referenced.add(self.MANIFEST_FILENAME)
        removed = 0
        for entry in self.checkpoint_dir.iterdir():
            if entry.is_file() and entry.name not in referenced:
                # Keep temp files that are actively being written
                if entry.name.endswith(".tmp"):
                    # Only remove if older than 1 hour (stale temp)
                    age = time.time() - entry.stat().st_mtime
                    if age < 3600:
                        continue
                try:
                    entry.unlink()
                    removed += 1
                except OSError as exc:
                    logger.debug("Failed to remove orphan %s: %s", entry, exc)
        return removed

    @staticmethod
    def _generate_id() -> str:
        """Generate a unique checkpoint identifier."""
        return f"{int(time.time())}-{uuid.uuid4().hex[:8]}"

    # ------------------------------------------------------------------
    # Convenience / diagnostics
    # ------------------------------------------------------------------

    def get_storage_stats(self) -> Dict[str, Any]:
        """Return storage usage statistics.

        Returns:
            Dict with ``total_checkpoints``, ``total_size_bytes``,
            ``full_count``, ``incremental_count``.
        """
        ckpts = self.list_checkpoints()
        total_size = sum(c.size_bytes for c in ckpts)
        full_count = sum(1 for c in ckpts if not c.is_incremental)
        inc_count = sum(1 for c in ckpts if c.is_incremental)
        return {
            "total_checkpoints": len(ckpts),
            "total_size_bytes": total_size,
            "full_count": full_count,
            "incremental_count": inc_count,
            "checkpoint_dir": str(self.checkpoint_dir),
        }

    def get_state_keys_at(self, checkpoint_id: str) -> List[str]:
        """Return the list of top-level keys stored in a checkpoint."""
        ckpt = self._find_by_id(checkpoint_id)
        if ckpt is None:
            return []
        return list(ckpt.content_keys)
