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
import subprocess
from datetime import datetime
from typing import Dict, List, Optional, Any

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
