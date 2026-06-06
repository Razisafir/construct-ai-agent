"""SQLMap Tool — SQL injection detection and database enumeration.

Provides async SQLMap scanning with structured result parsing, target
validation, rate limiting, and audit logging.

Requirements:
    - sqlmap binary installed and accessible on PATH
    - Python 3.11+ (or use ``from __future__ import annotations``)

Usage::

    from tools.sqlmap_tool import SQLMapTool, SQLMapScanResult

    tool = SQLMapTool()
    result = await tool.scan(target="http://example.com/page.php?id=1")
    print(result.injections)
"""

from __future__ import annotations

import asyncio
import ipaddress
import json
import logging
import os
import re
import shutil
import sqlite3
import time
import uuid
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional

from tools.nmap_tool import AuditLogger

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MAX_SCAN_TIMEOUT = 600       # 10 minutes max per scan
DEFAULT_SCAN_TIMEOUT = 300   # 5 minutes default
MAX_CONCURRENT_SCANS = 1
MAX_SCANS_PER_HOUR = 5
COOLDOWN_BETWEEN_SCANS = 10  # seconds

# Allowed SQLMap technique characters
ALLOWED_TECHNIQUES = {"B", "E", "U", "S", "T", "Q"}

# Dangerous flags that are NEVER allowed
BLOCKED_FLAGS = {
    "--os-shell", "--os-cmd", "--os-pwn", "--os-smbrelay", "--os-bof",
    "--priv-esc", "--dump-all", "--passwords", "--file-write", "--file-read",
}

# Private / loopback ranges that are blocked by default
BLOCKED_LOOPBACK = {"127.0.0.1", "::1", "localhost", "0.0.0.0"}

PRIVATE_RANGES = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
]

# URL validation regex — requires scheme, host, and at least one query parameter
TARGET_URL_REGEX = re.compile(
    r"^https?://"
    r"[A-Za-z0-9](?:[A-Za-z0-9\-]{0,61}[A-Za-z0-9])?"
    r"(?:\.[A-Za-z0-9](?:[A-Za-z0-9\-]{0,61}[A-Za-z0-9])?)*"
    r"(?::\d{1,5})?"
    r"/[^\s]*\?.+=.+"
)

# Injection type mapping from technique letter to full name
TECHNIQUE_NAMES: Dict[str, str] = {
    "B": "Boolean-based blind",
    "E": "Error-based",
    "U": "Union-based",
    "S": "Stacked queries",
    "T": "Time-based blind",
    "Q": "Inline queries",
}

# Regex patterns for parsing sqlmap text output
PARAM_PATTERN = re.compile(r"Parameter:\s*(.+?)(?:\s*\([^)]+\))?\s*$", re.MULTILINE)
TYPE_PATTERN = re.compile(r"Type:\s*(.+?)$", re.MULTILINE)
TITLE_PATTERN = re.compile(r"Title:\s*(.+?)$", re.MULTILINE)
PAYLOAD_PATTERN = re.compile(r"Payload:\s*(.+?)$", re.MULTILINE)
DBMS_PATTERN = re.compile(r"back-end DBMS:\s*(.+?)$", re.MULTILINE)
DBMS_VERSION_PATTERN = re.compile(r"back-end DBMS version:\s*(.+?)$", re.MULTILINE)
CURRENT_DB_PATTERN = re.compile(r"current database:\s*['\"]?(.+?)['\"]?\s*$", re.MULTILINE)
HOSTNAME_PATTERN = re.compile(r"hostname:\s*['\"]?(.+?)['\"]?\s*$", re.MULTILINE)
AVAILABLE_DB_PATTERN = re.compile(r"available databases \[\d+\]:\s*\[(.+?)\]", re.MULTILINE | re.DOTALL)
USER_PATTERN = re.compile(r"database management system users \[\d+\]:\s*\[(.+?)\]", re.MULTILINE | re.DOTALL)


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------

@dataclass
class SQLMapInjection:
    """A single SQL injection finding from sqlmap."""

    parameter: str
    injection_type: str
    title: str
    payload: str
    dbms: str = ""
    risk: int = 1
    severity: str = "medium"

    def to_dict(self) -> Dict[str, Any]:
        """Return a plain dict representation."""
        return asdict(self)


@dataclass
class SQLMapDatabaseInfo:
    """Database metadata discovered during an sqlmap scan."""

    dbms: str = ""
    dbms_version: str = ""
    current_db: str = ""
    hostname: str = ""
    users: List[str] = field(default_factory=list)
    databases: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Return a plain dict representation."""
        return asdict(self)


@dataclass
class SQLMapScanResult:
    """Complete result of an SQLMap scan."""

    scan_id: str
    target: str
    status: str = "running"
    injections: List[SQLMapInjection] = field(default_factory=list)
    db_info: Optional[SQLMapDatabaseInfo] = None
    start_time: str = ""
    end_time: Optional[str] = None
    elapsed: float = 0.0
    error: Optional[str] = None
    raw_output: Optional[str] = None
    command: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Return a plain dict representation with nested serialisation."""
        return {
            "scan_id": self.scan_id,
            "target": self.target,
            "status": self.status,
            "injections": [i.to_dict() for i in self.injections],
            "db_info": self.db_info.to_dict() if self.db_info else None,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "elapsed": self.elapsed,
            "error": self.error,
            "raw_output": self.raw_output,
            "command": self.command,
        }


# ---------------------------------------------------------------------------
# Security Validation
# ---------------------------------------------------------------------------

class TargetValidationError(Exception):
    """Raised when a scan target fails security validation."""
    pass


class RateLimitError(Exception):
    """Raised when scan rate limits are exceeded."""
    pass


def validate_sqlmap_target(target: str, allow_localhost: bool = False) -> str:
    """Validate an SQLMap target URL for security compliance.

    The target **must** be a valid URL with query parameters so that sqlmap
    has injection points to test (e.g. ``http://example.com/page.php?id=1``).

    Parameters
    ----------
    target:
        Full URL including query string.
    allow_localhost:
        If True, allow localhost / private IP targets.

    Returns
    -------
    str
        The validated target URL.

    Raises
    ------
    TargetValidationError
        If the target is blocked or malformed.
    """
    target = target.strip()

    if not target:
        raise TargetValidationError("Empty target specified")

    # Must look like a URL with query parameters
    if not TARGET_URL_REGEX.match(target):
        raise TargetValidationError(
            f"Invalid target URL: {target}. "
            "Target must be a full HTTP(S) URL with query parameters "
            "(e.g. http://example.com/page.php?id=1)."
        )

    # Extract hostname from URL for IP checks
    host_match = re.match(r"^https?://([^/:]+)", target)
    if not host_match:
        raise TargetValidationError(f"Cannot extract hostname from target: {target}")

    hostname = host_match.group(1)

    # Block localhost / loopback hostnames
    if not allow_localhost:
        if hostname.lower() in BLOCKED_LOOPBACK:
            raise TargetValidationError(
                f"Scanning {hostname} is blocked for safety. "
                "Set allow_localhost=True to scan localhost targets."
            )

    # Try to resolve hostname as an IP address and check private ranges
    try:
        addr = ipaddress.ip_address(hostname)
        if not allow_localhost and addr.is_loopback:
            raise TargetValidationError(
                f"Scanning loopback address {hostname} is blocked. "
                "Set allow_localhost=True to scan localhost targets."
            )
        if not allow_localhost and addr.is_private:
            raise TargetValidationError(
                f"Scanning private address {hostname} is blocked for safety. "
                "Set allow_localhost=True to scan private network targets."
            )
    except ValueError:
        # hostname is not a raw IP — DNS resolution happens at scan time
        pass

    return target


# ---------------------------------------------------------------------------
# Scan Rate Limiter
# ---------------------------------------------------------------------------

class ScanRateLimiter:
    """Rate limiter for sqlmap scans.

    Enforces:
    - Max 1 concurrent scan
    - Max 5 scans per hour
    - 10 second cooldown between scans
    """

    def __init__(self) -> None:
        self._active_scans = 0
        self._scan_timestamps: List[float] = []
        self._last_scan_end = 0.0

    def acquire(self) -> None:
        """Acquire a scan slot.  Raises ``RateLimitError`` if limits exceeded."""
        now = time.time()

        # Check concurrent limit
        if self._active_scans >= MAX_CONCURRENT_SCANS:
            raise RateLimitError(
                f"Maximum {MAX_CONCURRENT_SCANS} concurrent sqlmap scan(s) already running. "
                "Please wait for the current scan to finish."
            )

        # Check hourly limit
        window_start = now - 3600
        self._scan_timestamps = [
            ts for ts in self._scan_timestamps if ts > window_start
        ]
        if len(self._scan_timestamps) >= MAX_SCANS_PER_HOUR:
            raise RateLimitError(
                f"Maximum {MAX_SCANS_PER_HOUR} sqlmap scans per hour exceeded. "
                "Please wait before starting another scan."
            )

        # Check cooldown
        if self._last_scan_end > 0 and (now - self._last_scan_end) < COOLDOWN_BETWEEN_SCANS:
            remaining = COOLDOWN_BETWEEN_SCANS - (now - self._last_scan_end)
            raise RateLimitError(
                f"Cooldown period active. Please wait {remaining:.1f}s before "
                "starting another sqlmap scan."
            )

        self._active_scans += 1
        self._scan_timestamps.append(now)

    def release(self) -> None:
        """Release a scan slot."""
        self._active_scans = max(0, self._active_scans - 1)
        self._last_scan_end = time.time()


# ---------------------------------------------------------------------------
# SQLMap Tool
# ---------------------------------------------------------------------------

class SQLMapTool:
    """Async SQLMap scanner with security validation, rate limiting, and audit logging.

    Usage::

        tool = SQLMapTool()
        result = await tool.scan(target="http://example.com/page.php?id=1")
    """

    def __init__(self) -> None:
        self._rate_limiter = ScanRateLimiter()
        self._audit_logger = AuditLogger()
        self._available = self._check_sqlmap()

        if self._available:
            logger.info("SQLMap found on PATH")
        else:
            logger.warning(
                "SQLMap not found on PATH — install with: "
                "sudo apt install sqlmap (Ubuntu/Debian) or "
                "pip install sqlmap / clone from https://github.com/sqlmapproject/sqlmap"
            )

    def is_available(self) -> bool:
        """Check if sqlmap is installed and accessible."""
        return self._available

    def _check_sqlmap(self) -> bool:
        """Check if sqlmap binary is available on the system PATH."""
        return shutil.which("sqlmap") is not None

    async def scan(
        self,
        target: str,
        level: int = 1,
        risk: int = 1,
        techniques: str = "BEUSTQ",
        enumerate_db: bool = False,
        enumerate_tables: bool = False,
        workspace_id: Optional[str] = None,
        allow_localhost: bool = False,
        timeout: int = DEFAULT_SCAN_TIMEOUT,
    ) -> SQLMapScanResult:
        """Run an SQLMap scan with full security validation.

        Parameters
        ----------
        target:
            Full URL with query parameters to test for SQL injection.
        level:
            Level of tests to perform (1-5).  Higher levels deliver more
            payload iterations but take longer.
        risk:
            Risk level of tests (1-3).  Higher risk may cause database
            modifications.
        techniques:
            SQL injection techniques to test.  Must consist only of characters
            from ``ALLOWED_TECHNIQUES`` (B, E, U, S, T, Q).
        enumerate_db:
            If True, add ``--dbs`` to enumerate available databases.
        enumerate_tables:
            If True, add ``--tables`` to enumerate tables.
        workspace_id:
            Optional workspace ID for result association.
        allow_localhost:
            Allow scanning localhost / private IP targets.
        timeout:
            Maximum scan duration in seconds (max 600).

        Returns
        -------
        SQLMapScanResult
            Structured scan results including injection findings and DB info.
        """
        scan_id = str(uuid.uuid4())[:8]
        start_time = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

        # Check availability
        if not self._available:
            result = SQLMapScanResult(
                scan_id=scan_id,
                target=target,
                command="",
                start_time=start_time,
                status="failed",
                error="SQLMap is not installed. Install with: sudo apt install sqlmap",
            )
            self._audit_logger.log(
                tool="sqlmap", action="scan", target=target,
                status="failed", error="SQLMap not installed", scan_id=scan_id,
            )
            return result

        # Validate timeout
        timeout = min(timeout, MAX_SCAN_TIMEOUT)

        # Validate target URL
        try:
            validated_target = validate_sqlmap_target(
                target, allow_localhost=allow_localhost,
            )
        except TargetValidationError as exc:
            result = SQLMapScanResult(
                scan_id=scan_id,
                target=target,
                command="",
                start_time=start_time,
                status="failed",
                error=str(exc),
            )
            self._audit_logger.log(
                tool="sqlmap", action="scan", target=target,
                status="blocked", error=str(exc), scan_id=scan_id,
            )
            return result

        # Validate level (1-5)
        if not 1 <= level <= 5:
            result = SQLMapScanResult(
                scan_id=scan_id,
                target=target,
                command="",
                start_time=start_time,
                status="failed",
                error=f"Invalid level {level}. Must be between 1 and 5.",
            )
            return result

        # Validate risk (1-3)
        if not 1 <= risk <= 3:
            result = SQLMapScanResult(
                scan_id=scan_id,
                target=target,
                command="",
                start_time=start_time,
                status="failed",
                error=f"Invalid risk {risk}. Must be between 1 and 3.",
            )
            return result

        # Validate techniques
        techniques = techniques.upper().strip()
        for ch in techniques:
            if ch not in ALLOWED_TECHNIQUES:
                result = SQLMapScanResult(
                    scan_id=scan_id,
                    target=target,
                    command="",
                    start_time=start_time,
                    status="failed",
                    error=f"Invalid technique '{ch}'. Allowed: {', '.join(sorted(ALLOWED_TECHNIQUES))}",
                )
                return result

        # Rate limiting
        try:
            self._rate_limiter.acquire()
        except RateLimitError as exc:
            result = SQLMapScanResult(
                scan_id=scan_id,
                target=target,
                command="",
                start_time=start_time,
                status="failed",
                error=str(exc),
            )
            self._audit_logger.log(
                tool="sqlmap", action="scan", target=target,
                status="rate_limited", error=str(exc), scan_id=scan_id,
            )
            return result

        # Build command
        output_dir = f"/tmp/sqlmap-{scan_id}"
        cmd = [
            "sqlmap",
            "-u", validated_target,
            "--batch",
            "--random-agent",
            f"--output-dir={output_dir}",
            f"--level={level}",
            f"--risk={risk}",
            f"--technique={techniques}",
        ]

        if enumerate_db:
            cmd.append("--dbs")

        if enumerate_tables:
            cmd.append("--tables")

        command_str = " ".join(cmd)

        # Log scan start
        self._audit_logger.log(
            tool="sqlmap", action="scan", target=validated_target,
            status="started", scan_id=scan_id,
        )
        logger.info("Starting sqlmap scan [%s]: %s", scan_id, command_str)

        result = SQLMapScanResult(
            scan_id=scan_id,
            target=validated_target,
            command=command_str,
            start_time=start_time,
            status="running",
        )

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=timeout,
                )
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                result.status = "failed"
                result.error = f"Scan timed out after {timeout}s"
                result.end_time = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                self._audit_logger.log(
                    tool="sqlmap", action="scan", target=validated_target,
                    status="timeout", error=result.error, scan_id=scan_id,
                )
                return result

            output_text = stdout.decode("utf-8", errors="replace")
            stderr_text = stderr.decode("utf-8", errors="replace")

            if process.returncode not in (0, None):
                # sqlmap sometimes returns non-zero even with useful output
                if not output_text.strip():
                    result.status = "failed"
                    result.error = (
                        f"SQLMap exited with code {process.returncode}: "
                        f"{stderr_text[:2000]}"
                    )
                    result.end_time = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                    self._audit_logger.log(
                        tool="sqlmap", action="scan", target=validated_target,
                        status="failed", error=result.error, scan_id=scan_id,
                    )
                    return result

            # Store raw output (truncated for safety)
            result.raw_output = output_text[:50000]

            # Parse structured results
            injections = self._parse_output(output_text)
            result.injections = injections

            db_info = self._parse_db_info(output_text)
            result.db_info = db_info

            result.status = "completed"
            result.end_time = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            result.elapsed = time.time() - time.mktime(time.strptime(start_time, "%Y-%m-%dT%H:%M:%SZ"))

            # Audit log completion
            summary = f"{len(injections)} injection(s) found"
            if db_info and db_info.dbms:
                summary += f", DBMS: {db_info.dbms}"
            self._audit_logger.log(
                tool="sqlmap", action="scan", target=validated_target,
                status="completed", result_summary=summary, scan_id=scan_id,
            )
            logger.info("SQLMap scan [%s] completed: %s", scan_id, summary)

        except Exception as exc:
            result.status = "failed"
            result.error = f"Scan failed: {exc}"
            result.end_time = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            self._audit_logger.log(
                tool="sqlmap", action="scan", target=validated_target,
                status="failed", error=str(exc), scan_id=scan_id,
            )
            logger.exception("SQLMap scan [%s] failed", scan_id)
        finally:
            self._rate_limiter.release()

        return result

    def _parse_output(self, output: str) -> List[SQLMapInjection]:
        """Parse sqlmap text output for injection findings.

        Looks for structured patterns emitted by sqlmap such as::

            Parameter: id
                Type: Boolean-based blind
                Title: AND boolean-based blind ...
                Payload: id=1 AND 1234=1234

        Parameters
        ----------
        output:
            Raw stdout from sqlmap.

        Returns
        -------
        list[SQLMapInjection]
            Parsed injection results.
        """
        injections: List[SQLMapInjection] = []

        # Split output into per-parameter blocks
        param_matches = list(PARAM_PATTERN.finditer(output))
        if not param_matches:
            return injections

        for idx, param_match in enumerate(param_matches):
            param_name = param_match.group(1).strip()

            # Determine the block of text belonging to this parameter
            block_start = param_match.end()
            if idx + 1 < len(param_matches):
                block_end = param_matches[idx + 1].start()
            else:
                block_end = len(output)
            block = output[block_start:block_end]

            # Extract injection types within this block
            type_matches = list(TYPE_PATTERN.finditer(block))
            title_matches = list(TITLE_PATTERN.finditer(block))
            payload_matches = list(PAYLOAD_PATTERN.finditer(block))

            max_items = max(len(type_matches), len(title_matches), len(payload_matches), 1)

            for i in range(max_items):
                inj_type = type_matches[i].group(1).strip() if i < len(type_matches) else ""
                title = title_matches[i].group(1).strip() if i < len(title_matches) else ""
                payload = payload_matches[i].group(1).strip() if i < len(payload_matches) else ""

                # Determine risk and severity heuristically
                risk = 1
                severity = "low"
                if any(kw in inj_type.lower() for kw in ("union", "stacked", "inline")):
                    risk = 3
                    severity = "high"
                elif any(kw in inj_type.lower() for kw in ("error", "time")):
                    risk = 2
                    severity = "medium"

                injections.append(SQLMapInjection(
                    parameter=param_name,
                    injection_type=inj_type,
                    title=title,
                    payload=payload,
                    risk=risk,
                    severity=severity,
                ))

        return injections

    def _parse_db_info(self, output: str) -> Optional[SQLMapDatabaseInfo]:
        """Extract database metadata from sqlmap output.

        Parses DBMS type, version, current database, hostname, and
        enumerated databases / users.

        Parameters
        ----------
        output:
            Raw stdout from sqlmap.

        Returns
        -------
        SQLMapDatabaseInfo or None
            Parsed database information, or None if nothing was found.
        """
        dbms_match = DBMS_PATTERN.search(output)
        if not dbms_match:
            return None

        dbms = dbms_match.group(1).strip()

        version_match = DBMS_VERSION_PATTERN.search(output)
        dbms_version = version_match.group(1).strip() if version_match else ""

        current_db_match = CURRENT_DB_PATTERN.search(output)
        current_db = current_db_match.group(1).strip() if current_db_match else ""

        hostname_match = HOSTNAME_PATTERN.search(output)
        hostname = hostname_match.group(1).strip() if hostname_match else ""

        # Parse available databases list
        databases: List[str] = []
        avail_db_match = AVAILABLE_DB_PATTERN.search(output)
        if avail_db_match:
            raw = avail_db_match.group(1)
            databases = [
                db.strip().strip("'\"")
                for db in raw.split(",")
                if db.strip()
            ]

        # Parse users list
        users: List[str] = []
        user_match = USER_PATTERN.search(output)
        if user_match:
            raw = user_match.group(1)
            users = [
                u.strip().strip("'\"")
                for u in raw.split(",")
                if u.strip()
            ]

        return SQLMapDatabaseInfo(
            dbms=dbms,
            dbms_version=dbms_version,
            current_db=current_db,
            hostname=hostname,
            users=users,
            databases=databases,
        )

    def get_audit_log(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent audit log entries for sqlmap scans."""
        return self._audit_logger.get_recent(limit=limit, tool="sqlmap")
