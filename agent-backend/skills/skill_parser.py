"""
Skill Parser — Convert ANY document into reusable agent skills.

Supported formats:
- .pdf (PyPDF2 + pdfplumber)
- .md, .mdx (direct parse)
- .txt, .rst (text extraction)
- .docx (python-docx)
- .html, .htm (BeautifulSoup)
- .json, .yaml, .yml (structured import)
- .png, .jpg, .jpeg (OCR via pytesseract / easyocr)
- GitHub repo URLs (clone → analyze → extract patterns)
"""

from __future__ import annotations

import os
import re
import json
import time
import shutil
import logging
import tempfile
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from enum import Enum

try:
    import yaml
    _HAS_YAML = True
except ImportError:
    _HAS_YAML = False

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Kimi skill format constants
# ---------------------------------------------------------------------------

# Pattern for Kimi /command syntax (e.g., "/legal-risk-assessment", "/fix-bug")
_KIMI_COMMAND_PATTERN = re.compile(r"^/([a-zA-Z][-a-zA-Z0-9]*)(?:\s+|$)")

# Pattern to detect Kimi markdown format (frontmatter + structured sections)
_KIMI_FRONTMATTER_PATTERN = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)

# Kimi section headers commonly used in skill definitions
_KIMI_SECTION_HEADERS = {
    "checks performed": "checks",
    "execution steps": "steps",
    "examples": "examples",
    "validation criteria": "validation",
    "best practices": "best_practices",
    "tools required": "tools",
    "related skills": "related_skills",
    "overview": "overview",
}

# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


class SkillCategory(Enum):
    """Classification categories for skills."""

    CODING = "coding"
    DESIGN = "design"
    RESEARCH = "research"
    DEVOPS = "devops"
    SECURITY = "security"
    TESTING = "testing"


@dataclass
class SkillStep:
    """A single executable step within a skill."""

    order: int
    action: str
    description: str
    tool: Optional[str] = None
    parameters: Dict[str, Any] = field(default_factory=dict)
    validation: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "order": self.order,
            "action": self.action,
            "description": self.description,
            "tool": self.tool,
            "parameters": self.parameters,
            "validation": self.validation,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SkillStep":
        return cls(
            order=data.get("order", 0),
            action=data.get("action", ""),
            description=data.get("description", ""),
            tool=data.get("tool"),
            parameters=data.get("parameters", {}),
            validation=data.get("validation"),
        )


@dataclass
class Skill:
    """A reusable skill extracted from a document."""

    name: str
    description: str
    category: SkillCategory
    steps: List[SkillStep]
    tools_needed: List[str] = field(default_factory=list)
    examples: List[str] = field(default_factory=list)
    confidence: float = 0.0
    source_document: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    version: str = "1.0"
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "category": self.category.value,
            "steps": [s.to_dict() for s in self.steps],
            "tools_needed": self.tools_needed,
            "examples": self.examples,
            "confidence": self.confidence,
            "source_document": self.source_document,
            "created_at": self.created_at,
            "version": self.version,
            "tags": self.tags,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Skill":
        category_val = data.get("category", "coding")
        if isinstance(category_val, str):
            category = SkillCategory(category_val)
        else:
            category = SkillCategory.CODING
        return cls(
            name=data["name"],
            description=data.get("description", ""),
            category=category,
            steps=[SkillStep.from_dict(s) for s in data.get("steps", [])],
            tools_needed=data.get("tools_needed", []),
            examples=data.get("examples", []),
            confidence=data.get("confidence", 0.0),
            source_document=data.get("source_document"),
            created_at=data.get("created_at", time.time()),
            version=data.get("version", "1.0"),
            tags=data.get("tags", []),
        )


@dataclass
class ParsedDocument:
    """Intermediate representation of a parsed document."""

    source: str
    text: str
    file_type: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source": self.source,
            "text": self.text[:500] + "..." if len(self.text) > 500 else self.text,
            "file_type": self.file_type,
            "metadata": self.metadata,
            "confidence": self.confidence,
        }


# ---------------------------------------------------------------------------
# Category detection keywords (defined after SkillCategory enum)
# ---------------------------------------------------------------------------

_CATEGORY_KEYWORDS: Dict[SkillCategory, List[str]] = {
    SkillCategory.CODING: [
        "code", "programming", "function", "class", "api", "module",
        "library", "framework", "component", "debug", "refactor",
        "typescript", "javascript", "python", "rust", "go", "java",
        "react", "vue", "angular", "node", "npm", "cargo", "pip",
        "import", "export", "interface", "type", "generic", "async",
        "algorithm", "data structure", "design pattern", "sdk",
    ],
    SkillCategory.DESIGN: [
        "design", "ui", "ux", "layout", "color", "typography",
        "component", "figma", "sketch", "wireframe", "prototype",
        "responsive", "css", "sass", "less", "styled", "theme",
        "icon", "animation", "gradient", "spacing", "grid",
    ],
    SkillCategory.RESEARCH: [
        "research", "analysis", "study", "survey", "data",
        "experiment", "hypothesis", "literature", "review",
        "benchmark", "comparison", "evaluation", "metric",
        "dataset", "model", "training", "inference", "ml",
        "machine learning", "deep learning", "neural", "ai",
    ],
    SkillCategory.DEVOPS: [
        "deploy", "ci/cd", "pipeline", "docker", "kubernetes",
        "k8s", "terraform", "ansible", "aws", "gcp", "azure",
        "cloud", "serverless", "infrastructure", "monitoring",
        "logging", "observability", "helm", "nginx", "load balancer",
        "scaling", "backup", "restore", "migration", "git",
        "github actions", "gitlab ci", "jenkins", "argo",
    ],
    SkillCategory.SECURITY: [
        "security", "auth", "authentication", "authorization",
        "oauth", "jwt", "token", "encryption", "hash", "ssl",
        "tls", "certificate", "vulnerability", "penetration",
        "firewall", "cors", "csp", "xss", "csrf", "injection",
        "sanitize", "validate", "permission", "role", "rbac",
    ],
    SkillCategory.TESTING: [
        "test", "testing", "unit test", "integration test",
        "e2e", "end to end", "jest", "pytest", "mocha",
        "cypress", "playwright", "selenium", "coverage",
        "mock", "stub", "fixture", "assertion", "benchmark",
        "tdd", "bdd", "spec", "scenario", "snapshot",
    ],
}

# Tool names commonly referenced in documents
_TOOL_NAMES: Dict[str, List[str]] = {
    "git": ["git ", "git status", "git commit", "git push", "git pull", "git clone", "git branch"],
    "docker": ["docker ", "dockerfile", "docker-compose", "docker build", "docker run"],
    "npm": ["npm ", "npm install", "npm run", "npm test", "npm publish", "package.json"],
    "cargo": ["cargo ", "cargo build", "cargo test", "cargo run", "cargo.toml"],
    "pip": ["pip ", "pip install", "requirements.txt", "pyproject.toml"],
    "pytest": ["pytest", "py.test"],
    "node": ["node ", "nodejs"],
    "kubernetes": ["kubectl", "k8s", "kubernetes"],
    "terraform": ["terraform ", "tfstate", "tfvars"],
    "aws": ["aws ", "aws cli", "amazon web services"],
    "gcloud": ["gcloud ", "google cloud"],
    "azure": ["az ", "azure cli"],
    "curl": ["curl ", "wget "],
    "ssh": ["ssh ", "scp "],
    "make": ["make ", "makefile", "cmake"],
}

# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------


def _slugify(name: str) -> str:
    """Convert a title to a slug-format name."""
    slug = re.sub(r"[^\w\s-]", "", name.lower())
    slug = re.sub(r"[-\s]+", "_", slug).strip("_")
    return slug[:80]  # cap length


def _detect_category(text: str) -> SkillCategory:
    """Detect skill category from text content using keyword scoring."""
    text_lower = text.lower()
    scores: Dict[SkillCategory, int] = {cat: 0 for cat in SkillCategory}
    for category, keywords in _CATEGORY_KEYWORDS.items():
        for kw in keywords:
            scores[category] += text_lower.count(kw)
    best = max(scores, key=lambda c: scores[c])
    if scores[best] == 0:
        return SkillCategory.CODING
    return best


def _extract_tools(text: str) -> List[str]:
    """Identify tools referenced in the text."""
    text_lower = text.lower()
    found: List[str] = []
    for tool_name, patterns in _TOOL_NAMES.items():
        for pat in patterns:
            if pat.lower() in text_lower:
                found.append(tool_name)
                break
    return sorted(set(found))


def _extract_steps(text: str) -> List[SkillStep]:
    """Extract numbered steps from text using regex heuristics."""
    steps: List[SkillStep] = []

    # Pattern 1: Numbered lists (1. Step, 2. Step, ...)
    numbered = re.findall(
        r"^\s*(?:\d+[.\)]\s+)(.+)$", text, re.MULTILINE
    )

    # Pattern 2: Bullet points with action keywords
    bullet = re.findall(
        r"^\s*(?:[-*•]\s+)(\w+(?:\s+\w+){0,5})(?:\s*[:-]\s*(.+))?$",
        text,
        re.MULTILINE,
    )

    # Pattern 3: Code blocks as steps
    code_blocks = re.findall(
        r"```(?:\w+)?\n(.*?)```", text, re.DOTALL
    )

    all_items = []
    for i, line in enumerate(numbered, 1):
        all_items.append((i, line.strip(), "numbered"))

    offset = len(all_items)
    for i, (action, desc) in enumerate(bullet, 1):
        full = f"{action}: {desc}" if desc else action
        all_items.append((offset + i, full.strip(), "bullet"))

    offset = len(all_items)
    for i, code in enumerate(code_blocks, 1):
        first_line = code.strip().split("\n")[0][:80]
        all_items.append((offset + i, first_line, "code"))

    for order, content, source in all_items:
        # Detect if a tool is mentioned
        tool: Optional[str] = None
        params: Dict[str, Any] = {}
        for tool_name in _TOOL_NAMES:
            if tool_name in content.lower():
                tool = tool_name
                break

        # Extract code command as parameter
        code_match = re.search(r"`([^`]+)`", content)
        if code_match:
            params["command"] = code_match.group(1)

        steps.append(
            SkillStep(
                order=order,
                action=content[:120],
                description=content,
                tool=tool,
                parameters=params,
            )
        )

    return steps


def _generate_skill_name(text: str) -> str:
    """Generate a descriptive skill name from text content."""
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    if not lines:
        return "untitled_skill"

    # Try first non-empty line (likely a heading)
    first = lines[0]
    if len(first) > 5 and len(first) < 100:
        return _slugify(first)

    # Try to find a heading pattern
    heading_match = re.search(r"^#+\s+(.+)$", text, re.MULTILINE)
    if heading_match:
        return _slugify(heading_match.group(1))

    # Fallback: use first sentence
    sentence_match = re.search(r"^([^.]{10,80})[.]", text)
    if sentence_match:
        return _slugify(sentence_match.group(1))

    return "extracted_skill"


def _calculate_parse_confidence(
    text: str, steps: List[SkillStep], fallback_used: bool = False
) -> float:
    """Calculate a confidence score for the parse quality."""
    score = 1.0 if not fallback_used else 0.5

    # Penalize if text is very short
    if len(text) < 100:
        score *= 0.5

    # Boost for structured steps
    if len(steps) >= 3:
        score *= 1.0
    elif len(steps) >= 1:
        score *= 0.8
    else:
        score *= 0.5

    # Boost for clear structure (headers, code blocks)
    if "```" in text:
        score = min(1.0, score * 1.1)
    if re.search(r"^#+\s", text, re.MULTILINE):
        score = min(1.0, score * 1.1)

    return round(min(1.0, max(0.0, score)), 2)


# ---------------------------------------------------------------------------
# Standalone tag extraction (used by both SkillParser and Kimi parsers)
# ---------------------------------------------------------------------------


def _extract_tags_standalone(text: str, category: SkillCategory) -> List[str]:
    """Extract relevant tags from text — standalone version for Kimi parsers."""
    tags = [category.value]

    tag_patterns = [
        ("python", r"\b[Pp]ython\b"),
        ("javascript", r"\b[Jj]ava[Ss]cript\b|\b[jsJS]\b"),
        ("typescript", r"\b[Tt]ype[Ss]cript\b"),
        ("react", r"\b[Rr]eact\b"),
        ("vue", r"\b[Vv]ue\.?js?\b"),
        ("docker", r"\b[Dd]ocker\b"),
        ("kubernetes", r"\b[Kk]ubernetes\b|\bk8s\b"),
        ("aws", r"\bAWS\b|\bAmazon Web Services\b"),
        ("git", r"\b[Gg]it\b"),
        ("api", r"\bAPI\b"),
        ("testing", r"\b[Tt]est(?:ing)?\b"),
        ("database", r"\b[Dd]atabase\b|\bDB\b|\bSQL\b"),
        ("frontend", r"\b[Ff]ront[- ]?[Ee]nd\b"),
        ("backend", r"\b[Bb]ack[- ]?[Ee]nd\b"),
        ("tutorial", r"\b[Tt]utorial\b|\b[Gg]uide\b|\b[Hh]ow[- ][Tt]o\b"),
        ("legal", r"\b[Ll]egal\b|\b[Ll]icense\b|\b[Gg]DPR\b|\b[ Cc]ompliance\b"),
        ("security", r"\b[Ss]ecurity\b|\b[Vv]ulnerability\b|\b[Cc][Vv][Ee]\b"),
        ("branding", r"\b[Bb]rand\b|\b[Tt]rademark\b|\b[Dd]omain\b"),
        ("research", r"\b[Rr]esearch\b|\b[Mm]arket\b|\b[Tt]rend\b"),
        ("audit", r"\b[Aa]udit\b|\b[Qq]uality\b|\b[Hh]ealth\b"),
    ]

    for tag, pattern in tag_patterns:
        if re.search(pattern, text):
            tags.append(tag)

    return sorted(set(tags))


# ---------------------------------------------------------------------------
# Kimi format detection and parsing
# ---------------------------------------------------------------------------


def detect_kimi_format(content: str) -> bool:
    """Detect whether the given content uses Kimi skill format.

    Kimi skills are identified by either:
    - YAML frontmatter with ``---`` delimiters containing skill metadata
    - A leading ``/command-name`` line (slash-command syntax)
    - Presence of structured markdown sections (Overview, Steps, Examples)

    Parameters
    ----------
    content:
        Raw file content to analyze.

    Returns
    -------
    bool
        True if the content appears to be in Kimi format.
    """
    if not content or not content.strip():
        return False

    # Check for YAML frontmatter
    if _KIMI_FRONTMATTER_PATTERN.search(content):
        return True

    # Check for /command-name as first non-whitespace line
    first_line = content.strip().splitlines()[0].strip()
    if _KIMI_COMMAND_PATTERN.match(first_line):
        return True

    # Check for characteristic Kimi section headers (at least 3)
    content_lower = content.lower()
    section_hits = sum(
        1 for header in _KIMI_SECTION_HEADERS
        if header in content_lower
    )
    if section_hits >= 3:
        return True

    return False


def parse_kimi_skill(content: str) -> Skill:
    """Parse a Kimi-format skill definition into a :class:`Skill`.

    Handles two Kimi input styles:
    1. **Markdown with YAML frontmatter** (the standard bundled skill format):
       ``---\nname: ...\n---\n# Heading...``
    2. **Slash-command style**: ``/command-name`` followed by description
       and structured sections.

    Parameters
    ----------
    content:
        Raw Kimi skill content.

    Returns
    -------
    Skill
        Parsed skill in Construct format.

    Raises
    ------
    ValueError
        If the content cannot be parsed as a Kimi skill.
    """
    if not content or not content.strip():
        raise ValueError("Empty content — cannot parse Kimi skill")

    # Strategy 1: YAML frontmatter present (standard bundled format)
    frontmatter_match = _KIMI_FRONTMATTER_PATTERN.search(content)
    if frontmatter_match and _HAS_YAML:
        try:
            metadata = yaml.safe_load(frontmatter_match.group(1))
        except Exception as exc:
            logger.warning("Failed to parse YAML frontmatter: %s", exc)
            metadata = {}

        # Extract markdown body (everything after frontmatter)
        body_start = frontmatter_match.end()
        body = content[body_start:]

        return _parse_kimi_frontmatter_skill(metadata, body, content)

    # Strategy 2: Slash-command style (/command-name)
    first_line = content.strip().splitlines()[0].strip()
    cmd_match = _KIMI_COMMAND_PATTERN.match(first_line)
    if cmd_match:
        command_name = cmd_match.group(1)
        # Body is everything after the command line
        body_lines = content.strip().splitlines()[1:]
        body = "\n".join(body_lines)
        return _parse_kimi_slash_command(command_name, body, content)

    # Strategy 3: Plain markdown with characteristic sections
    return _parse_kimi_plain_markdown(content)


def _parse_kimi_frontmatter_skill(
    metadata: Dict[str, Any], body: str, raw_content: str
) -> Skill:
    """Parse a Kimi skill that has YAML frontmatter + markdown body."""
    name = metadata.get("name", "")
    description = metadata.get("description", "")
    category_str = metadata.get("category", "coding")
    version = metadata.get("version", "1.0")
    author = metadata.get("author", "")
    tags = metadata.get("tags", [])

    # Resolve category
    category = _resolve_category(category_str)

    # Extract title from first # heading if name not in frontmatter
    if not name:
        heading_match = re.search(r"^#\s+(.+)$", body, re.MULTILINE)
        name = _slugify(heading_match.group(1)) if heading_match else "untitled_skill"

    # If description is still empty, extract from first paragraph
    if not description:
        description = _extract_first_paragraph(body)

    # Extract steps from the body
    steps = _extract_kimi_steps(body)
    if not steps:
        steps = _extract_steps(body)

    # Extract examples from code blocks
    examples = _extract_kimi_examples(body)

    # Extract tools from Tools Required section
    tools_needed = _extract_kimi_tools(body)
    if not tools_needed:
        tools_needed = _extract_tools(body)

    # Build tags
    if not tags:
        tags = _extract_tags_standalone(body, category)
    if author and author not in tags:
        tags.append(author.lower().replace(" ", "-"))

    confidence = _calculate_parse_confidence(raw_content, steps, fallback_used=False)

    return Skill(
        name=name,
        description=description,
        category=category,
        steps=steps,
        tools_needed=tools_needed,
        examples=examples,
        confidence=confidence,
        source_document="kimi_frontmatter_skill",
        version=version,
        tags=tags,
    )


def _parse_kimi_slash_command(command_name: str, body: str, raw_content: str) -> Skill:
    """Parse a Kimi skill that starts with ``/command-name``."""
    # Extract description from first paragraph after command
    description = _extract_first_paragraph(body)

    # Detect category from content
    category = _detect_category(body)

    # Extract steps
    steps = _extract_kimi_steps(body)
    if not steps:
        steps = _extract_steps(body)

    # Extract examples
    examples = _extract_kimi_examples(body)

    # Extract tools
    tools_needed = _extract_kimi_tools(body)
    if not tools_needed:
        tools_needed = _extract_tools(body)

    # Tags
    tags = _extract_tags_standalone(body, category)
    tags.append("slash-command")

    confidence = _calculate_parse_confidence(raw_content, steps, fallback_used=False)

    return Skill(
        name=command_name,
        description=description,
        category=category,
        steps=steps,
        tools_needed=tools_needed,
        examples=examples,
        confidence=confidence,
        source_document="kimi_slash_command",
        version="1.0",
        tags=tags,
    )


def _parse_kimi_plain_markdown(content: str) -> Skill:
    """Parse a Kimi skill written as plain markdown without frontmatter or slash-command."""
    # Extract name from first heading
    heading_match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
    name = _slugify(heading_match.group(1)) if heading_match else "untitled_skill"

    description = _extract_first_paragraph(content)
    category = _detect_category(content)

    steps = _extract_kimi_steps(content)
    if not steps:
        steps = _extract_steps(content)

    examples = _extract_kimi_examples(content)
    tools_needed = _extract_kimi_tools(content)
    if not tools_needed:
        tools_needed = _extract_tools(content)

    tags = _extract_tags_standalone(content, category)
    confidence = _calculate_parse_confidence(content, steps, fallback_used=False)

    return Skill(
        name=name,
        description=description,
        category=category,
        steps=steps,
        tools_needed=tools_needed,
        examples=examples,
        confidence=confidence,
        source_document="kimi_plain_markdown",
        version="1.0",
        tags=tags,
    )


def _extract_kimi_steps(text: str) -> List[SkillStep]:
    """Extract structured steps from Kimi skill markdown.

    Looks for numbered lists inside ``## Execution Steps`` or similar sections.
    """
    steps: List[SkillStep] = []

    # Find "Execution Steps" or "Steps" section
    # Note: (?=^##[^#]) ensures we only match exactly ## (not ###) headers
    section_pattern = re.compile(
        r"(?:^##\s*(?:Execution\s+)?Steps?\s*\n)(.*?)(?=^##[^#]|\Z)",
        re.MULTILINE | re.DOTALL | re.IGNORECASE,
    )
    section_match = section_pattern.search(text)

    if not section_match:
        return steps

    section_body = section_match.group(1)

    # Match numbered steps: "1. **Action** — Description" or "1. Action"
    step_pattern = re.compile(
        r"^\s*(?:\d+[.\)])\s+(?:\*\*?([^*\n]+)\*\*?\s*(?:[:\-—]\s*)?)?(.+?)$",
        re.MULTILINE,
    )

    for order, match in enumerate(step_pattern.finditer(section_body), start=1):
        action = (match.group(1) or "").strip()
        description = match.group(2).strip()

        # If no bold action, use the first sentence/phrase as action
        if not action:
            action = description.split(".")[0][:80]

        # Detect tool references
        tool: Optional[str] = None
        params: Dict[str, Any] = {}
        for tool_name in _TOOL_NAMES:
            if tool_name in description.lower():
                tool = tool_name
                break

        # Extract code commands
        code_match = re.search(r"`([^`]+)`", description)
        if code_match:
            params["command"] = code_match.group(1)

        steps.append(
            SkillStep(
                order=order,
                action=action[:120] if action else f"Step {order}",
                description=description,
                tool=tool,
                parameters=params,
            )
        )

    return steps


def _extract_kimi_examples(text: str) -> List[str]:
    """Extract examples from Kimi ``## Examples`` section.

    Captures code blocks with their preceding context (input/output descriptions).
    """
    examples: List[str] = []

    # Find Examples section
    # Note: (?=^##[^#]) ensures we only match exactly ## (not ###) headers
    section_pattern = re.compile(
        r"(?:^##\s*Examples?\s*\n)(.*?)(?=^##[^#]|\Z)",
        re.MULTILINE | re.DOTALL | re.IGNORECASE,
    )
    section_match = section_pattern.search(text)

    if not section_match:
        # Fallback: extract all code blocks
        return list(
            {
                ex.strip()[:500]
                for ex in re.findall(r"```(?:\w+)?\n(.*?)```", text, re.DOTALL)
                if len(ex.strip()) > 10
            }
        )

    section_body = section_match.group(1)

    # Extract Example subsections (### Example 1: ...)
    example_blocks = re.findall(
        r"###\s*Example.*?\n(.*?)(?=###\s*Example|\Z)",
        section_body,
        re.DOTALL | re.IGNORECASE,
    )

    if example_blocks:
        for block in example_blocks:
            cleaned = block.strip()
            if len(cleaned) > 10:
                examples.append(cleaned[:800])
    else:
        # No subsections — grab all code blocks from examples section
        code_blocks = re.findall(
            r"```(?:\w+)?\n(.*?)```", section_body, re.DOTALL
        )
        for code in code_blocks:
            cleaned = code.strip()
            if len(cleaned) > 10:
                examples.append(cleaned[:500])

    return examples[:5]  # max 5 examples


def _extract_kimi_tools(text: str) -> List[str]:
    """Extract tool names from Kimi ``## Tools Required`` section."""
    section_pattern = re.compile(
        r"(?:^##\s*(?:Tools?\s+Required|Required\s+Tools?)\s*\n)(.*?)(?=^##[^#]|\Z)",
        re.MULTILINE | re.DOTALL | re.IGNORECASE,
    )
    section_match = section_pattern.search(text)

    if not section_match:
        return []

    section_body = section_match.group(1)
    found: List[str] = []

    # Look for inline code tool names and table rows
    for tool_name in _TOOL_NAMES:
        # Check for tool in table cells or inline code
        patterns = [
            rf"`{re.escape(tool_name)}`",
            rf"\b{re.escape(tool_name)}\b",
        ]
        for pat in patterns:
            if re.search(pat, section_body, re.IGNORECASE):
                found.append(tool_name)
                break

    # Also check for any ``command-name`` entries in table cells
    table_tools = re.findall(
        r"\|\s*`?([a-z][-a-z0-9]+)`?\s*\|", section_body
    )
    for t in table_tools:
        if t not in found:
            found.append(t)

    return sorted(set(found))


def _resolve_category(category_str: str) -> SkillCategory:
    """Resolve a category string to a :class:`SkillCategory` enum member."""
    if isinstance(category_str, SkillCategory):
        return category_str

    category_map = {
        "coding": SkillCategory.CODING,
        "design": SkillCategory.DESIGN,
        "research": SkillCategory.RESEARCH,
        "devops": SkillCategory.DEVOPS,
        "security": SkillCategory.SECURITY,
        "testing": SkillCategory.TESTING,
    }

    normalized = category_str.lower().strip().replace(" ", "_")

    # Direct match
    if normalized in category_map:
        return category_map[normalized]

    # Keyword-based fallback
    keyword_map = {
        "code": SkillCategory.CODING,
        "program": SkillCategory.CODING,
        "develop": SkillCategory.CODING,
        "design": SkillCategory.DESIGN,
        "ui": SkillCategory.DESIGN,
        "ux": SkillCategory.DESIGN,
        "research": SkillCategory.RESEARCH,
        "market": SkillCategory.RESEARCH,
        "analysis": SkillCategory.RESEARCH,
        "deploy": SkillCategory.DEVOPS,
        "infrastructure": SkillCategory.DEVOPS,
        "ci/cd": SkillCategory.DEVOPS,
        "pipeline": SkillCategory.DEVOPS,
        "cloud": SkillCategory.DEVOPS,
        "security": SkillCategory.SECURITY,
        "legal": SkillCategory.SECURITY,
        "compliance": SkillCategory.SECURITY,
        "test": SkillCategory.TESTING,
        "quality": SkillCategory.TESTING,
    }

    for keyword, cat in keyword_map.items():
        if keyword in normalized:
            return cat

    logger.warning("Unknown category '%s', defaulting to CODING", category_str)
    return SkillCategory.CODING


def _extract_first_paragraph(text: str) -> str:
    """Extract the first meaningful paragraph from text (excluding headings)."""
    lines = text.splitlines()
    for line in lines:
        stripped = line.strip()
        if (
            stripped
            and not stripped.startswith("#")
            and not stripped.startswith("---")
            and not stripped.startswith("|")
            and len(stripped) > 20
        ):
            return stripped[:200]
    return text[:200] if text else "Skill extracted from document"


def convert_kimi_to_construct(kimi_skill: Dict[str, Any]) -> Skill:
    """Convert a parsed Kimi skill dictionary to a Construct :class:`Skill`.

    This is the inverse of ``parse_kimi_skill`` — useful when Kimi skills
    are pre-parsed into dictionaries (e.g., from JSON API responses).

    Parameters
    ----------
    kimi_skill:
        Dictionary with keys like ``name``, ``description``, ``category``,
        ``steps``, ``examples``, ``tools``, etc.

    Returns
    -------
    Skill
        A fully populated Construct-format Skill instance.

    Raises
    ------
    ValueError
        If required fields are missing.
    """
    name = kimi_skill.get("name") or kimi_skill.get("command", "").lstrip("/")
    if not name:
        raise ValueError("Kimi skill must have a 'name' or 'command' field")

    description = kimi_skill.get("description", "")
    category = _resolve_category(kimi_skill.get("category", "coding"))
    version = kimi_skill.get("version", "1.0")
    tags = kimi_skill.get("tags", [])

    # Convert steps
    steps: List[SkillStep] = []
    for i, step_data in enumerate(kimi_skill.get("steps", []), start=1):
        if isinstance(step_data, str):
            steps.append(
                SkillStep(
                    order=i,
                    action=step_data[:120],
                    description=step_data,
                )
            )
        elif isinstance(step_data, dict):
            steps.append(
                SkillStep(
                    order=step_data.get("order", i),
                    action=step_data.get("action", f"Step {i}"),
                    description=step_data.get("description", ""),
                    tool=step_data.get("tool"),
                    parameters=step_data.get("parameters", {}),
                    validation=step_data.get("validation"),
                )
            )

    # Extract tools
    tools_needed: List[str] = []
    if "tools" in kimi_skill:
        tools_needed = kimi_skill["tools"]
    elif "tools_needed" in kimi_skill:
        tools_needed = kimi_skill["tools_needed"]

    # Extract examples
    examples: List[str] = []
    if "examples" in kimi_skill:
        raw_examples = kimi_skill["examples"]
        for ex in raw_examples:
            if isinstance(ex, str):
                examples.append(ex[:500])
            elif isinstance(ex, dict):
                # Kimi often structures examples as {input, code, output}
                parts = []
                for key in ("input", "code", "output"):
                    if key in ex:
                        parts.append(f"**{key.capitalize()}:**\n{ex[key]}")
                if parts:
                    examples.append("\n\n".join(parts)[:800])

    confidence = kimi_skill.get("confidence", 0.95)

    return Skill(
        name=name,
        description=description,
        category=category,
        steps=steps,
        tools_needed=tools_needed,
        examples=examples,
        confidence=confidence,
        source_document=kimi_skill.get("source_document", "kimi_converted"),
        version=version,
        tags=tags,
    )


# ---------------------------------------------------------------------------
# Top-level convenience API
# ---------------------------------------------------------------------------


def parse_skill_file(file_path: str) -> Skill:
    """Parse a skill file, auto-detecting Kimi vs Construct format.

    This is the primary entry point for skill parsing. It reads the file,
    detects whether it is in Kimi format (YAML frontmatter, /command syntax,
    or structured markdown) or legacy Construct format, and parses
    accordingly.

    Parameters
    ----------
    file_path:
        Absolute or relative path to the skill file.

    Returns
    -------
    Skill
        Parsed skill in unified Construct format.

    Raises
    ------
    FileNotFoundError
        If the file does not exist.
    ValueError
        If the file format cannot be determined or parsed.

    Examples
    --------
    >>> skill = parse_skill_file("skills/legal-risk-assessment/SKILL.md")
    >>> print(skill.name)
    'legal-risk-assessment'
    >>> print(skill.category)
    <SkillCategory.SECURITY: 'security'>
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Skill file not found: {file_path}")

    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    # Detect format
    if detect_kimi_format(content):
        logger.info("Detected Kimi format for %s", file_path)
        skill = parse_kimi_skill(content)
        skill.source_document = str(path.resolve())
        return skill

    # Fall back to legacy Construct format via SkillParser
    logger.info("Falling back to Construct format parser for %s", file_path)
    parser = SkillParser()
    return parser.parse(file_path)


# ---------------------------------------------------------------------------
# Skill Parser
# ---------------------------------------------------------------------------


class SkillParser:
    """Convert documents into structured skills.

    Supports PDF, Markdown, text, DOCX, HTML, JSON, YAML, images (OCR),
    and GitHub repository URLs.
    """

    SUPPORTED_FORMATS = {
        ".pdf",
        ".md",
        ".mdx",
        ".txt",
        ".rst",
        ".docx",
        ".html",
        ".htm",
        ".json",
        ".yaml",
        ".yml",
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".bmp",
    }

    # -- Public API -----------------------------------------------------------

    def parse(self, file_path: str) -> Skill:
        """Parse a document and convert to a :class:`Skill`.

        Parameters
        ----------
        file_path:
            Absolute or relative path to the document.

        Returns
        -------
        Skill
            The extracted skill.

        Raises
        ------
        ValueError
            If the file format is not supported.
        FileNotFoundError
            If the file does not exist.
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        ext = path.suffix.lower()
        source = str(path.resolve())

        if ext == ".pdf":
            text = self._parse_pdf(source)
        elif ext in (".md", ".mdx"):
            text = self._parse_markdown(source)
            # Check if Kimi format was detected during markdown parsing
            if getattr(self, "_kimi_detected", False):
                kimi_content = getattr(self, "_kimi_content", text)
                skill = parse_kimi_skill(kimi_content)
                skill.source_document = source
                self._kimi_detected = False
                delattr(self, "_kimi_content")
                return skill
        elif ext in (".txt", ".rst"):
            text = self._parse_text(source)
            # Also check plain text files for Kimi /command syntax
            if detect_kimi_format(text):
                skill = parse_kimi_skill(text)
                skill.source_document = source
                return skill
        elif ext == ".docx":
            text = self._parse_docx(source)
        elif ext in (".html", ".htm"):
            text = self._parse_html(source)
        elif ext == ".json":
            return self._parse_json(source)
        elif ext in (".yaml", ".yml"):
            return self._parse_yaml(source)
        elif ext in (".png", ".jpg", ".jpeg", ".gif", ".bmp"):
            text = self._parse_image(source)
        else:
            raise ValueError(
                f"Unsupported format: '{ext}'. "
                f"Supported: {', '.join(sorted(self.SUPPORTED_FORMATS))}"
            )

        return self._text_to_skill(text, source)

    def parse_github_repo(self, repo_url: str) -> List[Skill]:
        """Clone a GitHub repository and extract coding patterns as skills.

        Parameters
        ----------
        repo_url:
            HTTPS or SSH URL of the GitHub repository.

        Returns
        -------
        list[Skill]
            Skills extracted from the repository.
        """
        skills: List[Skill] = []
        temp_dir = tempfile.mkdtemp(prefix="skill_parser_repo_")

        try:
            logger.info("Cloning repository: %s", repo_url)
            result = subprocess.run(
                ["git", "clone", "--depth", "1", repo_url, temp_dir],
                capture_output=True,
                text=True,
                timeout=120,
            )
            if result.returncode != 0:
                logger.error("Git clone failed: %s", result.stderr)
                return skills

            # Analyze repository structure
            repo_skills = self._analyze_repo(temp_dir, repo_url)
            skills.extend(repo_skills)

        except subprocess.TimeoutExpired:
            logger.error("Git clone timed out after 120s")
        except FileNotFoundError:
            logger.error("Git command not found — ensure git is installed")
        except Exception as exc:
            logger.exception("Error analyzing repository: %s", exc)
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

        return skills

    # -- Format-specific parsers ----------------------------------------------

    def _parse_pdf(self, path: str) -> str:
        """Extract text from PDF using pdfplumber (primary) + PyPDF2 (fallback).

        Parameters
        ----------
        path:
            Path to the PDF file.

        Returns
        -------
        str
            Extracted text content.
        """
        text_parts: List[str] = []
        fallback_used = False

        # Attempt 1: pdfplumber (best quality)
        try:
            import pdfplumber

            with pdfplumber.open(path) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text_parts.append(page_text)
            logger.info("PDF parsed with pdfplumber: %s", path)
        except Exception as exc:
            logger.warning("pdfplumber failed (%s), trying PyPDF2 fallback", exc)
            fallback_used = True

        # Attempt 2: PyPDF2 fallback
        if not text_parts:
            try:
                import PyPDF2

                with open(path, "rb") as f:
                    reader = PyPDF2.PdfReader(f)
                    for page in reader.pages:
                        page_text = page.extract_text()
                        if page_text:
                            text_parts.append(page_text)
                logger.info("PDF parsed with PyPDF2 fallback: %s", path)
            except Exception as exc:
                logger.error("PyPDF2 fallback also failed: %s", exc)

        full_text = "\n\n".join(text_parts)

        # Store fallback info in instance for confidence calculation
        self._last_fallback_used = fallback_used
        return full_text

    def _parse_markdown(self, path: str) -> str:
        """Read markdown file, strip frontmatter.

        Also detects Kimi-format skills and raises a signal so that
        the caller can route to ``parse_kimi_skill`` instead.

        Parameters
        ----------
        path:
            Path to the markdown file.

        Returns
        -------
        str
            Text content with frontmatter removed.
        """
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()

        # Detect Kimi format and route appropriately
        if detect_kimi_format(content):
            logger.info("Kimi format detected in markdown file: %s", path)
            # Store a marker so parse() knows to use Kimi parser
            self._kimi_detected = True
            self._kimi_content = content
            # Return the body only (legacy behavior for compatibility)
            # The full parsing happens in parse() when it sees _kimi_detected
        else:
            self._kimi_detected = False

        # Strip YAML/TOML frontmatter
        content = re.sub(r"^---\n.*?\n---\n", "", content, count=1, flags=re.DOTALL)
        content = re.sub(r"^\+\+\+\n.*?\n\+\+\+\n", "", content, count=1, flags=re.DOTALL)

        # Strip HTML comments
        content = re.sub(r"<!--.*?-->", "", content, flags=re.DOTALL)

        return content

    def _parse_text(self, path: str) -> str:
        """Read a plain text file.

        Parameters
        ----------
        path:
            Path to the text file.

        Returns
        -------
        str
            File contents.
        """
        with open(path, "r", encoding="utf-8") as f:
            return f.read()

    def _parse_docx(self, path: str) -> str:
        """Extract text from Word document using python-docx.

        Parameters
        ----------
        path:
            Path to the .docx file.

        Returns
        -------
        str
            Extracted text content.
        """
        try:
            import docx

            doc = docx.Document(path)
            paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
            return "\n\n".join(paragraphs)
        except Exception as exc:
            logger.error("Failed to parse DOCX: %s", exc)
            # Fallback: try zip extraction
            try:
                import xml.etree.ElementTree as ET
                import zipfile

                with zipfile.ZipFile(path) as z:
                    xml_content = z.read("word/document.xml")
                root = ET.fromstring(xml_content)
                ns = {
                    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
                }
                texts = []
                for elem in root.iter("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t"):
                    if elem.text:
                        texts.append(elem.text)
                return " ".join(texts)
            except Exception as exc2:
                logger.error("DOCX fallback also failed: %s", exc2)
                return ""

    def _parse_html(self, path: str) -> str:
        """Extract text from HTML using BeautifulSoup.

        Parameters
        ----------
        path:
            Path to the HTML file.

        Returns
        -------
        str
            Extracted text content.
        """
        try:
            from bs4 import BeautifulSoup

            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            soup = BeautifulSoup(content, "html.parser")

            # Remove script and style elements
            for tag in soup(["script", "style", "nav", "footer"]):
                tag.decompose()

            # Get text with good spacing
            text = soup.get_text(separator="\n", strip=True)
            # Collapse multiple blank lines
            text = re.sub(r"\n{3,}", "\n\n", text)
            return text
        except ImportError:
            logger.warning("BeautifulSoup not installed, using regex fallback for HTML")
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            text = re.sub(r"<[^>]+>", " ", content)
            text = re.sub(r"\s+", " ", text).strip()
            return text
        except Exception as exc:
            logger.error("Failed to parse HTML: %s", exc)
            return ""

    def _parse_json(self, path: str) -> Skill:
        """Load a skill from a JSON file.

        Parameters
        ----------
        path:
            Path to the JSON file.

        Returns
        -------
        Skill
            The loaded skill.
        """
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        skill = Skill.from_dict(data)
        skill.source_document = path
        return skill

    def _parse_yaml(self, path: str) -> Skill:
        """Load a skill from a YAML file.

        Parameters
        ----------
        path:
            Path to the YAML file.

        Returns
        -------
        Skill
            The loaded skill.
        """
        try:
            import yaml

            with open(path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
            skill = Skill.from_dict(data)
            skill.source_document = path
            return skill
        except ImportError:
            logger.error("PyYAML not installed — cannot parse YAML files")
            raise

    def _parse_image(self, path: str) -> str:
        """OCR an image using pytesseract, falling back to easyocr.

        Parameters
        ----------
        path:
            Path to the image file.

        Returns
        -------
        str
            OCR-extracted text.
        """
        # Attempt 1: pytesseract
        try:
            import pytesseract
            from PIL import Image

            image = Image.open(path)
            text = pytesseract.image_to_string(image)
            logger.info("OCR completed with pytesseract: %s", path)
            self._last_fallback_used = False
            return text
        except ImportError:
            logger.warning("pytesseract not installed, trying easyocr")
        except Exception as exc:
            logger.warning("pytesseract failed (%s), trying easyocr fallback", exc)

        # Attempt 2: easyocr fallback
        try:
            import easyocr  # type: ignore[import-untyped]

            reader = easyocr.Reader(["en"])
            results = reader.readtext(path, detail=0)
            text = "\n".join(results)
            logger.info("OCR completed with easyocr fallback: %s", path)
            self._last_fallback_used = True
            return text
        except ImportError:
            logger.error("Neither pytesseract nor easyocr is installed")
            return ""
        except Exception as exc:
            logger.error("easyocr also failed: %s", exc)
            return ""

    # -- Text-to-skill conversion ---------------------------------------------

    def _text_to_skill(self, text: str, source: str) -> Skill:
        """Convert extracted text into a structured :class:`Skill`.

        Uses heuristic analysis to detect the category, extract procedure
        steps, identify required tools, generate examples, and score
        confidence.

        Parameters
        ----------
        text:
            The raw extracted text from the document.
        source:
            Original file path (stored in the skill).

        Returns
        -------
        Skill
            The structured skill representation.
        """
        # 1. Generate skill name
        name = _generate_skill_name(text)

        # 2. Extract a description from the first paragraph
        description = self._extract_description(text)

        # 3. Detect category
        category = _detect_category(text)

        # 4. Extract steps
        steps = _extract_steps(text)

        # 5. If no structured steps, create a single fallback step
        if not steps:
            steps = [
                SkillStep(
                    order=1,
                    action="Review extracted document content",
                    description=text[:500],
                )
            ]

        # 6. Identify required tools
        tools_needed = _extract_tools(text)

        # 7. Generate examples from code blocks
        examples = self._extract_examples(text)

        # 8. Calculate confidence
        fallback_used = getattr(self, "_last_fallback_used", False)
        confidence = _calculate_parse_confidence(text, steps, fallback_used)
        self._last_fallback_used = False  # reset

        # 9. Extract tags
        tags = self._extract_tags(text, category)

        return Skill(
            name=name,
            description=description,
            category=category,
            steps=steps,
            tools_needed=tools_needed,
            examples=examples,
            confidence=confidence,
            source_document=source,
            tags=tags,
        )

    # -- GitHub repo analysis -------------------------------------------------

    def _analyze_repo(self, repo_path: str, repo_url: str) -> List[Skill]:
        """Analyze a cloned repository and extract skills from patterns.

        Parameters
        ----------
        repo_path:
            Local path to the cloned repository.
        repo_url:
            Original repository URL.

        Returns
        -------
        list[Skill]
            Skills extracted from the repository.
        """
        skills: List[Skill] = []
        repo_name = Path(repo_url).stem or "repo"

        # Detect language/framework from file patterns
        lang, framework = self._detect_repo_stack(repo_path)

        # Extract README as overview skill
        readme_paths = [
            Path(repo_path) / "README.md",
            Path(repo_path) / "README.rst",
            Path(repo_path) / "readme.md",
        ]
        for readme in readme_paths:
            if readme.exists():
                try:
                    readme_skill = self.parse(str(readme))
                    readme_skill.name = f"{repo_name}_setup_guide"
                    readme_skill.source_document = repo_url
                    skills.append(readme_skill)
                except Exception as exc:
                    logger.warning("Failed to parse README: %s", exc)
                break

        # Extract CI/CD configuration as a skill
        ci_skills = self._extract_ci_skills(repo_path, repo_name, repo_url)
        skills.extend(ci_skills)

        # Extract testing patterns
        test_skill = self._extract_testing_skill(repo_path, repo_name, repo_url, lang)
        if test_skill:
            skills.append(test_skill)

        # Extract dependency management skill
        dep_skill = self._extract_dependency_skill(repo_path, repo_name, repo_url, lang)
        if dep_skill:
            skills.append(dep_skill)

        # Extract build/deploy skill
        build_skill = self._extract_build_skill(
            repo_path, repo_name, repo_url, lang, framework
        )
        if build_skill:
            skills.append(build_skill)

        logger.info(
            "Extracted %d skills from repository: %s", len(skills), repo_url
        )
        return skills

    def _detect_repo_stack(self, repo_path: str) -> Tuple[Optional[str], Optional[str]]:
        """Detect the primary language and framework of a repository.

        Returns
        -------
        tuple[str | None, str | None]
            (language, framework) or (None, None).
        """
        path = Path(repo_path)
        lang: Optional[str] = None
        framework: Optional[str] = None

        # Language detection via file presence
        if (path / "package.json").exists():
            lang = "javascript"
            # Check for framework
            try:
                with open(path / "package.json") as f:
                    pkg = json.load(f)
                deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
                for fw in ["react", "vue", "angular", "next", "svelte"]:
                    if fw in deps:
                        framework = fw
                        break
            except Exception:
                pass
        elif (path / "Cargo.toml").exists():
            lang = "rust"
        elif (path / "requirements.txt").exists() or (path / "pyproject.toml").exists():
            lang = "python"
        elif (path / "go.mod").exists():
            lang = "go"
        elif (path / "pom.xml").exists() or (path / "build.gradle").exists():
            lang = "java"

        return lang, framework

    def _extract_ci_skills(
        self, repo_path: str, repo_name: str, repo_url: str
    ) -> List[Skill]:
        """Extract CI/CD pipeline skills from repository."""
        skills: List[Skill] = []
        path = Path(repo_path)

        ci_configs = {
            ".github/workflows": "github_actions",
            ".gitlab-ci.yml": "gitlab_ci",
            "Jenkinsfile": "jenkins",
            ".circleci": "circleci",
            "azure-pipelines.yml": "azure_pipelines",
        }

        for ci_path, ci_name in ci_configs.items():
            full_path = path / ci_path
            if full_path.exists():
                steps = [
                    SkillStep(
                        order=1,
                        action=f"Review {ci_name} configuration",
                        description=f"Examine {ci_path} for pipeline steps",
                    ),
                    SkillStep(
                        order=2,
                        action="Run CI pipeline locally",
                        description=f"Execute {ci_name} workflow for validation",
                        tool="execute_command",
                        parameters={"command": f"# Review {ci_path} for commands"},
                    ),
                ]
                skills.append(
                    Skill(
                        name=f"{repo_name}_{ci_name}_pipeline",
                        description=f"CI/CD pipeline using {ci_name}",
                        category=SkillCategory.DEVOPS,
                        steps=steps,
                        tools_needed=[ci_name.replace("_", "-")],
                        source_document=repo_url,
                        tags=["ci/cd", ci_name, repo_name],
                    )
                )

        return skills

    def _extract_testing_skill(
        self, repo_path: str, repo_name: str, repo_url: str, lang: Optional[str]
    ) -> Optional[Skill]:
        """Extract testing patterns as a skill."""
        path = Path(repo_path)
        test_tools: Dict[str, List[str]] = {
            "javascript": ["jest", "mocha", "vitest", "cypress", "playwright"],
            "python": ["pytest", "unittest"],
            "rust": ["cargo test"],
            "go": ["go test"],
            "java": ["junit", "maven test"],
        }

        found_tools = test_tools.get(lang or "", [])
        if not found_tools:
            return None

        steps = [
            SkillStep(
                order=1,
                action="Run test suite",
                description=f"Execute tests using {found_tools[0]}",
                tool="run_test",
                parameters={"test_command": found_tools[0]},
            ),
            SkillStep(
                order=2,
                action="Review test coverage",
                description="Check code coverage reports",
            ),
        ]

        return Skill(
            name=f"{repo_name}_testing_workflow",
            description=f"Testing workflow for {lang or 'project'}",
            category=SkillCategory.TESTING,
            steps=steps,
            tools_needed=found_tools,
            source_document=repo_url,
            tags=["testing", lang or "general", repo_name],
        )

    def _extract_dependency_skill(
        self, repo_path: str, repo_name: str, repo_url: str, lang: Optional[str]
    ) -> Optional[Skill]:
        """Extract dependency management as a skill."""
        dep_commands: Dict[str, str] = {
            "javascript": "npm install",
            "python": "pip install -r requirements.txt",
            "rust": "cargo build",
            "go": "go mod download",
        }

        cmd = dep_commands.get(lang or "", "")
        if not cmd:
            return None

        steps = [
            SkillStep(
                order=1,
                action="Install dependencies",
                description=f"Run '{cmd}' to install all dependencies",
                tool="execute_command",
                parameters={"command": cmd},
            ),
            SkillStep(
                order=2,
                action="Verify installation",
                description="Check that all packages resolved correctly",
                tool="execute_command",
                parameters={"command": f"{cmd} --dry-run" if "npm" in cmd else "echo 'Done'"},
            ),
        ]

        return Skill(
            name=f"{repo_name}_dependency_setup",
            description=f"Install dependencies for {lang or 'project'}",
            category=SkillCategory.DEVOPS,
            steps=steps,
            tools_needed=["npm" if lang == "javascript" else lang or ""],
            source_document=repo_url,
            tags=["dependencies", lang or "general", repo_name],
        )

    def _extract_build_skill(
        self,
        repo_path: str,
        repo_name: str,
        repo_url: str,
        lang: Optional[str],
        framework: Optional[str],
    ) -> Optional[Skill]:
        """Extract build/deploy skill from the repository."""
        build_commands: Dict[str, str] = {
            "javascript": "npm run build",
            "python": "python -m build",
            "rust": "cargo build --release",
            "go": "go build",
        }

        cmd = build_commands.get(lang or "", "")
        if not cmd:
            return None

        steps = [
            SkillStep(
                order=1,
                action="Build project",
                description=f"Run production build: {cmd}",
                tool="execute_command",
                parameters={"command": cmd},
            ),
        ]

        # Add framework-specific build steps
        if framework in ["react", "next"]:
            steps.append(
                SkillStep(
                    order=2,
                    action="Optimize bundle",
                    description="Review bundle size and optimize imports",
                    tool="execute_command",
                    parameters={"command": "npm run analyze"},
                )
            )

        return Skill(
            name=f"{repo_name}_build_deploy",
            description=f"Build and deploy {repo_name}",
            category=SkillCategory.DEVOPS,
            steps=steps,
            tools_needed=[lang or ""],
            source_document=repo_url,
            tags=["build", "deploy", lang or "general", framework or "", repo_name],
        )

    # -- Extraction helpers ---------------------------------------------------

    def _extract_description(self, text: str) -> str:
        """Extract a short description from the first meaningful paragraph."""
        lines = [l.strip() for l in text.splitlines() if l.strip()]
        for line in lines[1:] if len(lines) > 1 else lines:  # skip likely heading
            if len(line) > 20 and not line.startswith("#"):
                return line[:200]
        return text[:200] if text else "Skill extracted from document"

    def _extract_examples(self, text: str) -> List[str]:
        """Extract code examples from markdown code blocks."""
        examples = re.findall(r"```(?:\w+)?\n(.*?)```", text, re.DOTALL)
        # Clean and truncate
        cleaned = []
        for ex in examples:
            stripped = ex.strip()
            if len(stripped) > 10:
                cleaned.append(stripped[:500])
        return cleaned[:5]  # max 5 examples

    def _extract_tags(self, text: str, category: SkillCategory) -> List[str]:
        """Extract relevant tags from text."""
        tags = [category.value]

        tag_patterns = [
            ("python", r"\b[Pp]ython\b"),
            ("javascript", r"\b[Jj]ava[Ss]cript\b|\b[jsJS]\b"),
            ("typescript", r"\b[Tt]ype[Ss]cript\b"),
            ("react", r"\b[Rr]eact\b"),
            ("vue", r"\b[Vv]ue\.?js?\b"),
            ("docker", r"\b[Dd]ocker\b"),
            ("kubernetes", r"\b[Kk]ubernetes\b|\bk8s\b"),
            ("aws", r"\bAWS\b|\bAmazon Web Services\b"),
            ("git", r"\b[Gg]it\b"),
            ("api", r"\bAPI\b"),
            ("testing", r"\b[Tt]est(?:ing)?\b"),
            ("database", r"\b[Dd]atabase\b|\bDB\b|\bSQL\b"),
            ("frontend", r"\b[Ff]ront[- ]?[Ee]nd\b"),
            ("backend", r"\b[Bb]ack[- ]?[Ee]nd\b"),
            ("tutorial", r"\b[Tt]utorial\b|\b[Gg]uide\b|\b[Hh]ow[- ][Tt]o\b"),
        ]

        for tag, pattern in tag_patterns:
            if re.search(pattern, text):
                tags.append(tag)

        return sorted(set(tags))

    # -- Batch processing -----------------------------------------------------

    def parse_directory(self, dir_path: str) -> List[Skill]:
        """Parse all supported documents in a directory.

        Parameters
        ----------
        dir_path:
            Path to the directory to scan.

        Returns
        -------
        list[Skill]
            All successfully extracted skills.
        """
        skills: List[Skill] = []
        path = Path(dir_path)

        for file_path in path.rglob("*"):
            if file_path.suffix.lower() in self.SUPPORTED_FORMATS:
                try:
                    skill = self.parse(str(file_path))
                    skills.append(skill)
                    logger.info("Parsed: %s", file_path)
                except Exception as exc:
                    logger.warning("Failed to parse %s: %s", file_path, exc)

        return skills

    def parse_url(self, url: str) -> List[Skill]:
        """Parse a URL — either a GitHub repo or a raw document.

        Parameters
        ----------
        url:
            URL to parse.

        Returns
        -------
        list[Skill]
            Extracted skills.
        """
        if "github.com" in url:
            return self.parse_github_repo(url)

        # For raw documents, download and parse
        import urllib.request

        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".html")
        try:
            urllib.request.urlretrieve(url, temp_file.name)
            skill = self.parse(temp_file.name)
            return [skill]
        except Exception as exc:
            logger.error("Failed to download/parse URL %s: %s", url, exc)
            return []
        finally:
            os.unlink(temp_file.name)
