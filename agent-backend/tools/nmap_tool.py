"""Nmap Tool — network port scanning and host discovery.

Provides async Nmap scanning with XML output parsing, structured results,
and security validation (target blocklist, rate limiting, audit logging).

Requirements:
    - nmap binary installed and accessible on PATH
    - Python 3.11+ for str | None syntax (or use Optional[str])

Usage::

    from tools.nmap_tool import NmapTool, NmapScanRequest, NmapScanResult

    tool = NmapTool()
    result = await tool.scan(target="192.168.1.0/24", ports="80,443")
    print(result.hosts)
"""

from __future__ import annotations

import asyncio
import hashlib
import ipaddress
import json
import logging
import os
import re
import sqlite3
import time
import uuid
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MAX_SCAN_TIMEOUT = 300  # 5 minutes max per scan
DEFAULT_SCAN_TIMEOUT = 120  # 2 minutes default
MAX_CONCURRENT_SCANS = 1
MAX_SCANS_PER_HOUR = 10
COOLDOWN_BETWEEN_SCANS = 5  # seconds

# Blocked targets — localhost/loopback unless explicitly allowed
BLOCKED_LOOPBACK = {"127.0.0.1", "::1", "localhost", "0.0.0.0"}

# Private ranges that require user confirmation
PRIVATE_RANGES = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("169.254.0.0/16"),  # link-local
    ipaddress.ip_network("fc00::/7"),  # IPv6 unique local
    ipaddress.ip_network("fe80::/10"),  # IPv6 link-local
]

# Multicast and broadcast
BLOCKED_MULTICAST = [
    ipaddress.ip_network("224.0.0.0/4"),   # multicast
    ipaddress.ip_network("239.0.0.0/8"),   # administratively scoped
    ipaddress.ip_network("ff00::/8"),      # IPv6 multicast
]

# Allowed nmap options whitelist
ALLOWED_NMAP_OPTIONS = {
    # Scan techniques
    "-sS", "-sT", "-sA", "-sW", "-sM", "-sU", "-sN", "-sF", "-sX",
    # Timing templates
    "-T0", "-T1", "-T2", "-T3", "-T4", "-T5",
    # Service/version detection
    "-sV", "-sC", "-A",
    # OS detection
    "-O", "--osscan-limit", "--osscan-guess",
    # Port specification
    "-p", "-F", "--top-ports", "-r",
    # Output
    "-v", "-vv", "-d", "-dd",
    # DNS
    "-n", "-R", "--dns-servers",
    # Ping
    "-Pn", "-PS", "-PA", "-PU", "-PE", "-PP", "-PM",
    # Script scanning
    "--script", "--script-args", "--script-help",
    # Misc
    "--version-intensity", "--version-light", "--version-all",
    "--max-retries", "--host-timeout", "--min-rate", "--max-rate",
    "--min-parallelism", "--max-parallelism",
    "-6",  # IPv6
}

# Dangerous flags that are NEVER allowed
BLOCKED_NMAP_FLAGS = {
    "--datadir",  # could load malicious data files
    "--servicedb",  # could load malicious service DB
    "--versiondb",  # could load malicious version DB
    "--excludefile",  # could bypass filters
    "-iL",  # input from file — injection risk
    "-iR",  # random targets — unpredictable
    "--badsum",  # for evasion
    "-f", "--fragment",  # fragmentation evasion
    "-D", "--decoy",  # decoy scanning
    "-S", "--source-ip",  # IP spoofing
    "--source-port", "-g",  # source port manipulation
    "--data-length",  # packet manipulation
    "--ip-options",  # IP options manipulation
    "--ttl",  # TTL manipulation
    "--spoof-mac",  # MAC spoofing
}

# IP address regex for validation
IP_REGEX = re.compile(
    r"^(?:(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}"
    r"(?:25[0-5]|2[0-4]\d|[01]?\d\d?)$"
)

# CIDR regex
CIDR_REGEX = re.compile(
    r"^(?:(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}"
    r"(?:25[0-5]|2[0-4]\d|[01]?\d\d?)/\d{1,3}$"
)

# Port specification regex (80,443 or 1-1000 or 80,443,8080-8090)
PORT_REGEX = re.compile(
    r"^[0-9,\-\s]+$"
)

# Hostname regex
HOSTNAME_REGEX = re.compile(
    r"^(?:[a-zA-Z0-9](?:[a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?\.)*"
    r"[a-zA-Z]{2,}$"
)


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------

@dataclass
class NmapPort:
    """A single port result from an nmap scan."""
    port: int
    protocol: str
    state: str
    service: str = ""
    version: str = ""
    product: str = ""
    extra_info: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class NmapOSMatch:
    """An OS detection match from an nmap scan."""
    name: str
    accuracy: int
    family: str = ""
    version: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class NmapHost:
    """A host discovered during an nmap scan."""
    ip: str
    hostname: Optional[str] = None
    status: str = "unknown"
    ports: List[NmapPort] = field(default_factory=list)
    os_matches: List[NmapOSMatch] = field(default_factory=list)
    latency: float = 0.0  # milliseconds

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ip": self.ip,
            "hostname": self.hostname,
            "status": self.status,
            "ports": [p.to_dict() for p in self.ports],
            "os_matches": [o.to_dict() for o in self.os_matches],
            "latency": self.latency,
        }


@dataclass
class NmapScanResult:
    """Complete result of an nmap scan."""
    scan_id: str
    target: str
    command: str
    start_time: str
    end_time: Optional[str] = None
    status: str = "running"  # running, completed, failed
    hosts: List[NmapHost] = field(default_factory=list)
    raw_xml: Optional[str] = None
    error: Optional[str] = None
    elapsed: float = 0.0
    hosts_up: int = 0
    hosts_down: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "scan_id": self.scan_id,
            "target": self.target,
            "command": self.command,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "status": self.status,
            "hosts": [h.to_dict() for h in self.hosts],
            "raw_xml": self.raw_xml,
            "error": self.error,
            "elapsed": self.elapsed,
            "hosts_up": self.hosts_up,
            "hosts_down": self.hosts_down,
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


def validate_target(target: str, allow_localhost: bool = False, allow_private: bool = True) -> str:
    """Validate a scan target for security compliance.

    Parameters
    ----------
    target:
        IP address, CIDR range, or hostname to scan.
    allow_localhost:
        If True, allow scanning localhost/127.0.0.1/::1.
    allow_private:
        If True, allow scanning RFC 1918 private ranges (10.x, 172.16.x, 192.168.x).

    Returns
    -------
    str
        The validated target string.

    Raises
    ------
    TargetValidationError
        If the target is blocked or malformed.
    """
    target = target.strip()

    if not target:
        raise TargetValidationError("Empty target specified")

    # Block localhost/loopback unless explicitly allowed
    if not allow_localhost:
        lower = target.lower()
        if lower in BLOCKED_LOOPBACK:
            raise TargetValidationError(
                f"Scanning {target} is blocked for safety. "
                "Set allow_localhost=True if you intend to scan localhost."
            )
        # Also check if it resolves to 127.0.0.1
        if target == "127.0.0.1" or target == "::1":
            raise TargetValidationError(
                f"Scanning loopback address {target} is blocked. "
                "Set allow_localhost=True if you intend to scan localhost."
            )

    # Validate format — must be IP, CIDR, or hostname
    is_valid = False

    # Check CIDR notation
    if "/" in target:
        try:
            network = ipaddress.ip_network(target, strict=False)
            is_valid = True

            # Check private ranges
            if not allow_private and not network.is_global:
                raise TargetValidationError(
                    f"Scanning private range {target} requires confirmation. "
                    "Set allow_private=True to allow scanning private networks."
                )

            # Check multicast
            if not allow_localhost:
                for mc_net in BLOCKED_MULTICAST:
                    if network.overlaps(mc_net):
                        raise TargetValidationError(
                            f"Scanning multicast range {target} is not allowed."
                        )

        except ipaddress.AddressValueError:
            pass

    # Check plain IP
    if not is_valid and IP_REGEX.match(target):
        try:
            addr = ipaddress.ip_address(target)
            is_valid = True

            if not allow_localhost and addr.is_loopback:
                raise TargetValidationError(
                    f"Scanning loopback address {target} is blocked."
                )

            if not allow_private and addr.is_private:
                raise TargetValidationError(
                    f"Scanning private address {target} requires confirmation. "
                    "Set allow_private=True to allow."
                )

            for mc_net in BLOCKED_MULTICAST:
                if addr in mc_net:
                    raise TargetValidationError(
                        f"Scanning multicast address {target} is not allowed."
                    )

            # Block broadcast addresses
            if target.endswith(".255") or target.endswith(".0"):
                # Could be broadcast or network address — warn but allow
                logger.warning("Target %s may be a broadcast/network address", target)

        except ValueError:
            pass

    # Check hostname
    if not is_valid and HOSTNAME_REGEX.match(target):
        is_valid = True
        # Hostname targets are generally okay — DNS resolution happens at scan time
        if not allow_localhost and target.lower() == "localhost":
            raise TargetValidationError(
                "Scanning localhost is blocked. Set allow_localhost=True to allow."
            )

    if not is_valid:
        raise TargetValidationError(
            f"Invalid target format: {target}. "
            "Must be an IP address (192.168.1.1), CIDR range (192.168.1.0/24), "
            "or hostname (example.com)."
        )

    return target


def validate_ports(ports: str) -> str:
    """Validate port specification string.

    Parameters
    ----------
    ports:
        Port specification like "80,443" or "1-1000" or "80,443,8080-8090".

    Returns
    -------
    str
        The validated ports string.

    Raises
    ------
    TargetValidationError
        If the port specification is invalid.
    """
    ports = ports.strip()
    if not ports:
        return ports

    if not PORT_REGEX.match(ports):
        raise TargetValidationError(
            f"Invalid port specification: {ports}. "
            "Use comma-separated ports (80,443) or ranges (1-1000)."
        )

    # Validate individual port numbers
    parts = ports.split(",")
    for part in parts:
        part = part.strip()
        if "-" in part:
            range_parts = part.split("-")
            if len(range_parts) != 2:
                raise TargetValidationError(f"Invalid port range: {part}")
            try:
                start, end = int(range_parts[0]), int(range_parts[1])
                if not (1 <= start <= 65535 and 1 <= end <= 65535):
                    raise TargetValidationError(f"Port out of range: {part}")
                if start > end:
                    raise TargetValidationError(f"Invalid port range: {part} (start > end)")
            except ValueError:
                raise TargetValidationError(f"Invalid port range: {part}")
        else:
            try:
                port_num = int(part)
                if not 1 <= port_num <= 65535:
                    raise TargetValidationError(f"Port out of range: {part}")
            except ValueError:
                raise TargetValidationError(f"Invalid port number: {part}")

    # Check for excessively large port ranges
    total_ports = 0
    for part in parts:
        part = part.strip()
        if "-" in part:
            range_parts = part.split("-")
            total_ports += int(range_parts[1]) - int(range_parts[0]) + 1
        else:
            total_ports += 1

    if total_ports > 65535:
        raise TargetValidationError(
            f"Too many ports specified ({total_ports}). Maximum is 65535."
        )

    return ports


def validate_options(options: str) -> str:
    """Validate nmap options string against the whitelist.

    Parameters
    ----------
    options:
        Space-separated nmap flags (e.g., "-sV -O").

    Returns
    -------
    str
        The validated options string.

    Raises
    ------
    TargetValidationError
        If any option is not in the whitelist or is in the blocked list.
    """
    if not options or not options.strip():
        return options

    tokens = options.strip().split()

    i = 0
    while i < len(tokens):
        token = tokens[i]

        # Check if this is a blocked flag
        if token in BLOCKED_NMAP_FLAGS:
            raise TargetValidationError(
                f"Nmap flag {token} is blocked for security reasons."
            )

        # Check if this is an allowed flag
        if token.startswith("-") or token.startswith("--"):
            # Handle flags that take parameters
            base_flag = token.split("=")[0]

            if base_flag not in ALLOWED_NMAP_OPTIONS:
                raise TargetValidationError(
                    f"Nmap flag {token} is not in the allowed list. "
                    f"Allowed flags: {', '.join(sorted(ALLOWED_NMAP_OPTIONS))}"
                )

            # Some flags consume the next token as a value
            if token in ("-p", "--top-ports", "--dns-servers",
                         "--script", "--script-args", "--script-help",
                         "--max-retries", "--host-timeout",
                         "--min-rate", "--max-rate",
                         "--min-parallelism", "--max-parallelism",
                         "--version-intensity", "--source-port", "-g",
                         "--data-length", "--ttl"):
                i += 1  # Skip the next token (parameter value)

        i += 1

    return options


# ---------------------------------------------------------------------------
# Scan Rate Limiter
# ---------------------------------------------------------------------------

class ScanRateLimiter:
    """Rate limiter for nmap scans.

    Enforces:
    - Max 1 concurrent scan
    - Max 10 scans per hour
    - 5 second cooldown between scans
    """

    def __init__(self):
        self._active_scans = 0
        self._scan_timestamps: List[float] = []
        self._last_scan_end = 0.0

    def acquire(self) -> None:
        """Acquire a scan slot. Raises RateLimitError if limits exceeded."""
        now = time.time()

        # Check concurrent limit
        if self._active_scans >= MAX_CONCURRENT_SCANS:
            raise RateLimitError(
                f"Maximum {MAX_CONCURRENT_SCANS} concurrent scan(s) already running. "
                "Please wait for the current scan to finish."
            )

        # Check hourly limit
        window_start = now - 3600
        self._scan_timestamps = [
            ts for ts in self._scan_timestamps if ts > window_start
        ]
        if len(self._scan_timestamps) >= MAX_SCANS_PER_HOUR:
            raise RateLimitError(
                f"Maximum {MAX_SCANS_PER_HOUR} scans per hour exceeded. "
                "Please wait before starting another scan."
            )

        # Check cooldown
        if self._last_scan_end > 0 and (now - self._last_scan_end) < COOLDOWN_BETWEEN_SCANS:
            remaining = COOLDOWN_BETWEEN_SCANS - (now - self._last_scan_end)
            raise RateLimitError(
                f"Cooldown period active. Please wait {remaining:.1f}s before "
                "starting another scan."
            )

        self._active_scans += 1
        self._scan_timestamps.append(now)

    def release(self) -> None:
        """Release a scan slot."""
        self._active_scans = max(0, self._active_scans - 1)
        self._last_scan_end = time.time()


# ---------------------------------------------------------------------------
# Audit Logger
# ---------------------------------------------------------------------------

class AuditLogger:
    """Logs all security tool operations to SQLite for audit review."""

    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            data_dir = os.getenv("CONSTRUCT_DATA_DIR", os.path.join(os.path.dirname(__file__), "..", "..", "data"))
            os.makedirs(data_dir, exist_ok=True)
            db_path = os.path.join(data_dir, "security_audit.db")

        self._db_path = db_path
        self._init_db()

    def _init_db(self):
        """Initialize the audit log database."""
        conn = sqlite3.connect(self._db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL NOT NULL,
                tool TEXT NOT NULL,
                action TEXT NOT NULL,
                target TEXT,
                user TEXT DEFAULT 'default',
                status TEXT NOT NULL,
                result_summary TEXT,
                error TEXT,
                scan_id TEXT
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_audit_timestamp
            ON audit_log(timestamp)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_audit_tool
            ON audit_log(tool)
        """)
        conn.commit()
        conn.close()

    def log(
        self,
        tool: str,
        action: str,
        target: Optional[str] = None,
        user: str = "default",
        status: str = "started",
        result_summary: Optional[str] = None,
        error: Optional[str] = None,
        scan_id: Optional[str] = None,
    ):
        """Log an audit entry."""
        try:
            conn = sqlite3.connect(self._db_path)
            conn.execute(
                """
                INSERT INTO audit_log
                    (timestamp, tool, action, target, user, status, result_summary, error, scan_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    time.time(),
                    tool,
                    action,
                    target,
                    user,
                    status,
                    result_summary,
                    error,
                    scan_id,
                ),
            )
            conn.commit()
            conn.close()
        except Exception as exc:
            logger.error("Failed to write audit log: %s", exc)

    def get_recent(self, limit: int = 50, tool: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get recent audit log entries."""
        try:
            conn = sqlite3.connect(self._db_path)
            conn.row_factory = sqlite3.Row

            if tool:
                rows = conn.execute(
                    "SELECT * FROM audit_log WHERE tool = ? ORDER BY timestamp DESC LIMIT ?",
                    (tool, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM audit_log ORDER BY timestamp DESC LIMIT ?",
                    (limit,),
                ).fetchall()

            result = [dict(row) for row in rows]
            conn.close()
            return result
        except Exception as exc:
            logger.error("Failed to read audit log: %s", exc)
            return []


# ---------------------------------------------------------------------------
# Nmap Tool
# ---------------------------------------------------------------------------

class NmapTool:
    """Async Nmap scanner with security validation, rate limiting, and audit logging.

    Usage::

        tool = NmapTool()
        result = await tool.scan(target="192.168.1.0/24", ports="80,443")
    """

    def __init__(self) -> None:
        self._rate_limiter = ScanRateLimiter()
        self._audit_logger = AuditLogger()
        self._available = self._check_nmap()

        if self._available:
            logger.info("Nmap found on PATH")
        else:
            logger.warning(
                "Nmap not found on PATH — install with: "
                "sudo apt install nmap (Ubuntu/Debian) or brew install nmap (macOS)"
            )

    def is_available(self) -> bool:
        """Check if nmap is installed and accessible."""
        return self._available

    def _check_nmap(self) -> bool:
        """Check if nmap binary is available on the system PATH."""
        import shutil
        return shutil.which("nmap") is not None

    async def scan(
        self,
        target: str,
        ports: Optional[str] = None,
        options: Optional[str] = None,
        workspace_id: Optional[str] = None,
        allow_localhost: bool = False,
        allow_private: bool = True,
        timeout: int = DEFAULT_SCAN_TIMEOUT,
    ) -> NmapScanResult:
        """Run an nmap scan with full security validation.

        Parameters
        ----------
        target:
            IP address, CIDR range, or hostname to scan.
        ports:
            Optional port specification (e.g., "80,443" or "1-1000").
        options:
            Optional additional nmap flags (e.g., "-sV -O").
        workspace_id:
            Optional workspace ID for result association.
        allow_localhost:
            Allow scanning localhost/127.0.0.1.
        allow_private:
            Allow scanning RFC 1918 private ranges.
        timeout:
            Maximum scan duration in seconds (max 300).

        Returns
        -------
        NmapScanResult
            Structured scan results including hosts, ports, and OS info.
        """
        scan_id = str(uuid.uuid4())[:8]
        start_time = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

        # Check availability
        if not self._available:
            result = NmapScanResult(
                scan_id=scan_id,
                target=target,
                command="",
                start_time=start_time,
                status="failed",
                error="Nmap is not installed. Install with: sudo apt install nmap",
            )
            self._audit_logger.log(
                tool="nmap", action="scan", target=target,
                status="failed", error="Nmap not installed", scan_id=scan_id,
            )
            return result

        # Validate timeout
        timeout = min(timeout, MAX_SCAN_TIMEOUT)

        # Validate target
        try:
            validated_target = validate_target(
                target,
                allow_localhost=allow_localhost,
                allow_private=allow_private,
            )
        except TargetValidationError as exc:
            result = NmapScanResult(
                scan_id=scan_id,
                target=target,
                command="",
                start_time=start_time,
                status="failed",
                error=str(exc),
            )
            self._audit_logger.log(
                tool="nmap", action="scan", target=target,
                status="blocked", error=str(exc), scan_id=scan_id,
            )
            return result

        # Validate ports
        if ports:
            try:
                validated_ports = validate_ports(ports)
            except TargetValidationError as exc:
                result = NmapScanResult(
                    scan_id=scan_id,
                    target=target,
                    command="",
                    start_time=start_time,
                    status="failed",
                    error=str(exc),
                )
                self._audit_logger.log(
                    tool="nmap", action="scan", target=target,
                    status="blocked", error=str(exc), scan_id=scan_id,
                )
                return result
        else:
            validated_ports = None

        # Validate options
        if options:
            try:
                validated_options = validate_options(options)
            except TargetValidationError as exc:
                result = NmapScanResult(
                    scan_id=scan_id,
                    target=target,
                    command="",
                    start_time=start_time,
                    status="failed",
                    error=str(exc),
                )
                self._audit_logger.log(
                    tool="nmap", action="scan", target=target,
                    status="blocked", error=str(exc), scan_id=scan_id,
                )
                return result
        else:
            validated_options = None

        # Rate limiting
        try:
            self._rate_limiter.acquire()
        except RateLimitError as exc:
            result = NmapScanResult(
                scan_id=scan_id,
                target=target,
                command="",
                start_time=start_time,
                status="failed",
                error=str(exc),
            )
            self._audit_logger.log(
                tool="nmap", action="scan", target=target,
                status="rate_limited", error=str(exc), scan_id=scan_id,
            )
            return result

        # Build command
        cmd = ["nmap", "-oX", "-"]  # XML output to stdout
        if validated_ports:
            cmd.extend(["-p", validated_ports])
        if validated_options:
            cmd.extend(validated_options.split())
        cmd.append(validated_target)

        command_str = " ".join(cmd)

        # Log scan start
        self._audit_logger.log(
            tool="nmap", action="scan", target=validated_target,
            status="started", scan_id=scan_id,
        )
        logger.info("Starting nmap scan [%s]: %s", scan_id, command_str)

        result = NmapScanResult(
            scan_id=scan_id,
            target=validated_target,
            command=command_str,
            start_time=start_time,
            status="running",
        )

        try:
            # Run nmap as async subprocess
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
                    tool="nmap", action="scan", target=validated_target,
                    status="timeout", error=result.error, scan_id=scan_id,
                )
                return result

            if process.returncode != 0:
                stderr_text = stderr.decode("utf-8", errors="replace")[:2000]
                result.status = "failed"
                result.error = f"Nmap exited with code {process.returncode}: {stderr_text}"
                result.end_time = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                self._audit_logger.log(
                    tool="nmap", action="scan", target=validated_target,
                    status="failed", error=result.error, scan_id=scan_id,
                )
                return result

            # Parse XML output
            xml_output = stdout.decode("utf-8", errors="replace")
            result.raw_xml = xml_output

            parsed = self._parse_xml(xml_output)
            result.hosts = parsed["hosts"]
            result.hosts_up = parsed["hosts_up"]
            result.hosts_down = parsed["hosts_down"]
            result.elapsed = parsed["elapsed"]
            result.status = "completed"
            result.end_time = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

            # Audit log completion
            summary = f"{len(result.hosts)} hosts, {sum(len(h.ports) for h in result.hosts)} ports found"
            self._audit_logger.log(
                tool="nmap", action="scan", target=validated_target,
                status="completed", result_summary=summary, scan_id=scan_id,
            )
            logger.info("Nmap scan [%s] completed: %s", scan_id, summary)

        except Exception as exc:
            result.status = "failed"
            result.error = f"Scan failed: {exc}"
            result.end_time = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            self._audit_logger.log(
                tool="nmap", action="scan", target=validated_target,
                status="failed", error=str(exc), scan_id=scan_id,
            )
            logger.exception("Nmap scan [%s] failed", scan_id)
        finally:
            self._rate_limiter.release()

        return result

    def _parse_xml(self, xml_string: str) -> Dict[str, Any]:
        """Parse nmap XML output into structured data.

        Parameters
        ----------
        xml_string:
            Raw XML output from nmap (-oX -).

        Returns
        -------
        dict
            Parsed results with hosts, counts, and elapsed time.
        """
        hosts: List[NmapHost] = []
        hosts_up = 0
        hosts_down = 0
        elapsed = 0.0

        try:
            root = ET.fromstring(xml_string)

            # Get scan stats
            runstats = root.find("runstats")
            if runstats is not None:
                hosts_elem = runstats.find("hosts")
                if hosts_elem is not None:
                    hosts_up = int(hosts_elem.get("up", 0))
                    hosts_down = int(hosts_elem.get("down", 0))

            # Get elapsed time
            finished = root.find("runstats/finished")
            if finished is not None:
                elapsed = float(finished.get("elapsed", 0))

            # Parse hosts
            for host_elem in root.findall(".//host"):
                # Get status
                status_elem = host_elem.find("status")
                status = status_elem.get("state", "unknown") if status_elem is not None else "unknown"

                # Get address
                ip = ""
                hostname = None
                for addr in host_elem.findall("address"):
                    addrtype = addr.get("addrtype", "")
                    if addrtype == "ipv4" or addrtype == "ipv6":
                        ip = addr.get("addr", "")
                    elif addrtype not in ("mac", "ipv4", "ipv6"):
                        # Vendor or other info
                        pass

                # Get hostname
                hostnames = host_elem.find("hostnames")
                if hostnames is not None:
                    for hostname_elem in hostnames.findall("hostname"):
                        if hostname_elem.get("type") == "user" or hostname is None:
                            hostname = hostname_elem.get("name")

                # Get latency
                latency_elem = host_elem.find("status")
                latency = 0.0
                if latency_elem is not None:
                    try:
                        latency = float(latency_elem.get("latency", "0").replace("s", ""))
                    except (ValueError, AttributeError):
                        pass

                # Parse ports
                ports_list: List[NmapPort] = []
                ports_elem = host_elem.find("ports")
                if ports_elem is not None:
                    for port_elem in ports_elem.findall("port"):
                        port_id = port_elem.get("portid", "")
                        protocol = port_elem.get("protocol", "")

                        state_elem = port_elem.find("state")
                        state = state_elem.get("state", "unknown") if state_elem is not None else "unknown"

                        service_elem = port_elem.find("service")
                        service = service_elem.get("name", "") if service_elem is not None else ""
                        product = service_elem.get("product", "") if service_elem is not None else ""
                        version = service_elem.get("version", "") if service_elem is not None else ""
                        extra_info = service_elem.get("extrainfo", "") if service_elem is not None else ""

                        try:
                            port_num = int(port_id)
                        except ValueError:
                            continue

                        ports_list.append(NmapPort(
                            port=port_num,
                            protocol=protocol,
                            state=state,
                            service=service,
                            version=version,
                            product=product,
                            extra_info=extra_info,
                        ))

                # Parse OS detection
                os_matches: List[NmapOSMatch] = []
                os_elem = host_elem.find("os")
                if os_elem is not None:
                    for osmatch in os_elem.findall("osmatch"):
                        os_matches.append(NmapOSMatch(
                            name=osmatch.get("name", ""),
                            accuracy=int(osmatch.get("accuracy", 0)),
                            family=osmatch.get("osfamily", ""),
                            version=osmatch.get("osgen", ""),
                        ))

                host = NmapHost(
                    ip=ip,
                    hostname=hostname,
                    status=status,
                    ports=ports_list,
                    os_matches=os_matches,
                    latency=latency,
                )
                hosts.append(host)

        except ET.ParseError as exc:
            logger.error("Failed to parse nmap XML output: %s", exc)
        except Exception as exc:
            logger.exception("Unexpected error parsing nmap XML: %s", exc)

        return {
            "hosts": hosts,
            "hosts_up": hosts_up,
            "hosts_down": hosts_down,
            "elapsed": elapsed,
        }

    def get_audit_log(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent audit log entries for nmap scans."""
        return self._audit_logger.get_recent(limit=limit, tool="nmap")
