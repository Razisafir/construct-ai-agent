"""
Code analysis and refactoring tools using AST parsing.

Tools: parse_ast, find_references, refactor_rename, extract_function

Python code is parsed using the built-in ``ast`` module.  For JavaScript/
TypeScript files, a regex-based fallback is used since full AST parsing
would require additional dependencies.
"""

import os
import re
import ast
import logging
import textwrap
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple

# astor is optional — fallback to ast.unparse (Python 3.9+)
try:
    import astor
except ImportError:
    astor = None

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Language detection
# ---------------------------------------------------------------------------

PYTHON_EXTENSIONS: set = {".py", ".pyw"}
JS_EXTENSIONS: set = {".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"}


def _detect_language(file_path: str) -> str:
    """Detect programming language from file extension."""
    ext = os.path.splitext(file_path)[1].lower()
    if ext in PYTHON_EXTENSIONS:
        return "python"
    if ext in JS_EXTENSIONS:
        return "javascript"
    return "unknown"


def _read_file_safe(file_path: str) -> Optional[str]:
    """Safely read a file, returning *None* on error."""
    try:
        expanded = os.path.expanduser(file_path)
        abs_path = os.path.abspath(expanded)
        if not os.path.isfile(abs_path):
            return None
        if os.path.getsize(abs_path) > 1_048_576:  # 1 MB limit
            return None
        with open(abs_path, "r", encoding="utf-8", errors="replace") as f:
            return f.read()
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Python AST helpers
# ---------------------------------------------------------------------------


def _parse_python_ast(source: str) -> Optional[ast.AST]:
    """Parse Python source into an AST, returning *None* on syntax error."""
    try:
        return ast.parse(source)
    except SyntaxError as exc:
        logger.warning("Python syntax error: %s", exc)
        return None


def _ast_node_to_dict(node: ast.AST, source: str) -> Dict[str, Any]:
    """
    Recursively convert an AST node to a dictionary representation.

    Includes node type, line numbers, names, and child nodes.
    """
    if node is None:
        return {}

    result: Dict[str, Any] = {
        "type": type(node).__name__,
        "lineno": getattr(node, "lineno", None),
        "col_offset": getattr(node, "col_offset", None),
        "end_lineno": getattr(node, "end_lineno", None),
    }

    # Add relevant fields based on node type
    if isinstance(node, ast.FunctionDef):
        result["name"] = node.name
        result["args"] = [_arg.arg for _arg in node.args.args]
        result["decorators"] = [
            _ast_node_to_dict(d, source) for d in node.decorator_list
        ]
        result["body_count"] = len(node.body)
    elif isinstance(node, ast.AsyncFunctionDef):
        result["name"] = node.name
        result["async"] = True
        result["args"] = [_arg.arg for _arg in node.args.args]
        result["body_count"] = len(node.body)
    elif isinstance(node, ast.ClassDef):
        result["name"] = node.name
        result["bases"] = [
            ast.unparse(b) if hasattr(ast, "unparse") else str(type(b).__name__)
            for b in node.bases
        ]
        result["methods"] = [
            item.name
            for item in node.body
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
        ]
    elif isinstance(node, ast.Import):
        result["names"] = [alias.name for alias in node.names]
    elif isinstance(node, ast.ImportFrom):
        result["module"] = node.module
        result["names"] = [alias.name for alias in node.names]
    elif isinstance(node, ast.Assign):
        targets = []
        for t in node.targets:
            if isinstance(t, ast.Name):
                targets.append(t.id)
            elif isinstance(t, ast.Tuple):
                targets.append(
                    [
                        elt.id if isinstance(elt, ast.Name) else "..."
                        for elt in t.elts
                    ]
                )
        result["targets"] = targets
    elif isinstance(node, ast.Name):
        result["id"] = node.id

    # Recurse into child nodes (limit depth to avoid huge output)
    children: List[Dict[str, Any]] = []
    for child in ast.iter_child_nodes(node):
        child_dict = _ast_node_to_dict(child, source)
        if child_dict:
            children.append(child_dict)
    if children:
        result["children"] = children[:50]  # limit

    return result


# ---------------------------------------------------------------------------
# JS/TS regex-based helpers (fallback)
# ---------------------------------------------------------------------------


def _parse_js_fallback(source: str) -> Dict[str, Any]:
    """
    Parse JavaScript/TypeScript using regex heuristics.

    This is a best-effort fallback that extracts functions, classes,
    imports, and exports without requiring a full parser.
    """
    result: Dict[str, Any] = {
        "type": "javascript_fallback",
        "note": "Parsed with regex heuristics — not a full AST",
        "functions": [],
        "classes": [],
        "imports": [],
        "exports": [],
        "variables": [],
    }

    lines = source.split("\n")

    # Find functions: function name(...) or const name = (...) => or name(...) {
    func_pattern = re.compile(
        r"(?:async\s+)?(?:function\s+(\w+)|const\s+(\w+)\s*=\s*(?:async\s+)?\(|(\w+)\s*\([^)]*\)\s*\{)",
        re.MULTILINE,
    )
    for match in func_pattern.finditer(source):
        name = match.group(1) or match.group(2) or match.group(3)
        line_no = source[: match.start()].count("\n") + 1
        result["functions"].append(
            {"name": name, "line": line_no, "type": "function"}
        )

    # Arrow functions: const name = (...) =>
    arrow_pattern = re.compile(
        r"const\s+(\w+)\s*=\s*(?:async\s+)?\([^)]*\)\s*=>", re.MULTILINE
    )
    for match in arrow_pattern.finditer(source):
        name = match.group(1)
        line_no = source[: match.start()].count("\n") + 1
        result["functions"].append(
            {"name": name, "line": line_no, "type": "arrow_function"}
        )

    # Classes: class Name { ... } or class Name extends Base {
    class_pattern = re.compile(
        r"class\s+(\w+)(?:\s+extends\s+(\w+))?\s*\{", re.MULTILINE
    )
    for match in class_pattern.finditer(source):
        name = match.group(1)
        base = match.group(2)
        line_no = source[: match.start()].count("\n") + 1
        cls = {"name": name, "line": line_no}
        if base:
            cls["extends"] = base
        result["classes"].append(cls)

    # Imports: import { ... } from '...' or import * as X from '...'
    import_pattern = re.compile(
        r"import\s+(?:(\*\s+as\s+\w+)|\{([^}]+)\}|(\w+))\s+from\s+['\"]([^'\"]+)['\"]",
        re.MULTILINE,
    )
    for match in import_pattern.finditer(source):
        names = (match.group(2) or match.group(3) or match.group(1) or "").strip()
        module = match.group(4)
        line_no = source[: match.start()].count("\n") + 1
        result["imports"].append(
            {"names": names, "module": module, "line": line_no}
        )

    # Exports: export ... or export default ...
    export_pattern = re.compile(
        r"export\s+(?:default\s+)?(?:const|let|var|function|class)?\s*(\w+)",
        re.MULTILINE,
    )
    for match in export_pattern.finditer(source):
        name = match.group(1)
        line_no = source[: match.start()].count("\n") + 1
        result["exports"].append({"name": name, "line": line_no})

    return result


# ---------------------------------------------------------------------------
# Reference finding
# ---------------------------------------------------------------------------


def _find_python_references(
    symbol: str, tree: ast.AST, source: str
) -> List[Dict[str, Any]]:
    """Find all references to *symbol* in a Python AST."""
    references: List[Dict[str, Any]] = []

    class ReferenceVisitor(ast.NodeVisitor):
        def visit_Name(self, node: ast.Name) -> None:
            if node.id == symbol:
                references.append(
                    {
                        "line": node.lineno,
                        "column": node.col_offset,
                        "context": _get_line_context(source, node.lineno),
                    }
                )
            self.generic_visit(node)

        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            if node.name == symbol:
                references.append(
                    {
                        "line": node.lineno,
                        "column": node.col_offset,
                        "type": "definition",
                        "context": _get_line_context(source, node.lineno),
                    }
                )
            self.generic_visit(node)

        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
            if node.name == symbol:
                references.append(
                    {
                        "line": node.lineno,
                        "column": node.col_offset,
                        "type": "definition",
                        "context": _get_line_context(source, node.lineno),
                    }
                )
            self.generic_visit(node)

        def visit_ClassDef(self, node: ast.ClassDef) -> None:
            if node.name == symbol:
                references.append(
                    {
                        "line": node.lineno,
                        "column": node.col_offset,
                        "type": "definition",
                        "context": _get_line_context(source, node.lineno),
                    }
                )
            self.generic_visit(node)

    visitor = ReferenceVisitor()
    visitor.visit(tree)
    return references


def _find_js_references(symbol: str, source: str) -> List[Dict[str, Any]]:
    """Find references to *symbol* in JS/TS using regex."""
    references: List[Dict[str, Any]] = []
    # Match the symbol as a word boundary
    pattern = re.compile(r"\b" + re.escape(symbol) + r"\b")
    for match in pattern.finditer(source):
        line_no = source[: match.start()].count("\n") + 1
        references.append(
            {
                "line": line_no,
                "column": match.start() - source.rfind("\n", 0, match.start()),
                "context": _get_line_context(source, line_no),
            }
        )
    return references


def _get_line_context(source: str, line_no: int, context: int = 2) -> str:
    """Get surrounding lines for context."""
    lines = source.split("\n")
    start = max(0, line_no - context - 1)
    end = min(len(lines), line_no + context)
    return "\n".join(f"{i + 1}: {lines[i]}" for i in range(start, end))


# ---------------------------------------------------------------------------
# Refactoring helpers
# ---------------------------------------------------------------------------


class _RenameTransformer(ast.NodeTransformer):
    """AST transformer that renames a symbol."""

    def __init__(self, old_name: str, new_name: str) -> None:
        self.old_name = old_name
        self.new_name = new_name
        self.renames = 0

    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.FunctionDef:
        if node.name == self.old_name:
            node.name = self.new_name
            self.renames += 1
        self.generic_visit(node)
        return node

    def visit_AsyncFunctionDef(
        self, node: ast.AsyncFunctionDef
    ) -> ast.AsyncFunctionDef:
        if node.name == self.old_name:
            node.name = self.new_name
            self.renames += 1
        self.generic_visit(node)
        return node

    def visit_ClassDef(self, node: ast.ClassDef) -> ast.ClassDef:
        if node.name == self.old_name:
            node.name = self.new_name
            self.renames += 1
        self.generic_visit(node)
        return node

    def visit_Name(self, node: ast.Name) -> ast.Name:
        if node.id == self.old_name:
            node.id = self.new_name
            self.renames += 1
        return node

    def visit_arg(self, node: ast.arg) -> ast.arg:
        if node.arg == self.old_name:
            node.arg = self.new_name
            self.renames += 1
        return node


def _rename_python(
    old_name: str, new_name: str, tree: ast.AST, source: str
) -> Tuple[str, int]:
    """Rename a symbol in Python source. Returns (new_source, renames_count)."""
    transformer = _RenameTransformer(old_name, new_name)
    new_tree = transformer.visit(tree)
    ast.fix_missing_locations(new_tree)

    if astor is not None:
        try:
            new_source = astor.to_source(new_tree)
        except Exception:
            # Fallback to ast.unparse (Python 3.9+)
            if hasattr(ast, "unparse"):
                new_source = ast.unparse(new_tree)
            else:
                raise RuntimeError(
                    "Cannot convert AST back to source. "
                    "Install 'astor' or use Python 3.9+"
                )
    elif hasattr(ast, "unparse"):
        new_source = ast.unparse(new_tree)
    else:
        raise RuntimeError(
            "Cannot convert AST back to source. "
            "Install 'astor' or use Python 3.9+"
        )

    return new_source, transformer.renames


def _rename_js(old_name: str, new_name: str, source: str) -> Tuple[str, int]:
    """Rename a symbol in JS/TS using regex."""
    pattern = re.compile(r"\b" + re.escape(old_name) + r"\b")
    new_source, count = pattern.subn(new_name, source)
    return new_source, count


# ---------------------------------------------------------------------------
# Function extraction
# ---------------------------------------------------------------------------


def _extract_python_function(
    source: str, start_line: int, end_line: int, new_name: str
) -> str:
    """Extract a block of Python code into a new function."""
    lines = source.split("\n")
    start_idx = max(0, start_line - 1)
    end_idx = min(len(lines), end_line)

    block_lines = lines[start_idx:end_idx]
    block_text = textwrap.dedent("\n".join(block_lines))

    # Indent the block
    indented = textwrap.indent(block_text, "    ")

    # Build the new function
    func_def = f"def {new_name}():\n{indented}\n"
    return func_def


def _extract_js_function(
    source: str, start_line: int, end_line: int, new_name: str
) -> str:
    """Extract a block of JS/TS code into a new function."""
    lines = source.split("\n")
    start_idx = max(0, start_line - 1)
    end_idx = min(len(lines), end_line)

    block_lines = lines[start_idx:end_idx]
    block_text = "\n".join(block_lines)

    # Build the new function
    func_def = f"function {new_name}() {{\n    {block_text.replace(chr(10), chr(10) + '    ')}\n}}\n"
    return func_def


# ---------------------------------------------------------------------------
# Public tool functions
# ---------------------------------------------------------------------------


def parse_ast(file_path: str) -> Dict[str, Any]:
    """
    Parse a source file into an AST structure.

    Parameters
    ----------
    file_path:
        Path to the source file.

    Returns
    -------
    dict
        Parsed AST with ``success``, ``language``, ``structure``,
        ``line_count``, ``functions``, ``classes``, ``imports``.
    """
    logger.info("parse_ast: %s", file_path)

    source = _read_file_safe(file_path)
    if source is None:
        return {"success": False, "error": f"Cannot read file: {file_path}"}

    language = _detect_language(file_path)
    line_count = len(source.split("\n"))

    if language == "python":
        tree = _parse_python_ast(source)
        if tree is None:
            return {
                "success": False,
                "error": "Python syntax error in file",
                "file_path": file_path,
            }

        structure = _ast_node_to_dict(tree, source)

        # Extract summary info
        functions = [
            n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
        ]
        classes = [n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]
        imports = [n for n in ast.walk(tree) if isinstance(n, (ast.Import, ast.ImportFrom))]

        return {
            "success": True,
            "language": "python",
            "file_path": file_path,
            "line_count": line_count,
            "structure": structure,
            "functions": [
                {
                    "name": f.name,
                    "line": f.lineno,
                    "async": isinstance(f, ast.AsyncFunctionDef),
                    "args": [a.arg for a in f.args.args],
                }
                for f in functions
            ],
            "classes": [
                {
                    "name": c.name,
                    "line": c.lineno,
                    "methods": [
                        m.name
                        for m in c.body
                        if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef))
                    ],
                }
                for c in classes
            ],
            "imports": [
                {
                    "names": [a.name for a in i.names],
                    "module": getattr(i, "module", None),
                    "line": i.lineno,
                }
                for i in imports
            ],
        }

    elif language == "javascript":
        structure = _parse_js_fallback(source)
        return {
            "success": True,
            "language": "javascript",
            "file_path": file_path,
            "line_count": line_count,
            "structure": structure,
            "functions": structure.get("functions", []),
            "classes": structure.get("classes", []),
            "imports": structure.get("imports", []),
            "note": "JS/TS parsed with regex heuristics — limited accuracy",
        }

    else:
        return {
            "success": False,
            "error": f"Unsupported language for AST parsing: {language}",
            "file_path": file_path,
        }


def find_references(symbol: str, file_path: str) -> Dict[str, Any]:
    """
    Find all references to a symbol in a source file.

    Parameters
    ----------
    symbol:
        The symbol (variable/function/class name) to search for.
    file_path:
        Path to the source file.

    Returns
    -------
    dict
        ``success``, ``references`` (list of dicts with line, column, context).
    """
    logger.info("find_references: %s in %s", symbol, file_path)

    source = _read_file_safe(file_path)
    if source is None:
        return {"success": False, "error": f"Cannot read file: {file_path}"}

    language = _detect_language(file_path)

    if language == "python":
        tree = _parse_python_ast(source)
        if tree is None:
            return {"success": False, "error": "Python syntax error in file"}
        references = _find_python_references(symbol, tree, source)
    elif language == "javascript":
        references = _find_js_references(symbol, source)
    else:
        return {
            "success": False,
            "error": f"Unsupported language: {language}",
        }

    return {
        "success": True,
        "symbol": symbol,
        "file_path": file_path,
        "language": language,
        "reference_count": len(references),
        "references": references,
    }


def refactor_rename(
    old_name: str, new_name: str, file_path: str
) -> Dict[str, Any]:
    """
    Rename a symbol (function, class, variable) in a source file.

    Parameters
    ----------
    old_name:
        Current symbol name.
    new_name:
        New symbol name.
    file_path:
        Path to the source file.

    Returns
    -------
    dict
        ``success``, ``renames`` (count), ``new_source`` (preview),
        and writes the renamed file.
    """
    logger.info("refactor_rename: %s -> %s in %s", old_name, new_name, file_path)

    source = _read_file_safe(file_path)
    if source is None:
        return {"success": False, "error": f"Cannot read file: {file_path}"}

    language = _detect_language(file_path)

    try:
        if language == "python":
            tree = _parse_python_ast(source)
            if tree is None:
                return {"success": False, "error": "Python syntax error in file"}
            new_source, renames = _rename_python(old_name, new_name, tree, source)
        elif language == "javascript":
            new_source, renames = _rename_js(old_name, new_name, source)
        else:
            return {
                "success": False,
                "error": f"Unsupported language for rename: {language}",
            }
    except Exception as exc:
        logger.exception("Rename failed")
        return {"success": False, "error": f"Rename failed: {exc}"}

    if renames == 0:
        return {
            "success": False,
            "error": f"Symbol '{old_name}' not found in file",
        }

    # Preview the change (first 20 lines of diff context)
    preview_lines = new_source.split("\n")[:40]

    return {
        "success": True,
        "old_name": old_name,
        "new_name": new_name,
        "renames": renames,
        "language": language,
        "file_path": file_path,
        "preview": "\n".join(preview_lines),
    }


def extract_function(
    file_path: str,
    start_line: int,
    end_line: int,
    new_name: str,
) -> Dict[str, Any]:
    """
    Extract a block of code into a new function.

    Parameters
    ----------
    file_path:
        Path to the source file (to detect language).
    start_line:
        First line to extract (1-based).
    end_line:
        Last line to extract (1-based, inclusive).
    new_name:
        Name for the extracted function.

    Returns
    -------
    dict
        ``success``, ``extracted_function`` (source code),
        ``lines_extracted``.
    """
    logger.info(
        "extract_function: %s lines %d-%d as '%s'",
        file_path,
        start_line,
        end_line,
        new_name,
    )

    source = _read_file_safe(file_path)
    if source is None:
        return {"success": False, "error": f"Cannot read file: {file_path}"}

    language = _detect_language(file_path)

    if start_line < 1 or end_line < start_line:
        return {
            "success": False,
            "error": "Invalid line range",
        }

    if language == "python":
        extracted = _extract_python_function(source, start_line, end_line, new_name)
    elif language == "javascript":
        extracted = _extract_js_function(source, start_line, end_line, new_name)
    else:
        return {
            "success": False,
            "error": f"Unsupported language for extraction: {language}",
        }

    return {
        "success": True,
        "new_name": new_name,
        "language": language,
        "lines_extracted": end_line - start_line + 1,
        "extracted_function": extracted,
    }
