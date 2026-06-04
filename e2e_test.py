#!/usr/bin/env python3
"""
E2E File Creation Test — Standalone Script
Starts the backend, runs all tests, and documents results.
"""
import json
import os
import sys
import time
import subprocess
import signal
import urllib.request
import urllib.error

# Configuration
BACKEND_PORT = 8000
BASE_URL = f"http://127.0.0.1:{BACKEND_PORT}"
PROJECT_DIR = os.path.expanduser("~/construct-projects/default")

# Test results
results = []
current_test = None

def record(step, expected, actual, passed):
    results.append({"step": step, "expected": expected, "actual": actual, "pass": passed})
    status = "PASS" if passed else "FAIL"
    print(f"  [{status}] {step}")
    if not passed:
        print(f"    Expected: {expected}")
        print(f"    Actual:   {actual}")

def api_get(path):
    try:
        req = urllib.request.Request(f"{BASE_URL}{path}")
        with urllib.request.urlopen(req, timeout=5) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        return {"error": str(e)}

def api_post(path, data):
    try:
        body = json.dumps(data).encode()
        req = urllib.request.Request(
            f"{BASE_URL}{path}",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        try:
            body = e.read().decode()
            return {"http_error": e.code, "body": body}
        except:
            return {"http_error": e.code}
    except Exception as e:
        return {"error": str(e)}

def file_exists(path):
    return os.path.exists(path)

def read_file(path):
    try:
        with open(path, 'r') as f:
            return f.read()
    except FileNotFoundError:
        return None
    except Exception as e:
        return f"ERROR: {e}"

# ============================================================
# Start Backend
# ============================================================
print("=" * 60)
print("E2E FILE CREATION TEST — Starting Backend")
print("=" * 60)

env = os.environ.copy()
env["CONSTRUCT_MOCK_LLM"] = "1"
env["CONSTRUCT_OFFLINE"] = "1"
env["PATH"] = os.path.expanduser("~/.local/bin:") + env.get("PATH", "")

proc = subprocess.Popen(
    [sys.executable, "-m", "uvicorn", "app:app", "--host", "127.0.0.1", "--port", str(BACKEND_PORT)],
    cwd=os.path.expanduser("~/construct-ai-agent/agent-backend"),
    env=env,
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
)

# Wait for startup
print("Waiting for backend to start...")
time.sleep(12)

# Check if alive
health = api_get("/health")
if "error" in health:
    print(f"Backend failed to start: {health['error']}")
    proc.terminate()
    sys.exit(1)

print(f"Backend started. Status: {health.get('status')}")
print(f"LLM Providers: {health.get('llm_providers')}")
print()

# ============================================================
# TEST C: Direct Tool Execution
# ============================================================
print("=" * 60)
print("TEST C: Direct Tool Execution")
print("=" * 60)

# Step C1: Health check
h = api_get("/health")
record("C1: Health check", "status=ok", f"status={h.get('status')}", h.get("status") == "ok")

# Step C2: Write file with relative path (will go to CWD)
r = api_post("/tools/execute", {
    "tool_name": "write_file",
    "arguments": {
        "file_path": "direct_test.py",
        "content": 'print("Direct tool test")\n'
    }
})
success = r.get("result", {}).get("success", False)
record("C2: write_file relative path", "success=true", f"success={success}", success)

# Verify on disk (relative = CWD = agent-backend)
content_cwd = read_file(os.path.expanduser("~/construct-ai-agent/agent-backend/direct_test.py"))
record("C2b: File on disk (CWD)", 'print("Direct tool test")', str(content_cwd)[:50] if content_cwd else "NOT FOUND", content_cwd and "Direct tool test" in content_cwd)

# Step C3: Write file with absolute path to project dir
r2 = api_post("/tools/execute", {
    "tool_name": "write_file",
    "arguments": {
        "file_path": f"{PROJECT_DIR}/e2e_test.py",
        "content": 'print("E2E test - absolute path")\n\n# Created via direct tool execution\n# Testing write_file with absolute path\n'
    }
})
success2 = r2.get("result", {}).get("success", False)
record("C3: write_file absolute path", "success=true", f"success={success2}", success2)

# Verify on disk
content_abs = read_file(f"{PROJECT_DIR}/e2e_test.py")
record("C3b: File on disk (absolute)", "E2E test", str(content_abs)[:100] if content_abs else "NOT FOUND", content_abs and "E2E test" in content_abs)

# Step C4: Read file back via tool
r3 = api_post("/tools/execute", {
    "tool_name": "read_file",
    "arguments": {
        "file_path": f"{PROJECT_DIR}/e2e_test.py"
    }
})
content_read = r3.get("result", {}).get("content", "")
record("C4: read_file roundtrip", "E2E test content", str(content_read)[:100], "E2E test" in content_read)

# Step C5: List directory via tool
r4 = api_post("/tools/execute", {
    "tool_name": "list_directory",
    "arguments": {
        "dir_path": PROJECT_DIR
    }
})
entries = r4.get("result", {}).get("entries", [])
filenames = [e.get("name") for e in entries] if isinstance(entries, list) else []
record("C5: list_directory", "e2e_test.py in listing", str(filenames), "e2e_test.py" in filenames)

print()

# ============================================================
# TEST B: Mock LLM Agent Loop
# ============================================================
print("=" * 60)
print("TEST B: Mock LLM Agent Loop")
print("=" * 60)

# Step B1: Start agent session with mock LLM
r5 = api_post("/agent/start", {
    "goal": "Create mock_test.py that prints hello",
    "project_path": PROJECT_DIR,
    "mode": "code"
})
session_id = r5.get("session_id", "")
session_status = r5.get("status", "")
record("B1: Agent session started", "session_id + status=running", f"session_id={session_id}, status={session_status}", bool(session_id))

if session_id:
    print(f"  Session ID: {session_id}")
    
    # Step B2: Wait for agent to execute
    print("  Waiting for agent to execute (max 30s)...")
    for i in range(30):
        time.sleep(1)
        status_resp = api_get(f"/agent/{session_id}/status")
        current_status = status_resp.get("status", "")
        task_summary = status_resp.get("task_summary", {})
        print(f"  [{i+1}s] status={current_status}, tasks={task_summary}")
        if current_status in ("completed", "failed"):
            break
    
    record("B2: Agent completed", "status=completed", f"status={current_status}", current_status == "completed")
    
    # Step B3: Check if mock_test.py was created on disk
    content_mock = read_file(f"{PROJECT_DIR}/mock_test.py")
    record("B3: mock_test.py on disk", "prints hello", str(content_mock)[:200] if content_mock else "FILE NOT FOUND", 
           content_mock is not None and content_mock != "FILE NOT FOUND")
    
    # Step B4: Get output log
    output_resp = api_get(f"/agent/{session_id}/output")
    events = output_resp.get("events", [])
    tool_calls = [e for e in events if "write_file" in str(e)]
    print(f"  Output events: {len(events)}")
    print(f"  write_file events: {len(tool_calls)}")
    record("B4: Agent output log", "write_file events > 0", f"write_file events: {len(tool_calls)}", len(tool_calls) > 0)
    
    # Step B5: Check session status details
    if task_summary:
        print(f"  Task summary: {task_summary}")
        record("B5: Task summary", "completed > 0", str(task_summary), task_summary.get("completed", 0) > 0)
    
    # Step B6: Print some output events for debugging
    if events:
        print(f"\n  First 10 output events:")
        for e in events[:10]:
            print(f"    {json.dumps(e)[:200]}")
else:
    record("B1: Agent session started", "session_id", "FAILED - no session_id", False)
    current_status = "never_started"

print()

# ============================================================
# TEST D: File Modification + Diff Simulation
# ============================================================
print("=" * 60)
print("TEST D: File Modification + Diff Simulation")
print("=" * 60)

# Step D1: Write initial file
r6 = api_post("/tools/execute", {
    "tool_name": "write_file",
    "arguments": {
        "file_path": f"{PROJECT_DIR}/modify_test.py",
        "content": 'print("Version 1")\n\ndef original():\n    return "original"\n'
    }
})
content_v1 = read_file(f"{PROJECT_DIR}/modify_test.py")
record("D1: Create modify_test.py", "Version 1", str(content_v1)[:50] if content_v1 else "NOT FOUND", content_v1 and "Version 1" in content_v1)

# Step D2: Overwrite file (simulating agent modification)
r7 = api_post("/tools/execute", {
    "tool_name": "write_file",
    "arguments": {
        "file_path": f"{PROJECT_DIR}/modify_test.py",
        "content": 'print("Version 2 - Updated via diff")\n\ndef modified():\n    return "updated"\n'
    }
})
content_v2 = read_file(f"{PROJECT_DIR}/modify_test.py")
record("D2: Overwrite modify_test.py", "Version 2", str(content_v2)[:50] if content_v2 else "NOT FOUND", content_v2 and "Version 2" in content_v2)

# Step D3: Verify file ACTUALLY changed on disk
record("D3: File actually changed on disk", "Version 2 - Updated via diff", str(content_v2)[:80] if content_v2 else "NOT FOUND",
       content_v2 and "Updated via diff" in content_v2)

print()

# ============================================================
# Summary
# ============================================================
print("=" * 60)
print("TEST SUMMARY")
print("=" * 60)

total = len(results)
passed = sum(1 for r in results if r["pass"])
failed = total - passed

for r in results:
    status = "PASS" if r["pass"] else "FAIL"
    print(f"  [{status}] {r['step']}")

print()
print(f"Total: {total} | Passed: {passed} | Failed: {failed}")
print()

if failed > 0:
    print("FAILED TESTS:")
    for r in results:
        if not r["pass"]:
            print(f"  - {r['step']}")
            print(f"    Expected: {r['expected']}")
            print(f"    Actual:   {r['actual']}")
    print()

# Verdict
all_pass = failed == 0
print(f"VERDICT: {'ALL PASS' if all_pass else 'CRITICAL BUGS FOUND'}")
print()

# List files in project dir
print(f"Files in {PROJECT_DIR}:")
for f in os.listdir(PROJECT_DIR):
    fpath = os.path.join(PROJECT_DIR, f)
    size = os.path.getsize(fpath) if os.path.isfile(fpath) else 0
    print(f"  {f} ({size} bytes)")
    if f.endswith('.py'):
        content = read_file(fpath)
        if content:
            print(f"    Content: {content[:100]}")

# Cleanup
proc.terminate()
try:
    proc.wait(timeout=5)
except:
    proc.kill()
print("\nBackend terminated.")

# Output JSON results
with open(os.path.expanduser("~/my-project/e2e_results.json"), "w") as f:
    json.dump({"results": results, "total": total, "passed": passed, "failed": failed, "all_pass": all_pass}, f, indent=2)
print("Results saved to ~/my-project/e2e_results.json")
