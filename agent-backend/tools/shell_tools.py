"""
Shell command execution with safety validation.

Tools: execute_command, run_test, install_dependency

All shell commands are validated against a blocklist of dangerous operations
before execution.  Output, timing, and exit codes are captured and returned
in a structured format for LLM consumption.
"""

import os
import re
import time
import shlex
import logging
import subprocess
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Safety configuration
# ---------------------------------------------------------------------------

# Commands that are always blocked (exact match or substring)
BLOCKED_COMMANDS: List[str] = [
    "rm -rf /",
    "rm -rf /*",
    "rm -rf ~",
    "rm -rf ~/",
    "mkfs",
    "dd if=/dev/zero",
    "dd if=/dev/random",
    "dd if=/dev/urandom",
    "chmod -R 777 /",
    "chmod -R 777 /*",
    "> /dev/sda",
    "> /dev/hda",
    "curl *| sh",
    "curl *| bash",
    "wget *| sh",
    "wget *| bash",
    "sudo ",
    "su -",
    "su root",
    "passwd",
    "deluser",
    "delgroup",
    "userdel",
    "groupdel",
    ":(){ :|:& };:",  # fork bomb
    "eval $(curl",
    "eval $(wget",
    "bash <(curl",
    "bash <(wget",
    # Additional dangerous commands
    "reboot",
    "shutdown",
    "poweroff",
    "halt",
    "init 0",
    "init 6",
    "killall",
    "pkill",
    "iptables",
    "nft",
    "mount",
    "umount",
    "losetup",
    "pvcreate",
    "pvremove",
    "vgremove",
    "lvremove",
    "fdisk",
    "parted",
    "sfdisk",
    "chroot",
    "setfacl",
    "sysctl -w",
    "echo * > /proc",
    "echo * > /sys",
]

# Command prefixes that are blocked (exact word match)
BLOCKED_PREFIXES: List[str] = [
    "sudo",
    "su",
    "mkfs",
    "fdisk",
    "dd",
    "format",
    "reboot",
    "shutdown",
    "poweroff",
    "halt",
    "killall",
    "pkill",
    "iptables",
    "nft",
    "mount",
    "umount",
    "losetup",
    "chroot",
]

# Default timeout in seconds
DEFAULT_TIMEOUT: int = 60

# Maximum timeout allowed
MAX_TIMEOUT: int = 300


# ---------------------------------------------------------------------------
# Safety helpers
# ---------------------------------------------------------------------------


def _is_command_blocked(command: str) -> Optional[str]:
    """
    Check if a command matches any blocked pattern.

    Returns
    -------
    Optional[str]
        The matched block reason if blocked, *None* if safe.
    """
    stripped = command.strip()
    lowered = stripped.lower()

    # Check exact/substring blocked commands
    for blocked in BLOCKED_COMMANDS:
        # Use re.escape for literal matching, then restore wildcards
        pattern = re.escape(blocked.lower()).replace(r"\*", ".*")
        if re.search(pattern, lowered):
            return f"Command blocked: matches '{blocked}'"

    # Check blocked prefixes (word boundary match)
    try:
        tokens = shlex.split(stripped)
        if tokens:
            first_token = tokens[0].lower()
            for prefix in BLOCKED_PREFIXES:
                if first_token == prefix:
                    return f"Command blocked: '{prefix}' is not allowed"
    except ValueError:
        # If shlex fails (unmatched quote), do a simple prefix check
        for prefix in BLOCKED_PREFIXES:
            if lowered.startswith(prefix.lower() + " "):
                return f"Command blocked: '{prefix}' is not allowed"

    # Block pipe-to-shell patterns
    pipe_shell_patterns = [
        r"\|\s*sh\s*$",
        r"\|\s*bash\s*$",
        r"\|\s*sh\s+",
        r"\|\s*bash\s+",
    ]
    for pat in pipe_shell_patterns:
        if re.search(pat, lowered):
            return "Command blocked: piping to shell is not allowed"

    return None


def _validate_working_dir(cwd: str) -> str:
    """
    Validate and return an absolute working directory path.

    Restricts execution to the project directory and its subdirectories
    to prevent accidental damage to the system.
    """
    expanded = os.path.expanduser(cwd)
    abs_cwd = os.path.abspath(expanded)

    # Block system directories and their subdirectories
    blocked_roots = ["/bin", "/sbin", "/usr", "/lib", "/lib64", "/etc",
                     "/var", "/proc", "/sys", "/dev", "/boot", "/root"]
    for blocked in blocked_roots:
        if abs_cwd == blocked or abs_cwd.startswith(blocked + os.sep):
            logger.warning(
                "Working directory '%s' is under blocked system path '%s'; using '.'",
                abs_cwd, blocked
            )
            return os.path.abspath(".")

    # Block raw root and paths with traversal
    if abs_cwd == "/":
        logger.warning("Working directory '/' is blocked; using '.'")
        return os.path.abspath(".")

    if ".." in os.path.normpath(expanded).split(os.sep):
        # Extra check: prevent traversal outside project
        resolved = os.path.realpath(expanded)
        base_dir = os.path.abspath(os.getcwd())
        try:
            common = os.path.commonpath([base_dir, resolved])
            if common != base_dir:
                logger.warning(
                    "Working directory '%s' resolves outside project; using '.'",
                    abs_cwd
                )
                return os.path.abspath(".")
        except ValueError:
            return os.path.abspath(".")

    return abs_cwd


def _sanitize_command(command: str) -> str:
    """
    Sanitize a command string before execution.

    - Strips control characters
    - Blocks null bytes
    - Limits command length

    Parameters
    ----------
    command:
        Raw command string.

    Returns
    -------
    str
        Sanitized command string.

    Raises
    ------
    ValueError
        If the command contains dangerous patterns.
    """
    # Block null bytes
    if "\x00" in command:
        raise ValueError("Command contains null bytes")

    # Strip control characters (except common whitespace)
    sanitized = "".join(ch for ch in command if ch == "\n" or ch == "\t" or (ch.isprintable() or ch in " \r\n\t"))

    # Limit command length (prevent DoS via huge commands)
    MAX_COMMAND_LENGTH = 10_000
    if len(sanitized) > MAX_COMMAND_LENGTH:
        raise ValueError(f"Command exceeds maximum length of {MAX_COMMAND_LENGTH} characters")

    # Block backtick command substitution (dangerous)
    if "`" in sanitized:
        raise ValueError("Backtick command substitution is not allowed")

    return sanitized.strip()


# ---------------------------------------------------------------------------
# Public tool functions
# ---------------------------------------------------------------------------


def execute_command(
    command: str, cwd: str = ".", timeout: int = DEFAULT_TIMEOUT
) -> Dict[str, Any]:
    """
    Execute a shell command and return structured output.

    Parameters
    ----------
    command:
        The shell command to execute.
    cwd:
        Working directory for the command (default current directory).
    timeout:
        Maximum execution time in seconds (default 60, max 300).

    Returns
    -------
    dict
        Structured result with ``success``, ``stdout``, ``stderr``,
        ``exit_code``, ``duration_ms``, ``command``.
    """
    logger.info("execute_command: %s (cwd=%s, timeout=%d)", command, cwd, timeout)

    # Safety checks
    block_reason = _is_command_blocked(command)
    if block_reason:
        logger.warning("Blocked command: %s — %s", command, block_reason)
        return {
            "success": False,
            "error": block_reason,
            "stdout": "",
            "stderr": "",
            "exit_code": -1,
            "duration_ms": 0,
            "command": command,
        }

    # Sanitize command
    try:
        command = _sanitize_command(command)
    except ValueError as exc:
        logger.warning("Sanitization failed for command: %s — %s", command, exc)
        return {
            "success": False,
            "error": f"Command sanitization failed: {exc}",
            "stdout": "",
            "stderr": "",
            "exit_code": -1,
            "duration_ms": 0,
            "command": command,
        }

    # Validate timeout (reject rather than silently clamp)
    if timeout > MAX_TIMEOUT:
        logger.warning("Timeout %ds exceeds max %ds; using max", timeout, MAX_TIMEOUT)
        timeout = MAX_TIMEOUT
    if timeout <= 0:
        return {
            "success": False,
            "error": f"Invalid timeout: {timeout}",
            "stdout": "",
            "stderr": "",
            "exit_code": -1,
            "duration_ms": 0,
            "command": command,
        }

    # Validate working directory
    safe_cwd = _validate_working_dir(cwd)

    start_time = time.time()
    try:
        # Run the command synchronously with subprocess (works in both sync and async contexts)
        proc_result = subprocess.run(
            command,
            cwd=safe_cwd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        duration_ms = int((time.time() - start_time) * 1000)

        stdout = proc_result.stdout
        stderr = proc_result.stderr

        # Truncate very long outputs
        MAX_OUTPUT = 100_000
        if len(stdout) > MAX_OUTPUT:
            stdout = stdout[:MAX_OUTPUT] + f"\n... [truncated, total {len(stdout)} chars]"
        if len(stderr) > MAX_OUTPUT:
            stderr = stderr[:MAX_OUTPUT] + f"\n... [truncated, total {len(stderr)} chars]"

        result = {
            "success": proc_result.returncode == 0,
            "stdout": stdout,
            "stderr": stderr,
            "exit_code": proc_result.returncode,
            "duration_ms": duration_ms,
            "command": command,
            "cwd": safe_cwd,
        }

        logger.info(
            "Command completed in %dms (exit_code=%d): %s",
            duration_ms,
            result.get("exit_code", -1),
            command[:80],
        )
        return result

    except subprocess.TimeoutExpired:
        duration_ms = int((time.time() - start_time) * 1000)
        logger.warning("Command timed out after %ds: %s", timeout, command)
        return {
            "success": False,
            "error": f"Command timed out after {timeout} seconds",
            "stdout": "",
            "stderr": "",
            "exit_code": -1,
            "duration_ms": duration_ms,
            "command": command,
        }
    except Exception as exc:
        duration_ms = int((time.time() - start_time) * 1000)
        logger.exception("Error executing command: %s", command)
        return {
            "success": False,
            "error": f"Execution error: {exc}",
            "stdout": "",
            "stderr": "",
            "exit_code": -1,
            "duration_ms": duration_ms,
            "command": command,
        }


# _run_subprocess removed — execute_command now uses subprocess.run()
# directly, which works correctly in both sync and async contexts.


def run_test(test_command: str = "npm test", cwd: str = ".") -> Dict[str, Any]:
    """
    Run the project's test suite.

    Parameters
    ----------
    test_command:
        The test command to run (default ``npm test``).
    cwd:
        Working directory (default current directory).

    Returns
    -------
    dict
        Structured test result with ``success``, ``stdout``, ``stderr``,
        ``exit_code``, ``duration_ms``.
    """
    logger.info("run_test: %s (cwd=%s)", test_command, cwd)

    # Detect project type if default command is used
    if test_command == "npm test":
        abs_cwd = os.path.abspath(os.path.expanduser(cwd))
        if os.path.exists(os.path.join(abs_cwd, "package.json")):
            test_command = "npm test"
        elif os.path.exists(os.path.join(abs_cwd, "requirements.txt")):
            test_command = "python -m pytest"
        elif os.path.exists(os.path.join(abs_cwd, "Cargo.toml")):
            test_command = "cargo test"
        elif os.path.exists(os.path.join(abs_cwd, "go.mod")):
            test_command = "go test ./..."
        elif os.path.exists(os.path.join(abs_cwd, "pom.xml")):
            test_command = "mvn test"
        elif os.path.exists(os.path.join(abs_cwd, "build.gradle")):
            test_command = "gradle test"

    return execute_command(test_command, cwd=cwd, timeout=120)


def install_dependency(package: str, cwd: str = ".") -> Dict[str, Any]:
    """
    Install a package dependency.

    Auto-detects the package manager from project files and installs
    the given package.

    Parameters
    ----------
    package:
        Package name to install (e.g. ``lodash``, ``requests``, ``serde``).
    cwd:
        Working directory (default current directory).

    Returns
    -------
    dict
        Structured result from the install command.
    """
    logger.info("install_dependency: %s (cwd=%s)", package, cwd)

    abs_cwd = os.path.abspath(os.path.expanduser(cwd))

    # Validate package name (prevent injection)
    safe_package = shlex.quote(package)
    # Also validate the package name looks reasonable
    if not re.match(r"^[A-Za-z0-9@_\-/.:^~]+$", package):
        return {
            "success": False,
            "error": f"Invalid package name: '{package}'. Package names may only contain letters, numbers, and common separators.",
            "stdout": "",
            "stderr": "",
            "exit_code": -1,
            "command": "",
            "duration_ms": 0,
        }

    # Detect package manager
    if os.path.exists(os.path.join(abs_cwd, "package.json")):
        # Detect npm/yarn/pnpm
        if os.path.exists(os.path.join(abs_cwd, "pnpm-lock.yaml")):
            cmd = f"pnpm add {safe_package}"
        elif os.path.exists(os.path.join(abs_cwd, "yarn.lock")):
            cmd = f"yarn add {safe_package}"
        else:
            cmd = f"npm install {safe_package}"
    elif os.path.exists(os.path.join(abs_cwd, "requirements.txt")) or os.path.exists(
        os.path.join(abs_cwd, "pyproject.toml")
    ):
        cmd = f"pip install {safe_package}"
    elif os.path.exists(os.path.join(abs_cwd, "Cargo.toml")):
        cmd = f"cargo add {safe_package}"
    elif os.path.exists(os.path.join(abs_cwd, "go.mod")):
        cmd = f"go get {safe_package}"
    elif os.path.exists(os.path.join(abs_cwd, "Gemfile")):
        cmd = f"bundle add {safe_package}"
    else:
        # Default to npm
        cmd = f"npm install {safe_package}"

    return execute_command(cmd, cwd=cwd, timeout=120)
