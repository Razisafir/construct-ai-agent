"""Tests for AgentShield security scanning and grading."""

import os
import re
import ast
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from unittest.mock import MagicMock, patch, Mock

import pytest


# ============================================================================
# AgentShield Tests
# ============================================================================


class TestAgentShield:
    """Test AgentShield security scanner for detecting and fixing vulnerabilities."""

    @pytest.fixture
    def shield(self):
        """Create an AgentShield instance with security rules."""
        class MockAgentShield:
            def __init__(self):
                self.rules = {
                    "hardcoded_secret": {
                        "pattern": r'(api[_-]?key|password|secret|token)\s*[=:]\s*["\'][^"\']{8,}["\']',
                        "severity": "high",
                        "category": "secrets",
                    },
                    "eval_usage": {
                        "pattern": r'\beval\s*\(',
                        "severity": "critical",
                        "category": "code-injection",
                    },
                    "exec_usage": {
                        "pattern": r'\bexec\s*\(',
                        "severity": "critical",
                        "category": "code-injection",
                    },
                    "shell_true": {
                        "pattern": r'shell\s*=\s*True',
                        "severity": "high",
                        "category": "command-injection",
                    },
                    "sql_injection": {
                        "pattern": r'execute\s*\(\s*["\'].*%s',
                        "severity": "critical",
                        "category": "sql-injection",
                    },
                    "pickle_load": {
                        "pattern": r'pickle\.loads?\s*\(',
                        "severity": "medium",
                        "category": "deserialization",
                    },
                    "yaml_load": {
                        "pattern": r'yaml\.load\s*\(',
                        "severity": "medium",
                        "category": "deserialization",
                    },
                    "debug_true": {
                        "pattern": r'DEBUG\s*=\s*True',
                        "severity": "low",
                        "category": "configuration",
                    },
                    "hardcoded_ip": {
                        "pattern": r'\b(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b',
                        "severity": "low",
                        "category": "configuration",
                    },
                }
                self.grade_weights = {
                    "critical": 10,
                    "high": 5,
                    "medium": 2,
                    "low": 1,
                }

            def scan_code(self, code: str, filename: str = "<string>") -> List[Dict[str, Any]]:
                """Scan code for security issues."""
                findings = []
                lines = code.split("\n")

                for line_num, line in enumerate(lines, 1):
                    for rule_name, rule in self.rules.items():
                        if re.search(rule["pattern"], line, re.IGNORECASE):
                            findings.append({
                                "rule": rule_name,
                                "severity": rule["severity"],
                                "category": rule["category"],
                                "line": line_num,
                                "column": line.find(re.search(rule["pattern"], line, re.IGNORECASE).group()) + 1,
                                "message": f"Found {rule_name}: {line.strip()}",
                                "code": line.strip(),
                            })

                return findings

            def scan_directory(self, directory: Path) -> List[Dict[str, Any]]:
                """Recursively scan a directory for security issues."""
                all_findings = []
                for file_path in directory.rglob("*"):
                    if file_path.is_file() and file_path.suffix in {".py", ".js", ".ts", ".sh", ".env"}:
                        try:
                            code = file_path.read_text()
                            findings = self.scan_code(code, str(file_path))
                            for finding in findings:
                                finding["file"] = str(file_path)
                            all_findings.extend(findings)
                        except (UnicodeDecodeError, PermissionError):
                            continue
                return all_findings

            def calculate_grade(self, findings: List[Dict[str, Any]]) -> Tuple[str, int]:
                """Calculate security grade based on findings."""
                score = 100
                for finding in findings:
                    weight = self.grade_weights.get(finding["severity"], 1)
                    score -= weight

                if score >= 90:
                    return "A", score
                elif score >= 80:
                    return "B", score
                elif score >= 70:
                    return "C", score
                elif score >= 60:
                    return "D", score
                else:
                    return "F", score

            def auto_fix(self, code: str, findings: List[Dict[str, Any]]) -> str:
                """Automatically fix safe security issues."""
                fixed = code
                for finding in findings:
                    if finding["rule"] == "debug_true":
                        fixed = re.sub(r'DEBUG\s*=\s*True', 'DEBUG = False', fixed)
                    elif finding["rule"] == "shell_true":
                        fixed = re.sub(r'shell\s*=\s*True', 'shell = False', fixed)
                    elif finding["rule"] == "eval_usage":
                        # Replace eval with ast.literal_eval where possible
                        fixed = re.sub(
                            r'eval\s*\(([^)]+)\)',
                            r'ast.literal_eval(\1)',
                            fixed,
                        )
                    elif finding["rule"] == "yaml_load":
                        fixed = re.sub(
                            r'yaml\.load\s*\(([^)]+)\)',
                            r'yaml.safe_load(\1)',
                            fixed,
                        )
                return fixed

            def get_summary(self, findings: List[Dict[str, Any]]) -> Dict[str, Any]:
                """Get summary statistics of findings."""
                by_severity = {}
                by_category = {}
                for f in findings:
                    sev = f["severity"]
                    cat = f["category"]
                    by_severity[sev] = by_severity.get(sev, 0) + 1
                    by_category[cat] = by_category.get(cat, 0) + 1

                grade, score = self.calculate_grade(findings)
                return {
                    "total": len(findings),
                    "by_severity": by_severity,
                    "by_category": by_category,
                    "grade": grade,
                    "score": score,
                }

        return MockAgentShield()

    # --- detects_hardcoded_api_key ---

    def test_detects_hardcoded_api_key(self, shield):
        """Test detection of hardcoded API keys."""
        code = """
API_KEY = "sk-1234567890abcdef"
client = OpenAI(api_key="sk-production-key-12345")
"""
        findings = shield.scan_code(code)
        api_key_findings = [f for f in findings if "secret" in f["category"] or "hardcoded" in f["rule"]]
        assert len(api_key_findings) >= 1

    def test_detects_hardcoded_password(self, shield):
        """Test detection of hardcoded passwords."""
        code = """
DB_PASSWORD = "SuperSecret123!"
"""
        findings = shield.scan_code(code)
        password_findings = [f for f in findings if "password" in f["rule"] or "secret" in f["category"]]
        assert len(password_findings) >= 1

    def test_detects_hardcoded_token(self, shield):
        """Test detection of hardcoded tokens."""
        code = """
AUTH_TOKEN = "Bearer eyJhbGciOiJIUzI1NiIs"
"""
        findings = shield.scan_code(code)
        assert len([f for f in findings if "token" in f["rule"]]) >= 1

    # --- detects_eval_usage ---

    def test_detects_eval_usage(self, shield):
        """Test detection of eval() usage."""
        code = """
result = eval(user_input)
"""
        findings = shield.scan_code(code)
        eval_findings = [f for f in findings if f["rule"] == "eval_usage"]
        assert len(eval_findings) == 1
        assert eval_findings[0]["severity"] == "critical"

    def test_detects_exec_usage(self, shield):
        """Test detection of exec() usage."""
        code = """
exec(malicious_code)
"""
        findings = shield.scan_code(code)
        exec_findings = [f for f in findings if f["rule"] == "exec_usage"]
        assert len(exec_findings) == 1

    # --- detects_shell_true ---

    def test_detects_shell_true(self, shield):
        """Test detection of shell=True."""
        code = """
import subprocess
result = subprocess.run(cmd, shell=True)
"""
        findings = shield.scan_code(code)
        shell_findings = [f for f in findings if f["rule"] == "shell_true"]
        assert len(shell_findings) == 1
        assert shell_findings[0]["severity"] == "high"

    # --- scan_directory ---

    def test_scan_directory_finds_issues(self, shield, temp_dir: Path):
        """Test scanning a directory for security issues."""
        # Create files with security issues
        (temp_dir / "config.py").write_text("""
API_KEY = "sk-test-12345678"
DEBUG = True
""")
        (temp_dir / "utils.py").write_text("""
import subprocess
import os

def run_command(cmd):
    return subprocess.run(cmd, shell=True)
""")
        (temp_dir / "parser.py").write_text("""
import yaml

def load_config(path):
    with open(path) as f:
        return yaml.load(f)
""")

        findings = shield.scan_directory(temp_dir)
        assert len(findings) >= 3  # API_KEY, shell=True, yaml.load, DEBUG

        # Check findings are associated with correct files
        files_with_issues = set(f.get("file", "") for f in findings)
        assert any("config.py" in f for f in files_with_issues)
        assert any("utils.py" in f for f in files_with_issues)

    def test_scan_directory_skips_binary(self, shield, temp_dir: Path):
        """Test that binary files are skipped."""
        # Create a binary file
        (temp_dir / "binary.dat").write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR")
        findings = shield.scan_directory(temp_dir)
        # Should not crash and should find nothing in the binary file
        assert not any("binary.dat" in f.get("file", "") for f in findings)

    def test_scan_directory_empty(self, shield, temp_dir: Path):
        """Test scanning an empty directory."""
        findings = shield.scan_directory(temp_dir)
        assert len(findings) == 0

    # --- grade_calculation ---

    def test_grade_calculation_a(self, shield):
        """Test grade A (90+ score)."""
        findings = [
            {"severity": "low"},
        ]
        grade, score = shield.calculate_grade(findings)
        assert grade == "A"
        assert score >= 90

    def test_grade_calculation_f(self, shield):
        """Test grade F (< 60 score)."""
        findings = [
            {"severity": "critical"} for _ in range(5)
        ] + [
            {"severity": "high"} for _ in range(5)
        ]
        grade, score = shield.calculate_grade(findings)
        assert grade == "F"
        assert score < 60

    def test_grade_calculation_weights(self, shield):
        """Test that severity weights are applied correctly."""
        # 1 critical = -10
        grade, score = shield.calculate_grade([{"severity": "critical"}])
        assert score == 90
        assert grade == "A"

        # 2 critical = -20
        grade, score = shield.calculate_grade([{"severity": "critical"} for _ in range(2)])
        assert score == 80
        assert grade == "B"

        # 1 high = -5
        grade, score = shield.calculate_grade([{"severity": "high"}])
        assert score == 95
        assert grade == "A"

        # 1 medium = -2
        grade, score = shield.calculate_grade([{"severity": "medium"}])
        assert score == 98
        assert grade == "A"

    def test_grade_calculation_empty(self, shield):
        """Test grade with no findings."""
        grade, score = shield.calculate_grade([])
        assert grade == "A"
        assert score == 100

    # --- auto_fix ---

    def test_auto_fix_debug_true(self, shield):
        """Test auto-fix for DEBUG = True."""
        code = "DEBUG = True\n"
        findings = shield.scan_code(code)
        fixed = shield.auto_fix(code, findings)
        assert "DEBUG = False" in fixed
        assert "DEBUG = True" not in fixed

    def test_auto_fix_shell_true(self, shield):
        """Test auto-fix for shell=True."""
        code = "result = subprocess.run(cmd, shell=True)\n"
        findings = shield.scan_code(code)
        fixed = shield.auto_fix(code, findings)
        assert "shell = False" in fixed
        assert "shell = True" not in fixed

    def test_auto_fix_yaml_load(self, shield):
        """Test auto-fix for yaml.load."""
        code = "data = yaml.load(file)\n"
        findings = shield.scan_code(code)
        fixed = shield.auto_fix(code, findings)
        assert "yaml.safe_load" in fixed
        assert "yaml.load(" not in fixed

    def test_auto_fix_preserves_other_code(self, shield):
        """Test that auto-fix preserves unaffected code."""
        code = """
# Some config
API_KEY = os.environ.get("API_KEY")
DEBUG = True
# Other settings
TIMEOUT = 30
"""
        findings = shield.scan_code(code)
        fixed = shield.auto_fix(code, findings)
        assert "TIMEOUT = 30" in fixed
        assert "os.environ.get" in fixed
        assert "DEBUG = False" in fixed

    def test_auto_fix_only_safe_changes(self, shield):
        """Test that auto-fix only applies safe, automated changes."""
        code = """
API_KEY = "sk-secret-12345"
eval(user_input)
"""
        findings = shield.scan_code(code)
        fixed = shield.auto_fix(code, findings)

        # Hardcoded secrets should NOT be auto-fixed (requires manual review)
        assert "API_KEY" in fixed  # Still present
        # eval should be replaced where possible
        # but the result may not be perfect for all cases

    # --- summary ---

    def test_get_summary(self, shield):
        """Test getting a summary of findings."""
        findings = [
            {"severity": "critical", "category": "code-injection"},
            {"severity": "high", "category": "secrets"},
            {"severity": "high", "category": "command-injection"},
            {"severity": "medium", "category": "deserialization"},
        ]
        summary = shield.get_summary(findings)

        assert summary["total"] == 4
        assert summary["by_severity"]["critical"] == 1
        assert summary["by_severity"]["high"] == 2
        assert summary["by_severity"]["medium"] == 1
        assert summary["by_category"]["code-injection"] == 1
        assert summary["by_category"]["secrets"] == 1
        assert summary["grade"] in ["A", "B", "C", "D", "F"]

    # --- edge_cases ---

    def test_empty_code(self, shield):
        """Test scanning empty code."""
        findings = shield.scan_code("")
        assert len(findings) == 0

    def test_code_with_no_issues(self, shield):
        """Test scanning clean code."""
        code = """
import os

def safe_function():
    value = os.environ.get("VALUE")
    return value
"""
        findings = shield.scan_code(code)
        # Should find minimal or no issues
        assert len(findings) <= 2

    def test_multiple_issues_same_line(self, shield):
        """Test detecting multiple issues on the same line."""
        code = 'result = eval(input()); subprocess.run(cmd, shell=True)\n'
        findings = shield.scan_code(code)
        # Should detect both eval and shell=True
        rules_found = [f["rule"] for f in findings]
        assert "eval_usage" in rules_found
        assert "shell_true" in rules_found

    def test_false_positives_minimal(self, shield):
        """Test that false positives are minimized."""
        code = """
# This is a comment about api keys but not an actual key
# password_policy is just a variable name
# The shell module is imported
"""
        findings = shield.scan_code(code)
        # Should not flag comments as issues
        assert len(findings) == 0
