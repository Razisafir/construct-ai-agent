"""Ghidra MCP Client — async client for the Ghidra MCP reverse engineering server.

Connects to the ghidra-mcp Docker container (http://localhost:8765) and provides
high-level Python methods for binary analysis, decompilation, string extraction,
import enumeration, and risk assessment.

MCP Tool Mapping:
    analyze_binary    — Import and auto-analyze a binary
    get_function_list — All functions with addresses and metadata
    decompile_function — C-like pseudocode for one function
    get_strings       — All strings with categorization
    get_imports       — Import table (DLL/symbol mapping)
    get_sections      — Memory sections with permissions
    rename_function   — Agent can suggest better names
    get_references_to — Cross-references to an address
    run_ghidra_script — Custom Python/Java scripts

Requirements:
    - aiohttp (pip install aiohttp)
    - Ghidra MCP server running (docker compose up ghidra-mcp)

Usage::

    from tools.ghidra_mcp_client import GhidraMCPClient, GhidraAnalysisResult

    client = GhidraMCPClient()
    connected = await client.connect()
    if connected:
        async for event in client.analyze_binary("/workspace/suspect.exe"):
            if event["type"] == "progress":
                print(f"{event['phase']}: {event['percent']}%")
            elif event["type"] == "complete":
                result = event["result"]
                print(f"Found {len(result.functions)} functions")
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
import uuid
from dataclasses import dataclass, field, asdict
from typing import Any, AsyncGenerator, Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_MCP_URL = os.environ.get("GHIDRA_MCP_URL", "http://localhost:8765")
ANALYSIS_TIMEOUT = 600  # 10 minutes max per analysis
HEALTH_CHECK_TIMEOUT = 5  # seconds

# Binary file extensions that can be analyzed
SUPPORTED_EXTENSIONS = {
    ".exe", ".dll", ".sys", ".drv",  # Windows
    ".elf", ".so", ".o", ".ko",      # Linux
    ".dylib", ".macho",               # macOS
    ".apk", ".dex", ".so",            # Android
    ".bin", ".rom", ".img",           # Firmware
    ".gba", ".nds", ".3ds",           # Game ROMs
}

# String categories for risk assessment
STRING_CATEGORIES = {
    "URL": ["http://", "https://", "ftp://", "ws://", "wss://"],
    "API_KEY": ["sk_live_", "sk_test_", "AKIA", "AIza", "ghp_", "glpat-"],
    "CRYPTO": ["AES", "RSA", "DES", "SHA", "MD5", "encrypt", "decrypt", "cipher", "key"],
    "SUSPICIOUS": ["cmd.exe", "/bin/sh", "/bin/bash", "powershell", "whoami", "net user"],
    "MUTEX": ["Global\\\\", "Local\\\\"],
    "REGISTRY": ["HKEY_", "SOFTWARE\\\\"],
    "PATH": ["C:\\\\", "\\\\??\\\\", "/etc/", "/tmp/", "/var/"],
    "EMAIL": ["@", "mailto:"],
    "IP_ADDR": [],  # detected via regex
}


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------

@dataclass
class GhidraFunction:
    """A function discovered during Ghidra analysis."""
    name: str
    address: str
    size: int
    return_type: Optional[str] = None
    parameter_count: int = 0
    calling_convention: Optional[str] = None
    is_external: bool = False
    is_thunk: bool = False
    calls: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)  # e.g., "suspicious", "crypto"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class GhidraString:
    """A string extracted from a binary, with categorization."""
    value: str
    address: str
    length: int
    category: str = "unknown"  # URL, API_KEY, CRYPTO, SUSPICIOUS, MUTEX, etc.
    string_type: str = "ascii"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class GhidraImport:
    """An imported symbol from an external library."""
    name: str
    address: str
    library: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class GhidraSection:
    """A memory section in the binary."""
    name: str
    start: str
    end: str
    size: int
    permissions: str  # "rwx", "rx", "rw", etc.
    is_initialized: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class RiskIndicator:
    """A security risk finding from binary analysis."""
    severity: str  # "critical", "high", "medium", "low"
    category: str  # "process_injection", "crypto", "hardcoded_secret", etc.
    description: str
    address: Optional[str] = None
    function_name: Optional[str] = None
    evidence: Optional[str] = None
    recommendation: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class GhidraAnalysisResult:
    """Complete result of a Ghidra binary analysis."""
    binary_path: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    functions: List[Dict[str, Any]] = field(default_factory=list)
    strings: List[Dict[str, Any]] = field(default_factory=list)
    imports: List[Dict[str, Any]] = field(default_factory=list)
    sections: List[Dict[str, Any]] = field(default_factory=list)
    risk_indicators: List[Dict[str, Any]] = field(default_factory=list)
    decompiled_functions: List[Dict[str, Any]] = field(default_factory=list)
    status: str = "in_progress"  # "complete", "failed", "in_progress"
    progress_percent: int = 0
    error: Optional[str] = None
    analysis_id: Optional[str] = None
    start_time: Optional[float] = None
    end_time: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# MCP Client
# ---------------------------------------------------------------------------

class GhidraMCPClient:
    """Async MCP client for the Ghidra reverse engineering server.

    Connects to the ghidra-mcp Docker container and provides structured
    methods for binary analysis with real-time progress streaming.

    The client gracefully handles the case where the MCP server is not
    running by returning mock/empty results with appropriate status codes.
    """

    def __init__(self, base_url: str = DEFAULT_MCP_URL):
        self.base_url = base_url
        self._session: Optional[Any] = None  # aiohttp.ClientSession
        self._connected = False
        self._server_info: Dict[str, Any] = {}

    # -- Connection Management ------------------------------------------------

    async def connect(self) -> bool:
        """Check if Ghidra MCP server is available and establish session.

        Returns
        -------
        bool
            True if the MCP server is reachable, False otherwise.
        """
        try:
            import aiohttp
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=HEALTH_CHECK_TIMEOUT)
            )
            async with self._session.get(f"{self.base_url}/health") as resp:
                if resp.status == 200:
                    self._connected = True
                    self._server_info = await resp.json()
                    logger.info(
                        "Ghidra MCP server connected: %s",
                        self._server_info.get("version", "unknown"),
                    )
                    return True
                return False
        except Exception as exc:
            logger.debug("Ghidra MCP server not available: %s", exc)
            self._connected = False
            return False

    async def disconnect(self) -> None:
        """Close the client session."""
        if self._session is not None:
            try:
                await self._session.close()
            except Exception:
                pass
            self._session = None
        self._connected = False

    def is_connected(self) -> bool:
        """Check if currently connected to the MCP server."""
        return self._connected

    # -- Analysis Pipeline ----------------------------------------------------

    async def analyze_binary(
        self,
        binary_path: str,
        workspace_id: Optional[str] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Analyze a binary file with Ghidra, yielding progress events.

        This is the primary entry point for binary analysis. It streams
        real-time progress events and produces a final GhidraAnalysisResult.

        Parameters
        ----------
        binary_path:
            Absolute path to the binary file to analyze.
        workspace_id:
            Optional workspace ID for result association.

        Yields
        ------
        dict
            Progress events with keys:
            - type: "progress" or "complete"
            - phase: str (import, analysis, functions, strings, decompilation, report)
            - percent: int (0-100)
            - message: str (human-readable description)
            Final event has type="complete" with a "result" key.
        """
        analysis_id = str(uuid.uuid4())[:8]
        start_time = time.time()

        result = GhidraAnalysisResult(
            binary_path=binary_path,
            analysis_id=analysis_id,
            start_time=start_time,
            status="in_progress",
        )

        # Phase 1: Import binary
        yield {
            "type": "progress",
            "phase": "import",
            "percent": 5,
            "message": f"Importing binary: {os.path.basename(binary_path)}",
            "analysis_id": analysis_id,
        }

        if not self._connected:
            # Return mock result when MCP server is not available
            result.status = "failed"
            result.error = (
                "Ghidra MCP server is not running. "
                "Start it with: docker compose up ghidra-mcp"
            )
            result.end_time = time.time()
            yield {"type": "complete", "result": result.to_dict()}
            return

        try:
            # Call MCP server to import binary
            import_result = await self._mcp_call(
                "analyze_binary",
                {"binary_path": binary_path},
            )

            if not import_result.get("success", False):
                result.status = "failed"
                result.error = import_result.get("error", "Import failed")
                result.end_time = time.time()
                yield {"type": "complete", "result": result.to_dict()}
                return

            result.metadata = import_result.get("metadata", {})

        except Exception as exc:
            result.status = "failed"
            result.error = f"Import failed: {exc}"
            result.end_time = time.time()
            yield {"type": "complete", "result": result.to_dict()}
            return

        # Phase 2: Auto-analysis
        yield {
            "type": "progress",
            "phase": "analysis",
            "percent": 15,
            "message": "Running auto-analysis (disassembly, type inference, calling conventions)...",
            "analysis_id": analysis_id,
        }

        await asyncio.sleep(0.1)  # Yield control for UI updates

        # Phase 3: Extract functions
        yield {
            "type": "progress",
            "phase": "functions",
            "percent": 35,
            "message": "Extracting function list...",
            "analysis_id": analysis_id,
        }

        try:
            func_result = await self._mcp_call(
                "get_function_list",
                {"binary_path": binary_path},
            )
            raw_functions = func_result.get("functions", [])
            result.functions = self._enrich_functions(raw_functions)
        except Exception as exc:
            logger.warning("Failed to extract functions: %s", exc)
            result.functions = []

        # Phase 4: Extract strings
        yield {
            "type": "progress",
            "phase": "strings",
            "percent": 55,
            "message": "Extracting and categorizing strings...",
            "analysis_id": analysis_id,
        }

        try:
            str_result = await self._mcp_call(
                "get_strings",
                {"binary_path": binary_path},
            )
            raw_strings = str_result.get("strings", [])
            result.strings = self._categorize_strings(raw_strings)
        except Exception as exc:
            logger.warning("Failed to extract strings: %s", exc)
            result.strings = []

        # Phase 5: Extract imports
        yield {
            "type": "progress",
            "phase": "imports",
            "percent": 65,
            "message": "Extracting import table...",
            "analysis_id": analysis_id,
        }

        try:
            imp_result = await self._mcp_call(
                "get_imports",
                {"binary_path": binary_path},
            )
            result.imports = imp_result.get("imports", [])
        except Exception as exc:
            logger.warning("Failed to extract imports: %s", exc)
            result.imports = []

        # Phase 6: Extract sections
        yield {
            "type": "progress",
            "phase": "sections",
            "percent": 72,
            "message": "Extracting memory sections...",
            "analysis_id": analysis_id,
        }

        try:
            sec_result = await self._mcp_call(
                "get_sections",
                {"binary_path": binary_path},
            )
            result.sections = sec_result.get("sections", [])
        except Exception as exc:
            logger.warning("Failed to extract sections: %s", exc)
            result.sections = []

        # Phase 7: Decompile suspicious functions
        yield {
            "type": "progress",
            "phase": "decompilation",
            "percent": 80,
            "message": "Decompiling high-priority functions...",
            "analysis_id": analysis_id,
        }

        try:
            suspicious_funcs = self._identify_suspicious_functions(result.functions, result.imports)
            decompiled = []
            for i, func_name in enumerate(suspicious_funcs[:20]):  # Limit to top 20
                decomp = await self._mcp_call(
                    "decompile_function",
                    {"binary_path": binary_path, "function_name": func_name},
                )
                if decomp.get("success") and decomp.get("c_code"):
                    decompiled.append({
                        "function_name": func_name,
                        "address": decomp.get("address"),
                        "c_code": decomp.get("c_code"),
                        "signature": decomp.get("signature"),
                    })

                # Update progress
                percent = 80 + int((i + 1) / min(len(suspicious_funcs), 20) * 12)
                yield {
                    "type": "progress",
                    "phase": "decompilation",
                    "percent": min(percent, 92),
                    "message": f"Decompiling {func_name} ({i+1}/{min(len(suspicious_funcs), 20)})",
                    "analysis_id": analysis_id,
                }

            result.decompiled_functions = decompiled
        except Exception as exc:
            logger.warning("Decompilation phase failed: %s", exc)

        # Phase 8: Generate risk report
        yield {
            "type": "progress",
            "phase": "report",
            "percent": 95,
            "message": "Generating risk assessment report...",
            "analysis_id": analysis_id,
        }

        result.risk_indicators = self._generate_risk_indicators(result)

        # Complete
        result.status = "complete"
        result.progress_percent = 100
        result.end_time = time.time()

        yield {
            "type": "complete",
            "result": result.to_dict(),
        }

    # -- Individual Tool Methods -----------------------------------------------

    async def decompile_function(self, binary_path: str, function_address: str) -> str:
        """Get decompiled C-like pseudocode for a specific function.

        Parameters
        ----------
        binary_path:
            Path to the analyzed binary.
        function_address:
            Address or name of the function to decompile.

        Returns
        -------
        str
            Decompiled C pseudocode, or empty string on failure.
        """
        if not self._connected:
            return ""

        try:
            result = await self._mcp_call(
                "decompile_function",
                {
                    "binary_path": binary_path,
                    "function_name": function_address,
                },
            )
            return result.get("c_code", "")
        except Exception as exc:
            logger.error("Decompilation failed for %s: %s", function_address, exc)
            return ""

    async def get_function_list(self, binary_path: str) -> List[Dict[str, Any]]:
        """List all functions in the binary with metadata.

        Parameters
        ----------
        binary_path:
            Path to the analyzed binary.

        Returns
        -------
        list[dict]
            Function metadata dicts with name, address, size, etc.
        """
        if not self._connected:
            return []

        try:
            result = await self._mcp_call(
                "get_function_list",
                {"binary_path": binary_path},
            )
            return self._enrich_functions(result.get("functions", []))
        except Exception as exc:
            logger.error("Failed to get function list: %s", exc)
            return []

    async def get_strings(self, binary_path: str) -> List[Dict[str, Any]]:
        """Extract and categorize all strings from the binary.

        Parameters
        ----------
        binary_path:
            Path to the analyzed binary.

        Returns
        -------
        list[dict]
            String data with category annotations.
        """
        if not self._connected:
            return []

        try:
            result = await self._mcp_call(
                "get_strings",
                {"binary_path": binary_path},
            )
            return self._categorize_strings(result.get("strings", []))
        except Exception as exc:
            logger.error("Failed to extract strings: %s", exc)
            return []

    async def get_imports(self, binary_path: str) -> List[Dict[str, Any]]:
        """Get all imported functions/libraries.

        Parameters
        ----------
        binary_path:
            Path to the analyzed binary.

        Returns
        -------
        list[dict]
            Import entries with library and symbol names.
        """
        if not self._connected:
            return []

        try:
            result = await self._mcp_call(
                "get_imports",
                {"binary_path": binary_path},
            )
            return result.get("imports", [])
        except Exception as exc:
            logger.error("Failed to get imports: %s", exc)
            return []

    async def get_sections(self, binary_path: str) -> List[Dict[str, Any]]:
        """Get memory sections with permissions.

        Parameters
        ----------
        binary_path:
            Path to the analyzed binary.

        Returns
        -------
        list[dict]
            Section data with name, start/end, permissions.
        """
        if not self._connected:
            return []

        try:
            result = await self._mcp_call(
                "get_sections",
                {"binary_path": binary_path},
            )
            return result.get("sections", [])
        except Exception as exc:
            logger.error("Failed to get sections: %s", exc)
            return []

    async def rename_function(
        self, binary_path: str, function_address: str, new_name: str
    ) -> bool:
        """Rename a function in the Ghidra project.

        Parameters
        ----------
        binary_path:
            Path to the analyzed binary.
        function_address:
            Address of the function to rename.
        new_name:
            New name for the function.

        Returns
        -------
        bool
            True if rename succeeded.
        """
        if not self._connected:
            return False

        try:
            result = await self._mcp_call(
                "rename_function",
                {
                    "binary_path": binary_path,
                    "function_address": function_address,
                    "new_name": new_name,
                },
            )
            return result.get("success", False)
        except Exception as exc:
            logger.error("Failed to rename function: %s", exc)
            return False

    async def get_references_to(self, binary_path: str, address: str) -> List[Dict[str, Any]]:
        """Get cross-references to a specific address.

        Parameters
        ----------
        binary_path:
            Path to the analyzed binary.
        address:
            Address to find references to.

        Returns
        -------
        list[dict]
            Reference entries with source address and type.
        """
        if not self._connected:
            return []

        try:
            result = await self._mcp_call(
                "get_references_to",
                {"binary_path": binary_path, "address": address},
            )
            return result.get("references", [])
        except Exception as exc:
            logger.error("Failed to get references: %s", exc)
            return []

    # -- Internal Methods -----------------------------------------------------

    async def _mcp_call(self, tool_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Make an MCP tool call to the Ghidra server.

        Parameters
        ----------
        tool_name:
            Name of the MCP tool to invoke.
        params:
            Parameters for the tool call.

        Returns
        -------
        dict
            Tool result data.
        """
        if self._session is None:
            raise RuntimeError("Not connected — call connect() first")

        import aiohttp

        payload = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": params,
            },
            "id": str(uuid.uuid4())[:8],
        }

        async with self._session.post(
            f"{self.base_url}/mcp",
            json=payload,
            timeout=aiohttp.ClientTimeout(total=ANALYSIS_TIMEOUT),
        ) as resp:
            if resp.status != 200:
                raise RuntimeError(f"MCP call failed: HTTP {resp.status}")

            data = await resp.json()

            if "error" in data:
                raise RuntimeError(f"MCP error: {data['error'].get('message', 'unknown')}")

            result = data.get("result", {})
            # MCP results can be wrapped in content blocks
            if isinstance(result, dict) and "content" in result:
                content = result["content"]
                if isinstance(content, list) and len(content) > 0:
                    text = content[0].get("text", "{}")
                    try:
                        return json.loads(text)
                    except json.JSONDecodeError:
                        return {"raw": text}
            return result

    def _enrich_functions(self, raw_functions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Add tags and annotations to function entries.

        Tags functions based on naming patterns and imported symbols
        to identify suspicious, crypto, network, and other categories.
        """
        suspicious_names = {
            "inject", "shellcode", "hook", "patch", "detour",
            "rootkit", "keylog", "capture", "sniff", "spoof",
        }
        network_names = {
            "connect", "send", "recv", "socket", "bind", "listen",
            "accept", "http", "ftp", "download", "upload", "beacon",
        }
        crypto_names = {
            "encrypt", "decrypt", "aes", "rsa", "des", "hash",
            "sign", "verify", "cipher", "keygen", "derive",
        }
        evasion_names = {
            "anti_debug", "anti_vm", "anti_disasm", "packed",
            "obfuscate", "decode", "unpack", "deobfuscate",
        }

        enriched = []
        for func in raw_functions:
            name = func.get("name", "").lower()
            tags = []

            if any(s in name for s in suspicious_names):
                tags.append("suspicious")
            if any(n in name for n in network_names):
                tags.append("network")
            if any(c in name for c in crypto_names):
                tags.append("crypto")
            if any(e in name for e in evasion_names):
                tags.append("evasion")

            func["tags"] = tags
            enriched.append(func)

        return enriched

    def _categorize_strings(self, raw_strings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Add category annotations to extracted strings.

        Categorizes strings as URL, API_KEY, CRYPTO, SUSPICIOUS, MUTEX,
        REGISTRY, PATH, EMAIL, or unknown.
        """
        import re

        ip_regex = re.compile(
            r"^(?:(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}(?:25[0-5]|2[0-4]\d|[01]?\d\d?)$"
        )

        categorized = []
        for s in raw_strings:
            value = s.get("value", "")
            category = "unknown"

            # Check each category
            for cat_name, patterns in STRING_CATEGORIES.items():
                if any(p.lower() in value.lower() for p in patterns):
                    category = cat_name
                    break

            # Check IP address pattern
            if category == "unknown" and ip_regex.match(value.strip()):
                category = "IP_ADDR"

            s["category"] = category
            categorized.append(s)

        return categorized

    def _identify_suspicious_functions(
        self,
        functions: List[Dict[str, Any]],
        imports: List[Dict[str, Any]],
    ) -> List[str]:
        """Identify functions that should be decompiled for security review.

        Prioritizes functions tagged as suspicious, crypto, or network,
        plus functions that call dangerous imports.
        """
        dangerous_imports = {
            "VirtualAllocEx", "WriteProcessMemory", "CreateRemoteThread",
            "OpenProcess", "ReadProcessMemory", "VirtualProtectEx",
            "CreateProcess", "ShellExecute", "WinExec",
            "WSAStartup", "socket", "connect", "send", "recv",
            "InternetOpen", "InternetConnect", "HttpOpenRequest",
            "URLDownloadToFile", "WinHttpOpen",
            "CryptEncrypt", "CryptDecrypt", "CryptDeriveKey",
            "RegOpenKey", "RegSetValue", "RegCreateKey",
            "CreateService", "StartService",
        }

        # Check import table for dangerous symbols
        has_dangerous_imports = any(
            imp.get("name", "") in dangerous_imports for imp in imports
        )

        # Prioritize tagged functions
        priority_funcs = []
        for func in functions:
            name = func.get("name", "")
            tags = func.get("tags", [])

            if any(t in tags for t in ("suspicious", "crypto", "network", "evasion")):
                priority_funcs.append(name)

        # Add functions with suspicious names
        for func in functions:
            name = func.get("name", "")
            name_lower = name.lower()
            if any(kw in name_lower for kw in ("main", "entry", "start", "init")):
                if name not in priority_funcs:
                    priority_funcs.append(name)

        # If dangerous imports found, add the first few non-external functions
        if has_dangerous_imports:
            for func in functions[:30]:
                name = func.get("name", "")
                if not func.get("is_external", False) and name not in priority_funcs:
                    priority_funcs.append(name)

        return priority_funcs

    def _generate_risk_indicators(self, result: GhidraAnalysisResult) -> List[Dict[str, Any]]:
        """Generate risk indicators from analysis results.

        Scans functions, strings, imports, and sections for security-relevant
        patterns and produces structured risk findings with severity ratings.
        """
        indicators: List[RiskIndicator] = []

        # Check for process injection capability
        injection_imports = {
            "VirtualAllocEx", "WriteProcessMemory", "CreateRemoteThread",
        }
        found_injection = [
            imp for imp in result.imports
            if imp.get("name") in injection_imports
        ]
        if found_injection:
            indicators.append(RiskIndicator(
                severity="critical",
                category="process_injection",
                description="Process injection capability detected",
                evidence=", ".join(imp["name"] for imp in found_injection),
                recommendation="Investigate functions using these APIs for malicious intent",
            ))

        # Check for hardcoded secrets
        for s in result.strings:
            if s.get("category") == "API_KEY":
                indicators.append(RiskIndicator(
                    severity="high",
                    category="hardcoded_secret",
                    description=f"Hardcoded API key found: {s['value'][:30]}...",
                    address=s.get("address"),
                    evidence=s["value"],
                    recommendation="Remove hardcoded credentials; use environment variables or secret management",
                ))

        # Check for command execution
        cmd_strings = [
            s for s in result.strings
            if s.get("category") == "SUSPICIOUS"
        ]
        if cmd_strings:
            indicators.append(RiskIndicator(
                severity="high",
                category="command_execution",
                description=f"Command execution strings found ({len(cmd_strings)})",
                evidence=", ".join(s["value"][:50] for s in cmd_strings[:5]),
                recommendation="Verify these strings are used for legitimate purposes",
            ))

        # Check for network C2 indicators
        url_strings = [s for s in result.strings if s.get("category") == "URL"]
        if url_strings:
            indicators.append(RiskIndicator(
                severity="medium",
                category="network_communication",
                description=f"URL strings found ({len(url_strings)})",
                evidence=", ".join(s["value"][:60] for s in url_strings[:5]),
                recommendation="Review URLs for command-and-control indicators",
            ))

        # Check for crypto usage
        crypto_funcs = [
            f for f in result.functions
            if "crypto" in f.get("tags", [])
        ]
        if crypto_funcs:
            indicators.append(RiskIndicator(
                severity="medium",
                category="crypto_usage",
                description=f"Cryptography functions detected ({len(crypto_funcs)})",
                evidence=", ".join(f["name"] for f in crypto_funcs[:5]),
                recommendation="Verify crypto implementation is not weakened or custom",
            ))

        # Check for writable + executable sections
        wx_sections = [
            s for s in result.sections
            if "w" in s.get("permissions", "") and "x" in s.get("permissions", "")
        ]
        if wx_sections:
            indicators.append(RiskIndicator(
                severity="high",
                category="wx_memory",
                description=f"Writable and executable memory sections found ({len(wx_sections)})",
                evidence=", ".join(s["name"] for s in wx_sections),
                recommendation="Investigate why sections are both writable and executable",
            ))

        # Check for NX bit disabled
        metadata = result.metadata
        if metadata.get("nx_bit") is False:
            indicators.append(RiskIndicator(
                severity="high",
                category="nx_disabled",
                description="NX (No-Execute) bit is disabled",
                recommendation="Enable NX bit for stack/heap memory protection",
            ))

        # Check for missing stack canaries
        if metadata.get("canary") is False:
            indicators.append(RiskIndicator(
                severity="medium",
                category="no_canary",
                description="Stack canaries not detected",
                recommendation="Compile with -fstack-protector-strong",
            ))

        # Check for no PIE
        if metadata.get("pie") is False:
            indicators.append(RiskIndicator(
                severity="low",
                category="no_pie",
                description="Binary is not position-independent (no PIE)",
                recommendation="Compile with -fPIE -pie for ASLR support",
            ))

        # Check for mutex names (potential malware indicator)
        mutex_strings = [s for s in result.strings if s.get("category") == "MUTEX"]
        if mutex_strings:
            indicators.append(RiskIndicator(
                severity="medium",
                category="mutex",
                description=f"Named mutex objects found ({len(mutex_strings)})",
                evidence=", ".join(s["value"][:40] for s in mutex_strings[:5]),
                recommendation="Check for known malware mutex names",
            ))

        # Sort by severity
        severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        indicators.sort(key=lambda i: severity_order.get(i.severity, 4))

        return [ind.to_dict() for ind in indicators]
