"""
Ghidra Function Decompilation Script
=====================================

This is a Jython script designed to run **inside** Ghidra's
``analyzeHeadless`` environment. It decompiles a single named
function to C pseudocode and exports the result as JSON.

Usage (from host, via GhidraTool)::

    ghidra.decompile_function("/path/to/binary", "main")

Or manually::

    $GHIDRA/support/analyzeHeadless /tmp/projects temp_project \\
        -import /path/to/binary \\
        -postScript ghidra_decompile.py main /tmp/decomp.json \\
        -deleteProject

Required Ghidra API objects (injected by the runtime):
    - ``currentProgram`` — the analyzed Program object
    - ``monitor`` — TaskMonitor for progress/cancellation
    - ``state`` — PluginTool state
"""

# Jython / Ghidra API imports (unavailable outside Ghidra)
try:
    from ghidra.app.decompiler import DecompInterface
    from ghidra.program.model.symbol import SymbolType
    from ghidra.program.flatapi import FlatProgramAPI

    HAS_GHIDRA_API = True
except ImportError:
    HAS_GHIDRA_API = False

import json
import os


def run_decompile(function_name, output_path):
    """Decompile a specific function and export to JSON.

    Parameters
    ----------
    function_name:
        Name of the function to decompile (e.g., ``"main"``).
    output_path:
        Path where the JSON result will be written.
    """

    if not HAS_GHIDRA_API:
        raise RuntimeError(
            "This script must be run inside Ghidra's analyzeHeadless. "
            "Ghidra API objects (currentProgram, monitor) are injected by the runtime."
        )

    # Access Ghidra globals injected by the scripting runtime
    program = currentProgram  # noqa: F821 — injected by Ghidra
    task_monitor = monitor  # noqa: F821 — injected by Ghidra

    flat_api = FlatProgramAPI(program, task_monitor)

    result = {
        "program_name": program.getName(),
        "function_name": function_name,
        "c_code": None,
        "address": None,
        "signature": None,
        "error": None,
    }

    # ------------------------------------------------------------------
    # Find the target function
    # ------------------------------------------------------------------
    func_manager = program.getFunctionManager()
    target_func = None

    # First pass: exact match
    for func in func_manager.getFunctions(True):
        if func.getName() == function_name:
            target_func = func
            break

    # Second pass: case-insensitive match
    if target_func is None:
        for func in func_manager.getFunctions(True):
            if func.getName().lower() == function_name.lower():
                target_func = func
                break

    # Third pass: substring match
    if target_func is None:
        candidates = []
        for func in func_manager.getFunctions(True):
            if function_name.lower() in func.getName().lower():
                candidates.append(func)
        if len(candidates) == 1:
            target_func = candidates[0]
        elif len(candidates) > 1:
            result["error"] = (
                "Multiple functions match '%s': %s" % (
                    function_name,
                    ", ".join(f.getName() for f in candidates[:10])
                )
            )
            _write_result(output_path, result)
            return

    if target_func is None:
        # List available functions for the error message
        available = [f.getName() for f in func_manager.getFunctions(True)]
        result["error"] = (
            "Function '%s' not found. Available functions (%d): %s" % (
                function_name,
                len(available),
                ", ".join(available[:50])  # limit to first 50
            )
        )
        _write_result(output_path, result)
        return

    # ------------------------------------------------------------------
    # Decompile the function
    # ------------------------------------------------------------------
    entry_point = target_func.getEntryPoint()
    result["address"] = str(entry_point)

    # Build signature string
    try:
        ret_type = target_func.getReturnType()
        params = target_func.getParameters()
        param_strs = []
        for p in params:
            param_strs.append("%s %s" % (p.getDataType(), p.getName()))
        signature = "%s %s(%s)" % (
            ret_type if ret_type else "void",
            target_func.getName(),
            ", ".join(param_strs),
        )
        result["signature"] = signature
    except Exception as sig_exc:
        result["signature"] = "unknown /* %s */" % str(sig_exc)

    # Initialize decompiler
    decomp = DecompInterface()
    decomp.openProgram(program)

    try:
        decomp_result = decomp.decompileFunction(target_func, 60, task_monitor)

        if decomp_result.decompileCompleted():
            c_code = str(decomp_result.getDecompiledFunction().getC())
            result["c_code"] = c_code
            print("[ghidra_decompile] Decompiled '%s' at %s (%d lines)" % (
                function_name,
                result["address"],
                len(c_code.splitlines()),
            ))
        else:
            error_msg = decomp_result.getErrorMessage()
            result["error"] = "Decompilation failed: %s" % (error_msg or "unknown error")
            print("[ghidra_decompile] ERROR: %s" % result["error"])

    except Exception as exc:
        result["error"] = "Decompilation exception: %s" % str(exc)
        print("[ghidra_decompile] ERROR: %s" % result["error"])
    finally:
        decomp.dispose()

    _write_result(output_path, result)


def _write_result(output_path, result):
    """Write the result dict to a JSON file."""
    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    with open(output_path, "w") as f:
        json.dump(result, f, indent=2)

    print("[ghidra_decompile] Wrote result to: " + output_path)


# ---------------------------------------------------------------------------
# Ghidra script entry point
# ---------------------------------------------------------------------------
if HAS_GHIDRA_API:
    try:
        script_args = getScriptArgs()  # noqa: F821 — injected by Ghidra
        if len(script_args) >= 2:
            func_name = script_args[0]
            out_file = script_args[1]
        elif len(script_args) == 1:
            func_name = script_args[0]
            import tempfile
            out_file = os.path.join(tempfile.gettempdir(), "ghidra_decompile.json")
        else:
            raise ValueError(
                "Usage: ghidra_decompile.py <function_name> <output.json>"
            )
        run_decompile(func_name, out_file)
    except Exception as e:
        print("[ghidra_decompile] ERROR: " + str(e))
        raise
