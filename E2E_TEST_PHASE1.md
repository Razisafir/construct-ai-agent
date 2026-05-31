# E2E Test — Phase 1: Real Goal, Real File

**Date**: 2026-05-31
**Tester**: Automated (CI server)
**Environment**: Linux x86_64, 7.9 GiB RAM, CPU-only (no GPU)

## Setup

| Component | Version | Notes |
|---|---|---|
| OS | Linux x86_64 | CI server, no GUI |
| Ollama | 0.24.0 | Installed from tar.zst, CPU-only |
| Model | tinyllama (0.6GB) | qwen2.5:3b failed — server OOM killed during download |
| Backend | FastAPI + uvicorn | CONSTRUCT_OFFLINE=1, port 8000 |
| ChromaDB | 1.5.9 | ONNX embedding model downloaded (79.3MB) |

## Test Execution

### Agent Start Request
```bash
curl -X POST http://127.0.0.1:8000/agent/start \
  -H "Content-Type: application/json" \
  -d '{"goal":"Create hello_world.py that prints Hello from Construct","project_path":"/home/z/construct-projects/default","mode":"code"}'
```

### Response
```json
{"session_id":"953fa5b3","goal":"Create hello_world.py that prints Hello from Construct","status":"idle","mode":"code","message":"Agent session started in code mode"}
```

### What Happened

1. **Session started successfully** — session `953fa5b3` created in code mode
2. **Observe phase worked** — `list_directory` and `git_status` tools executed
3. **Memory recall worked** — 1 memory entry injected into planning prompt
4. **ChromaDB ONNX model downloaded** (79.3MB, 42 seconds) — first-time initialization
5. **LLM call FAILED** — Ollama server was killed (OOM) by the ChromaDB embedding model download, consuming too much memory alongside uvicorn + chromadb processes
6. **Planning fell back** — Created 1 task (the goal itself) without LLM decomposition
7. **Acting phase FAILED** — LLM unreachable, agent couldn't execute tools

### Root Cause

The CI server has only 7.9 GiB RAM with no swap. Running Ollama (~500MB for tinyllama inference) + ChromaDB + ONNX embedding model + FastAPI simultaneously exceeds available memory, causing the Ollama server to be OOM-killed.

## Results

| Criterion | Status | Notes |
|---|---|---|
| File exists on disk with correct content | ❌ | Ollama killed before agent could call write_file |
| LLM log shows real Ollama calls | ❌ | Connection refused — Ollama was dead |
| Tools log shows write_file execution | ❌ | Agent couldn't reach LLM to plan tool calls |
| Diff appeared in Changes panel | ❌ | No Tauri GUI in CI |
| E2E_TEST_PHASE1.md committed | ✅ | This file |

## Memory System Verification

Despite the LLM failure, the memory system **did work correctly**:

- **ChromaDB conversation_embeddings**: 1 entry (planning phase stored successfully)
- **ChromaDB code_embeddings**: 1 entry (list_directory tool call stored)
- Memory writes are happening during execution as designed (Prompt 1.3 ✅)
- Memory recall injected into planning prompt (Prompt 1.4 ✅)

## Backend Log Highlights

```
[INFO] Starting session 953fa5b3 [code mode]: Create hello_world.py that prints Hello from Construct
[INFO] [953fa5b3] thought: Observing current project state...
[INFO] Executing tool: list_directory(dir_path='/home/z/construct-projects/default')
[INFO] ChromaDB client initialised at ./resources/memory/vector
[INFO] Injected 1 memory entries into planning prompt
[WARNING] Primary provider ollama streaming failed: Cannot connect to host 127.0.0.1:11434
[WARNING] Failed to parse LLM task plan as JSON: Expecting value: line 1 column 2 (char 1)
[INFO] [953fa5b3] plan: Created 1 tasks: Create hello_world.py that prints Hello from Construct
```

## Recommendations for Successful E2E

1. **Run on a machine with ≥16GB RAM** or add swap space
2. **Use `CONSTRUCT_OFFLINE=1`** to skip ONNX embedding model download (saves ~80MB RAM)
3. **Pre-download models** before starting the stack
4. **Use qwen2.5:3b** instead of tinyllama for better tool-calling capability
5. **Run on a machine with GUI** to test the DiffViewer (Prompt 1.5)
6. **Alternative**: Test the LLM → tool execution pipeline separately without ChromaDB overhead

## Architecture Verified (Partial)

| Component | Working? | Evidence |
|---|---|---|
| FastAPI `/agent/start` route | ✅ | Returned session_id in 44s (including ONNX download) |
| `AgentExecutor.start_session()` | ✅ | Created session, set base_dir, kicked off _run() |
| `observe()` phase | ✅ | list_directory + git_status executed |
| `plan()` phase | ✅ | Memory recalled, prompt assembled (LLM was down) |
| Memory write (planning) | ✅ | ChromaDB conversation_embeddings has entry |
| Memory write (code events) | ✅ | ChromaDB code_embeddings has entry |
| Memory recall in planning | ✅ | "Injected 1 memory entries into planning prompt" |
| LLM service (Ollama) | ❌ | OOM killed before could respond |
| `act()` phase | ❌ | Depends on LLM |
| `verify()` phase | ❌ | Depends on act() |
| File creation (write_file) | ❌ | Depends on act() |
| DiffViewer (React) | ❌ | No GUI in CI |
