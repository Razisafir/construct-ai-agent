# Configuration Guide

> **Version:** 0.1.0  
> **Last Updated:** 2026-05-28

---

## Overview

Construct uses environment variables for configuration. Copy the example file and customize:

```bash
cp agent-backend/.env.example agent-backend/.env
```

All environment variables are loaded from the `.env` file in the `agent-backend/` directory.

---

## LLM Providers

Configure at least one cloud provider or ensure Ollama is running locally.

### OpenAI

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `OPENAI_API_KEY` | **Yes** | — | Your OpenAI API key |
| `OPENAI_MODEL` | No | `gpt-4o` | Model identifier |
| `OPENAI_TEMPERATURE` | No | `0.7` | Sampling temperature (0.0–2.0) |
| `OPENAI_MAX_TOKENS` | No | `4096` | Maximum tokens per response |

```bash
OPENAI_API_KEY=sk-proj-xxxxxxxxxxxxxxxxxxxxxxxx
OPENAI_MODEL=gpt-4o
OPENAI_TEMPERATURE=0.7
OPENAI_MAX_TOKENS=4096
```

### Anthropic

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `ANTHROPIC_API_KEY` | **Yes** | — | Your Anthropic API key |
| `ANTHROPIC_MODEL` | No | `claude-sonnet-4-20250514` | Model identifier |
| `ANTHROPIC_TEMPERATURE` | No | `0.7` | Sampling temperature (0.0–1.0) |
| `ANTHROPIC_MAX_TOKENS` | No | `4096` | Maximum tokens per response |

```bash
ANTHROPIC_API_KEY=sk-ant-api03-xxxxxxxxxxxxxxxxxxxxxxxx
ANTHROPIC_MODEL=claude-sonnet-4-20250514
ANTHROPIC_TEMPERATURE=0.7
ANTHROPIC_MAX_TOKENS=4096
```

### Google

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `GOOGLE_API_KEY` | **Yes** | — | Your Google AI API key |
| `GOOGLE_MODEL` | No | `gemini-1.5-pro` | Model identifier |
| `GOOGLE_TEMPERATURE` | No | `0.7` | Sampling temperature (0.0–2.0) |
| `GOOGLE_MAX_TOKENS` | No | `4096` | Maximum tokens per response |

```bash
GOOGLE_API_KEY=AIzaSyxxxxxxxxxxxxxxxxxxxxxxxx
GOOGLE_MODEL=gemini-1.5-pro
GOOGLE_TEMPERATURE=0.7
GOOGLE_MAX_TOKENS=4096
```

### Ollama (Local)

Ollama is always configured as a fallback provider. No API key is required.

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `OLLAMA_HOST` | No | `http://localhost:11434` | Ollama server URL |
| `OLLAMA_MODEL` | No | `qwen2.5-coder:14b` | Default local model |
| `OLLAMA_TEMPERATURE` | No | `0.7` | Sampling temperature |
| `OLLAMA_MAX_TOKENS` | No | `4096` | Maximum tokens per response |

```bash
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=qwen2.5-coder:14b
OLLAMA_TEMPERATURE=0.7
OLLAMA_MAX_TOKENS=4096
```

**Recommended Ollama models:**

| Model | Size | Speed | Code Quality |
|-------|------|-------|--------------|
| `qwen2.5-coder:14b` | 14B | Fast | Excellent |
| `qwen2.5-coder:32b` | 32B | Medium | Outstanding |
| `codellama:13b` | 13B | Fast | Good |
| `deepseek-coder:33b` | 33B | Slow | Excellent |

---

## Agent Settings

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `MAX_TOOL_CALLS_PER_TASK` | No | `10` | Maximum tool calls before the agent stops for a single task |
| `REQUIRE_APPROVAL` | No | `destructive_only` | When to require human approval: `none`, `destructive_only`, `all` |
| `AGENT_MAX_CPU` | No | `30.0` | Maximum CPU percentage the background worker can use |
| `AGENT_MAX_MEMORY` | No | `2048.0` | Maximum memory (MB) the background worker can use |

```bash
MAX_TOOL_CALLS_PER_TASK=10
REQUIRE_APPROVAL=destructive_only
AGENT_MAX_CPU=30.0
AGENT_MAX_MEMORY=2048.0
```

### Approval Levels

| Level | Behavior |
|-------|----------|
| `none` | No approval required for any operation (not recommended) |
| `destructive_only` | Only destructive operations need approval (default) |
| `all` | All operations need explicit user approval |

**Destructive operations include:**
- Deleting files or directories
- Force-pushing to git
- Running shell commands that modify system state
- Installing dependencies globally

---

## Memory Settings

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DB_PATH` | No | (auto) | SQLite database file path |
| `CHROMA_PATH` | No | `./chroma_data` | ChromaDB storage directory |
| `MEMORY_API_HOST` | No | `127.0.0.1` | FastAPI server bind address |
| `MEMORY_API_PORT` | No | `8000` | FastAPI server port |

```bash
DB_PATH=/path/to/construct.db
CHROMA_PATH=./chroma_data
MEMORY_API_HOST=127.0.0.1
MEMORY_API_PORT=8000
```

### SQLite Auto-Paths

If `DB_PATH` is not set, the database is stored in the OS app data directory:

| OS | Default Path |
|----|-------------|
| macOS | `~/Library/Application Support/construct/construct.db` |
| Windows | `%APPDATA%\construct\construct.db` |
| Linux | `~/.local/share/construct/construct.db` |

---

## Tauri Settings

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `TAURI_PORT` | No | `3000` | Port for Tauri-to-Python notification bridge |

```bash
TAURI_PORT=3000
```

---

## MCP (Model Context Protocol) Settings

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `MCP_GITHUB_TOKEN` | No | — | GitHub Personal Access Token for GitHub MCP |
| `MCP_SERVERS` | No | — | Comma-separated list of MCP server names to enable |

```bash
MCP_GITHUB_TOKEN=ghp_xxxxxxxxxxxxxxxxxxxxxxxx
MCP_SERVERS=github,gitlab,slack
```

---

## Security Settings

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `AGENTSHIELD_ENABLED` | No | `true` | Enable the AgentShield security scanner |
| `MAX_FILE_DELETIONS_PER_SESSION` | No | `10` | Maximum file deletions allowed per session |
| `BLOCKED_SHELL_COMMANDS` | No | — | Comma-separated list of shell commands to block |

```bash
AGENTSHIELD_ENABLED=true
MAX_FILE_DELETIONS_PER_SESSION=10
BLOCKED_SHELL_COMMANDS=rm -rf,dd,fdisk,mkfs
```

---

## Development Settings

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `RUST_LOG` | No | `info` | Rust logging level (error, warn, info, debug, trace) |
| `PYTHON_LOG_LEVEL` | No | `INFO` | Python logging level |
| `TAURI_DEV_TOOLS` | No | `false` | Auto-open DevTools in development mode |

```bash
RUST_LOG=debug
PYTHON_LOG_LEVEL=DEBUG
TAURI_DEV_TOOLS=true
```

---

## Full Example `.env` File

```bash
# ============================================
# Construct Configuration
# ============================================

# --- LLM Providers (configure at least one) ---
OPENAI_API_KEY=sk-proj-xxxxxxxxxxxxxxxxxxxxxxxx
OPENAI_MODEL=gpt-4o
OPENAI_TEMPERATURE=0.7
OPENAI_MAX_TOKENS=4096

ANTHROPIC_API_KEY=sk-ant-api03-xxxxxxxxxxxxxxxxxxxxxxxx
ANTHROPIC_MODEL=claude-sonnet-4-20250514
ANTHROPIC_TEMPERATURE=0.7
ANTHROPIC_MAX_TOKENS=4096

# GOOGLE_API_KEY=AIzaSyxxxxxxxxxxxxxxxxxxxxxxxx
# GOOGLE_MODEL=gemini-1.5-pro

OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=qwen2.5-coder:14b
OLLAMA_TEMPERATURE=0.7
OLLAMA_MAX_TOKENS=4096

# --- Agent Settings ---
MAX_TOOL_CALLS_PER_TASK=10
REQUIRE_APPROVAL=destructive_only
AGENT_MAX_CPU=30.0
AGENT_MAX_MEMORY=2048.0

# --- Memory Settings ---
# DB_PATH=/custom/path/construct.db
CHROMA_PATH=./chroma_data
MEMORY_API_HOST=127.0.0.1
MEMORY_API_PORT=8000

# --- Tauri ---
TAURI_PORT=3000

# --- MCP ---
# MCP_GITHUB_TOKEN=ghp_xxxxxxxxxxxxxxxxxxxxxxxx

# --- Security ---
AGENTSHIELD_ENABLED=true
MAX_FILE_DELETIONS_PER_SESSION=10

# --- Development ---
RUST_LOG=info
PYTHON_LOG_LEVEL=INFO
```

---

## Configuration Priority

Configuration values are loaded in this priority order (highest first):

1. Environment variables set in the shell
2. Values in `agent-backend/.env` file
3. Default values built into the code

This means you can temporarily override any setting:

```bash
# Override for a single run
OPENAI_MODEL=gpt-4o-mini npm run tauri:dev
```
