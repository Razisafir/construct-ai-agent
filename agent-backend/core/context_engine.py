"""Context Engine -- codebase analysis for intelligent context awareness.

Features:
- AST-based code structure parsing (Python, JS/TS, Rust, Go)
- Dependency graph: which files import/reference which
- "Hot files": most referenced, most modified, user focus
- Auto-context: silently include relevant files in agent prompt
- Smart @mentions: ranked file suggestions

Typical usage::

    engine = ContextEngine("/path/to/project")
    engine.scan_project()

    # Get most important files
    hot = engine.get_hot_files(limit=10)

    # Get related files for current editor tab
    related = engine.get_related_files("src/core/app.py")

    # Get @mention suggestions
    suggestions = engine.get_suggestions(query="auth", current_file="src/api/routes.py")

    # Get files to auto-include in agent context
    auto_ctx = engine.get_auto_context("src/api/routes.py", max_files=5)
"""

from __future__ import annotations

import ast
import fnmatch
import logging
import os
import re
import time
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Default ignore patterns (similar to .gitignore defaults)
# ---------------------------------------------------------------------------

_DEFAULT_IGNORE_PATTERNS: List[str] = [
    "*.pyc", "*.pyo", "__pycache__", "*.so", "*.dylib", "*.dll",
    ".git", ".hg", ".svn", ".bzr",
    "node_modules", "vendor", ".venv", "venv", "env", ".env",
    "*.egg-info", "dist", "build", "_build",
    ".tox", ".pytest_cache", ".mypy_cache",
    "*.min.js", "*.min.css", "*.map",
    ".idea", ".vscode", "*.swp", "*.swo",
    "*.log", "*.lock",
]


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class FileContext:
    """Structured context for a single source file."""

    path: str
    imports: List[str] = field(default_factory=list)
    exports: List[str] = field(default_factory=list)
    references: int = 0  # How many files reference this one
    last_accessed: float = 0
    last_modified: float = 0
    language: str = ""
    size_bytes: int = 0
    line_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "path": self.path,
            "imports": self.imports,
            "exports": self.exports,
            "references": self.references,
            "last_accessed": self.last_accessed,
            "last_modified": self.last_modified,
            "language": self.language,
            "size_bytes": self.size_bytes,
            "line_count": self.line_count,
        }


@dataclass
class Suggestion:
    """A ranked file suggestion for @mentions."""

    path: str
    relevance_score: float  # 0-1
    reason: str  # e.g. "recently_opened", "imported_by_current", "hot_file"


# ---------------------------------------------------------------------------
# ContextEngine
# ---------------------------------------------------------------------------

class ContextEngine:
    """Analyzes codebase structure for intelligent context awareness.

    Parameters
    ----------
    project_path:
        Root directory of the project to analyze.
    ignore_patterns:
        Glob patterns for files/directories to skip.  Merged with defaults.
    """

    SUPPORTED_LANGUAGES: Dict[str, str] = {
        ".py": "python",
        ".js": "javascript",
        ".ts": "typescript",
        ".tsx": "typescript",
        ".rs": "rust",
        ".go": "go",
        ".java": "java",
        ".rb": "ruby",
    }

    # Conventional-commit style scope keywords extracted from paths
    _SCOPE_HINTS: Dict[str, List[str]] = {
        "auth": ["auth", "login", "oauth", "sso", "session", "credential", "password", "token"],
        "api": ["api", "endpoint", "route", "controller", "handler", "rest", "graphql"],
        "db": ["db", "database", "model", "schema", "migration", "orm", "repository", "sql"],
        "ui": ["ui", "component", "view", "template", "page", "screen", "frontend", "react", "vue"],
        "test": ["test", "spec", "e2e", "fixture", "mock", "stub"],
        "ci": ["ci", "cd", "pipeline", "github", "gitlab", "jenkins", "dockerfile"],
        "docs": ["docs", "readme", "changelog", "license", "contributing"],
        "config": ["config", "settings", "env", "yaml", "toml", "ini"],
        "core": ["core", "engine", "context", "util", "common", "shared"],
    }

    def __init__(
        self,
        project_path: str = ".",
        ignore_patterns: Optional[List[str]] = None,
    ) -> None:
        self.project_path: Path = Path(project_path).resolve()
        self.files: Dict[str, FileContext] = {}
        self._dependency_graph: Dict[str, Set[str]] = defaultdict(set)
        self._reverse_graph: Dict[str, Set[str]] = defaultdict(set)
        self._user_focus: Dict[str, float] = {}  # path -> timestamp
        self._ignore_patterns: List[str] = _DEFAULT_IGNORE_PATTERNS + (ignore_patterns or [])
        self._file_hashes: Dict[str, float] = {}  # path -> mtime cache

    # -- Analysis methods ----------------------------------------------------

    def scan_project(self) -> int:
        """Scan the entire project and build file contexts.

        Walks the directory tree, parses each supported source file,
        extracts imports/exports, and builds the dependency graph.

        Returns
        -------
        int
            Number of files parsed successfully.
        """
        parsed_count = 0
        all_source_files: List[Path] = []

        for root, dirs, files in os.walk(self.project_path):
            # Filter out ignored directories in-place to prune traversal
            dirs[:] = [
                d for d in dirs
                if not any(fnmatch.fnmatch(d, pat) for pat in self._ignore_patterns)
            ]

            for fname in files:
                if any(fnmatch.fnmatch(fname, pat) for pat in self._ignore_patterns):
                    continue

                ext = Path(fname).suffix.lower()
                if ext in self.SUPPORTED_LANGUAGES:
                    full_path = Path(root) / fname
                    rel_path = str(full_path.relative_to(self.project_path))
                    all_source_files.append(full_path)

        # Parse each file
        for full_path in all_source_files:
            rel_path = str(full_path.relative_to(self.project_path))
            try:
                # Caching: skip re-parse if mtime unchanged
                mtime = full_path.stat().st_mtime
                cached_mtime = self._file_hashes.get(rel_path)
                if cached_mtime and cached_mtime == mtime and rel_path in self.files:
                    continue  # File unchanged, keep cached context

                fc = self.parse_file(rel_path)
                self.files[rel_path] = fc
                self._file_hashes[rel_path] = mtime
                parsed_count += 1
            except Exception:
                logger.debug("Failed to parse %s", rel_path, exc_info=True)

        # Build dependency graph after all files are indexed
        self.build_dependency_graph()
        logger.info(
            "Scanned %d files (%d parsed) in %s",
            len(all_source_files), parsed_count, self.project_path,
        )
        return parsed_count

    def parse_file(self, file_path: str) -> FileContext:
        """Parse a single file and extract its context.

        Parameters
        ----------
        file_path:
            Path relative to *project_path*.

        Returns
        -------
        FileContext
            Populated context for the file.
        """
        full_path = self.project_path / file_path
        ext = full_path.suffix.lower()
        language = self.SUPPORTED_LANGUAGES.get(ext, "")

        # File metadata
        stat = full_path.stat()
        size_bytes = stat.st_size
        content = full_path.read_text(encoding="utf-8", errors="replace")
        line_count = content.count("\n") + 1

        # Extract imports based on language
        imports: List[str] = []
        exports: List[str] = []
        if language == "python":
            imports, exports = self._parse_python_imports(content)
        elif language in ("javascript", "typescript"):
            imports, exports = self._parse_js_ts_imports(content)
        elif language == "rust":
            imports, exports = self._parse_rust_imports(content)
        elif language == "go":
            imports, exports = self._parse_go_imports(content)

        return FileContext(
            path=file_path,
            imports=imports,
            exports=exports,
            last_modified=stat.st_mtime,
            language=language,
            size_bytes=size_bytes,
            line_count=line_count,
        )

    def _parse_python_imports(self, content: str) -> tuple[List[str], List[str]]:
        """Extract imports and exports from Python source using the *ast* module.

        Returns (imports, exports) where imports are module names and
        exports are top-level definitions (classes, functions, assignments).
        """
        imports: List[str] = []
        exports: List[str] = []

        try:
            tree = ast.parse(content)
        except SyntaxError:
            return imports, exports

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if node.level:
                    # Relative import: convert to dotted notation
                    module = "." * node.level + (module or "")
                imports.append(module)
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                exports.append(node.name)
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        exports.append(target.id)

        return imports, exports

    def _parse_js_ts_imports(self, content: str) -> tuple[List[str], List[str]]:
        """Extract imports and exports from JavaScript / TypeScript via regex.

        Handles ``import``, ``export``, ``require()``, and dynamic ``import()``.
        """
        imports: List[str] = []
        exports: List[str] = []

        # ES6 imports: import X from 'module' or import { x } from "module"
        for match in re.finditer(
            r"import\s+(?:(?:type\s+)?\{[^}]*\}|[^'\"]+?)\s+from\s+['\"]([^'\"]+)['\"]",
            content,
        ):
            imports.append(match.group(1))

        # Bare import: import 'module'
        for match in re.finditer(r"import\s+['\"]([^'\"]+)['\"]", content):
            imports.append(match.group(1))

        # CommonJS require: require('module')
        for match in re.finditer(r"require\s*\(\s*['\"]([^'\"]+)['\"]\s*\)", content):
            imports.append(match.group(1))

        # Dynamic import: import('module')
        for match in re.finditer(r"import\s*\(\s*['\"]([^'\"]+)['\"]\s*\)", content):
            imports.append(match.group(1))

        # ES6 exports: export { x }, export const x, export function x, export default
        for match in re.finditer(
            r"export\s+(?:default\s+)?(?:(?:const|let|var|function|class|interface|type)\s+)?([A-Za-z_$][A-Za-z0-9_$]*)",
            content,
        ):
            exports.append(match.group(1))

        # Re-exports: export { ... } from 'module'
        for match in re.finditer(
            r"export\s+\{[^}]*\}\s+from\s+['\"]([^'\"]+)['\"]", content
        ):
            imports.append(match.group(1))

        return imports, exports

    def _parse_rust_imports(self, content: str) -> tuple[List[str], List[str]]:
        """Extract imports and exports from Rust source via regex.

        Handles ``use``, ``mod``, ``pub mod``, and ``extern crate``.
        """
        imports: List[str] = []
        exports: List[str] = []

        # use statements: use crate::foo::bar; use std::collections::HashMap;
        for match in re.finditer(r"^\s*use\s+([^;]+);", content, re.MULTILINE):
            imports.append(match.group(1).strip())

        # mod declarations: mod foo; pub mod foo;
        for match in re.finditer(r"^\s*(?:pub\s+)?mod\s+([A-Za-z_][A-Za-z0-9_]*)", content, re.MULTILINE):
            mod_name = match.group(1)
            imports.append(mod_name)
            exports.append(mod_name)

        # extern crate
        for match in re.finditer(r"^\s*extern\s+crate\s+([A-Za-z_][A-Za-z0-9_]*)", content, re.MULTILINE):
            imports.append(match.group(1))

        # pub struct / enum / fn / trait / type / const / static
        for match in re.finditer(
            r"^\s*pub\s+(?:\([^)]*\)\s+)?(?:struct|enum|fn|trait|type|const|static|use)\s+([A-Za-z_][A-Za-z0-9_]*)",
            content, re.MULTILINE,
        ):
            exports.append(match.group(1))

        return imports, exports

    def _parse_go_imports(self, content: str) -> tuple[List[str], List[str]]:
        """Extract imports and exports from Go source via regex.

        Handles ``import`` blocks and single imports.  Exports are public
        identifiers (capitalized) in ``func``, ``type``, ``var``, ``const``.
        """
        imports: List[str] = []
        exports: List[str] = []

        # Multi-line import block: import ( ... )
        block_match = re.search(r"import\s*\((.*?)\)", content, re.DOTALL)
        if block_match:
            block = block_match.group(1)
            for line in block.split("\n"):
                line = line.strip()
                if not line or line.startswith("//"):
                    continue
                # Handle alias: alias "path" or just "path"
                path_match = re.search(r'"([^"]+)"', line)
                if path_match:
                    imports.append(path_match.group(1))
        else:
            # Single-line import: import "path" or import alias "path"
            for match in re.finditer(r"import\s+(?:[A-Za-z_]+\s+)?\"([^\"]+)\",?", content):
                imports.append(match.group(1))

        # Exports: capitalized identifiers in func/type/var/const declarations
        for match in re.finditer(
            r"^\s*(?:func\s+(?:\([^)]*\)\s*)?([A-Z][A-Za-z0-9_]*)",
            content, re.MULTILINE,
        ):
            exports.append(match.group(1))
        for match in re.finditer(
            r"^\s*(?:type|var|const)\s+([A-Z][A-Za-z0-9_]*)",
            content, re.MULTILINE,
        ):
            exports.append(match.group(1))

        return imports, exports

    def build_dependency_graph(self) -> Dict[str, Set[str]]:
        """Build the forward dependency graph from parsed imports.

        For each file, resolves its import strings to actual file paths
        within the project and updates both forward and reverse graphs.

        Returns
        -------
        dict
            Forward dependency graph: ``{file_path: {dep_path, ...}}``.
        """
        self._dependency_graph.clear()
        self._reverse_graph.clear()

        for rel_path, fc in self.files.items():
            resolved: Set[str] = set()
            for imp in fc.imports:
                dep = self._resolve_import_to_path(rel_path, imp, fc.language)
                if dep and dep in self.files and dep != rel_path:
                    resolved.add(dep)

            self._dependency_graph[rel_path] = resolved
            for dep in resolved:
                self._reverse_graph[dep].add(rel_path)

        # Update reference counts
        for rel_path, fc in self.files.items():
            fc.references = len(self._reverse_graph.get(rel_path, set()))

        logger.debug(
            "Dependency graph: %d nodes, %d edges",
            len(self._dependency_graph),
            sum(len(v) for v in self._dependency_graph.values()),
        )
        return dict(self._dependency_graph)

    def _resolve_import_to_path(
        self, current_file: str, import_name: str, language: str
    ) -> Optional[str]:
        """Resolve an import string to a relative file path in the project.

        Handles relative imports, package-relative resolution, and
        attempts to map import names to likely file paths.
        """
        current_dir = Path(current_file).parent

        # Python: relative imports (e.g., "..utils", ".models")
        if language == "python" and import_name.startswith("."):
            dots = len(import_name) - len(import_name.lstrip("."))
            parts = import_name.lstrip(".").split(".") if import_name.lstrip(".") else []
            base = self.project_path / current_file
            for _ in range(dots):
                base = base.parent
            candidate = base
            for part in parts:
                candidate = candidate / part
            # Try as file (.py) or package (__init__.py)
            trial = str(candidate.with_suffix(".py")).replace(str(self.project_path) + "/", "")
            if trial in self.files:
                return trial
            trial_pkg = str(candidate / "__init__.py").replace(str(self.project_path) + "/", "")
            if trial_pkg in self.files:
                return trial_pkg
            return None

        # Python: dotted module -> path
        if language == "python" and "." in import_name:
            parts = import_name.split(".")
            candidate_path = "/".join(parts)
            for suffix in [".py", "/__init__.py"]:
                trial = candidate_path + suffix
                if trial in self.files:
                    return trial
            return None

        # JS/TS: relative path imports (./foo, ../bar)
        if language in ("javascript", "typescript") and import_name.startswith("."):
            resolved = (current_dir / import_name).resolve()
            # Try with extensions
            exts = ["", ".ts", ".tsx", ".js", ".jsx"]
            # Also try /index.ts etc.
            index_exts = exts + ["/index.ts", "/index.tsx", "/index.js", "/index.jsx"]
            for suffix in index_exts:
                trial = str(resolved) + suffix
                trial_rel = str(Path(trial).relative_to(self.project_path)) if str(trial).startswith(str(self.project_path)) else trial
                if trial_rel in self.files:
                    return trial_rel
            return None

        # JS/TS: bare imports (npm packages) — skip resolution
        if language in ("javascript", "typescript") and not import_name.startswith("."):
            return None

        # Rust: use crate::foo::bar -> src/foo/bar.rs or src/foo.rs
        if language == "rust" and (import_name.startswith("crate::") or import_name.startswith("super::")):
            parts = import_name.replace("crate::", "").replace("super::", "").split("::")
            base_dir = current_dir
            if import_name.startswith("super::"):
                base_dir = current_dir.parent
                parts = parts[1:] if parts and parts[0] == "" else parts
            candidate = self.project_path / base_dir / "/".join(parts)
            for suffix in [".rs", "/mod.rs"]:
                trial_rel = str((candidate.with_suffix(suffix) if not suffix.startswith("/") else candidate / suffix[1:])).replace(str(self.project_path) + "/", "")
                if trial_rel in self.files:
                    return trial_rel
            return None

        # Go: github.com/user/repo/pkg -> try to find pkg directory
        if language == "go" and "/" in import_name:
            parts = import_name.split("/")
            # Try progressively from the right
            for i in range(len(parts)):
                candidate = "/".join(parts[i:])
                if candidate + ".go" in self.files:
                    return candidate + ".go"
                trial = candidate + "/"
                for f in self.files:
                    if f.startswith(trial) and f.endswith(".go"):
                        return f
            return None

        return None

    def get_hot_files(self, limit: int = 10) -> List[FileContext]:
        """Return the most important files (most referenced + recently accessed).

        Scoring::

            score = references * 0.5 + recency * 0.3 + (lines / 1000) * 0.2

        Parameters
        ----------
        limit:
            Maximum number of files to return.

        Returns
        -------
        list[FileContext]
            Hot files sorted by importance, descending.
        """
        scored: List[tuple[float, FileContext]] = []
        for fc in self.files.values():
            score = self._score_file(fc)
            scored.append((score, fc))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [fc for _, fc in scored[:limit]]

    def get_related_files(self, file_path: str, limit: int = 10) -> List[FileContext]:
        """Get files related to *file_path* (imports + importers).

        Parameters
        ----------
        file_path:
            Path of the file whose relations are queried.
        limit:
            Maximum number of related files to return.

        Returns
        -------
        list[FileContext]
            Related files, sorted by reference count.
        """
        if file_path not in self.files:
            return []

        related_paths: Set[str] = set()
        # Files that this file imports
        related_paths.update(self._dependency_graph.get(file_path, set()))
        # Files that import this file
        related_paths.update(self._reverse_graph.get(file_path, set()))

        # Exclude self
        related_paths.discard(file_path)

        results: List[FileContext] = []
        for p in related_paths:
            if p in self.files:
                results.append(self.files[p])

        results.sort(key=lambda f: f.references, reverse=True)
        return results[:limit]

    # -- User focus tracking -------------------------------------------------

    def record_access(self, file_path: str) -> None:
        """Record that the user accessed *file_path* (for recency scoring).

        Parameters
        ----------
        file_path:
            Path of the accessed file (relative to *project_path*).
        """
        now = time.time()
        self._user_focus[file_path] = now
        if file_path in self.files:
            self.files[file_path].last_accessed = now
        logger.debug("Recorded access: %s", file_path)

    def get_suggestions(
        self,
        query: str = "",
        current_file: Optional[str] = None,
        limit: int = 10,
    ) -> List[Suggestion]:
        """Get ranked file suggestions for ``@mentions``.

        Ranking criteria (in order of priority):

        1. Recently opened files (last_accessed)
        2. Files importing *current_file*
        3. Hot files (most referenced)
        4. Query match (fuzzy on filename)

        Parameters
        ----------
        query:
            Optional fuzzy search string (matched against filename).
        current_file:
            Optional path of the currently focused file.
        limit:
            Maximum number of suggestions.

        Returns
        -------
        list[Suggestion]
            Suggestions sorted by *relevance_score*, descending.
        """
        suggestions: Dict[str, Suggestion] = {}
        now = time.time()

        for rel_path, fc in self.files.items():
            if rel_path == current_file:
                continue

            score = 0.0
            reasons: List[str] = []

            # 1. Recently accessed
            if fc.last_accessed > 0:
                recency = max(0, 1 - (now - fc.last_accessed) / 86400)
                if recency > 0.3:
                    score += recency * 0.35
                    reasons.append("recently_opened")

            # 2. Files importing current file
            if current_file and rel_path in self._reverse_graph.get(current_file, set()):
                score += 0.25
                reasons.append("imported_by_current")

            # 3. Files imported by current file
            if current_file and rel_path in self._dependency_graph.get(current_file, set()):
                score += 0.20
                reasons.append("imported_by_current")

            # 4. Hot file (reference count)
            if fc.references > 0:
                ref_score = min(fc.references / 10, 0.15)
                score += ref_score
                reasons.append("hot_file")

            # 5. Query fuzzy match
            if query:
                match_score = self._fuzzy_match(query, rel_path)
                if match_score > 0:
                    score += match_score * 0.20
                    reasons.append("query_match")
                elif match_score == 0:
                    # If query is provided but doesn't match at all, skip
                    continue

            if score > 0:
                suggestions[rel_path] = Suggestion(
                    path=rel_path,
                    relevance_score=min(score, 1.0),
                    reason="|".join(reasons) if reasons else "general",
                )

        # Sort by relevance score descending
        sorted_suggestions = sorted(
            suggestions.values(), key=lambda s: s.relevance_score, reverse=True
        )
        return sorted_suggestions[:limit]

    def get_auto_context(self, current_file: str, max_files: int = 5) -> List[str]:
        """Get files to automatically include in the agent prompt context.

        Combines related files and hot files, deduplicates, and limits
        to *max_files*.

        Parameters
        ----------
        current_file:
            Path of the currently focused file.
        max_files:
            Maximum number of additional files to include.

        Returns
        -------
        list[str]
            Paths of files to include in context.
        """
        selected: List[str] = []
        seen: Set[str] = {current_file}

        # 1. Direct imports and importers of current file
        related = self.get_related_files(current_file, limit=max_files)
        for fc in related:
            if fc.path not in seen:
                selected.append(fc.path)
                seen.add(fc.path)
            if len(selected) >= max_files:
                return selected

        # 2. Recently accessed files (not already selected)
        recent = sorted(
            (f for f in self.files.values() if f.last_accessed > 0),
            key=lambda f: f.last_accessed,
            reverse=True,
        )
        for fc in recent:
            if fc.path not in seen:
                selected.append(fc.path)
                seen.add(fc.path)
            if len(selected) >= max_files:
                return selected

        # 3. Fill remainder with hot files
        hot = self.get_hot_files(limit=max_files * 2)
        for fc in hot:
            if fc.path not in seen:
                selected.append(fc.path)
                seen.add(fc.path)
            if len(selected) >= max_files:
                return selected

        return selected

    def invalidate_cache(self, file_path: Optional[str] = None) -> None:
        """Invalidate cached parse results.

        Parameters
        ----------
        file_path:
            If given, invalidate only this file.  Otherwise clear all.
        """
        if file_path:
            self._file_hashes.pop(file_path, None)
            logger.debug("Invalidated cache for %s", file_path)
        else:
            self._file_hashes.clear()
            logger.debug("Invalidated entire cache")

    # -- Scoring & matching --------------------------------------------------

    def _score_file(self, fc: FileContext) -> float:
        """Calculate an importance score for *fc* in the range [0, inf).

        Scoring weights::

            references  -> 0.5 points each
            recency     -> 0.0-0.3 (24-hour decay)
            line count  -> 0.2 per 1000 lines
        """
        now = time.time()
        recency = max(0.0, 1.0 - (now - fc.last_accessed) / 86400) if fc.last_accessed else 0.0
        size_factor = (fc.line_count / 1000) * 0.2
        return fc.references * 0.5 + recency * 0.3 + size_factor

    @staticmethod
    def _fuzzy_match(query: str, target: str) -> float:
        """Compute a fuzzy-match score between *query* and *target*.

        Returns a float in [0, 1] where 1 is an exact substring match
        and lower values indicate weaker character-sequence overlap.
        """
        query_lower = query.lower()
        target_lower = target.lower()

        # Exact substring match
        if query_lower in target_lower:
            return 1.0 - (target_lower.index(query_lower) / max(len(target_lower), 1)) * 0.1

        # Character-by-character sequence match (simplified)
        q_idx = 0
        t_idx = 0
        matched = 0
        while q_idx < len(query_lower) and t_idx < len(target_lower):
            if query_lower[q_idx] == target_lower[t_idx]:
                matched += 1
                q_idx += 1
            t_idx += 1

        if matched == 0:
            return 0.0
        return (matched / len(query_lower)) * 0.5

    # -- Serialization -------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        """Return a summary dictionary for debugging or API responses."""
        return {
            "project_path": str(self.project_path),
            "files": len(self.files),
            "languages": list(set(f.language for f in self.files.values() if f.language)),
            "hot_files": [f.path for f in self.get_hot_files(5)],
            "dependency_edges": sum(len(v) for v in self._dependency_graph.values()),
        }

    def __repr__(self) -> str:
        return (
            f"ContextEngine(project={self.project_path}, "
            f"files={len(self.files)}, "
            f"edges={sum(len(v) for v in self._dependency_graph.values())})"
        )
