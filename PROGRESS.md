# Construct AI Agent — Progress Checklist

> Auto-maintained. Updated after every push.

## 01 Make the product real
Wire the real executor to the frontend — everything the user sees must be genuine

- [x] Delete `execute_agent_session()` and `_decompose_goal()` from app.py — commit `98e8513`
- [x] Route `/agent/start` to real `AgentExecutor.start_session()` — commit `98e8513`
- [x] Route `/agent/{id}/output` endpoint + Rust polling — commit `98e8513`
- [x] Add `store_conversation_message()` calls in executor task completion — commit `6f6afae`
- [x] Inject `recall_context()` results into LLM planning prompt — commit `6f6afae`
- [x] Update `start_agent` Rust command to call `/agent/start` — commit `98e8513`
- [x] Update Rust event polling to use `/agent/{id}/output` — commit `98e8513`
- [x] Compile and run Tauri app on a real machine — verified
- [x] Wire InlineDiff viewer to real agent diff events — commit `c26d07f`
- [x] Wire agent mode selection to pass `mode: string` to executor — commit `8818189`
- [x] E2E test: real goal → LLM plans → tools run → file written → diff in UI — commit `13d3eff`
- [x] E2E test: memory recall across sessions — commit `6f6afae`

**Phase 1: 12/12 complete ✅**

## 02 Ship a credible Beta
Close the stubs, fix the broken claims, make the UX honest

- [x] Fix context compression: `messages` list on AgentSession, `/context/compact` 200 — commit `ff8293a`
- [x] Fix thinking mode: `_call_llm()` reads `thinking_mode` dict, changes system prompt — commit `ff8293a`
- [x] Expose Orchestrator via `/orchestrate/team` endpoint — commit `8818189`
- [x] Honest onboarding: Demo Mode label when no LLM connected — commit `ff8293a`
- [x] README: 41 security rules, Roadmap section — commit `ff8293a`
- [x] SSE streaming endpoint `GET /agent/{id}/stream` — commit `41ce13f`
- [x] Rust SSE consumer → Tauri events — commit `41ce13f`
- [x] Streaming token rendering in AgentPanel — commit `41ce13f`
- [ ] E2E test: autonomous worker POST `/autonomous/start` runs end to end
- [ ] Test checkpoint save/restore: kill mid-task, restart, resume

**Phase 2: 8/10 complete**

## 03 Build the differentiators
Features that make Construct worth $20/month vs just running Cursor

- [x] Replace MultiAgentPanel demo data with real `/orchestrate/team` API — commit `8818189`
- [x] Build team composition UI: interactive role picker → POST `/orchestrate/team` — commit `db238b7`
- [x] Display live agent-to-agent messages in panel — commit `8818189`
- [ ] E2E test: 3-agent team completes a real feature together
- [x] Skill install copies files from GitHub — `installer.py` has `install_from_github()`
- [x] Load installed skills into ToolRegistry at startup — commit `db238b7`
- [ ] Replace hardcoded marketplace entries with real registry (frontend calls backend API)
- [x] MCP client: real JSON-RPC connection + tool discovery — `mcp_client.py`
- [x] Bridge MCP tools into ToolRegistry so agent can invoke them — commit `db238b7`

**Phase 3: 6/9 complete**

## 04 Polish and scale
Details that justify keeping a paid subscription

- [ ] Expand safety rules to 44+ with clear count
- [x] Git sandboxing: auto-create feature branch in executor session — commit `db238b7`
- [x] Rate-limit destructive tool calls per session — commit `db238b7`
- [x] Project-level memory: ChromaDB PersistentClient (but not scoped per-project)
- [x] Wire MemoryPanel.tsx to real `/memory/query` endpoint — commit `db238b7`
- [x] Screen control: `action_recorder.py` implemented (900 lines)
- [ ] Crash reporting (Sentry or equivalent)
- [ ] Auto-update flow via Tauri updater plugin
- [ ] Load test: 10 simultaneous sessions, verify resource limits

**Phase 4: 4/9 complete**

---

## Summary

| Phase | Done | Total | Status |
|-------|------|-------|--------|
| 01 Make the product real | 12 | 12 | ✅ Complete |
| 02 Ship a credible Beta | 8 | 10 | 🟡 80% |
| 03 Build the differentiators | 6 | 9 | 🟡 67% |
| 04 Polish and scale | 4 | 9 | 🟡 44% |
| **Total** | **30** | **40** | **75%** |

## Remaining items

1. E2E test: autonomous worker end to end
2. Test checkpoint save/restore
3. E2E test: 3-agent team
4. Replace hardcoded marketplace with real API
5. Expand safety rules to 44+
6. Crash reporting (Sentry)
7. Auto-update flow
8. Load test: 10 simultaneous sessions

---
_Last updated: 2026-05-31 — commit `db238b7`_
