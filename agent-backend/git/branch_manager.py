"""Branch Manager — automated branch creation, merging, cleanup.

Features:
- Auto-create feature branches from main/master with sanitised names
- Clean merges (rebase preferred, squash and merge supported)
- Old branch cleanup with dry-run support
- Branch status reporting (ahead/behind, merge status, last commit)
"""

from __future__ import annotations

import logging
import re
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Optional

logger = logging.getLogger(__name__)


@dataclass
class BranchStatus:
    """Status snapshot for a single Git branch."""

    name: str
    ahead: int
    behind: int
    last_commit: str
    last_commit_date: str
    is_merged: bool
    author: str


class BranchManager:
    """Manages Git branches via subprocess calls to the git CLI."""

    _BRANCH_PREFIXES = {
        "feat": "feat", "fix": "fix", "docs": "docs",
        "test": "test", "refactor": "refactor", "chore": "chore", "perf": "perf",
    }
    _BASE_BRANCH_CANDIDATES = ["main", "master", "develop", "dev"]

    def __init__(self, repo_path: str = ".") -> None:
        self.repo_path = repo_path
        logger.debug("BranchManager for %s", repo_path)

    # ------------------------------------------------------------------
    # Branch creation
    # ------------------------------------------------------------------

    def create_feature_branch(self, feature_name: str) -> str:
        """Create a feature branch from the default base branch.

        Sanitises: ``"Add auth"`` → ``"feat/add-auth"``.
        Returns the branch name. Raises on git error.
        """
        branch = self._sanitize_branch_name(feature_name)
        base = self._detect_base_branch()
        logger.info("Creating '%s' from '%s'", branch, base)
        self._run_git(["checkout", base])
        self._run_git(["pull", "--ff-only"])
        self._run_git(["checkout", "-b", branch])
        return branch

    def create_branch_from(self, feature_name: str, base_branch: str) -> str:
        """Create a branch from an explicit base branch."""
        branch = self._sanitize_branch_name(feature_name)
        self._run_git(["checkout", base_branch])
        self._run_git(["pull", "--ff-only"])
        self._run_git(["checkout", "-b", branch])
        return branch

    # ------------------------------------------------------------------
    # Merging
    # ------------------------------------------------------------------

    def merge_to_main(self, branch: str, strategy: str = "rebase") -> bool:
        """Merge a branch into the default base branch.

        Strategies: ``"rebase"`` (default), ``"merge"``, ``"squash"``.
        Returns ``True`` on success, ``False`` if conflicts occurred.
        """
        base = self._detect_base_branch()
        if strategy not in ("rebase", "merge", "squash"):
            raise ValueError(f"Unknown strategy: {strategy}")

        logger.info("Merging '%s' into '%s' via '%s'", branch, base, strategy)
        self._run_git(["checkout", base])
        self._run_git(["pull", "--ff-only"])

        try:
            if strategy == "rebase":
                return self._merge_rebase(branch, base)
            if strategy == "merge":
                return self._merge_commit(branch, base)
            return self._merge_squash(branch, base)
        except subprocess.CalledProcessError:
            if self._has_conflicts():
                logger.error("Merge conflicts on '%s'; aborting", branch)
                self._abort_merge(strategy)
                return False
            raise

    def _merge_rebase(self, branch: str, base: str) -> bool:
        """Rebase branch onto base, then fast-forward."""
        self._run_git(["checkout", branch])
        try:
            self._run_git(["rebase", base])
        except subprocess.CalledProcessError:
            if self._has_conflicts():
                self._run_git(["rebase", "--abort"])
                return False
            raise
        self._run_git(["checkout", base])
        self._run_git(["merge", "--ff-only", branch])
        return True

    def _merge_commit(self, branch: str, base: str) -> bool:
        """Create a merge commit."""
        try:
            self._run_git(["merge", "--no-ff", "-m", f"Merge branch '{branch}'", branch])
        except subprocess.CalledProcessError:
            if self._has_conflicts():
                self._run_git(["merge", "--abort"])
                return False
            raise
        return True

    def _merge_squash(self, branch: str, base: str) -> bool:
        """Squash-merge branch into base."""
        try:
            self._run_git(["merge", "--squash", branch])
        except subprocess.CalledProcessError:
            if self._has_conflicts():
                self._run_git(["merge", "--abort"])
                return False
            raise
        self._run_git(["commit", "-m", f"feat: squash merge '{branch}'"])
        return True

    def _has_conflicts(self) -> bool:
        """Check for merge conflicts in working tree."""
        try:
            return bool(self._run_git(["diff", "--name-only", "--diff-filter=U"]).strip())
        except subprocess.CalledProcessError:
            return False

    def _abort_merge(self, strategy: str) -> None:
        """Abort in-progress merge/rebase."""
        try:
            flag = "--abort"
            self._run_git(["rebase" if strategy == "rebase" else "merge", flag])
        except subprocess.CalledProcessError:
            pass

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def clean_old_branches(self, age_days: int = 30, dry_run: bool = True) -> List[str]:
        """Delete merged branches older than age_days. Dry-run by default.
        Returns list of deleted (or would-delete) branch names.
        """
        merged = self._list_merged_branches()
        cutoff = datetime.now(timezone.utc).timestamp() - (age_days * 86400)
        to_delete: List[str] = []

        for branch in merged:
            if branch in self._BASE_BRANCH_CANDIDATES:
                continue
            ts = self._get_branch_last_commit_timestamp(branch)
            if ts and ts < cutoff:
                to_delete.append(branch)

        if dry_run:
            logger.info("DRY-RUN: would delete %d: %s", len(to_delete), to_delete)
            return to_delete

        deleted: List[str] = []
        for branch in to_delete:
            try:
                self._run_git(["branch", "-d", branch])
                deleted.append(branch)
                logger.info("Deleted '%s'", branch)
            except subprocess.CalledProcessError as exc:
                logger.warning("Failed to delete '%s': %s", branch, exc)
        return deleted

    def delete_branch(self, branch: str, force: bool = False) -> bool:
        """Delete a branch. Use force=True for unmerged branches."""
        flag = "-D" if force else "-d"
        try:
            self._run_git(["branch", flag, branch])
            return True
        except subprocess.CalledProcessError as exc:
            logger.error("Delete '%s' failed: %s", branch, exc)
            return False

    # ------------------------------------------------------------------
    # Status / reporting
    # ------------------------------------------------------------------

    def get_branch_status(self) -> List[BranchStatus]:
        """Get status of all local branches."""
        base = self._detect_base_branch()
        branches = self._list_local_branches()
        merged = set(self._list_merged_branches())

        result: List[BranchStatus] = []
        for branch in branches:
            ahead, behind = self._get_ahead_behind(branch, base)
            result.append(BranchStatus(
                name=branch, ahead=ahead, behind=behind,
                last_commit=self._get_last_commit_message(branch),
                last_commit_date=self._get_last_commit_date(branch),
                is_merged=branch in merged,
                author=self._get_last_commit_author(branch),
            ))
        return sorted(result, key=lambda b: b.name)

    def get_current_branch(self) -> str:
        """Return currently checked-out branch name."""
        return self._run_git(["rev-parse", "--abbrev-ref", "HEAD"])

    def branch_exists(self, branch: str) -> bool:
        """Check whether a local branch exists."""
        try:
            self._run_git(["show-ref", "--verify", f"refs/heads/{branch}"])
            return True
        except subprocess.CalledProcessError:
            return False

    # ------------------------------------------------------------------
    # Git helpers
    # ------------------------------------------------------------------

    def _run_git(self, args: List[str]) -> str:
        """Run git command, return stripped stdout. Raises on non-zero exit."""
        cmd = ["git", "-C", self.repo_path] + args
        logger.debug("git %s", " ".join(args))
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return result.stdout.strip()

    def _run_git_optional(self, args: List[str]) -> Optional[str]:
        """Run git command, return None on failure."""
        try:
            return self._run_git(args)
        except subprocess.CalledProcessError:
            return None

    # ------------------------------------------------------------------
    # Name sanitisation & detection
    # ------------------------------------------------------------------

    def _sanitize_branch_name(self, name: str) -> str:
        """Convert description to valid branch name.

        ``"Add auth system"`` → ``"feat/add-auth-system"``
        """
        prefix = "feat"
        lower = name.lower().strip()
        for key, pfx in self._BRANCH_PREFIXES.items():
            if lower.startswith(key) or lower.startswith(f"{key}:"):
                prefix = pfx
                name = re.sub(rf"^{key}\s*[:-]?\s*", "", name, flags=re.IGNORECASE)
                break

        sanitized = re.sub(r"[^a-z0-9\s-]+", "", name.lower().strip())
        sanitized = re.sub(r"[\s_]+", "-", sanitized)
        sanitized = re.sub(r"-{2,}", "-", sanitized).strip("-")
        if not sanitized:
            sanitized = "unnamed-branch"
        return f"{prefix}/{sanitized}"

    def _detect_base_branch(self) -> str:
        """Return default base branch (main/master/develop/dev)."""
        for candidate in self._BASE_BRANCH_CANDIDATES:
            if self.branch_exists(candidate):
                return candidate
        try:
            return self._run_git(["rev-parse", "--abbrev-ref", "origin/HEAD"]).replace("origin/", "")
        except subprocess.CalledProcessError:
            return "main"

    def _list_local_branches(self) -> List[str]:
        """Return all local branch names."""
        out = self._run_git(["branch", "--format=%(refname:short)"])
        return [b.strip() for b in out.splitlines() if b.strip()] if out else []

    def _list_merged_branches(self) -> List[str]:
        """Return branches merged into base (excluding base itself)."""
        base = self._detect_base_branch()
        out = self._run_git_optional(["branch", "--merged", base, "--format=%(refname:short)"])
        if not out:
            return []
        return [b.strip() for b in out.splitlines() if b.strip() and b.strip() != base]

    def _get_ahead_behind(self, branch: str, base: str) -> tuple[int, int]:
        """Return (ahead, behind) for branch vs base."""
        try:
            rev = self._run_git(["rev-list", "--left-right", "--count", f"{base}...{branch}"])
            parts = rev.split("\t")
            return (int(parts[1]), int(parts[0])) if len(parts) == 2 else (0, 0)
        except (subprocess.CalledProcessError, ValueError):
            return 0, 0

    def _get_last_commit_message(self, branch: str) -> str:
        return self._run_git_optional(["log", "-1", "--format=%s", branch]) or ""

    def _get_last_commit_date(self, branch: str) -> str:
        return self._run_git_optional(["log", "-1", "--format=%ci", branch]) or ""

    def _get_branch_last_commit_timestamp(self, branch: str) -> Optional[float]:
        date_str = self._get_last_commit_date(branch)
        if not date_str:
            return None
        try:
            dt = datetime.strptime(date_str[:19], "%Y-%m-%d %H:%M:%S")
            return dt.replace(tzinfo=timezone.utc).timestamp()
        except ValueError:
            return None

    def _get_last_commit_author(self, branch: str) -> str:
        return self._run_git_optional(["log", "-1", "--format=%an", branch]) or ""
