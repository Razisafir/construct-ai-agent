"""Commit Message Generator — analyze diffs, generate conventional commits.

Output format:
  feat(auth): implement JWT middleware with refresh rotation
  fix(api): handle CORS preflight for localhost origins
  refactor(dashboard): extract layout into reusable component
  docs(readme): add installation instructions for Windows
  test(auth): add unit tests for token validation
  chore(deps): update react to v18.3

LLM-powered generation (primary) with rule-based fallback for environments
without an LLM service. Supports single-commit and batch (squash) modes.
"""

from __future__ import annotations

import logging
import re
from collections import Counter
from dataclasses import dataclass
from enum import Enum
from typing import Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class CommitType(str, Enum):
    """Conventional Commit types."""

    FEAT = "feat"
    FIX = "fix"
    REFACTOR = "refactor"
    DOCS = "docs"
    TEST = "test"
    CHORE = "chore"
    STYLE = "style"
    PERF = "perf"
    BUILD = "build"
    CI = "ci"


@dataclass
class CommitSuggestion:
    """A commit message suggestion with metadata."""

    type: CommitType
    scope: str
    description: str
    body: Optional[str] = None
    breaking: bool = False
    confidence: float = 0.0

    def to_message(self, include_body: bool = False) -> str:
        """Render as a conventional commit message string."""
        prefix = f"{self.type.value}({self.scope})"
        if self.breaking:
            prefix = f"{prefix}!"
        msg = f"{prefix}: {self.description}"
        if include_body and self.body:
            msg = f"{msg}\n\n{self.body}"
        return msg

    def __str__(self) -> str:
        return self.to_message()


class CommitMessageGenerator:
    """Generates conventional commit messages from Git diffs.

    * LLM mode: structured prompt → conventional commit response.
    * Rule-based: file paths, change stats, keyword heuristics.
    """

    _MAX_DIFF_CHARS: int = 8_000
    _SCOPE_FALLBACK: str = "repo"

    _KEYWORD_PATTERNS: Dict[CommitType, List[str]] = {
        CommitType.FEAT: [
            "add", "implement", "create", "new", "support", "enable",
            "introduce", "feature",
        ],
        CommitType.FIX: [
            "fix", "bug", "resolve", "correct", "patch", "repair",
            "hotfix", "bugfix", "close #", "closes #", "fixes #",
        ],
        CommitType.REFACTOR: [
            "refactor", "restructure", "reorganize", "simplify",
            "extract", "move", "rename", "clean up", "cleanup",
        ],
        CommitType.DOCS: [
            "doc", "readme", "comment", "guide", "manual", "changelog",
        ],
        CommitType.TEST: [
            "test", "spec", "assertion", "mock", "coverage",
        ],
        CommitType.PERF: [
            "optimiz", "performance", "speed", "cache", "lazy", "memo",
        ],
        CommitType.BUILD: [
            "build", "gradle", "maven", "webpack", "cargo", "cmake",
        ],
        CommitType.CI: [
            "ci", "pipeline", "github action", "workflow",
        ],
        CommitType.STYLE: [
            "format", "style", "whitespace", "indent", "lint", "prettier",
        ],
    }

    _SCOPE_OVERRIDES: Dict[str, str] = {
        "test": "test", "tests": "test", "docs": "docs", "doc": "docs",
        "ci": "ci", ".github": "ci", "scripts": "chore",
    }

    def __init__(self, llm_service: Optional[Callable[[str], str]] = None) -> None:
        self.llm = llm_service
        logger.debug("CommitMessageGenerator initialised (llm=%s)",
                     "available" if llm_service else "unavailable")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate(self, diff: str, context: str = "") -> CommitSuggestion:
        """Generate a commit message from a diff.

        Tries LLM first, falls back to rule-based. Args:
            diff: Unified diff string (e.g. ``git diff --cached``).
            context: Optional human-readable context.
        """
        if not diff or not diff.strip():
            logger.warning("Empty diff received; returning default")
            return CommitSuggestion(
                type=CommitType.CHORE, scope=self._SCOPE_FALLBACK,
                description="empty commit", confidence=0.0,
            )

        if self.llm is not None:
            try:
                suggestion = self._generate_with_llm(diff, context)
                if suggestion:
                    logger.info("LLM commit: %s", suggestion.to_message())
                    return suggestion
            except Exception as exc:
                logger.warning("LLM failed (%s); falling back", exc)

        return self._generate_rule_based(diff)

    def batch_generate(self, diffs: List[str]) -> List[CommitSuggestion]:
        """Generate commit messages for multiple diffs (squash analysis).
        
        Uses combined context for better scope detection.
        """
        if not diffs:
            return []
        combined = "\n".join(diffs)
        scope = self._detect_scope(combined)
        suggestions: List[CommitSuggestion] = []
        for i, diff in enumerate(diffs):
            try:
                suggestion = self.generate(diff, f"batch {i + 1}/{len(diffs)}")
                if scope and suggestion.scope == self._SCOPE_FALLBACK:
                    suggestion.scope = scope
                suggestions.append(suggestion)
            except Exception as exc:
                logger.error("Diff %d failed: %s", i, exc)
                suggestions.append(CommitSuggestion(
                    type=CommitType.CHORE, scope=scope or self._SCOPE_FALLBACK,
                    description=f"changes (batch {i + 1})", confidence=0.0,
                ))
        return suggestions

    # ------------------------------------------------------------------
    # LLM generation
    # ------------------------------------------------------------------

    def _generate_with_llm(
        self, diff: str, context: str = ""
    ) -> Optional[CommitSuggestion]:
        """Use LLM to generate a conventional-commit suggestion."""
        prompt = self._build_llm_prompt(diff, context)
        try:
            raw = self.llm(prompt)  # type: ignore[misc]
        except Exception as exc:
            logger.warning("LLM call failed: %s", exc)
            return None
        if not raw:
            return None
        return self._parse_llm_response(raw, diff)

    def _build_llm_prompt(self, diff: str, context: str = "") -> str:
        """Build the structured prompt for the LLM."""
        diff_summary = diff[:self._MAX_DIFF_CHARS]
        if len(diff) > self._MAX_DIFF_CHARS:
            diff_summary += "\n... [truncated]"
        added, deleted = self._count_changes(diff)
        ctx_block = f"\nContext: {context}" if context else ""

        return (
            "You are an expert software engineer writing precise conventional "
            "commit messages.\n\n"
            "Analyze the following Git diff and produce a commit message "
            "following the Conventional Commits specification.\n\n"
            "Rules:\n"
            "- type: feat, fix, refactor, docs, test, chore, style, perf, build, ci\n"
            "- scope: affected module/component (lowercase)\n"
            "- description: short imperative sentence (max 72 chars)\n"
            "- breaking: add '!' before colon if breaking\n\n"
            "Respond in this exact format (no markdown):\n"
            "type|scope|description|breaking|confidence\n\n"
            f"Files changed: {self._count_files(diff)}\n"
            f"Insertions: {added}\nDeletions: {deleted}{ctx_block}\n\n"
            f"Diff:\n{diff_summary}"
        )

    def _parse_llm_response(
        self, response: str, diff: str
    ) -> Optional[CommitSuggestion]:
        """Parse pipe-delimited or conventional-format LLM response."""
        cleaned = re.sub(r"```[a-z]*\n?|```", "", response).strip()

        # Try pipe-delimited format
        parts = cleaned.split("|")
        if len(parts) >= 3:
            try:
                commit_type = CommitType(parts[0].strip().lower())
            except ValueError:
                logger.warning("LLM invalid type: %s", parts[0])
                return None
            scope = parts[1].strip() or self._detect_scope(diff)
            desc = parts[2].strip()
            breaking = (parts[3].strip().lower() == "true") if len(parts) > 3 else False
            conf = 0.95
            try:
                if len(parts) > 4:
                    conf = float(parts[4].strip())
            except ValueError:
                pass
            return CommitSuggestion(
                type=commit_type, scope=scope, description=desc,
                breaking=breaking, confidence=min(conf, 1.0),
            )

        # Fallback: match "type(scope): description" format
        match = re.match(
            r"^(\w+)(?:\(([^)]+)\))?(!?)?:\s*(.+)$", cleaned, re.IGNORECASE
        )
        if match:
            try:
                commit_type = CommitType(match.group(1).lower())
            except ValueError:
                return None
            scope = match.group(2) or self._detect_scope(diff)
            return CommitSuggestion(
                type=commit_type, scope=scope,
                description=match.group(4).strip(),
                breaking=match.group(3) == "!", confidence=0.90,
            )

        logger.warning("Unparseable LLM response: %s", cleaned[:200])
        return None

    # ------------------------------------------------------------------
    # Rule-based generation
    # ------------------------------------------------------------------

    def _generate_rule_based(self, diff: str) -> CommitSuggestion:
        """Generate commit message using heuristics."""
        commit_type, type_conf = self._detect_type(diff)
        scope = self._detect_scope(diff)
        desc = self._build_description(diff, commit_type)
        breaking = self._detect_breaking(diff)
        confidence = type_conf * 0.6 + (0.4 if scope != self._SCOPE_FALLBACK else 0.2)

        return CommitSuggestion(
            type=commit_type, scope=scope, description=desc,
            breaking=breaking, confidence=round(confidence, 2),
        )

    def _detect_type(self, diff: str) -> tuple[CommitType, float]:
        """Detect commit type from keyword frequency. Returns (type, confidence)."""
        diff_lower = diff.lower()
        scores: Counter[CommitType] = Counter()

        for commit_type, keywords in self._KEYWORD_PATTERNS.items():
            for keyword in keywords:
                count = diff_lower.count(keyword.lower())
                if count:
                    scores[commit_type] += count

        # Boost from file path patterns
        for path in self._extract_file_paths(diff):
            pl = path.lower()
            if any(p in pl for p in ("test", "spec", "__tests__")):
                scores[CommitType.TEST] += 2
            if any(p in pl for p in ("doc", "readme", ".md", "changelog")):
                scores[CommitType.DOCS] += 2
            if any(p in pl for p in (".github/workflows", ".gitlab-ci")):
                scores[CommitType.CI] += 3
            if any(p in pl for p in ("setup.py", "pyproject.toml", "package.json")):
                scores[CommitType.BUILD] += 2

        if not scores:
            return CommitType.CHORE, 0.3

        (best_type, best_score), = scores.most_common(1)
        total = sum(scores.values())
        conf = min(best_score / total, 1.0) if total > 0 else 0.3
        return best_type, round(conf, 2)

    def _detect_scope(self, diff: str) -> str:
        """Detect scope from changed file paths."""
        paths = self._extract_file_paths(diff)
        if not paths:
            return self._SCOPE_FALLBACK

        for path in paths:
            pl = path.lower()
            for key, override in self._SCOPE_OVERRIDES.items():
                if key in pl:
                    return override

        dirs: Counter[str] = Counter()
        for path in paths:
            parts = path.replace("\\", "/").split("/")
            for part in parts[:-1]:
                if part and part not in (".", "..", "src", "lib", "app"):
                    dirs[part.lower()] += 1

        if dirs:
            (best_dir, _), = dirs.most_common(1)
            return best_dir

        # Fallback: file extension
        exts = Counter(p.rsplit(".", 1)[-1].lower() for p in paths if "." in p)
        valid_exts = {"py", "js", "ts", "tsx", "go", "rs", "java"}
        filtered = {k: v for k, v in exts.items() if k in valid_exts}
        if filtered:
            (best_ext, _), = Counter(filtered).most_common(1)
            return best_ext

        return self._SCOPE_FALLBACK

    def _build_description(self, diff: str, commit_type: CommitType) -> str:
        """Build imperative description from diff analysis."""
        added, deleted = self._count_changes(diff)
        paths = self._extract_file_paths(diff)

        type_verbs: Dict[CommitType, str] = {
            CommitType.FEAT: "add" if added > deleted else "implement",
            CommitType.FIX: "fix",
            CommitType.REFACTOR: "refactor",
            CommitType.DOCS: "update" if deleted > 0 else "add",
            CommitType.TEST: "add" if added > deleted else "update",
            CommitType.CHORE: "update",
            CommitType.STYLE: "format",
            CommitType.PERF: "optimize",
            CommitType.BUILD: "update",
            CommitType.CI: "update",
        }
        verb = type_verbs.get(commit_type, "update")

        if paths:
            names = [p.rsplit("/", 1)[-1].rsplit(".", 1)[0] for p in paths]
            names = [n for n in names if n]
            if len(names) == 1:
                return f"{verb} {names[0]}".lower()
            elif names:
                return f"{verb} {names[0]} and {len(names) - 1} other(s)".lower()

        return f"{verb} code"

    def _detect_breaking(self, diff: str) -> bool:
        """Detect breaking change indicators in diff."""
        indicators = [
            "breaking change", "BREAKING", "!:", "deprecated",
            "remove support", "drop support",
        ]
        dl = diff.lower()
        return any(ind.lower() in dl for ind in indicators)

    # ------------------------------------------------------------------
    # Diff utilities
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_file_paths(diff: str) -> List[str]:
        """Extract file paths from unified diff."""
        paths: List[str] = []
        for line in diff.splitlines():
            match = re.match(r"^[-+]{3}\s*[ab]/(.*)$", line)
            if match and match.group(1) != "/dev/null":
                paths.append(match.group(1))
        return list(dict.fromkeys(paths))

    @staticmethod
    def _count_changes(diff: str) -> tuple[int, int]:
        """Count (insertions, deletions) in diff."""
        added = sum(1 for line in diff.splitlines()
                    if line.startswith("+") and not line.startswith("+++")
                    and not line.startswith("+--"))
        deleted = sum(1 for line in diff.splitlines()
                      if line.startswith("-") and not line.startswith("---")
                      and not line.startswith("--+"))
        return added, deleted

    @staticmethod
    def _count_files(diff: str) -> int:
        """Count files changed in diff."""
        return len(CommitMessageGenerator._extract_file_paths(diff))
