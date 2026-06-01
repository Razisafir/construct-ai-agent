"""Pre-Commit Pipeline — run checks before allowing commits.

Stages (auto-detect available tools):
1. Tests (pytest / unittest)
2. Lint (ruff / flake8)
3. Type check (mypy / pyright)
4. Security scan (bandit / grep patterns)
5. Coverage threshold check
"""

from __future__ import annotations

import logging
import re
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class CheckStatus(str, Enum):
    """Outcome of a single pipeline check."""

    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    NOT_CONFIGURED = "not_configured"


@dataclass
class CheckResult:
    """Result from a single pipeline stage."""

    name: str
    status: CheckStatus
    duration_ms: float
    output: str
    errors: List[str] = field(default_factory=list)


@dataclass
class PipelineResult:
    """Aggregate pipeline result."""

    overall: CheckStatus
    checks: List[CheckResult]
    can_commit: bool
    summary: str


class PreCommitPipeline:
    """Runs pre-commit checks with auto-detection and timeout handling."""

    DEFAULT_TIMEOUT: int = 120
    COVERAGE_THRESHOLD: float = 80.0

    def __init__(self, repo_path: str = ".") -> None:
        self.repo_path = repo_path
        self._checks: Dict[str, Callable[[List[str]], CheckResult]] = {
            "tests": self._run_tests,
            "lint": self._run_lint,
            "typecheck": self._run_typecheck,
            "security": self._run_security_scan,
            "coverage": self._run_coverage_check,
        }
        self._tool_cache: Dict[str, bool] = {}
        logger.debug("PreCommitPipeline for %s", repo_path)

    def run(
        self, files: List[str], checks: Optional[List[str]] = None
    ) -> PipelineResult:
        """Run the pre-commit pipeline.

        Args:
            files: Files staged for commit.
            checks: Which checks to run (None = all).
        
        Returns:
            PipelineResult with overall status and per-check details.
        """
        to_run = checks if checks is not None else list(self._checks.keys())
        abs_files = [str(Path(self.repo_path) / f) for f in files]
        results: List[CheckResult] = []
        overall_pass = True

        logger.info("Pipeline checks %s on %d file(s)", to_run, len(files))

        for name in to_run:
            if name not in self._checks:
                results.append(CheckResult(
                    name=name, status=CheckStatus.NOT_CONFIGURED,
                    duration_ms=0.0, output=f"Unknown check: {name}",
                ))
                overall_pass = False
                continue

            try:
                result = self._checks[name](abs_files)
            except Exception as exc:
                logger.exception("Check '%s' failed", name)
                result = CheckResult(
                    name=name, status=CheckStatus.FAILED,
                    duration_ms=0.0, output=str(exc), errors=[str(exc)],
                )
            results.append(result)
            if result.status != CheckStatus.PASSED:
                overall_pass = False

        summary = self._build_summary(results, overall_pass)
        passed_count = sum(1 for r in results if r.status == CheckStatus.PASSED)
        logger.info("Pipeline: %s (%d/%d passed)",
                    "PASSED" if overall_pass else "FAILED",
                    passed_count, len(results))

        return PipelineResult(
            overall=CheckStatus.PASSED if overall_pass else CheckStatus.FAILED,
            checks=results, can_commit=overall_pass, summary=summary,
        )

    # ------------------------------------------------------------------
    # Check implementations
    # ------------------------------------------------------------------

    def _run_tests(self, files: List[str]) -> CheckResult:
        """Run tests: pytest preferred, unittest fallback."""
        start = time.perf_counter()
        if not self._has_tool("pytest"):
            if self._has_tool("python"):
                return self._run_unittest(files, start)
            return self._not_configured("tests", "pytest", start)

        targets = self._resolve_test_targets(files)
        cmd = ["pytest", "-q", "--tb=short", "--color=no"]
        cmd.extend(targets if targets else [self.repo_path])

        out, err, rc = self._run_cmd(cmd, self.DEFAULT_TIMEOUT)
        dur = (time.perf_counter() - start) * 1000

        if rc == 0:
            return CheckResult(name="tests", status=CheckStatus.PASSED,
                               duration_ms=dur, output=out or "All tests passed")
        return CheckResult(name="tests", status=CheckStatus.FAILED, duration_ms=dur,
                           output=out + "\n" + err, errors=self._extract_errors(out + "\n" + err))

    def _run_unittest(self, files: List[str], start: float) -> CheckResult:
        """Run unittest discovery."""
        test_dir = str(Path(self.repo_path) / "tests")
        if not Path(test_dir).is_dir():
            test_dir = self.repo_path
        out, err, rc = self._run_cmd(
            ["python", "-m", "unittest", "discover", "-s", test_dir, "-q"],
            self.DEFAULT_TIMEOUT,
        )
        dur = (time.perf_counter() - start) * 1000
        if rc == 0:
            return CheckResult(name="tests", status=CheckStatus.PASSED,
                               duration_ms=dur, output=out or "unittest passed")
        return CheckResult(name="tests", status=CheckStatus.FAILED, duration_ms=dur,
                           output=out + "\n" + err, errors=self._extract_errors(out + "\n" + err))

    def _run_lint(self, files: List[str]) -> CheckResult:
        """Run linter: ruff preferred, flake8 fallback."""
        start = time.perf_counter()
        if self._has_tool("ruff"):
            return self._run_tool("ruff", ["check", "--quiet"], files, ".py", "lint", start)
        if self._has_tool("flake8"):
            return self._run_tool("flake8", ["--max-line-length=100"], files, ".py", "lint", start)
        return self._not_configured("lint", "ruff or flake8", start)

    def _run_typecheck(self, files: List[str]) -> CheckResult:
        """Run type checker: mypy preferred, pyright fallback."""
        start = time.perf_counter()
        if self._has_tool("mypy"):
            return self._run_tool("mypy", ["--ignore-missing-imports", "--show-error-codes"],
                                  files, ".py", "typecheck", start)
        if self._has_tool("pyright"):
            return self._run_tool("pyright", [], files, ".py", "typecheck", start)
        return self._not_configured("typecheck", "mypy or pyright", start)

    def _run_security_scan(self, files: List[str]) -> CheckResult:
        """Security: bandit preferred, grep fallback."""
        start = time.perf_counter()
        if self._has_tool("bandit"):
            py_files = [f for f in files if f.endswith(".py")]
            if not py_files:
                return self._skip("security", "No Python files", start)
            out, err, rc = self._run_cmd(["bandit", "-f", "json", "-q", "-r"] + py_files, 120)
            dur = (time.perf_counter() - start) * 1000
            if rc == 0:
                return CheckResult(name="security", status=CheckStatus.PASSED,
                                   duration_ms=dur, output="Bandit: no issues")
            return CheckResult(name="security", status=CheckStatus.FAILED, duration_ms=dur,
                               output=out + "\n" + err, errors=["Security issues found"])
        return self._run_grep_security(files, start)

    def _run_grep_security(self, files: List[str], start: float) -> CheckResult:
        """Grep-based security scan fallback."""
        py_files = [f for f in files if f.endswith(".py")]
        if not py_files:
            return self._skip("security", "No Python files", start)

        patterns = [
            r"eval\s*\(", r"exec\s*\(", r"subprocess\.\w+.*shell\s*=\s*True",
            r"pickle\.loads?\s*\(", r"yaml\.load\s*\(", r"os\.system\s*\(",
        ]
        findings: List[str] = []
        for pat in patterns:
            out, _, rc = self._run_cmd(["grep", "-n", "-E", pat] + py_files, 30)
            if rc == 0 and out.strip():
                findings.extend(out.strip().splitlines())

        dur = (time.perf_counter() - start) * 1000
        if not findings:
            return CheckResult(name="security", status=CheckStatus.PASSED,
                               duration_ms=dur, output="No security issues")
        return CheckResult(name="security", status=CheckStatus.FAILED,
                           duration_ms=dur, output="\n".join(findings), errors=findings)

    def _run_coverage_check(self, files: List[str]) -> CheckResult:
        """Check test coverage against threshold."""
        start = time.perf_counter()
        if not self._has_tool("pytest"):
            return self._not_configured("coverage", "pytest", start)

        # Check pytest-cov availability
        out_check, _, rc_check = self._run_cmd(
            ["python", "-c", "import pytest_cov; print('ok')"], 10)
        if rc_check != 0 or "ok" not in out_check:
            dur = (time.perf_counter() - start) * 1000
            return CheckResult(name="coverage", status=CheckStatus.NOT_CONFIGURED,
                               duration_ms=dur, output="pytest-cov not installed")

        cmd = ["pytest", "--cov=.", f"--cov-fail-under={self.COVERAGE_THRESHOLD}",
               "-q", "--tb=no", "--color=no"]
        out, err, rc = self._run_cmd(cmd, self.DEFAULT_TIMEOUT)
        dur = (time.perf_counter() - start) * 1000

        if rc == 0:
            return CheckResult(name="coverage", status=CheckStatus.PASSED,
                               duration_ms=dur, output=out or f"Coverage >= {self.COVERAGE_THRESHOLD}%")

        cov_match = re.search(r"(\d+)%", out + err)
        actual = f"{cov_match.group(1)}%" if cov_match else "unknown"
        return CheckResult(name="coverage", status=CheckStatus.FAILED, duration_ms=dur,
                           output=out + "\n" + err,
                           errors=[f"Coverage {actual} < threshold {self.COVERAGE_THRESHOLD}%"])

    # ------------------------------------------------------------------
    # Generic helpers
    # ------------------------------------------------------------------

    def _run_tool(
        self, tool: str, base_args: List[str], files: List[str],
        ext: str, check_name: str, start: float
    ) -> CheckResult:
        """Run a CLI tool on files with given extension."""
        filtered = [f for f in files if f.endswith(ext)]
        if not filtered:
            return self._skip(check_name, f"No {ext} files", start)

        cmd = [tool] + base_args + filtered
        out, err, rc = self._run_cmd(cmd, 120)
        dur = (time.perf_counter() - start) * 1000

        if rc == 0:
            return CheckResult(name=check_name, status=CheckStatus.PASSED,
                               duration_ms=dur, output=out or f"{tool} passed")
        return CheckResult(name=check_name, status=CheckStatus.FAILED, duration_ms=dur,
                           output=out + "\n" + err,
                           errors=[l for l in (out + "\n" + err).splitlines() if l.strip()])

    def _skip(self, name: str, reason: str, start: float) -> CheckResult:
        dur = (time.perf_counter() - start) * 1000
        return CheckResult(name=name, status=CheckStatus.SKIPPED,
                           duration_ms=dur, output=reason)

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------

    def _has_tool(self, name: str) -> bool:
        """Check PATH for a CLI tool (cached)."""
        if name not in self._tool_cache:
            self._tool_cache[name] = shutil.which(name) is not None
        return self._tool_cache[name]

    def _run_cmd(self, cmd: List[str], timeout: int) -> Tuple[str, str, int]:
        """Run command, return (stdout, stderr, rc). Handles timeout."""
        logger.debug("cmd: %s", " ".join(cmd))
        try:
            r = subprocess.run(cmd, capture_output=True, text=True,
                               timeout=timeout, cwd=self.repo_path)
            return r.stdout, r.stderr, r.returncode
        except subprocess.TimeoutExpired as exc:
            stdout = exc.stdout.decode() if exc.stdout else ""
            return stdout, f"TIMEOUT after {timeout}s", -1
        except FileNotFoundError:
            return "", f"Command not found: {cmd[0]}", 127

    def _resolve_test_targets(self, files: List[str]) -> List[str]:
        """Map source files to likely test files."""
        targets: List[str] = []
        repo = Path(self.repo_path)
        for f in files:
            path = Path(f)
            name = path.stem
            candidates = [
                repo / "tests" / f"test_{name}.py",
                repo / "test" / f"test_{name}.py",
                repo / f"test_{name}.py",
                repo / "tests" / path.parent / f"test_{name}.py",
            ]
            for c in candidates:
                if c.exists() and str(c) not in targets:
                    targets.append(str(c))
        return targets

    def _extract_errors(self, output: str) -> List[str]:
        """Extract error lines from tool output."""
        errors: List[str] = []
        for line in output.splitlines():
            if any(kw in line.lower() for kw in ("error", "failed", "failure", "fatal")):
                stripped = line.strip()
                if stripped and stripped not in errors:
                    errors.append(stripped)
        return errors

    def _not_configured(self, name: str, tool: str, start: float) -> CheckResult:
        dur = (time.perf_counter() - start) * 1000
        msg = f"{tool} not found on PATH; skipping"
        logger.info(msg)
        return CheckResult(name=name, status=CheckStatus.NOT_CONFIGURED,
                           duration_ms=dur, output=msg)

    def _build_summary(self, results: List[CheckResult], overall_pass: bool) -> str:
        """Build human-readable summary."""
        lines = [
            "PASSED — ready to commit" if overall_pass
            else "FAILED — fix issues before committing",
            "",
        ]
        icons = {
            CheckStatus.PASSED: "✓", CheckStatus.FAILED: "✗",
            CheckStatus.SKIPPED: "⊘", CheckStatus.NOT_CONFIGURED: "−",
        }
        for r in results:
            icon = icons.get(r.status, "?")
            lines.append(f"  {icon} {r.name:<12} {r.status.value:<16} ({r.duration_ms:.0f}ms)")
            for err in r.errors[:3]:
                lines.append(f"      > {err}")
        return "\n".join(lines)
