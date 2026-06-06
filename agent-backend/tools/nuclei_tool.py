"""Nuclei Tool — vulnerability scanning using ProjectDiscovery Nuclei.

Provides async Nuclei scanning with JSONL output parsing, structured results,
and security validation (target blocklist, rate limiting, audit logging).

Requirements:
    - nuclei binary installed and accessible on PATH
    - nuclei-templates installed (default: ~/.nuclei-templates)

Usage::

    from tools.nuclei_tool import NucleiTool, NucleiScanResult

    tool = NucleiTool()
    result = await tool.scan(target="https://example.com", severity="high,critical")
    print(result.findings)
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

from tools.nmap_tool import AuditLogger, TargetValidationError, RateLimitError

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MAX_SCAN_TIMEOUT = 600  # 10 minutes max per scan
DEFAULT_SCAN_TIMEOUT = 300  # 5 minutes default
MAX_CONCURRENT_SCANS = 1
MAX_SCANS_PER_HOUR = 5
COOLDOWN_BETWEEN_SCANS = 10  # seconds

DEFAULT_TEMPLATES_DIR = "~/.nuclei-templates"

ALLOWED_TEMPLATE_CATEGORIES = [
    "cves",
    "vulnerabilities",
    "misconfiguration",
    "exposures",
    "default-logins",
    "fuzzing",
    "dns",
    "takeovers",
]

SEVERITY_LEVELS = ["critical", "high", "medium", "low", "info"]

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
    ipaddress.ip_network("224.0.0.0/4"),  # multicast
    ipaddress.ip_network("239.0.0.0/8"),  # administratively scoped
    ipaddress.ip_network("ff00::/8"),  # IPv6 multicast
]

# URL regex for validating http/https targets
URL_REGEX = re.compile(
    r"^https?://"
    r"(?:[a-zA-Z0-9](?:[a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?\.)*"
    r"[a-zA-Z]{2,}"
    r"(?::\d{1,5})?"
    r"(?:/.*)?$"
)

# IP address regex
IP_REGEX = re.compile(
    r"^(?:(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}"
    r"(?:25[0-5]|2[0-4]\d|[01]?\d\d?)$"
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
class NucleiFinding:
    """A single vulnerability finding from a Nuclei scan."""

    template_id: str
    template_name: str
    severity: str
    host: str
    matched_at: str
    extractors: Dict[str, Any] = field(default_factory=dict)
    description: str = ""
    remediation: str = ""
    cve_id: Optional[str] = None
    cvss_score: Optional[float] = None
    type: str = ""
    timestamp: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Return a dictionary representation of this finding."""
        return asdict(self)


@dataclass
class NucleiScanResult:
    """Complete result of a Nuclei vulnerability scan."""

    scan_id: str
    target: str
    status: str = "running"  # running, completed, failed
    findings: List[NucleiFinding] = field(default_factory=list)
    findings_by_severity: Dict[str, int] = field(default_factory=dict)
    templates_used: List[str] = field(default_factory=list)
    start_time: str = ""
    end_time: Optional[str] = None
    elapsed: float = 0.0
    error: Optional[str] = None
    raw_output: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Return a dictionary representation of this scan result."""
        return {
            "scan_id": self.scan_id,
            "target": self.target,
            "status": self.status,
            "findings": [f.to_dict() for f in self.findings],
            "findings_by_severity": self.findings_by_severity,
            "templates_used": self.templates_used,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "elapsed": self.elapsed,
            "error": self.error,
            "raw_output": self.raw_output,
        }


# ---------------------------------------------------------------------------
# Target Validation
# ---------------------------------------------------------------------------

def validate_nuclei_target(
    target: str,
    allow_localhost: bool = False,
    allow_private: bool = True,
) -> str:
    """Validate a Nuclei scan target for security compliance.

    Supports URLs (http/https), IP addresses, and hostnames.
    Blocks localhost/loopback unless explicitly allowed.
    Blocks private IPs unless explicitly allowed.

    Parameters
    ----------
    target:
        URL, IP address, or hostname to scan.
    allow_localhost:
        If True, allow scanning localhost/127.0.0.1/::1.
    allow_private:
        If True, allow scanning RFC 1918 private ranges.

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
        # Check raw target against blocked loopback entries
        for blocked in BLOCKED_LOOPBACK:
            if lower == blocked or lower.startswith(f"http://{blocked}") or lower.startswith(f"https://{blocked}"):
                raise TargetValidationError(
                    f"Scanning {target} is blocked for safety. "
                    "Set allow_localhost=True if you intend to scan localhost."
                )

    # Extract the host portion from URLs for IP/hostname validation
    host_part = target
    if target.startswith("http://") or target.startswith("https://"):
        # Strip scheme for host extraction
        stripped = re.sub(r"^https?://", "", target)
        # Strip port and path
        host_part = stripped.split("/")[0].split(":")[0]

    # Check if host_part is an IP address
    is_valid = False

    if IP_REGEX.match(host_part):
        try:
            addr = ipaddress.ip_address(host_part)
            is_valid = True

            if not allow_localhost and addr.is_loopback:
                raise TargetValidationError(
                    f"Scanning loopback address {host_part} is blocked. "
                    "Set allow_localhost=True if you intend to scan localhost."
                )

            if not allow_private and addr.is_private:
                raise TargetValidationError(
                    f"Scanning private address {host_part} requires confirmation. "
                    "Set allow_private=True to allow."
                )

            for mc_net in BLOCKED_MULTICAST:
                if addr in mc_net:
                    raise TargetValidationError(
                        f"Scanning multicast address {host_part} is not allowed."
                    )
        except ValueError:
            pass

    # Check if it's a valid URL
    if not is_valid and URL_REGEX.match(target):
        is_valid = True
        # Host validation happens through the URL regex structure

    # Check if it's a valid hostname (non-URL)
    if not is_valid and HOSTNAME_REGEX.match(host_part):
        is_valid = True
        if not allow_localhost and host_part.lower() == "localhost":
            raise TargetValidationError(
                "Scanning localhost is blocked. Set allow_localhost=True to allow."
            )

    if not is_valid:
        raise TargetValidationError(
            f"Invalid target format: {target}. "
            "Must be a URL (https://example.com), IP address (192.168.1.1), "
            "or hostname (example.com)."
        )

    return target


# ---------------------------------------------------------------------------
# Scan Rate Limiter
# ---------------------------------------------------------------------------

class ScanRateLimiter:
    """Rate limiter for Nuclei scans.

    Enforces:
    - Max concurrent scans
    - Max scans per hour
    - Cooldown between scans
    """

    def __init__(self):
        self._active_scans: int = 0
        self._scan_timestamps: List[float] = []
        self._last_scan_end: float = 0.0

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
        """Release a scan slot and record the scan end time."""
        self._active_scans = max(0, self._active_scans - 1)
        self._last_scan_end = time.time()


# ---------------------------------------------------------------------------
# Nuclei Tool
# ---------------------------------------------------------------------------

class NucleiTool:
    """Async Nuclei vulnerability scanner with security validation,
    rate limiting, and audit logging.

    Usage::

        tool = NucleiTool()
        result = await tool.scan(
            target="https://example.com",
            templates=["cves", "vulnerabilities"],
            severity="high,critical",
        )
    """

    def __init__(self) -> None:
        self._rate_limiter = ScanRateLimiter()
        self._audit_logger = AuditLogger()
        self._available = self._check_nuclei()

        if self._available:
            logger.info("Nuclei found on PATH")
        else:
            logger.warning(
                "Nuclei not found on PATH — install with: "
                "go install -v github.com/projectdiscovery/nuclei/v3/cmd/nuclei@latest"
            )

    def is_available(self) -> bool:
        """Check if nuclei binary is installed and accessible on PATH.

        Returns
        -------
        bool
            True if nuclei is available, False otherwise.
        """
        return self._available

    def _check_nuclei(self) -> bool:
        """Check if nuclei binary is available on the system PATH.

        Returns
        -------
        bool
            True if the nuclei binary is found, False otherwise.
        """
        return shutil.which("nuclei") is not None

    async def scan(
        self,
        target: str,
        templates: Optional[List[str]] = None,
        severity: Optional[str] = None,
        output_format: str = "json",
        workspace_id: Optional[str] = None,
        allow_localhost: bool = False,
        allow_private: bool = True,
        timeout: int = DEFAULT_SCAN_TIMEOUT,
    ) -> NucleiScanResult:
        """Run a Nuclei vulnerability scan with full security validation.

        Parameters
        ----------
        target:
            URL, IP address, or hostname to scan.
        templates:
            Optional list of template categories or paths to use
            (e.g., ["cves", "vulnerabilities"]).
        severity:
            Optional comma-separated severity levels to include
            (e.g., "high,critical").
        output_format:
            Output format — only "json" is supported (JSONL mode).
        workspace_id:
            Optional workspace ID for result association.
        allow_localhost:
            Allow scanning localhost/127.0.0.1.
        allow_private:
            Allow scanning RFC 1918 private ranges.
        timeout:
            Maximum scan duration in seconds (max 600).

        Returns
        -------
        NucleiScanResult
            Structured scan results including findings grouped by severity.
        """
        scan_id = str(uuid.uuid4())[:8]
        start_time = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

        # Check availability
        if not self._available:
            result = NucleiScanResult(
                scan_id=scan_id,
                target=target,
                start_time=start_time,
                status="failed",
                error="Nuclei is not installed. Install with: "
                      "go install -v github.com/projectdiscovery/nuclei/v3/cmd/nuclei@latest",
            )
            self._audit_logger.log(
                tool="nuclei", action="scan", target=target,
                status="failed", error="Nuclei not installed", scan_id=scan_id,
            )
            return result

        # Validate timeout
        timeout = min(timeout, MAX_SCAN_TIMEOUT)

        # Validate target
        try:
            validated_target = validate_nuclei_target(
                target,
                allow_localhost=allow_localhost,
                allow_private=allow_private,
            )
        except TargetValidationError as exc:
            result = NucleiScanResult(
                scan_id=scan_id,
                target=target,
                start_time=start_time,
                status="failed",
                error=str(exc),
            )
            self._audit_logger.log(
                tool="nuclei", action="scan", target=target,
                status="blocked", error=str(exc), scan_id=scan_id,
            )
            return result

        # Validate templates
        if templates:
            for tmpl in templates:
                if tmpl in ALLOWED_TEMPLATE_CATEGORIES:
                    continue
                # Allow template paths that start with the default templates dir
                expanded_dir = os.path.expanduser(DEFAULT_TEMPLATES_DIR)
                if tmpl.startswith(expanded_dir) or tmpl.startswith("/"):
                    continue
                # Block unrecognized template specs
                logger.warning("Unrecognized template category: %s", tmpl)

        # Validate severity
        if severity:
            requested_levels = [s.strip().lower() for s in severity.split(",")]
            for level in requested_levels:
                if level not in SEVERITY_LEVELS:
                    result = NucleiScanResult(
                        scan_id=scan_id,
                        target=target,
                        start_time=start_time,
                        status="failed",
                        error=f"Invalid severity level: {level}. "
                              f"Allowed: {', '.join(SEVERITY_LEVELS)}",
                    )
                    self._audit_logger.log(
                        tool="nuclei", action="scan", target=target,
                        status="blocked",
                        error=f"Invalid severity: {level}",
                        scan_id=scan_id,
                    )
                    return result

        # Rate limiting
        try:
            self._rate_limiter.acquire()
        except RateLimitError as exc:
            result = NucleiScanResult(
                scan_id=scan_id,
                target=target,
                start_time=start_time,
                status="failed",
                error=str(exc),
            )
            self._audit_logger.log(
                tool="nuclei", action="scan", target=target,
                status="rate_limited", error=str(exc), scan_id=scan_id,
            )
            return result

        # Build command
        cmd = ["nuclei", "-u", validated_target, "-jsonl", "-silent"]

        templates_used: List[str] = []

        if templates:
            for tmpl in templates:
                cmd.extend(["-t", tmpl])
                templates_used.append(tmpl)
        else:
            templates_used.append("all")

        if severity:
            cmd.extend(["-s", severity])

        command_str = " ".join(cmd)

        # Log scan start
        self._audit_logger.log(
            tool="nuclei", action="scan", target=validated_target,
            status="started", scan_id=scan_id,
        )
        logger.info("Starting nuclei scan [%s]: %s", scan_id, command_str)

        result = NucleiScanResult(
            scan_id=scan_id,
            target=validated_target,
            start_time=start_time,
            status="running",
            templates_used=templates_used,
        )

        try:
            # Run nuclei as async subprocess
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
                    tool="nuclei", action="scan", target=validated_target,
                    status="timeout", error=result.error, scan_id=scan_id,
                )
                return result

            stdout_text = stdout.decode("utf-8", errors="replace")
            stderr_text = stderr.decode("utf-8", errors="replace")

            if process.returncode != 0 and not stdout_text.strip():
                result.status = "failed"
                result.error = (
                    f"Nuclei exited with code {process.returncode}: "
                    f"{stderr_text[:2000]}"
                )
                result.end_time = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                self._audit_logger.log(
                    tool="nuclei", action="scan", target=validated_target,
                    status="failed", error=result.error, scan_id=scan_id,
                )
                return result

            # Parse JSONL output
            findings = self._parse_jsonl(stdout_text)
            result.findings = findings
            result.findings_by_severity = self._group_by_severity(findings)
            result.raw_output = stdout_text
            result.status = "completed"
            result.end_time = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            result.elapsed = round(
                time.time() - time.mktime(time.strptime(start_time, "%Y-%m-%dT%H:%M:%SZ")),
                2,
            )

            # Audit log completion
            total = len(findings)
            summary = (
                f"{total} finding(s): "
                + ", ".join(
                    f"{count} {sev}" for sev, count in sorted(result.findings_by_severity.items())
                )
                if result.findings_by_severity
                else f"{total} finding(s)"
            )
            self._audit_logger.log(
                tool="nuclei", action="scan", target=validated_target,
                status="completed", result_summary=summary, scan_id=scan_id,
            )
            logger.info("Nuclei scan [%s] completed: %s", scan_id, summary)

        except Exception as exc:
            result.status = "failed"
            result.error = f"Scan failed: {exc}"
            result.end_time = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            self._audit_logger.log(
                tool="nuclei", action="scan", target=validated_target,
                status="failed", error=str(exc), scan_id=scan_id,
            )
            logger.exception("Nuclei scan [%s] failed", scan_id)
        finally:
            self._rate_limiter.release()

        return result

    def _parse_jsonl(self, jsonl_output: str) -> List[NucleiFinding]:
        """Parse Nuclei JSONL output into structured findings.

        Each line in the JSONL output is a separate JSON object representing
        a single vulnerability finding.

        Parameters
        ----------
        jsonl_output:
            Raw JSONL text output from nuclei (-jsonl flag).

        Returns
        -------
        List[NucleiFinding]
            Parsed findings from the scan output.
        """
        findings: List[NucleiFinding] = []

        for line in jsonl_output.splitlines():
            line = line.strip()
            if not line:
                continue

            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                logger.warning("Skipping non-JSON line in nuclei output: %s", line[:200])
                continue

            try:
                # Extract template information
                info = data.get("info", {})
                template_id = data.get("template_id", data.get("templateID", ""))
                template_name = info.get("name", "")
                severity = info.get("severity", "info").lower()

                # Normalize severity
                if severity not in SEVERITY_LEVELS:
                    severity = "info"

                # Extract host and match details
                host = data.get("host", "")
                matched_at = data.get("matched-at", data.get("matched", host))

                # Extract description and remediation
                description = info.get("description", "")
                remediation = info.get("remediation", "")

                # Extract CVE ID if present
                cve_id: Optional[str] = None
                tags = info.get("tags", "")
                reference = info.get("reference", [])
                if isinstance(tags, str):
                    cve_match = re.search(r"CVE-\d{4}-\d+", tags, re.IGNORECASE)
                    if cve_match:
                        cve_id = cve_match.group(0).upper()
                if cve_id is None and isinstance(reference, list):
                    for ref in reference:
                        cve_match = re.search(r"CVE-\d{4}-\d+", str(ref), re.IGNORECASE)
                        if cve_match:
                            cve_id = cve_match.group(0).upper()
                            break

                # Extract CVSS score
                cvss_score: Optional[float] = None
                classification = info.get("classification", {})
                if isinstance(classification, dict):
                    cvss_score_str = classification.get("cvss-metrics", "")
                    cvss_score_val = classification.get("cvss-score")
                    if cvss_score_val is not None:
                        try:
                            cvss_score = float(cvss_score_val)
                        except (ValueError, TypeError):
                            pass

                # Extract type
                finding_type = data.get("type", "")

                # Extract extractors
                extractors_raw = data.get("extracted-results", [])
                extractors: Dict[str, Any] = {}
                if isinstance(extractors_raw, list) and extractors_raw:
                    extractors["results"] = extractors_raw

                # Timestamp
                timestamp = data.get("timestamp", time.time())
                if isinstance(timestamp, str):
                    try:
                        timestamp = time.mktime(time.strptime(timestamp, "%Y-%m-%dT%H:%M:%S.%fZ"))
                    except ValueError:
                        timestamp = time.time()

                finding = NucleiFinding(
                    template_id=template_id,
                    template_name=template_name,
                    severity=severity,
                    host=host,
                    matched_at=matched_at,
                    extractors=extractors,
                    description=description,
                    remediation=remediation,
                    cve_id=cve_id,
                    cvss_score=cvss_score,
                    type=finding_type,
                    timestamp=timestamp,
                )
                findings.append(finding)

            except Exception as exc:
                logger.warning("Failed to parse nuclei finding: %s", exc)
                continue

        return findings

    def _group_by_severity(self, findings: List[NucleiFinding]) -> Dict[str, int]:
        """Group findings by severity level and return counts.

        Parameters
        ----------
        findings:
            List of NucleiFinding objects to group.

        Returns
        -------
        Dict[str, int]
            Mapping of severity level to count of findings.
        """
        counts: Dict[str, int] = {}
        for finding in findings:
            sev = finding.severity
            counts[sev] = counts.get(sev, 0) + 1
        return counts

    def get_audit_log(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent audit log entries for nuclei scans.

        Parameters
        ----------
        limit:
            Maximum number of entries to return.

        Returns
        -------
        List[Dict[str, Any]]
            Recent audit log entries for nuclei.
        """
        return self._audit_logger.get_recent(limit=limit, tool="nuclei")
