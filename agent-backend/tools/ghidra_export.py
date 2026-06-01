"""
Ghidra Post-Analysis Export Script
====================================

This is a Jython script designed to run **inside** Ghidra's
``analyzeHeadless`` environment. It exports function listings,
strings, memory sections, imports, and metadata to a JSON file.

Usage (from host, via GhidraTool)::

    ghidra.analyze_binary("/path/to/binary")

Or manually::

    $GHIDRA/support/analyzeHeadless /tmp/projects temp_project \\
        -import /path/to/binary \\
        -postScript ghidra_export.py /tmp/output.json \\
        -deleteProject

The script uses Ghidra's built-in API objects:
    - ``currentProgram`` — the analyzed Program object
    - ``monitor`` — TaskMonitor for progress/cancellation
    - ``state`` — PluginTool state
"""

# Jython / Ghidra API imports (unavailable outside Ghidra)
# These are injected by the Ghidra scripting runtime.
try:
    from ghidra.program.model.listing import CodeUnit
    from ghidra.program.model.symbol import SymbolType
    from ghidra.util.task import ConsoleTaskMonitor
    from ghidra.app.script import GhidraScript
    from ghidra.program.flatapi import FlatProgramAPI

    HAS_GHIDRA_API = True
except ImportError:
    HAS_GHIDRA_API = False

import json
import os


def run_script(output_path):
    """Main entry point — called by Ghidra's script runner."""

    if not HAS_GHIDRA_API:
        raise RuntimeError(
            "This script must be run inside Ghidra's analyzeHeadless. "
            "Ghidra API objects (currentProgram, monitor) are injected by the runtime."
        )

    # Access Ghidra's globals injected by the scripting runtime
    program = currentProgram  # noqa: F821 — injected by Ghidra
    task_monitor = monitor  # noqa: F821 — injected by Ghidra

    flat_api = FlatProgramAPI(program, task_monitor)

    result = {
        "program_name": program.getName(),
        "functions": [],
        "strings": [],
        "sections": [],
        "imports": [],
        "metadata": {},
    }

    # ------------------------------------------------------------------
    # Metadata
    # ------------------------------------------------------------------
    exe_format = program.getExecutableFormat()
    lang = program.getLanguage()
    compiler = program.getCompilerSpec()

    result["metadata"] = {
        "format": str(exe_format),
        "language_id": str(lang.getLanguageID()),
        "processor": str(lang.getProcessor()),
        "compiler": str(compiler.getCompilerSpecID()),
        "base_address": str(program.getMinAddress()),
        "entry_point": str(program.getEntryPoint()) if program.getEntryPoint() else None,
        "memory_blocks": program.getMemory().getNumBlocks(),
        "creation_date": str(program.getCreationDate()),
    }

    # ------------------------------------------------------------------
    # Functions
    # ------------------------------------------------------------------
    func_manager = program.getFunctionManager()
    for func in func_manager.getFunctions(True):
        entry = func.getEntryPoint()
        body = func.getBody()

        func_info = {
            "name": str(func.getName()),
            "entry_point": str(entry),
            "size": body.getNumAddresses(),
            "return_type": str(func.getReturnType()) if func.getReturnType() else None,
            "calling_convention": str(func.getCallingConventionName()),
            "parameter_count": func.getParameterCount(),
            "is_external": func.isExternal(),
            "is_thunk": func.isThunk(),
        }
        result["functions"].append(func_info)

    # ------------------------------------------------------------------
    # Strings
    # ------------------------------------------------------------------
    string_table = flat_api.getStrings(True)
    for string_data in string_table:
        string_info = {
            "value": str(string_data.getString()),
            "address": str(string_data.getAddress()),
            "length": string_data.getLength(),
            "string_type": str(string_data.getStringType()),
        }
        result["strings"].append(string_info)

    # ------------------------------------------------------------------
    # Memory Sections
    # ------------------------------------------------------------------
    memory = program.getMemory()
    for block in memory.getBlocks():
        perms = []
        if block.isRead():
            perms.append("r")
        if block.isWrite():
            perms.append("w")
        if block.isExecute():
            perms.append("x")

        section_info = {
            "name": str(block.getName()),
            "start": str(block.getStart()),
            "end": str(block.getEnd()),
            "size": block.getSize(),
            "permissions": "".join(perms) if perms else "none",
            "is_initialized": block.isInitialized(),
            "is_loaded": block.isLoaded(),
        }
        result["sections"].append(section_info)

    # ------------------------------------------------------------------
    # Imports
    # ------------------------------------------------------------------
    symbol_table = program.getSymbolTable()
    for symbol in symbol_table.getExternalSymbols():
        if symbol.getSymbolType() == SymbolType.FUNCTION:
            lib_name = symbol.getLibraryName() if hasattr(symbol, "getLibraryName") else "unknown"
            result["imports"].append({
                "name": str(symbol.getName()),
                "address": str(symbol.getAddress()),
                "library": str(lib_name),
            })

    # ------------------------------------------------------------------
    # Security-relevant features
    # ------------------------------------------------------------------
    result["metadata"]["nx_bit"] = _has_nx_bit(memory)
    result["metadata"]["canary"] = _has_stack_canary(program, func_manager)
    result["metadata"]["pie"] = _is_pie(program)
    result["metadata"]["relro"] = _has_relro(program)

    # ------------------------------------------------------------------
    # Write JSON output
    # ------------------------------------------------------------------
    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    with open(output_path, "w") as f:
        json.dump(result, f, indent=2)

    print("[ghidra_export] Wrote analysis to: " + output_path)
    print("[ghidra_export] Functions: %d, Strings: %d, Sections: %d" % (
        len(result["functions"]),
        len(result["strings"]),
        len(result["sections"]),
    ))


def _has_nx_bit(memory):
    """Check if NX (No-Execute) bit is set for stack/heap regions."""
    try:
        for block in memory.getBlocks():
            name = block.getName().lower()
            if any(seg in name for seg in ["stack", "heap"]):
                if block.isExecute():
                    return False
        return True
    except Exception:
        return None


def _has_stack_canary(program, func_manager):
    """Heuristic: check for stack canary references in function bodies."""
    try:
        for func in func_manager.getFunctions(True):
            name = func.getName().lower()
            if any(canary in name for canary in ["__stack_chk_fail", "__stack_chk_guard"]):
                return True
        return False
    except Exception:
        return None


def _is_pie(program):
    """Check if the binary is position-independent (PIE)."""
    try:
        base = program.getMinAddress()
        # If base address is very low, likely PIE/ASLR-enabled
        base_val = base.getOffset()
        return base_val < 0x10000
    except Exception:
        return None


def _has_relro(program):
    """Check for RELRO (RELocation Read-Only)."""
    try:
        memory = program.getMemory()
        for block in memory.getBlocks():
            name = block.getName().lower()
            if ".got.plt" in name and not block.isWrite():
                return "full"
            if ".got" in name and not block.isWrite():
                return "partial"
        return "none"
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Ghidra script entry point
# ---------------------------------------------------------------------------
# When run inside Ghidra, the script runner sets up the environment
# and the following code executes automatically.
if HAS_GHIDRA_API:
    # The output path is passed as the first script argument
    try:
        script_args = getScriptArgs()  # noqa: F821 — injected by Ghidra
        if script_args:
            output_file = script_args[0]
        else:
            # Fallback: use a temp path
            import tempfile
            output_file = os.path.join(tempfile.gettempdir(), "ghidra_export.json")
        run_script(output_file)
    except Exception as e:
        print("[ghidra_export] ERROR: " + str(e))
        raise
