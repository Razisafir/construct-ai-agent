"""Ghidra Tool — binary analysis, decompilation, and vulnerability detection.

Requires Ghidra to be installed separately at /opt/ghidra (or custom path).
All operations run via Ghidra's analyzeHeadless in non-interactive mode.

This tool provides a Python interface to NSA Ghidra for:
- Binary analysis and function enumeration
- Decompilation to C pseudocode
- Vulnerability detection via dangerous function analysis
- Binary comparison and diffing
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class GhidraTool:
    """Interface to NSA Ghidra for binary analysis and reverse engineering."""

    DEFAULT_PATHS: List[str] = [
        "/opt/ghidra",
        "/usr/local/ghidra",
        os.path.expanduser("~/ghidra"),
        "/Applications/ghidra",
    ]

    # Known dangerous functions for vulnerability analysis
    DANGEROUS_FUNCTIONS: set[str] = {
        "strcpy",
        "strcat",
        "sprintf",
        "gets",
        "scanf",
        "sscanf",
        "system",
        "exec",
        "execve",
        "execl",
        "popen",
        "eval",
        "malloc",
        "realloc",
        "free",
        "memcpy",
        "memmove",
        "strncpy",
        "strncat",
        "snprintf",
        "vsprintf",
        "vprintf",
        "strlen",
        "wcscpy",
        "wcscat",
    }

    SUSPICIOUS_STRINGS: List[str] = [
        "password",
        "secret",
        "key",
        "admin",
        "root",
        "backdoor",
        "exploit",
        "payload",
        "hack",
        "CVE",
        "vulnerability",
        "attack",
        "bypass",
        "shell",
        "cmd.exe",
        "/bin/sh",
    ]

    def __init__(self, ghidra_path: Optional[str] = None) -> None:
        """Initialize Ghidra tool, auto-detecting installation path.

        Parameters
        ----------
        ghidra_path:
            Explicit path to Ghidra installation. If *None*, common
            installation locations are searched automatically.
        """
        self.ghidra_path = self._find_ghidra(ghidra_path)
        self._available = self.ghidra_path is not None

        if self._available:
            self.analyze_headless = os.path.join(
                self.ghidra_path, "support", "analyzeHeadless"
            )
            logger.info("Ghidra found at %s", self.ghidra_path)
        else:
            logger.warning(
                "Ghidra not found — install at /opt/ghidra or set ghidra_path"
            )

    def is_available(self) -> bool:
        """Check if Ghidra is installed and accessible.

        Returns
        -------
        bool
            *True* if the ``analyzeHeadless`` script was found.
        """
        return self._available

    def analyze_binary(
        self, binary_path: str, project_name: str = "construct_analysis"
    ) -> Dict[str, Any]:
        """Analyze a binary and return structured results.

        Imports the binary into a temporary Ghidra project, runs auto-analysis,
        and exports function listings, strings, sections, and metadata.

        Parameters
        ----------
        binary_path:
            Absolute path to the binary file to analyze.
        project_name:
            Name for the temporary Ghidra project.

        Returns
        -------
        dict
            Structured result with keys:
            - ``success`` (bool)
            - ``functions`` (list[dict]) — name, address, size, entry_point
            - ``strings`` (list[dict]) — value, address, length
            - ``sections`` (list[dict]) — name, start, end, permissions
            - ``imports`` (list[str]) — imported libraries/symbols
            - ``metadata`` (dict) — format, architecture, compiler, etc.
            - ``output_path`` (str|None) — path to exported JSON
            - ``error`` (str|None)
        """
        logger.info("analyze_binary: %s", binary_path)

        if not self._available:
            return {"success": False, "error": "Ghidra not available", "functions": [], "strings": [], "sections": [], "imports": [], "metadata": {}, "output_path": None}

        abs_binary = os.path.abspath(os.path.expanduser(binary_path))
        if not os.path.isfile(abs_binary):
            return {"success": False, "error": f"Binary not found: {binary_path}", "functions": [], "strings": [], "sections": [], "imports": [], "metadata": {}, "output_path": None}

        # Create temporary project directory
        temp_dir = tempfile.mkdtemp(prefix="ghidra_analysis_")
        project_dir = os.path.join(temp_dir, "projects")
        os.makedirs(project_dir, exist_ok=True)

        export_script = self._get_script_path("ghidra_export.py")
        output_json = os.path.join(temp_dir, "analysis_result.json")

        try:
            result = self._run_headless(
                project_dir=project_dir,
                project_name=project_name,
                script_name=export_script,
                script_params=[
                    "-scriptPath",
                    os.path.dirname(export_script),
                    "-postScript",
                    "ghidra_export.py",
                    output_json,
                ],
                import_path=abs_binary,
                timeout=600,
            )

            if result.returncode != 0:
                logger.error("Ghidra analysis failed: %s", result.stderr[-2000:])
                return {
                    "success": False,
                    "error": f"Ghidra analysis exited with code {result.returncode}. stderr: {result.stderr[-1000:]}",
                    "functions": [],
                    "strings": [],
                    "sections": [],
                    "imports": [],
                    "metadata": {},
                    "output_path": None,
                }

            # Read the exported JSON
            if os.path.exists(output_json):
                with open(output_json, "r", encoding="utf-8") as f:
                    analysis = json.load(f)
                analysis["success"] = True
                analysis["output_path"] = output_json
                analysis["error"] = None
                return analysis
            else:
                return {
                    "success": False,
                    "error": "Analysis completed but no output JSON was produced",
                    "functions": [],
                    "strings": [],
                    "sections": [],
                    "imports": [],
                    "metadata": {},
                    "output_path": None,
                }

        except subprocess.TimeoutExpired:
            return {"success": False, "error": "Ghidra analysis timed out (600s)", "functions": [], "strings": [], "sections": [], "imports": [], "metadata": {}, "output_path": None}
        except Exception as exc:
            logger.exception("Error during Ghidra analysis")
            return {"success": False, "error": f"Analysis failed: {exc}", "functions": [], "strings": [], "sections": [], "imports": [], "metadata": {}, "output_path": None}
        finally:
            # Clean up temp directory
            try:
                shutil.rmtree(temp_dir, ignore_errors=True)
            except Exception:
                pass

    def decompile_function(
        self, binary_path: str, function_name: str
    ) -> Dict[str, Any]:
        """Decompile a specific function to C pseudocode.

        Parameters
        ----------
        binary_path:
            Absolute path to the binary file.
        function_name:
            Name of the function to decompile (e.g., ``"main"``).

        Returns
        -------
        dict
            Structured result with keys:
            - ``success`` (bool)
            - ``function_name`` (str)
            - ``c_code`` (str|None) — decompiled C pseudocode
            - ``address`` (str|None) — function entry address
            - ``signature`` (str|None) — function signature
            - ``error`` (str|None)
        """
        logger.info("decompile_function: %s :: %s", binary_path, function_name)

        if not self._available:
            return {"success": False, "function_name": function_name, "c_code": None, "address": None, "signature": None, "error": "Ghidra not available"}

        abs_binary = os.path.abspath(os.path.expanduser(binary_path))
        if not os.path.isfile(abs_binary):
            return {"success": False, "function_name": function_name, "c_code": None, "address": None, "signature": None, "error": f"Binary not found: {binary_path}"}

        temp_dir = tempfile.mkdtemp(prefix="ghidra_decompile_")
        project_dir = os.path.join(temp_dir, "projects")
        os.makedirs(project_dir, exist_ok=True)

        decompile_script = self._get_script_path("ghidra_decompile.py")
        output_json = os.path.join(temp_dir, "decompile_result.json")

        try:
            result = self._run_headless(
                project_dir=project_dir,
                project_name="construct_decompile",
                script_name=decompile_script,
                script_params=[
                    "-scriptPath",
                    os.path.dirname(decompile_script),
                    "-postScript",
                    "ghidra_decompile.py",
                    function_name,
                    output_json,
                ],
                import_path=abs_binary,
                timeout=300,
            )

            if result.returncode != 0:
                return {
                    "success": False,
                    "function_name": function_name,
                    "c_code": None,
                    "address": None,
                    "signature": None,
                    "error": f"Ghidra decompilation exited with code {result.returncode}",
                }

            if os.path.exists(output_json):
                with open(output_json, "r", encoding="utf-8") as f:
                    decomp = json.load(f)
                decomp["success"] = decomp.get("c_code") is not None
                return decomp
            else:
                return {
                    "success": False,
                    "function_name": function_name,
                    "c_code": None,
                    "address": None,
                    "signature": None,
                    "error": "Decompilation completed but no output was produced",
                }

        except subprocess.TimeoutExpired:
            return {"success": False, "function_name": function_name, "c_code": None, "address": None, "signature": None, "error": "Ghidra decompilation timed out (300s)"}
        except Exception as exc:
            logger.exception("Error during Ghidra decompilation")
            return {"success": False, "function_name": function_name, "c_code": None, "address": None, "signature": None, "error": f"Decompilation failed: {exc}"}
        finally:
            try:
                shutil.rmtree(temp_dir, ignore_errors=True)
            except Exception:
                pass

    def find_vulnerabilities(self, binary_path: str) -> Dict[str, Any]:
        """Analyze binary and report potential vulnerabilities.

        Scans for dangerous function calls, suspicious strings, and
        other indicators of potential security issues.

        Parameters
        ----------
        binary_path:
            Absolute path to the binary file.

        Returns
        -------
        dict
            Structured result with keys:
            - ``success`` (bool)
            - ``dangerous_functions`` (list[dict]) — func_name, address, severity
            - ``suspicious_strings`` (list[dict]) — string, address, context
            - ``severity_score`` (int) — 0-100 risk score
            - ``recommendations`` (list[str]) — actionable security advice
            - ``error`` (str|None)
        """
        logger.info("find_vulnerabilities: %s", binary_path)

        # Run full analysis first
        analysis = self.analyze_binary(binary_path)
        if not analysis.get("success"):
            return {
                "success": False,
                "dangerous_functions": [],
                "suspicious_strings": [],
                "severity_score": 0,
                "recommendations": [],
                "error": analysis.get("error", "Analysis failed"),
            }

        dangerous: List[Dict[str, Any]] = []
        suspicious: List[Dict[str, Any]] = []
        recommendations: List[str] = []
        severity_score = 0

        # Check for dangerous functions
        for func in analysis.get("functions", []):
            func_name = func.get("name", "")
            if func_name in self.DANGEROUS_FUNCTIONS:
                severity = "high" if func_name in {"strcpy", "strcat", "sprintf", "gets", "system", "exec"} else "medium"
                dangerous.append(
                    {
                        "function_name": func_name,
                        "address": func.get("entry_point", "unknown"),
                        "severity": severity,
                    }
                )
                if severity == "high":
                    severity_score += 15
                else:
                    severity_score += 5

        # Check for suspicious strings
        for s in analysis.get("strings", []):
            str_val = s.get("value", "").lower()
            for susp in self.SUSPICIOUS_STRINGS:
                if susp.lower() in str_val:
                    suspicious.append(
                        {
                            "string": s["value"],
                            "address": s.get("address", "unknown"),
                            "context": susp,
                        }
                    )
                    severity_score += 3
                    break

        # Cap score at 100
        severity_score = min(100, severity_score)

        # Generate recommendations
        if dangerous:
            high_risk = [d for d in dangerous if d["severity"] == "high"]
            if high_risk:
                recommendations.append(
                    f"Found {len(high_risk)} high-risk dangerous function(s): "
                    f"{', '.join(d['function_name'] for d in high_risk)}. "
                    "Replace with safer alternatives (e.g., strncpy, strncat, snprintf)."
                )
            recommendations.append(
                "Review all calls to dangerous functions for buffer overflow vulnerabilities."
            )

        if suspicious:
            recommendations.append(
                f"Found {len(suspicious)} suspicious string(s) in the binary. "
                "These may indicate hardcoded credentials or malicious intent."
            )

        if not dangerous and not suspicious:
            recommendations.append("No obvious vulnerabilities detected via static analysis.")

        if analysis.get("metadata", {}).get("nx_bit") is False:
            recommendations.append("NX bit is disabled — stack/heap memory is executable.")
            severity_score += 10

        if analysis.get("metadata", {}).get("canary") is False:
            recommendations.append("Stack canaries not detected — stack overflow attacks may succeed.")
            severity_score += 10

        severity_score = min(100, severity_score)

        return {
            "success": True,
            "dangerous_functions": dangerous,
            "suspicious_strings": suspicious,
            "severity_score": severity_score,
            "recommendations": recommendations,
            "error": None,
        }

    def compare_binaries(
        self, binary_a: str, binary_b: str
    ) -> Dict[str, Any]:
        """Compare two binaries and report differences.

        Analyzes both binaries and produces a diff of functions,
        strings, and metadata.

        Parameters
        ----------
        binary_a:
            Path to the first binary.
        binary_b:
            Path to the second binary.

        Returns
        -------
        dict
            Structured result with keys:
            - ``success`` (bool)
            - ``functions_only_in_a`` (list[str])
            - ``functions_only_in_b`` (list[str])
            - ``functions_common`` (list[str])
            - ``strings_only_in_a`` (list[str])
            - ``strings_only_in_b`` (list[str])
            - ``metadata_diff`` (dict) — key-by-key differences
            - ``similarity_score`` (float) — 0.0 to 1.0
            - ``error`` (str|None)
        """
        logger.info("compare_binaries: %s vs %s", binary_a, binary_b)

        if not self._available:
            return {"success": False, "error": "Ghidra not available", "functions_only_in_a": [], "functions_only_in_b": [], "functions_common": [], "strings_only_in_a": [], "strings_only_in_b": [], "metadata_diff": {}, "similarity_score": 0.0}

        abs_a = os.path.abspath(os.path.expanduser(binary_a))
        abs_b = os.path.abspath(os.path.expanduser(binary_b))

        if not os.path.isfile(abs_a):
            return {"success": False, "error": f"Binary not found: {binary_a}", "functions_only_in_a": [], "functions_only_in_b": [], "functions_common": [], "strings_only_in_a": [], "strings_only_in_b": [], "metadata_diff": {}, "similarity_score": 0.0}
        if not os.path.isfile(abs_b):
            return {"success": False, "error": f"Binary not found: {binary_b}", "functions_only_in_a": [], "functions_only_in_b": [], "functions_common": [], "strings_only_in_a": [], "strings_only_in_b": [], "metadata_diff": {}, "similarity_score": 0.0}

        # Analyze both binaries
        analysis_a = self.analyze_binary(abs_a, project_name="compare_a")
        analysis_b = self.analyze_binary(abs_b, project_name="compare_b")

        if not analysis_a.get("success") or not analysis_b.get("success"):
            err = analysis_a.get("error") or analysis_b.get("error", "Unknown error")
            return {"success": False, "error": err, "functions_only_in_a": [], "functions_only_in_b": [], "functions_common": [], "strings_only_in_a": [], "strings_only_in_b": [], "metadata_diff": {}, "similarity_score": 0.0}

        funcs_a = {f["name"] for f in analysis_a.get("functions", [])}
        funcs_b = {f["name"] for f in analysis_b.get("functions", [])}

        strings_a = {s["value"] for s in analysis_a.get("strings", [])}
        strings_b = {s["value"] for s in analysis_b.get("strings", [])}

        # Compute similarity score
        all_funcs = funcs_a | funcs_b
        all_strings = strings_a | strings_b

        func_sim = len(funcs_a & funcs_b) / len(all_funcs) if all_funcs else 1.0
        str_sim = len(strings_a & strings_b) / len(all_strings) if all_strings else 1.0
        similarity = (func_sim + str_sim) / 2.0

        # Metadata diff
        meta_a = analysis_a.get("metadata", {})
        meta_b = analysis_b.get("metadata", {})
        meta_diff: Dict[str, Any] = {}
        all_keys = set(meta_a.keys()) | set(meta_b.keys())
        for key in sorted(all_keys):
            val_a = meta_a.get(key)
            val_b = meta_b.get(key)
            if val_a != val_b:
                meta_diff[key] = {"a": val_a, "b": val_b}

        return {
            "success": True,
            "functions_only_in_a": sorted(funcs_a - funcs_b),
            "functions_only_in_b": sorted(funcs_b - funcs_a),
            "functions_common": sorted(funcs_a & funcs_b),
            "strings_only_in_a": sorted(strings_a - strings_b),
            "strings_only_in_b": sorted(strings_b - strings_a),
            "metadata_diff": meta_diff,
            "similarity_score": round(similarity, 4),
            "error": None,
        }

    # -- Internal helpers -----------------------------------------------------

    def _find_ghidra(self, explicit_path: Optional[str]) -> Optional[str]:
        """Auto-detect Ghidra installation path.

        Parameters
        ----------
        explicit_path:
            User-provided path to check first.

        Returns
        -------
        Optional[str]
            Path to Ghidra installation, or *None* if not found.
        """
        if explicit_path and os.path.isdir(explicit_path):
            headless = os.path.join(explicit_path, "support", "analyzeHeadless")
            if os.path.exists(headless):
                return explicit_path

        for path in self.DEFAULT_PATHS:
            headless = os.path.join(path, "support", "analyzeHeadless")
            if os.path.exists(headless):
                return path

        # Also try to find via PATH
        headless_path = shutil.which("analyzeHeadless")
        if headless_path:
            # analyzeHeadless is in <ghidra>/support/
            return os.path.dirname(os.path.dirname(headless_path))

        return None

    def _run_headless(
        self,
        project_dir: str,
        project_name: str,
        script_name: str,
        script_params: List[str],
        import_path: Optional[str] = None,
        timeout: int = 300,
    ) -> subprocess.CompletedProcess:
        """Run Ghidra analyzeHeadless with given parameters.

        Parameters
        ----------
        project_dir:
            Directory for the Ghidra project.
        project_name:
            Name of the Ghidra project.
        script_name:
            Path to the Ghidra script to run.
        script_params:
            Additional parameters to pass to the script.
        import_path:
            Binary file to import for analysis.
        timeout:
            Maximum execution time in seconds.

        Returns
        -------
        subprocess.CompletedProcess
            The completed process result.

        Raises
        ------
        subprocess.TimeoutExpired
            If the analysis exceeds the timeout.
        """
        cmd: List[str] = [
            self.analyze_headless,
            project_dir,
            project_name,
            "-import",
            import_path,
            "-deleteProject",
        ]

        # Add script parameters
        cmd.extend(script_params)

        logger.info(
            "Running Ghidra headless: %s (timeout=%ds)",
            " ".join(cmd[:8]) + " ...",
            timeout,
        )

        env = os.environ.copy()
        # Ensure Ghidra has enough memory
        env["_JAVA_OPTIONS"] = "-Xmx4g"

        start = time.time()
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
        )
        elapsed = time.time() - start

        logger.info(
            "Ghidra headless completed in %.1fs (exit_code=%d)",
            elapsed,
            result.returncode,
        )

        return result

    def _get_script_path(self, script_name: str) -> str:
        """Resolve the absolute path to a Ghidra script.

        Scripts are expected to be in the same directory as this module.

        Parameters
        ----------
        script_name:
            Name of the script file (e.g., ``"ghidra_export.py"``).

        Returns
        -------
        str
            Absolute path to the script file.
        """
        module_dir = os.path.dirname(os.path.abspath(__file__))
        return os.path.join(module_dir, script_name)
