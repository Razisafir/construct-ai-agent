"""Trivy Tool — container image and filesystem vulnerability scanning.

Provides async Trivy scanning with JSON output parsing, structured results,
rate limiting, and severity grouping.

Requirements:
    - trivy binary installed and accessible on PATH
    - Python 3.11+ (or use from __future__ import annotations)

Usage::

    from tools.trivy_tool import TrivyTool, TrivyScanResult

    tool = TrivyTool()
    result = await tool.scan(mode="image", target="alpine:3.18")
    print(result.total_vulns)
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
import time
import uuid
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MAX_SCAN_TIMEOUT = 600  # 10 minutes max per scan
DEFAULT_SCAN_TIMEOUT = 300  # 5 minutes default
MAX_CONCURRENT_SCANS = 2
MAX_SCANS_PER_HOUR = 10

SCAN_MODES = {"image", "fs", "repo", "config"}


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------

@dataclass
class TrivyVulnerability:
    """A single vulnerability finding from a Trivy scan."""

    vulnerability_id: str
    pkg_name: str
    installed_version: str
    fixed_version: Optional[str]
    severity: str
    title: str
    description: str
    primary_url: str
    status: str

    def to_dict(self) -> Dict[str, Any]:
        """Return a dictionary representation of this vulnerability."""
        return asdict(self)


@dataclass
class TrivyScanResult:
    """Complete result of a Trivy scan."""

    scan_id: str
    target: str
    mode: str  # image / fs / repo / config
    status: str = "running"  # running, completed, failed
    vulnerabilities: List[TrivyVulnerability] = field(default_factory=list)
    vulns_by_severity: Dict[str, int] = field(default_factory=dict)
    total_vulns: int = 0
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
            "mode": self.mode,
            "status": self.status,
            "vulnerabilities": [v.to_dict() for v in self.vulnerabilities],
            "vulns_by_severity": self.vulns_by_severity,
            "total_vulns": self.total_vulns,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "elapsed": self.elapsed,
            "error": self.error,
            "raw_output": self.raw_output,
        }


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class RateLimitError(Exception):
    """Raised when scan rate limits are exceeded."""
    pass


# ---------------------------------------------------------------------------
# Scan Rate Limiter
# ---------------------------------------------------------------------------

class ScanRateLimiter:
    """Rate limiter for Trivy scans.

    Enforces:
    - Max 2 concurrent scans
    - Max 10 scans per hour
    """

    def __init__(self) -> None:
        self._active_scans: int = 0
        self._scan_timestamps: List[float] = []

    def acquire(self) -> None:
        """Acquire a scan slot.

        Raises
        ------
        RateLimitError
            If concurrent or hourly limits are exceeded.
        """
        now = time.time()

        # Check concurrent limit
        if self._active_scans >= MAX_CONCURRENT_SCANS:
            raise RateLimitError(
                f"Maximum {MAX_CONCURRENT_SCANS} concurrent scan(s) already running. "
                "Please wait for a current scan to finish."
            )

        # Prune timestamps older than one hour, then check hourly limit
        window_start = now - 3600
        self._scan_timestamps = [
            ts for ts in self._scan_timestamps if ts > window_start
        ]
        if len(self._scan_timestamps) >= MAX_SCANS_PER_HOUR:
            raise RateLimitError(
                f"Maximum {MAX_SCANS_PER_HOUR} scans per hour exceeded. "
                "Please wait before starting another scan."
            )

        self._active_scans += 1
        self._scan_timestamps.append(now)

    def release(self) -> None:
        """Release a scan slot."""
        self._active_scans = max(0, self._active_scans - 1)


# ---------------------------------------------------------------------------
# Trivy Tool
# ---------------------------------------------------------------------------

class TrivyTool:
    """Async Trivy scanner with rate limiting and structured JSON parsing.

    Supports four scan modes: *image*, *fs*, *repo*, and *config*.

    Usage::

        tool = TrivyTool()
        result = await tool.scan(mode="image", target="alpine:3.18")
        print(result.total_vulns)
    """

    def __init__(self) -> None:
        """Initialise the tool, checking for the trivy binary on PATH."""
        self._rate_limiter = ScanRateLimiter()
        self._available = self._check_trivy()

        if self._available:
            logger.info("Trivy found on PATH")
        else:
            logger.warning(
                "Trivy not found on PATH — install with: "
                "https://aquasecurity.github.io/trivy/latest/getting-started/installation/"
            )

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    def is_available(self) -> bool:
        """Return ``True`` if the trivy binary is installed and accessible."""
        return self._available

    # ------------------------------------------------------------------
    # Main scan entry point
    # ------------------------------------------------------------------

    async def scan(
        self,
        mode: str,
        target: str,
        severity: Optional[List[str]] = None,
        ignore_unfixed: bool = False,
        workspace_id: Optional[str] = None,
        timeout: int = DEFAULT_SCAN_TIMEOUT,
    ) -> TrivyScanResult:
        """Run a Trivy scan and return structured results.

        Parameters
        ----------
        mode:
            Scan mode — one of ``"image"``, ``"fs"``, ``"repo"``, ``"config"``.
        target:
            The target to scan (image ref, filesystem path, repo URL, etc.).
        severity:
            Optional list of severity levels to include (e.g. ``["CRITICAL", "HIGH"]``).
        ignore_unfixed:
            If ``True``, exclude vulnerabilities that have no available fix.
        workspace_id:
            Optional workspace ID for result association.
        timeout:
            Maximum scan duration in seconds (capped at ``MAX_SCAN_TIMEOUT``).

        Returns
        -------
        TrivyScanResult
            Structured scan result including vulnerabilities and severity counts.
        """
        scan_id = str(uuid.uuid4())[:8]
        start_time = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

        # --- Validate mode ---
        if mode not in SCAN_MODES:
            return TrivyScanResult(
                scan_id=scan_id,
                target=target,
                mode=mode,
                status="failed",
                start_time=start_time,
                end_time=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                error=f"Invalid scan mode '{mode}'. Must be one of: {', '.join(sorted(SCAN_MODES))}",
            )

        # --- Validate target ---
        if not target or not target.strip():
            return TrivyScanResult(
                scan_id=scan_id,
                target=target,
                mode=mode,
                status="failed",
                start_time=start_time,
                end_time=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                error="Empty target specified. Provide an image name, path, or repo URL.",
            )

        # --- Check availability ---
        if not self._available:
            return TrivyScanResult(
                scan_id=scan_id,
                target=target,
                mode=mode,
                status="failed",
                start_time=start_time,
                end_time=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                error="Trivy is not installed. See: https://aquasecurity.github.io/trivy/latest/getting-started/installation/",
            )

        # --- Cap timeout ---
        timeout = min(timeout, MAX_SCAN_TIMEOUT)

        # --- Rate limiting ---
        try:
            self._rate_limiter.acquire()
        except RateLimitError as exc:
            return TrivyScanResult(
                scan_id=scan_id,
                target=target,
                mode=mode,
                status="failed",
                start_time=start_time,
                end_time=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                error=str(exc),
            )

        # --- Build command ---
        cmd = ["trivy", mode, "-f", "json", "-q", target.strip()]

        if severity:
            cmd.extend(["--severity", ",".join(severity)])

        if ignore_unfixed:
            cmd.append("--ignore-unfixed")

        command_str = " ".join(cmd)
        logger.info("Starting trivy scan [%s]: %s", scan_id, command_str)

        result = TrivyScanResult(
            scan_id=scan_id,
            target=target.strip(),
            mode=mode,
            start_time=start_time,
            status="running",
        )

        try:
            # Run trivy as async subprocess
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
                result.elapsed = timeout
                logger.warning("Trivy scan [%s] timed out", scan_id)
                return result

            # Trivy may exit with non-zero even when it produces valid JSON
            # (e.g. exit code 1 when vulnerabilities are found).  We only
            # treat it as a hard failure when there is no usable stdout.
            stdout_text = stdout.decode("utf-8", errors="replace")
            stderr_text = stderr.decode("utf-8", errors="replace")[:2000]

            if process.returncode != 0 and not stdout_text.strip():
                result.status = "failed"
                result.error = (
                    f"Trivy exited with code {process.returncode}: {stderr_text}"
                )
                result.end_time = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                return result

            # Store raw output for debugging
            result.raw_output = stdout_text

            # Parse JSON output
            vulnerabilities = self._parse_json_output(stdout_text)
            result.vulnerabilities = vulnerabilities
            result.vulns_by_severity = self._group_by_severity(vulnerabilities)
            result.total_vulns = len(vulnerabilities)
            result.status = "completed"
            result.end_time = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            result.elapsed = time.time() - time.mktime(
                time.strptime(start_time, "%Y-%m-%dT%H:%M:%SZ")
            )

            logger.info(
                "Trivy scan [%s] completed: %d vulnerabilities found",
                scan_id,
                result.total_vulns,
            )

        except Exception as exc:
            result.status = "failed"
            result.error = f"Scan failed: {exc}"
            result.end_time = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            logger.exception("Trivy scan [%s] failed", scan_id)
        finally:
            self._rate_limiter.release()

        return result

    # ------------------------------------------------------------------
    # Parsing helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_json_output(json_output: str) -> List[TrivyVulnerability]:
        """Parse Trivy JSON output into a list of vulnerability objects.

        Trivy produces a JSON structure like::

            {
                "Results": [
                    {
                        "Target": "alpine:3.18",
                        "Vulnerabilities": [
                            {
                                "VulnerabilityID": "CVE-2023-XXXX",
                                "PkgName": "openssl",
                                "InstalledVersion": "3.1.0",
                                "FixedVersion": "3.1.1",
                                "Severity": "HIGH",
                                "Title": "OpenSSL ...",
                                "Description": "A flaw was found...",
                                "PrimaryURL": "https://avd.aquasec.com/...",
                                "Status": "fixed"
                            }
                        ]
                    }
                ]
            }

        Parameters
        ----------
        json_output:
            Raw JSON string from trivy stdout.

        Returns
        -------
        list[TrivyVulnerability]
            Flat list of all vulnerabilities found across all results.
        """
        vulns: List[TrivyVulnerability] = []

        try:
            data = json.loads(json_output)
        except json.JSONDecodeError as exc:
            logger.error("Failed to parse trivy JSON output: %s", exc)
            return vulns

        results = data.get("Results", [])
        if not results:
            return vulns

        for result_entry in results:
            vulnerability_list = result_entry.get("Vulnerabilities")
            if not vulnerability_list:
                continue

            for v in vulnerability_list:
                vulns.append(TrivyVulnerability(
                    vulnerability_id=v.get("VulnerabilityID", "UNKNOWN"),
                    pkg_name=v.get("PkgName", "UNKNOWN"),
                    installed_version=v.get("InstalledVersion", "UNKNOWN"),
                    fixed_version=v.get("FixedVersion"),
                    severity=v.get("Severity", "UNKNOWN"),
                    title=v.get("Title", ""),
                    description=v.get("Description", ""),
                    primary_url=v.get("PrimaryURL", ""),
                    status=v.get("Status", "unknown"),
                ))

        return vulns

    @staticmethod
    def _group_by_severity(vulns: List[TrivyVulnerability]) -> Dict[str, int]:
        """Group vulnerabilities by severity level and count them.

        Parameters
        ----------
        vulns:
            List of TrivyVulnerability objects to group.

        Returns
        -------
        dict[str, int]
            Mapping from severity name to count, e.g.
            ``{"CRITICAL": 3, "HIGH": 12, "MEDIUM": 5, "LOW": 1}``.
        """
        counts: Dict[str, int] = {}
        for v in vulns:
            sev = v.severity.upper()
            counts[sev] = counts.get(sev, 0) + 1
        return counts

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _check_trivy() -> bool:
        """Check if the trivy binary is available on the system PATH."""
        return shutil.which("trivy") is not None
