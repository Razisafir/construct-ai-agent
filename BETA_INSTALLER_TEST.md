# Beta Installer Test Report

## Build Information

- **Tag**: v0.1.0-beta.3
- **Commit**: fc6aa81f
- **Release URL**: https://github.com/Razisafir/construct-ai-agent/releases/tag/v0.1.0-beta.3
- **CI Status**: All green (Build & Test + Release workflows)

## Available Installers

| Platform | File | Size | Status |
|----------|------|------|--------|
| macOS (Apple Silicon) | `Construct_0.1.0_aarch64.dmg` | ~313MB | CI verified |
| Linux (Debian/Ubuntu) | `Construct_0.1.0_amd64.deb` | ~459MB | CI verified |
| Linux (Portable) | `Construct_0.1.0_amd64.AppImage` | ~533MB | CI verified |
| Windows (NSIS) | `Construct_0.1.0_x64-setup.exe` | ~338MB | CI verified |
| Windows (MSI) | `Construct_0.1.0_x64_en-US.msi` | ~340MB | CI verified |

## CI Verification Summary

| Job | Status |
|-----|--------|
| test-frontend | passed |
| test-python-unit | passed |
| test-rust | passed |
| test-e2e-mock | passed |
| release-macos | passed |
| release-linux | passed |
| release-windows | passed |
| create-release | passed |

## Manual Installer Test

> **NOTE**: The following tests require a real machine with a display.
> This server environment does not have a GUI, so manual testing must be
> done by the developer on their own machine.

### Test Checklist (fill in after manual testing)

#### macOS (Apple Silicon)

- OS: ___________
- Installer: Construct_0.1.0_aarch64.dmg
- Install time: ___________
- App opens: YES / NO
- Ollama test (Settings > Ollama > Test Connection): YES / NO
- Agent works (AgentChat > "Create hello_world.py" > Enter): YES / NO
- File created in ~/construct-projects/default/: YES / NO
- Any issues: ___________

#### Windows (x64)

- OS: ___________
- Installer: Construct_0.1.0_x64-setup.exe
- Install time: ___________
- App opens: YES / NO
- Ollama test (Settings > Ollama > Test Connection): YES / NO
- Agent works (AgentChat > "Create hello_world.py" > Enter): YES / NO
- File created in %USERPROFILE%\construct-projects\default\: YES / NO
- Any issues: ___________

#### Linux (x64)

- OS: ___________
- Installer: Construct_0.1.0_amd64.deb (or .AppImage)
- Install time: ___________
- App opens: YES / NO
- Ollama test (Settings > Ollama > Test Connection): YES / NO
- Agent works (AgentChat > "Create hello_world.py" > Enter): YES / NO
- File created in ~/construct-projects/default/: YES / NO
- Any issues: ___________

## Bug Fixes in This Build

1. **Server OOM on startup** — ChromaDB embeddings now lazy-load (commit ff8293a)
2. **Dishonest onboarding** — Demo Mode and Ready banners added (commit ff8293a)
3. **README inaccuracies** — Corrected to 41 rules, MCP/screen in Roadmap (commit ff8293a)
4. **Context compression 500** — Added `messages` field to AgentSession (commit ff8293a)
5. **Thinking mode ignored** — `_call_llm()` reads depth, adjusts prompt (commit ff8293a)
6. **Rust build failure** — Closed unclosed Ok(resp) match arm (commit dffa72d)
7. **Missing macOS dmg** — Fixed artifact path in release workflow (commit fc6aa81f)

## Known Limitations

- Agent runs in demo mode without Ollama running locally
- No streaming token output (polling-based event delivery)
- Multi-agent panel shows demo data (not wired to real orchestrator yet)
- MCP connector is skeleton-only
- Skill marketplace not yet implemented
