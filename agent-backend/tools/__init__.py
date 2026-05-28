"""
Tool registry — central registration and schema collection for all tools.

This module collects all tool function schemas in OpenAI's function calling format
and provides dispatch so the executor can call tools by name with JSON arguments.

Usage::

    from tools import ToolRegistry, TOOL_DEFINITIONS

    registry = ToolRegistry()
    schemas = registry.get_tool_schemas()          # for LLM function calling
    result = registry.execute_tool("read_file", {"file_path": "app.py"})
"""

import logging
import inspect
from typing import Dict, List, Any, Callable, Optional

from tools.file_tools import read_file, write_file, list_directory, search_files
from tools.shell_tools import execute_command, run_test, install_dependency
from tools.git_tools import (
    git_status,
    git_diff,
    git_commit,
    git_branch,
    git_log,
    git_checkout,
    git_add,
    git_reset,
)
from tools.code_tools import parse_ast, find_references, refactor_rename, extract_function

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Tool definitions (OpenAI function calling format)
# ---------------------------------------------------------------------------

TOOL_DEFINITIONS: List[Dict[str, Any]] = [
    # -- File tools ---------------------------------------------------------
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": (
                "Read the contents of a text file. Use offset and limit to "
                "read large files in chunks. Returns the file content, total "
                "line count, and whether there is more content to read."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Absolute or relative path to the file",
                    },
                    "offset": {
                        "type": "integer",
                        "description": "Number of lines to skip from the start (default 0)",
                        "default": 0,
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of lines to read (default 100)",
                        "default": 100,
                    },
                },
                "required": ["file_path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": (
                "Write or overwrite a text file with the given content. "
                "Use append=True to append instead of overwrite. "
                "Parent directories are created automatically."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Absolute or relative path to the file",
                    },
                    "content": {
                        "type": "string",
                        "description": "Text content to write",
                    },
                    "append": {
                        "type": "boolean",
                        "description": "If true, append to the file instead of overwriting",
                        "default": False,
                    },
                },
                "required": ["file_path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_directory",
            "description": (
                "List files and directories with metadata. Returns name, type, "
                "size, modified timestamp, and permissions for each entry."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "dir_path": {
                        "type": "string",
                        "description": "Directory path (default: current directory)",
                        "default": ".",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_files",
            "description": (
                "Search for text inside files (grep-like). Searches file contents "
                "using a regex pattern. Returns matching file path, line number, "
                "column, and the matching text. Skips binary files and hidden directories."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Text string or regex pattern to search for",
                    },
                    "dir_path": {
                        "type": "string",
                        "description": "Root directory to search in (default: current directory)",
                        "default": ".",
                    },
                    "glob_pattern": {
                        "type": "string",
                        "description": "File glob pattern to filter files (default: * for all)",
                        "default": "*",
                    },
                },
                "required": ["query"],
            },
        },
    },
    # -- Shell tools --------------------------------------------------------
    {
        "type": "function",
        "function": {
            "name": "execute_command",
            "description": (
                "Execute a shell command and return structured output including "
                "stdout, stderr, exit code, and duration. Dangerous commands are "
                "automatically blocked for safety."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "The shell command to execute",
                    },
                    "cwd": {
                        "type": "string",
                        "description": "Working directory (default: current directory)",
                        "default": ".",
                    },
                    "timeout": {
                        "type": "integer",
                        "description": "Maximum execution time in seconds (default 60, max 300)",
                        "default": 60,
                    },
                },
                "required": ["command"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_test",
            "description": (
                "Run the project's test suite. Auto-detects the test framework "
                "from project files (npm test, pytest, cargo test, go test, etc.). "
                "Returns test output, pass/fail status, and exit code."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "test_command": {
                        "type": "string",
                        "description": "Test command to run (default: auto-detect)",
                        "default": "npm test",
                    },
                    "cwd": {
                        "type": "string",
                        "description": "Working directory (default: current directory)",
                        "default": ".",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "install_dependency",
            "description": (
                "Install a package dependency. Auto-detects the package manager "
                "(npm, pip, cargo, go get, bundler) from project files."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "package": {
                        "type": "string",
                        "description": "Package name to install (e.g. 'requests', 'lodash')",
                    },
                    "cwd": {
                        "type": "string",
                        "description": "Working directory (default: current directory)",
                        "default": ".",
                    },
                },
                "required": ["package"],
            },
        },
    },
    # -- Git tools ----------------------------------------------------------
    {
        "type": "function",
        "function": {
            "name": "git_status",
            "description": (
                "Get the git working tree status. Returns current branch, "
                "ahead/behind counts, and lists of staged, unstaged, and untracked files."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "cwd": {
                        "type": "string",
                        "description": "Repository working directory (default: current directory)",
                        "default": ".",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "git_diff",
            "description": (
                "Show changes between commits, commit and working tree, etc. "
                "Returns the diff text and list of changed files."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "cwd": {
                        "type": "string",
                        "description": "Repository working directory",
                        "default": ".",
                    },
                    "staged": {
                        "type": "boolean",
                        "description": "If true, show staged changes instead of unstaged",
                        "default": False,
                    },
                    "file_path": {
                        "type": "string",
                        "description": "If provided, limit diff to this file",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "git_commit",
            "description": (
                "Create a git commit. Auto-stages all modified and deleted files. "
                "Returns the commit hash and message."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "message": {
                        "type": "string",
                        "description": "Commit message",
                    },
                    "cwd": {
                        "type": "string",
                        "description": "Repository working directory",
                        "default": ".",
                    },
                    "auto_stage": {
                        "type": "boolean",
                        "description": "If true, stage all changes before committing",
                        "default": True,
                    },
                },
                "required": ["message"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "git_branch",
            "description": (
                "List git branches or create a new branch. Returns current branch "
                "and a list of all branches with their names and current status."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "cwd": {
                        "type": "string",
                        "description": "Repository working directory",
                        "default": ".",
                    },
                    "create": {
                        "type": "string",
                        "description": "If provided, create a new branch with this name",
                    },
                    "list_all": {
                        "type": "boolean",
                        "description": "If true, list all branches",
                        "default": True,
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "git_log",
            "description": (
                "Show commit history. Returns structured commit info with hash, "
                "author, date, and message for each commit."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "cwd": {
                        "type": "string",
                        "description": "Repository working directory",
                        "default": ".",
                    },
                    "max_count": {
                        "type": "integer",
                        "description": "Maximum number of commits to return (default 20)",
                        "default": 20,
                    },
                    "file_path": {
                        "type": "string",
                        "description": "If provided, only show commits affecting this file",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "git_checkout",
            "description": (
                "Switch to a different git branch or commit. Returns the current "
                "branch after the operation."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "target": {
                        "type": "string",
                        "description": "Branch name, commit hash, or file path to checkout",
                    },
                    "cwd": {
                        "type": "string",
                        "description": "Repository working directory",
                        "default": ".",
                    },
                    "create": {
                        "type": "boolean",
                        "description": "If true, create the branch if it doesn't exist",
                        "default": False,
                    },
                },
                "required": ["target"],
            },
        },
    },
    # -- Code tools ---------------------------------------------------------
    {
        "type": "function",
        "function": {
            "name": "parse_ast",
            "description": (
                "Parse a source file into an AST structure. Supports Python and "
                "JavaScript/TypeScript (JS uses regex fallback). Returns functions, "
                "classes, imports, and the full AST structure."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Path to the source file",
                    },
                },
                "required": ["file_path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "find_references",
            "description": (
                "Find all references to a symbol (variable, function, class) "
                "in a source file. Returns line numbers, columns, and context "
                "for each reference."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {
                        "type": "string",
                        "description": "The symbol name to search for",
                    },
                    "file_path": {
                        "type": "string",
                        "description": "Path to the source file",
                    },
                },
                "required": ["symbol", "file_path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "refactor_rename",
            "description": (
                "Rename a symbol (function, class, variable) in a source file. "
                "Returns the number of renames performed and a preview of the "
                "modified source. The caller must write the result back with write_file."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "old_name": {
                        "type": "string",
                        "description": "Current symbol name",
                    },
                    "new_name": {
                        "type": "string",
                        "description": "New symbol name",
                    },
                    "file_path": {
                        "type": "string",
                        "description": "Path to the source file",
                    },
                },
                "required": ["old_name", "new_name", "file_path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "extract_function",
            "description": (
                "Extract a block of code (from start_line to end_line) into a "
                "new named function. Returns the extracted function source code "
                "which the caller can then insert elsewhere with write_file."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Path to the source file (for language detection)",
                    },
                    "start_line": {
                        "type": "integer",
                        "description": "First line to extract (1-based)",
                    },
                    "end_line": {
                        "type": "integer",
                        "description": "Last line to extract (1-based, inclusive)",
                    },
                    "new_name": {
                        "type": "string",
                        "description": "Name for the extracted function",
                    },
                },
                "required": ["file_path", "start_line", "end_line", "new_name"],
            },
        },
    },
]

# ---------------------------------------------------------------------------
# Tool dispatch map
# ---------------------------------------------------------------------------

_TOOL_FUNCTIONS: Dict[str, Callable] = {
    # File tools
    "read_file": read_file,
    "write_file": write_file,
    "list_directory": list_directory,
    "search_files": search_files,
    # Shell tools
    "execute_command": execute_command,
    "run_test": run_test,
    "install_dependency": install_dependency,
    # Git tools
    "git_status": git_status,
    "git_diff": git_diff,
    "git_commit": git_commit,
    "git_branch": git_branch,
    "git_log": git_log,
    "git_checkout": git_checkout,
    # Code tools
    "parse_ast": parse_ast,
    "find_references": find_references,
    "refactor_rename": refactor_rename,
    "extract_function": extract_function,
}

# ---------------------------------------------------------------------------
# Tool registry
# ---------------------------------------------------------------------------


class ToolRegistry:
    """
    Central registry for all agent tools.

    Collects tool schemas for LLM function calling and dispatches
    execution requests to the correct tool function.
    """

    def __init__(self) -> None:
        self._tools: Dict[str, Callable] = dict(_TOOL_FUNCTIONS)
        self._schemas: Dict[str, Dict[str, Any]] = {
            s["function"]["name"]: s for s in TOOL_DEFINITIONS
        }

    # -- Schema access ------------------------------------------------------

    def get_tool_schemas(self) -> List[Dict[str, Any]]:
        """
        Return all tool schemas in OpenAI function calling format.

        Returns
        -------
        list[dict]
            Tool definitions ready to pass to an LLM's ``tools`` parameter.
        """
        return list(TOOL_DEFINITIONS)

    def get_tool_names(self) -> List[str]:
        """Return a list of all registered tool names."""
        return list(self._tools.keys())

    def get_tool_schema(self, tool_name: str) -> Optional[Dict[str, Any]]:
        """Get the schema for a single tool by name."""
        return self._schemas.get(tool_name)

    def get_tool_description(self, tool_name: str) -> str:
        """Get the human-readable description for a tool."""
        schema = self._schemas.get(tool_name)
        if schema:
            return schema.get("function", {}).get("description", "")
        return ""

    # -- Tool execution -----------------------------------------------------

    def execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a tool by name with the given arguments.

        Parameters
        ----------
        tool_name:
            The registered name of the tool (e.g. ``"read_file"``).
        arguments:
            Keyword arguments to pass to the tool function.

        Returns
        -------
        dict
            The tool's result.  If the tool is not found, returns a dict
            with ``success: False`` and an error message.
        """
        if tool_name not in self._tools:
            available = ", ".join(sorted(self._tools.keys()))
            logger.error("Unknown tool: %s (available: %s)", tool_name, available)
            return {
                "success": False,
                "error": f"Unknown tool: '{tool_name}'. Available tools: {available}",
            }

        tool_func = self._tools[tool_name]
        logger.info(
            "Executing tool: %s(%s)",
            tool_name,
            ", ".join(f"{k}={repr(v)[:60]}" for k, v in arguments.items()),
        )

        try:
            # Inspect the function to determine if it's async
            if inspect.iscoroutinefunction(tool_func):
                import asyncio
                import concurrent.futures

                try:
                    # Check if we're already in an event loop (e.g., FastAPI)
                    asyncio.get_running_loop()
                    # We're in an async context — run in a thread pool
                    # to avoid "asyncio.run() cannot be called from a running loop"
                    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                        future = pool.submit(asyncio.run, tool_func(**arguments))
                        result = future.result()
                except RuntimeError:
                    # No running loop — safe to use asyncio.run directly
                    result = asyncio.run(tool_func(**arguments))
            else:
                result = tool_func(**arguments)

            # Normalize non-dict returns
            if not isinstance(result, dict):
                result = {"success": True, "output": result}

            return result

        except Exception as exc:
            logger.exception("Tool %s failed", tool_name)
            return {"success": False, "error": f"Tool execution failed: {exc}"}

    def has_tool(self, tool_name: str) -> bool:
        """Return *True* if the named tool is registered."""
        return tool_name in self._tools

    # -- Registration (extensibility) ---------------------------------------

    def register_tool(
        self,
        name: str,
        func: Callable,
        schema: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Register a new tool at runtime.

        Parameters
        ----------
        name:
            The tool name (used in LLM function calling).
        func:
            The callable to execute.
        schema:
            Optional OpenAI-format schema for the tool.
        """
        self._tools[name] = func
        if schema:
            self._schemas[name] = schema
        logger.info("Registered tool: %s", name)

    def unregister_tool(self, name: str) -> None:
        """Remove a tool from the registry."""
        self._tools.pop(name, None)
        self._schemas.pop(name, None)
        logger.info("Unregistered tool: %s", name)


# Convenience singleton
_default_registry: Optional[ToolRegistry] = None


def get_registry() -> ToolRegistry:
    """Return the default tool registry singleton."""
    global _default_registry
    if _default_registry is None:
        _default_registry = ToolRegistry()
    return _default_registry
