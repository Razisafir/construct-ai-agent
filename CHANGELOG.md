# Changelog

> All notable changes to Construct will be documented in this file.  
> This project adheres to [Semantic Versioning](https://semver.org/).

---

## [0.1.0] - 2026-05-28

### Added

- **Initial release** with full 6-phase development lifecycle
- **Tauri v2 desktop app** with React 18 + TypeScript + Tailwind CSS frontend
- **Persistent memory system** with dual-layer architecture:
  - SQLite layer (Rust) for structured data: conversations, code events, preferences, project state
  - ChromaDB layer (Python) for semantic search with sentence-transformer embeddings
- **Multi-provider LLM integration** supporting:
  - OpenAI GPT-4o for complex reasoning
  - Anthropic Claude Sonnet for code generation
  - Google Gemini 1.5 Pro for long context
  - Ollama (local) qwen2.5-coder:14b for fast, private inference
  - Smart routing: automatically selects the best provider based on prompt complexity
  - Automatic fallback to Ollama on cloud provider failure
- **21 built-in tools** across 4 categories:
  - File: read_file, write_file, list_directory, search_files
  - Shell: execute_command, run_test, install_dependency
  - Git: git_status, git_diff, git_commit, git_branch, git_log, git_checkout
  - Code: parse_ast, find_references, refactor_rename, extract_function
- **Agent execution loop**: observe -> plan -> act -> verify with iterative refinement
- **Autonomous mode** with background worker:
  - Continuous task execution without user intervention
  - Resource monitoring (CPU/memory throttling)
  - Automatic checkpointing for fault tolerance
  - Goal queue with priority levels (critical, high, normal, low)
- **7 specialized agent roles**:
  - Code Engineer, Test Engineer, Security Auditor, DevOps Engineer
  - UI Designer, Researcher, Project Manager, Legal Reviewer
- **Skill marketplace**: Document-to-skill pipeline for teaching the agent new capabilities
- **MCP connector**: Integration with 20+ MCP servers for external tool access
- **Screen control**: Desktop automation capabilities for GUI interactions
- **AgentShield security scanner**: Automated security scanning and approval controls
- **Premium glass-morphism UI**:
  - Monaco code editor with custom "construct-dark" theme
  - Real-time streaming output panel
  - Task progress visualization
  - Memory browser with semantic search
  - System tray integration

### Technical

- **Rust backend**: 20 Tauri commands for memory, agent, and autonomous control
- **Python backend**: FastAPI server with 39+ REST endpoints
- **SQLite WAL mode** for high-performance concurrent access
- **CORS-enabled** API for local development
- **Streaming LLM responses** for real-time UI updates
- **Tauri event system** for agent output streaming
- **System tray** with context menu
- **Cross-platform builds**: macOS (.app), Windows (.msi), Linux (.deb/.AppImage)

---

## Planned Releases

### [0.2.0] - Target: Q3 2026

- VS Code extension for remote agent control
- Collaborative editing with real-time sync
- Plugin marketplace for community tools
- Enhanced code review with inline suggestions
- Multi-project workspace support

### [0.3.0] - Target: Q4 2026

- Web version (webassembly compilation)
- CI/CD pipeline generation
- Advanced debugging integration
- Performance profiling tools
- Docker container management

---

## Version Format

Construct follows [Semantic Versioning](https://semver.org/):

```
MAJOR.MINOR.PATCH
```

| Component | Meaning |
|-----------|---------|
| **MAJOR** | Breaking changes requiring user action |
| **MINOR** | New features, backward compatible |
| **PATCH** | Bug fixes, backward compatible |

**Pre-release tags:** `alpha`, `beta`, `rc` (e.g., `0.2.0-beta.1`)
