"""
Git operations for codebase management.

Tools: git_status, git_diff, git_commit, git_branch, git_log, git_checkout

All operations use ``subprocess.run()`` with the ``git`` command and return
structured dictionaries with success/failure status, output, and parsed data.
"""

import re
import os
import shlex
import logging
import asyncio
import subprocess
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------

# Characters allowed in branch names (git ref naming rules)
_VALID_BRANCH_PATTERN = re.compile(r"^[A-Za-z0-9_\-/.@]+$")

# Maximum branch name length
_MAX_BRANCH_LENGTH = 244

# Blocked branch names (destructive or reserved)
_BLOCKED_BRANCH_NAMES = {
    "HEAD", "FETCH_HEAD", "ORIG_HEAD", "MERGE_HEAD",
    "-",  # disallowed by git
}


def _validate_branch_name(name: str) -> Optional[str]:
    """
    Validate a git branch name.

    Returns an error message if invalid, *None* if valid.
    """
    if not name:
        return "Branch name cannot be empty"
    if len(name) > _MAX_BRANCH_LENGTH:
        return f"Branch name too long ({len(name)} > {_MAX_BRANCH_LENGTH})"
    if name in _BLOCKED_BRANCH_NAMES:
        return f"Branch name '{name}' is reserved"
    if name.startswith("-"):
        return "Branch name cannot start with '-'"
    if name.startswith("."):
        return "Branch name cannot start with '.'"
    if ".." in name:
        return "Branch name cannot contain '..'"
    if "@{" in name:
        return "Branch name cannot contain '@{'"
    if not _VALID_BRANCH_PATTERN.match(name):
        return f"Branch name contains invalid characters: '{name}'"
    return None


def _escape_commit_message(message: str) -> str:
    """
    Escape a commit message to prevent git option injection.

    - Strips leading '-' to prevent option injection
    - Escapes newlines (git treats them specially)
    - Limits length
    """
    # Strip leading whitespace and '-'
    message = message.lstrip()
    while message.startswith("-"):
        message = message[1:].lstrip()

    # Limit length
    MAX_COMMIT_MSG = 10_000
    if len(message) > MAX_COMMIT_MSG:
        message = message[:MAX_COMMIT_MSG] + "... [truncated]"

    # Replace null bytes
    message = message.replace("\x00", "")

    return message


def _validate_file_paths(paths: List[str]) -> Optional[str]:
    """
    Validate a list of file paths for git operations.

    Returns an error message if any path is suspicious, *None* if all valid.
    """
    for p in paths:
        # Block path traversal
        normalized = os.path.normpath(p)
        if normalized.startswith("..") or "/../" in normalized:
            return f"Path traversal blocked in: '{p}'"
        # Block paths starting with '-' (git option injection)
        if p.startswith("-"):
            return f"Path cannot start with '-': '{p}'"
        # Block null bytes
        if "\x00" in p:
            return f"Path contains null bytes: '{p}'"
    return None

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _run_git(
    args: List[str],
    cwd: str = ".",
    timeout: int = 30,
    capture: bool = True,
) -> Dict[str, Any]:
    """
    Execute a git subcommand and return a structured result.

    Parameters
    ----------
    args:
        Git command arguments (e.g. ``["status", "--porcelain"]``).
    cwd:
        Working directory for the git repository.
    timeout:
        Maximum execution time in seconds.
    capture:
        If *True*, capture stdout/stderr; otherwise let them pass through.

    Returns
    -------
    dict
        ``success`` (bool), ``stdout`` (str), ``stderr`` (str),
        ``exit_code`` (int), ``command`` (str).
    """
    cmd = ["git"] + args
    cmd_str = " ".join(cmd)
    logger.debug("Running: %s (cwd=%s)", cmd_str, cwd)

    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=capture,
            text=True,
            timeout=timeout,
        )

        output = {
            "success": result.returncode == 0,
            "stdout": result.stdout or "",
            "stderr": result.stderr or "",
            "exit_code": result.returncode,
            "command": cmd_str,
        }

        if not output["success"]:
            logger.warning(
                "Git command failed (exit=%d): %s — %s",
                result.returncode,
                cmd_str,
                result.stderr[:200],
            )

        return output

    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "stdout": "",
            "stderr": f"Git command timed out after {timeout}s",
            "exit_code": -1,
            "command": cmd_str,
        }
    except FileNotFoundError:
        return {
            "success": False,
            "stdout": "",
            "stderr": "Git executable not found. Is git installed?",
            "exit_code": -1,
            "command": cmd_str,
        }
    except Exception as exc:
        logger.exception("Git command error: %s", cmd_str)
        return {
            "success": False,
            "stdout": "",
            "stderr": f"Error: {exc}",
            "exit_code": -1,
            "command": cmd_str,
        }


def _is_git_repo(cwd: str = ".") -> bool:
    """Return *True* if *cwd* is inside a git repository."""
    result = _run_git(["rev-parse", "--git-dir"], cwd=cwd, capture=True)
    return result["success"]


# ---------------------------------------------------------------------------
# Public tool functions
# ---------------------------------------------------------------------------


def git_status(cwd: str = ".") -> Dict[str, Any]:
    """
    Get the working tree status.

    Parameters
    ----------
    cwd:
        Repository working directory.

    Returns
    -------
    dict
        Parsed status with ``branch``, ``ahead``, ``behind``,
        ``staged``, ``unstaged``, ``untracked`` file lists.
    """
    if not _is_git_repo(cwd):
        return {"success": False, "error": "Not a git repository", "cwd": cwd}

    result = _run_git(["status", "--porcelain", "--branch"], cwd=cwd)
    if not result["success"]:
        return result

    lines = result["stdout"].strip().split("\n") if result["stdout"].strip() else []

    branch = ""
    ahead = 0
    behind = 0
    staged: List[str] = []
    unstaged: List[str] = []
    untracked: List[str] = []

    for line in lines:
        if not line:
            continue
        # Branch info line: ## branch.name...upstream [ahead N, behind M]
        if line.startswith("##"):
            match = re.match(
                r"##\s+([^\.\s]+)(?:\.\.\.[^\[]+)?(?:\s*\[([^\]]+)\])?", line
            )
            if match:
                branch = match.group(1)
                branch_info = match.group(2) or ""
                ahead_match = re.search(r"ahead\s+(\d+)", branch_info)
                behind_match = re.search(r"behind\s+(\d+)", branch_info)
                if ahead_match:
                    ahead = int(ahead_match.group(1))
                if behind_match:
                    behind = int(behind_match.group(1))
            continue

        # File status lines: XY path or XY path -> path (rename)
        status_code = line[:2]
        file_part = line[3:]

        # Extract the destination path for renames
        if " -> " in file_part:
            file_path = file_part.split(" -> ")[-1]
        else:
            file_path = file_part

        x, y = status_code[0], status_code[1]

        if x == "?" and y == "?":
            untracked.append(file_path)
        elif x != " ":
            staged.append({"file": file_path, "status": x})
        if y != " ":
            unstaged.append({"file": file_path, "status": y})

    return {
        "success": True,
        "branch": branch,
        "ahead": ahead,
        "behind": behind,
        "is_clean": len(staged) == 0 and len(unstaged) == 0 and len(untracked) == 0,
        "staged": staged,
        "unstaged": unstaged,
        "untracked": untracked,
    }


def git_diff(
    cwd: str = ".", staged: bool = False, file_path: Optional[str] = None
) -> Dict[str, Any]:
    """
    Show changes between commits, commit and working tree, etc.

    Parameters
    ----------
    cwd:
        Repository working directory.
    staged:
        If *True*, show staged changes instead of unstaged.
    file_path:
        If provided, limit diff to this file.

    Returns
    -------
    dict
        ``success``, ``diff`` (str), ``files_changed`` (list).
    """
    if not _is_git_repo(cwd):
        return {"success": False, "error": "Not a git repository", "cwd": cwd}

    args = ["diff"]
    if staged:
        args.append("--staged")
    if file_path:
        args.extend(["--", file_path])

    result = _run_git(args, cwd=cwd)
    if not result["success"]:
        return result

    diff_text = result["stdout"]

    # Parse changed files from diff
    files_changed = re.findall(r"^diff --git a/(.+?) b/", diff_text, re.MULTILINE)

    return {
        "success": True,
        "diff": diff_text,
        "files_changed": files_changed,
        "is_empty": not diff_text.strip(),
    }


def git_commit(
    message: str, cwd: str = ".", auto_stage: bool = True
) -> Dict[str, Any]:
    """
    Create a commit.

    Auto-stages all modified and deleted files with ``-a`` when
    *auto_stage* is *True*.

    Parameters
    ----------
    message:
        Commit message.
    cwd:
        Repository working directory.
    auto_stage:
        If *True*, stage modified/deleted files automatically.

    Returns
    -------
    dict
        ``success``, ``commit_hash``, ``message``.
    """
    if not _is_git_repo(cwd):
        return {"success": False, "error": "Not a git repository", "cwd": cwd}

    # Escape commit message to prevent injection
    safe_message = _escape_commit_message(message)
    if not safe_message:
        return {"success": False, "error": "Commit message cannot be empty"}

    # Stage changes if requested
    if auto_stage:
        stage_result = _run_git(["add", "-A"], cwd=cwd)
        if not stage_result["success"]:
            return {
                "success": False,
                "error": f"Failed to stage files: {stage_result['stderr']}",
            }

    # Commit with escaped message
    result = _run_git(["commit", "-m", safe_message], cwd=cwd)
    if not result["success"]:
        return {
            "success": False,
            "stdout": result["stdout"],
            "stderr": result["stderr"],
            "exit_code": result["exit_code"],
        }

    # Extract commit hash
    commit_hash = ""
    hash_match = re.search(r"\[([^\]]+)\s+([a-f0-9]+)]", result["stdout"])
    if hash_match:
        commit_hash = hash_match.group(2)

    return {
        "success": True,
        "commit_hash": commit_hash,
        "message": safe_message,
        "output": result["stdout"].strip(),
    }


def git_branch(
    cwd: str = ".", create: Optional[str] = None, list_all: bool = True
) -> Dict[str, Any]:
    """
    List or create branches.

    Parameters
    ----------
    cwd:
        Repository working directory.
    create:
        If provided, create a new branch with this name.
    list_all:
        If *True* (default), list all branches after the operation.

    Returns
    -------
    dict
        ``success``, ``current_branch``, ``branches`` (list),
        and ``created`` if a branch was created.
    """
    if not _is_git_repo(cwd):
        return {"success": False, "error": "Not a git repository", "cwd": cwd}

    output: Dict[str, Any] = {"success": True}

    # Create branch if requested
    if create:
        error = _validate_branch_name(create)
        if error:
            return {"success": False, "error": error}
        result = _run_git(["checkout", "-b", create], cwd=cwd)
        if not result["success"]:
            return {
                "success": False,
                "error": f"Failed to create branch '{create}': {result['stderr']}",
            }
        output["created"] = create

    # List branches
    if list_all:
        result = _run_git(["branch", "-vv"], cwd=cwd)
        if result["success"]:
            branches = []
            current_branch = ""
            for line in result["stdout"].strip().split("\n"):
                line = line.strip()
                if not line:
                    continue
                is_current = line.startswith("*")
                name = line[1:].strip().split()[0] if is_current else line.split()[0]
                if is_current:
                    current_branch = name
                branches.append(
                    {
                        "name": name,
                        "current": is_current,
                        "full": line,
                    }
                )
            output["current_branch"] = current_branch
            output["branches"] = branches
        else:
            output["branches"] = []
            output["current_branch"] = ""

    return output


def git_log(
    cwd: str = ".",
    max_count: int = 20,
    file_path: Optional[str] = None,
    oneline: bool = False,
) -> Dict[str, Any]:
    """
    Show commit history.

    Parameters
    ----------
    cwd:
        Repository working directory.
    max_count:
        Maximum number of commits to return (default 20).
    file_path:
        If provided, only show commits affecting this file.
    oneline:
        If *True*, return condensed one-line format.

    Returns
    -------
    dict
        ``success``, ``commits`` (list of dicts with hash, author,
        date, message).
    """
    if not _is_git_repo(cwd):
        return {"success": False, "error": "Not a git repository", "cwd": cwd}

    if oneline:
        args = ["log", f"--max-count={max_count}", "--oneline"]
        if file_path:
            args.extend(["--", file_path])
        result = _run_git(args, cwd=cwd)
        if not result["success"]:
            return result

        commits = []
        for line in result["stdout"].strip().split("\n"):
            if " " in line:
                hash_part, msg = line.split(" ", 1)
                commits.append({"hash": hash_part, "message": msg})

        return {"success": True, "commits": commits}

    # Full format
    format_str = (
        "%H|%an|%ae|%ad|%s"  # hash|author_name|author_email|date|subject
    )
    args = ["log", f"--max-count={max_count}", f"--format={format_str}", "--date=iso"]
    if file_path:
        args.extend(["--", file_path])

    result = _run_git(args, cwd=cwd)
    if not result["success"]:
        return result

    commits: List[Dict[str, Any]] = []
    for line in result["stdout"].strip().split("\n"):
        if "|" in line:
            parts = line.split("|", 4)
            if len(parts) >= 5:
                try:
                    date_parsed = datetime.fromisoformat(parts[3].strip())
                except (ValueError, IndexError):
                    date_parsed = None

                commits.append(
                    {
                        "hash": parts[0][:12],  # short hash
                        "hash_full": parts[0],
                        "author_name": parts[1],
                        "author_email": parts[2],
                        "date": parts[3].strip(),
                        "date_parsed": (
                            date_parsed.isoformat() if date_parsed else None
                        ),
                        "message": parts[4],
                    }
                )

    return {"success": True, "commits": commits}


def git_checkout(
    target: str, cwd: str = ".", create: bool = False
) -> Dict[str, Any]:
    """
    Switch branches or restore working tree files.

    Parameters
    ----------
    target:
        Branch name, commit hash, or file path to checkout.
    cwd:
        Repository working directory.
    create:
        If *True*, create the branch if it doesn't exist.

    Returns
    -------
    dict
        ``success``, ``current_branch``.
    """
    if not _is_git_repo(cwd):
        return {"success": False, "error": "Not a git repository", "cwd": cwd}

    # Validate target (prevent option injection)
    if target.startswith("-"):
        return {"success": False, "error": f"Checkout target cannot start with '-': '{target}'"}
    if "\x00" in target:
        return {"success": False, "error": "Checkout target contains null bytes"}

    # If creating a branch, validate the branch name
    if create:
        error = _validate_branch_name(target)
        if error:
            return {"success": False, "error": error}

    args = ["checkout"]
    if create:
        args.append("-b")
    args.append(target)

    result = _run_git(args, cwd=cwd)
    if not result["success"]:
        return {
            "success": False,
            "error": result["stderr"],
            "stdout": result["stdout"],
        }

    # Get current branch
    branch_result = _run_git(["branch", "--show-current"], cwd=cwd)
    current_branch = branch_result["stdout"].strip() if branch_result["success"] else target

    return {
        "success": True,
        "current_branch": current_branch,
        "output": result["stdout"].strip(),
    }


def git_add(files: List[str], cwd: str = ".") -> Dict[str, Any]:
    """
    Stage files for commit.

    Parameters
    ----------
    files:
        List of file paths to stage.
    cwd:
        Repository working directory.

    Returns
    -------
    dict
        ``success``, ``staged_files``.
    """
    if not _is_git_repo(cwd):
        return {"success": False, "error": "Not a git repository", "cwd": cwd}

    if not files:
        return {"success": False, "error": "No files provided to stage"}

    # Validate file paths (prevent option injection and traversal)
    error = _validate_file_paths(files)
    if error:
        return {"success": False, "error": error}

    result = _run_git(["add", "--"] + files, cwd=cwd)
    if result["success"]:
        return {
            "success": True,
            "staged_files": files,
        }
    return result


def git_reset(cwd: str = ".", hard: bool = False) -> Dict[str, Any]:
    """
    Reset the working tree.

    Parameters
    ----------
    cwd:
        Repository working directory.
    hard:
        If *True*, perform a hard reset (discards all changes).
        Hard reset requires explicit confirmation due to data loss risk.

    Returns
    -------
    dict
        ``success``, ``mode``.
    """
    if not _is_git_repo(cwd):
        return {"success": False, "error": "Not a git repository", "cwd": cwd}

    # Safety: hard reset is destructive and requires explicit opt-in
    if hard:
        logger.warning(
            "git reset --hard requested on %s — this will discard all uncommitted changes",
            cwd
        )
        # Return a warning that the caller must acknowledge
        return {
            "success": False,
            "error": (
                "Hard reset is a destructive operation that discards all uncommitted changes. "
                "To confirm, call git_reset_hard_confirm() instead."
            ),
            "mode": "hard",
            "requires_confirmation": True,
        }

    args = ["reset", "--soft", "HEAD"]

    result = _run_git(args, cwd=cwd)
    return result


def git_reset_hard_confirm(cwd: str = ".") -> Dict[str, Any]:
    """
    Perform a hard reset after explicit confirmation.

    This function exists as a separate entry point to ensure callers
    consciously acknowledge the data-loss risk of ``git reset --hard``.

    Parameters
    ----------
    cwd:
        Repository working directory.

    Returns
    -------
    dict
        ``success``, ``mode``.
    """
    if not _is_git_repo(cwd):
        return {"success": False, "error": "Not a git repository", "cwd": cwd}

    logger.info("Executing confirmed git reset --hard on %s", cwd)

    args = ["reset", "--hard", "HEAD"]
    result = _run_git(args, cwd=cwd)
    result["mode"] = "hard"
    result["warning"] = "All uncommitted changes have been discarded"
    return result


# ---------------------------------------------------------------------------
# Commit message generation
# ---------------------------------------------------------------------------

# Conventional commit type keywords mapped to type
_COMMIT_TYPE_KEYWORDS: Dict[str, List[str]] = {
    "feat": ["add", "implement", "introduce", "create", "new", "support", "enable"],
    "fix": ["fix", "bug", "repair", "resolve", "correct", "patch", "address", "issue"],
    "refactor": ["refactor", "restructure", "rewrite", "clean", "simplify", "improve", "optimize", "consolidate"],
    "docs": ["doc", "document", "readme", "comment", "changelog", "guide", "example"],
    "test": ["test", "spec", "assertion", "coverage", "mock", "e2e", "unit test"],
    "style": ["format", "lint", "style", "whitespace", "indent", "trailing"],
    "chore": ["update", "bump", "upgrade", "dependency", "deps", "config", "ci", "build", "tooling", "Makefile"],
    "perf": ["performance", "speed", "cache", "latency", "throughput", "benchmark", "fast"],
    "security": ["security", "vulnerability", "auth", "permission", "sanitize", "escape", "cve"],
}

# File path patterns mapped to scope
_SCOPE_PATH_PATTERNS: Dict[str, List[str]] = {
    "auth": ["auth", "login", "oauth", "sso", "session", "credential", "password", "token", "jwt", "permission", "rbac"],
    "api": ["/api/", "/routes/", "/controllers/", "/endpoints/", "/handlers/", "router", "middleware", "rest", "graphql"],
    "db": ["/db/", "/database/", "/models/", "/schema/", "/migration/", "orm", "repository", "sql", "mongo", "redis", "postgres"],
    "ui": ["/ui/", "/components/", "/views/", "/pages/", "/templates/", "/frontend/", "/widgets/", ".css", ".scss", ".less", ".html"],
    "core": ["/core/", "/engine/", "/context/", "/utils/", "/common/", "/shared/", "/lib/", "/internal/"],
    "test": ["/tests/", "/test/", "/spec/", "/__tests__/,", "/e2e/", "/integration/", ".test.", ".spec."],
    "ci": [".github/", ".gitlab/", "docker", "Dockerfile", "jenkins", ".travis", ".circleci/", "/pipelines/"],
    "config": ["config", "settings", ".env", ".yaml", ".yml", ".toml", ".ini", "setup.py", "pyproject", "package.json"],
    "docs": ["docs/", "doc/", "README", "CHANGELOG", "CONTRIBUTING", "LICENSE", ".md"],
    "deps": ["requirements", "package-lock", "yarn.lock", "Pipfile", "poetry.lock", "go.mod", "go.sum", "Cargo.toml"],
}

# Keywords indicating breaking changes
_BREAKING_KEYWORDS: List[str] = [
    "breaking", "break", "remove", "delete", "drop", "rename", "migrate",
    "upgrade", "v2", "deprecat", "incompatible",
]


async def generate_commit_message(
    diff: str,
    llm_service: Any = None,
) -> Dict[str, Any]:
    """Generate a conventional commit message from a diff string.

    Analyzes diff statistics, detects the scope from changed file paths,
    determines the commit type from keyword heuristics, and optionally
    uses an *llm_service* for high-quality message generation.

    Parameters
    ----------
    diff:
        The ``git diff`` output (or any unified-diff style text).
    llm_service:
        Optional async callable ``llm_service(prompt: str) -> str`` for
        LLM-based message generation.  If not provided, a rule-based
        fallback is used.

    Returns
    -------
    dict
        Dictionary with keys ``type``, ``scope``, ``description``,
        ``body``, ``breaking``, ``confidence``, ``full_message``.
    """
    if not diff or not diff.strip():
        return {
            "type": "chore",
            "scope": "",
            "description": "Empty commit",
            "body": "",
            "breaking": False,
            "confidence": 0.0,
            "full_message": "chore: Empty commit",
        }

    # 1. Analyze diff statistics
    file_stats = _analyze_diff(diff)
    total_additions = sum(s["additions"] for s in file_stats.values())
    total_deletions = sum(s["deletions"] for s in file_stats.values())
    changed_files = list(file_stats.keys())

    # 2. Detect scope from file paths
    scope = _detect_scope(changed_files)

    # 3. Detect commit type
    commit_type, type_confidence = _detect_commit_type(diff, changed_files, file_stats)

    # 4. Detect breaking changes
    is_breaking = _detect_breaking_change(diff)

    # 5. Generate description
    description = ""
    body = ""
    llm_confidence = 0.0

    if llm_service is not None:
        try:
            llm_result = await _generate_with_llm(
                llm_service, diff, commit_type, scope, changed_files,
                total_additions, total_deletions, is_breaking,
            )
            description = llm_result.get("description", "")
            body = llm_result.get("body", "")
            llm_confidence = llm_result.get("confidence", 0.85)
        except Exception as exc:
            logger.warning("LLM commit generation failed, using fallback: %s", exc)

    if not description:
        description, body = _generate_rule_based_description(
            diff, commit_type, scope, changed_files, file_stats,
        )
        llm_confidence = 0.6

    # 6. Clean and validate description
    description = _clean_description(description)

    # 7. Build full conventional commit message
    scope_part = f"({scope})" if scope else ""
    breaking_mark = "!" if is_breaking else ""
    full_message = f"{commit_type}{scope_part}{breaking_mark}: {description}"

    # Add body if present
    if body:
        full_message += f"\n\n{body}"

    # Add BREAKING CHANGE footer
    if is_breaking:
        full_message += "\n\nBREAKING CHANGE: This commit introduces breaking changes."

    # 8. Compute overall confidence
    confidence = _compute_confidence(
        commit_type, scope, type_confidence, bool(llm_service), llm_confidence,
        changed_files, total_additions + total_deletions,
    )

    return {
        "type": commit_type,
        "scope": scope,
        "description": description,
        "body": body,
        "breaking": is_breaking,
        "confidence": round(confidence, 2),
        "full_message": full_message,
    }


def _analyze_diff(diff: str) -> Dict[str, Dict[str, int]]:
    """Parse a unified diff and return per-file statistics.

    Returns
    -------
    dict
        ``{filename: {"additions": int, "deletions": int}}``.
    """
    stats: Dict[str, Dict[str, int]] = {}
    current_file: Optional[str] = None

    for line in diff.split("\n"):
        # Detect file header: diff --git a/<file> b/<file>
        match = re.match(r"^diff --git a/(.+?) b/\1", line)
        if match:
            current_file = match.group(1)
            stats.setdefault(current_file, {"additions": 0, "deletions": 0})
            continue

        # Also handle rename: diff --git a/old b/new
        match = re.match(r"^diff --git a/(.+?) b/(.+?)$", line)
        if match:
            current_file = match.group(2)  # Use new name
            stats.setdefault(current_file, {"additions": 0, "deletions": 0})
            continue

        if current_file is None:
            continue

        if line.startswith("+") and not line.startswith("+++"):
            stats[current_file]["additions"] += 1
        elif line.startswith("-") and not line.startswith("---"):
            stats[current_file]["deletions"] += 1

    return stats


def _detect_scope(changed_files: List[str]) -> str:
    """Detect the commit scope from changed file paths.

    Counts how many files match each scope pattern and returns the
    highest-scoring scope.
    """
    if not changed_files:
        return ""

    scope_scores: Dict[str, int] = {}
    for fpath in changed_files:
        fpath_lower = fpath.lower()
        for scope, patterns in _SCOPE_PATH_PATTERNS.items():
            for pat in patterns:
                if pat.lower() in fpath_lower:
                    scope_scores[scope] = scope_scores.get(scope, 0) + 1
                    break

    if not scope_scores:
        return ""

    best_scope = max(scope_scores, key=lambda s: scope_scores[s])
    # Require at least 2 matches or >30% of files
    if scope_scores[best_scope] >= 2 or scope_scores[best_scope] >= len(changed_files) * 0.3:
        return best_scope
    return ""


def _detect_commit_type(
    diff: str, changed_files: List[str], file_stats: Dict[str, Dict[str, int]],
) -> Tuple[str, float]:
    """Detect the conventional commit type from diff content.

    Uses keyword matching against added lines and file paths.

    Returns
    -------
    tuple
        ``(commit_type, confidence)`` where confidence is in [0, 1].
    """
    type_scores: Dict[str, float] = {}

    # Score from diff content (added lines carry more weight)
    added_lines = [l[1:].strip().lower() for l in diff.split("\n") if l.startswith("+") and not l.startswith("+++")]
    deleted_lines = [l[1:].strip().lower() for l in diff.split("\n") if l.startswith("-") and not l.startswith("---")]

    for commit_type, keywords in _COMMIT_TYPE_KEYWORDS.items():
        score = 0.0
        for line in added_lines:
            for kw in keywords:
                if kw in line:
                    score += 2.0
        for line in deleted_lines:
            for kw in keywords:
                if kw in line:
                    score += 0.5

        # Score from file paths
        for fpath in changed_files:
            fpath_lower = fpath.lower()
            for kw in keywords:
                if kw in fpath_lower:
                    score += 1.0

        type_scores[commit_type] = score

    # Special case: mostly deletions -> refactor or chore
    total_additions = sum(s["additions"] for s in file_stats.values())
    total_deletions = sum(s["deletions"] for s in file_stats.values())
    total = total_additions + total_deletions

    if total > 0:
        deletion_ratio = total_deletions / total
        if deletion_ratio > 0.7 and total_deletions > 20:
            type_scores["refactor"] = type_scores.get("refactor", 0) + 5.0
        if deletion_ratio > 0.9 and total < 10:
            type_scores["chore"] = type_scores.get("chore", 0) + 3.0

    # Test files -> test type boost
    test_file_count = sum(
        1 for f in changed_files
        if any(p in f.lower() for p in ["test", "spec", "__tests__"])
    )
    if test_file_count == len(changed_files) and changed_files:
        type_scores["test"] = type_scores.get("test", 0) + 10.0
    elif test_file_count > 0:
        type_scores["test"] = type_scores.get("test", 0) + 3.0

    # Doc files -> docs type boost
    doc_file_count = sum(
        1 for f in changed_files
        if any(p in f.lower() for p in [".md", "readme", "doc", "changelog"])
    )
    if doc_file_count == len(changed_files) and changed_files:
        type_scores["docs"] = type_scores.get("docs", 0) + 10.0

    if not type_scores or max(type_scores.values()) == 0:
        return "chore", 0.3

    best_type = max(type_scores, key=lambda t: type_scores[t])
    best_score = type_scores[best_type]
    # Compute confidence based on score margin over second-best
    sorted_scores = sorted(type_scores.values(), reverse=True)
    margin = (sorted_scores[0] - sorted_scores[1]) / max(sorted_scores[0], 1) if len(sorted_scores) > 1 else 1.0
    confidence = 0.5 + min(margin * 0.5, 0.5)

    return best_type, confidence


def _detect_breaking_change(diff: str) -> bool:
    """Detect whether the diff contains breaking changes.

    Checks for:
    - ``!`` prefix after type/scope in commit message hints
    - ``BREAKING CHANGE`` / ``BREAKING-CHANGE`` footer markers
    - Breaking-related keywords in removed API surface
    """
    diff_lower = diff.lower()

    # BREAKING CHANGE footer
    if re.search(r"BREAKING[ -]CHANGE", diff, re.IGNORECASE):
        return True

    # Breaking keywords on deleted lines (API removal)
    for line in diff.split("\n"):
        if line.startswith("-") and not line.startswith("---"):
            line_lower = line.lower()
            for kw in _BREAKING_KEYWORDS:
                if kw in line_lower:
                    return True

    # Function signature changes (deleted function params, return types)
    removed_signatures = re.findall(r"^-\s*(?:def|function|func|public|interface)\s+\w+\s*[\(:].*", diff, re.MULTILINE)
    added_signatures = re.findall(r"^\+\s*(?:def|function|func|public|interface)\s+\w+\s*[\(:].*", diff, re.MULTILINE)
    if removed_signatures and added_signatures and len(removed_signatures) == len(added_signatures):
        # Same functions modified -> potential signature change
        for old_sig, new_sig in zip(removed_signatures, added_signatures):
            # Strip diff markers for comparison
            old_clean = re.sub(r"^-\s*", "", old_sig).strip()
            new_clean = re.sub(r"^\+\s*", "", new_sig).strip()
            if old_clean != new_clean:
                # Parameter or return type changed
                return True

    return False


async def _generate_with_llm(
    llm_service: Any,
    diff: str,
    commit_type: str,
    scope: str,
    changed_files: List[str],
    total_additions: int,
    total_deletions: int,
    is_breaking: bool,
) -> Dict[str, Any]:
    """Generate a commit message using an LLM service.

    Parameters
    ----------
    llm_service:
        Async callable ``llm_service(prompt: str) -> str``.
    diff:
        The full diff text (truncated if too long).
    commit_type:
        The heuristically-detected commit type.
    scope:
        The heuristically-detected scope.
    changed_files:
        List of changed file paths.
    total_additions:
        Total lines added.
    total_deletions:
        Total lines deleted.
    is_breaking:
        Whether this is a breaking change.

    Returns
    -------
    dict
        ``{"description": str, "body": str, "confidence": float}``.
    """
    # Truncate diff for the prompt (LLM context window limit)
    max_diff_chars = 4000
    truncated_diff = diff[:max_diff_chars]
    if len(diff) > max_diff_chars:
        truncated_diff += f"\n\n... [{len(diff) - max_diff_chars} more characters truncated]"

    scope_hint = f"({scope})" if scope else ""
    breaking_hint = " with a BREAKING CHANGE footer" if is_breaking else ""

    prompt = f"""You are a commit message generator. Analyze the git diff and produce a conventional commit message.

Rules:
- Type: {commit_type}
- Scope: {scope_hint or "(infer from files)"}
- Subject line: max 72 characters, imperative mood, no period at end
- Body: explain WHAT changed and WHY (optional, use only if the change is complex)
- Format: type(scope): subject\n\nbody{"\n\nBREAKING CHANGE: ..." if is_breaking else ""}

Stats:
- Files changed: {len(changed_files)} ({', '.join(changed_files[:10])}{'...' if len(changed_files) > 10 else ''})
- Additions: {total_additions}, Deletions: {total_deletions}

Diff:
```diff
{truncated_diff}
```

Respond ONLY with the commit message (subject + optional body), no extra text."""

    try:
        if asyncio.iscoroutinefunction(llm_service):
            response = await llm_service(prompt)
        else:
            response = llm_service(prompt)
            if asyncio.isfuture(response) or hasattr(response, "__await__"):
                response = await response
    except Exception as exc:
        logger.warning("LLM call failed: %s", exc)
        raise

    response = response.strip()
    if not response:
        raise ValueError("LLM returned empty response")

    # Parse response: first line is subject, rest is body
    lines = response.split("\n")
    subject = lines[0].strip()

    # Extract description from subject (strip type/scope prefix)
    desc_match = re.match(r"^[\w]+(?:\([^)]*\))?!?\s*:\s*(.+)$", subject)
    if desc_match:
        description = desc_match.group(1).strip()
    else:
        description = subject

    # Body: everything after first blank line following the subject
    body = ""
    if len(lines) > 1:
        # Skip blank lines after subject
        body_lines = lines[1:]
        while body_lines and not body_lines[0].strip():
            body_lines = body_lines[1:]
        body = "\n".join(body_lines).strip()

    # Clean description
    description = description.rstrip(".").strip()
    if not description:
        raise ValueError("LLM returned empty description")

    # Confidence based on response quality
    confidence = 0.85
    if len(description) > 10 and len(description) <= 72:
        confidence = min(confidence + 0.05, 0.98)
    if body:
        confidence = min(confidence + 0.03, 0.98)

    return {
        "description": description,
        "body": body,
        "confidence": confidence,
    }


def _generate_rule_based_description(
    diff: str,
    commit_type: str,
    scope: str,
    changed_files: List[str],
    file_stats: Dict[str, Dict[str, int]],
) -> Tuple[str, str]:
    """Generate a commit description using rule-based heuristics (no LLM).

    Returns
    -------
    tuple
        ``(description, body)``.
    """
    descriptions: List[str] = []
    body_parts: List[str] = []

    # Describe file changes
    file_count = len(changed_files)
    additions = sum(s["additions"] for s in file_stats.values())
    deletions = sum(s["deletions"] for s in file_stats.values())

    # Verb mapping based on commit type
    verbs = {
        "feat": "Add",
        "fix": "Fix",
        "refactor": "Refactor",
        "docs": "Update documentation in",
        "test": "Add tests for",
        "style": "Format",
        "chore": "Update",
        "perf": "Improve performance of",
        "security": "Fix security issue in",
    }
    verb = verbs.get(commit_type, "Update")

    if file_count == 1:
        fname = changed_files[0]
        # Try to extract function/class name from diff
        names = _extract_changed_names(diff)
        if names:
            descriptions.append(f"{verb} {names[0]} in {fname}")
        else:
            descriptions.append(f"{verb} {fname}")
    elif file_count <= 3:
        fnames = ", ".join(changed_files)
        descriptions.append(f"{verb} {fnames}")
    else:
        descriptions.append(f"{verb} {file_count} files")
        body_parts.append(f"Changed files:\n" + "\n".join(f"- {f}" for f in changed_files[:20]))

    # Add stats to body for larger changes
    if additions + deletions > 20:
        body_parts.append(f"({additions} additions, {deletions} deletions)")

    description = descriptions[0] if descriptions else f"{verb} code"
    body = "\n\n".join(body_parts)

    return description, body


def _extract_changed_names(diff: str) -> List[str]:
    """Extract function/class names that appear in added lines of a diff."""
    names: List[str] = []
    seen: Set[str] = set()

    # Python: def name, class Name
    for match in re.finditer(r"^\+\s*(?:def|class)\s+([A-Za-z_][A-Za-z0-9_]*)", diff, re.MULTILINE):
        name = match.group(1)
        if name not in seen and name not in ("if", "else", "for", "while", "with", "try"):
            names.append(name)
            seen.add(name)

    # JS/TS: function name, class Name, const/let/var name =
    for match in re.finditer(
        r"^\+\s*(?:function|class)\s+([A-Za-z_$][A-Za-z0-9_$]*)", diff, re.MULTILINE
    ):
        name = match.group(1)
        if name not in seen:
            names.append(name)
            seen.add(name)

    # Rust: fn name, struct Name, impl X, trait Name
    for match in re.finditer(r"^\+\s*(?:fn|struct|trait)\s+([A-Za-z_][A-Za-z0-9_]*)" , diff, re.MULTILINE):
        name = match.group(1)
        if name not in seen:
            names.append(name)
            seen.add(name)

    # Go: func name, type Name
    for match in re.finditer(r"^\+\s*(?:func|type)\s+\(?[^)]*\)?\s*([A-Z][A-Za-z0-9_]*)", diff, re.MULTILINE):
        name = match.group(1)
        if name not in seen:
            names.append(name)
            seen.add(name)

    return names


def _clean_description(description: str) -> str:
    """Clean and normalize a commit description string.

    - Capitalize first letter
    - Remove trailing period
    - Limit to 72 characters
    - Use imperative mood (warn if not)
    """
    description = description.strip()

    # Remove conventional-commit prefix if accidentally included
    description = re.sub(r"^[\w]+(?:\([^)]*\))?!?\s*:\s*", "", description)

    # Capitalize first letter
    if description:
        description = description[0].upper() + description[1:]

    # Remove trailing period
    description = description.rstrip(".").strip()

    # Limit length
    if len(description) > 72:
        description = description[:69].rsplit(" ", 1)[0] + "..."

    return description


def _compute_confidence(
    commit_type: str,
    scope: str,
    type_confidence: float,
    used_llm: bool,
    llm_confidence: float,
    changed_files: List[str],
    total_changes: int,
) -> float:
    """Compute an overall confidence score for the generated message.

    Factors:
    - Type detection confidence (0.3-0.8)
    - LLM confidence if used (0.0-0.98)
    - Scope detected (bonus)
    - Change magnitude (smaller = more confident)
    """
    if used_llm:
        base = llm_confidence
    else:
        base = type_confidence * 0.7 + 0.3

    # Scope bonus
    if scope:
        base += 0.03

    # Small change bonus
    if len(changed_files) <= 3 and total_changes < 50:
        base += 0.02

    # Large change penalty (harder to summarize)
    if total_changes > 500:
        base -= 0.05
    if len(changed_files) > 20:
        base -= 0.03

    return max(0.3, min(0.98, base))
