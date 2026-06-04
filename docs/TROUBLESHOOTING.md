# Troubleshooting Guide

> **Version:** 0.1.0  
> **Last Updated:** 2026-05-28

---

## Build Issues

### `cargo not found` or `rustc not found`

**Symptoms:**
```
command not found: cargo
```

**Solutions:**

1. **Install Rust via rustup:**
   ```bash
   curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
   source $HOME/.cargo/env
   ```

2. **Verify the installation:**
   ```bash
   rustc --version  # Should show 1.70+
   cargo --version
   ```

3. **Ensure `cargo` is in PATH:**
   - macOS/Linux: Add `source $HOME/.cargo/env` to `~/.bashrc` or `~/.zshrc`
   - Windows: Rustup should add it to PATH automatically; restart your terminal

---

### `npm install` fails

**Symptoms:**
```
npm ERR! code ENOENT
npm ERR! syscall open
```

**Solutions:**

1. **Ensure Node.js 18+ is installed:**
   ```bash
   node --version  # Should show v18+
   ```

2. **Clear npm cache and reinstall:**
   ```bash
   rm -rf node_modules package-lock.json
   npm cache clean --force
   npm install
   ```

3. **If using a corporate proxy:**
   ```bash
   npm config set proxy http://proxy.company.com:8080
   npm config set https-proxy http://proxy.company.com:8080
   ```

4. **If native module compilation fails (node-gyp):**
   - macOS: `xcode-select --install`
   - Windows: Install Visual Studio Build Tools
   - Linux: `sudo apt install build-essential`

---

### `tauri build` fails with webkit error

**Symptoms:**
```
error: failed to run custom build command for `webkit2gtk-sys`
```

**Solutions:**

1. **macOS:** Install Xcode Command Line Tools:
   ```bash
   xcode-select --install
   ```

2. **Linux (Ubuntu/Debian):** Install webkit dependencies:
   ```bash
   sudo apt install libwebkit2gtk-4.1-dev libsoup-3.0-0 libjavascriptcoregtk-4.1-0
   ```

3. **Linux (Fedora):**
   ```bash
   sudo dnf install webkit2gtk4.1-devel libsoup3-devel
   ```

4. **Linux (Arch):**
   ```bash
   sudo pacman -S webkit2gtk-4.1 libsoup3
   ```

---

### Python virtual environment issues

**Symptoms:**
```
ModuleNotFoundError: No module named 'fastapi'
```

**Solutions:**

1. **Ensure the virtual environment is activated:**
   ```bash
   # macOS/Linux
   cd agent-backend
   source .venv/bin/activate
   
   # Windows
   cd agent-backend
   .venv\Scripts\activate
   ```

2. **Reinstall dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **If pip fails with SSL errors:**
   ```bash
   pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org -r requirements.txt
   ```

---

## Runtime Issues

### App window opens but shows blank screen

**Diagnosis steps:**

1. **Check the Tauri DevTools:**
   - Right-click the window → Inspect (in development mode)
   - Or check the terminal for WebView errors

2. **Check if the frontend dev server is running:**
   ```bash
   curl http://localhost:5173
   ```

3. **Common causes:**
   - **Port 5173 in use:** Kill the process using it: `lsof -ti:5173 | xargs kill -9`
   - **TypeScript build errors:** Run `npm run lint` to check
   - **Missing environment file:** Ensure `.env` exists in `agent-backend/`

---

### Agent not responding

**Symptoms:** Agent panel shows "Idle" but doesn't start tasks.

**Diagnosis steps:**

1. **Check the Python backend is running:**
   ```bash
   curl http://127.0.0.1:8000/health
   ```
   Should return `{ "status": "ok", ... }`.

2. **Check backend logs:**
   - Look at the terminal running `uvicorn`
   - Check for error messages or stack traces

3. **Check the frontend console:**
   - Open DevTools (right-click → Inspect)
   - Look for errors in the Console tab

4. **Common causes and solutions:**

   | Cause | Solution |
   |-------|----------|
   | Python backend not running | Start it: `cd agent-backend && uvicorn app:app --reload --port 8000` |
   | Port 8000 in use | Change port: `uvicorn app:app --reload --port 8001` |
   | LLM provider not configured | Add API key to `.env` file |
   | LLM API rate limited | Wait and retry, or switch provider |

5. **Restart both services:**
   ```bash
   # Terminal 1: Restart backend
   cd agent-backend && uvicorn app:app --reload --port 8000
   
   # Terminal 2: Restart Tauri
   npm run tauri:dev
   ```

---

### Memory not persisting

**Symptoms:** Conversations or code events disappear after restart.

**Diagnosis steps:**

1. **Check SQLite database exists:**
   ```bash
   # macOS
   ls ~/Library/Application\ Support/construct/construct.db
   
   # Linux
   ls ~/.local/share/construct/construct.db
   
   # Windows
   dir %APPDATA%\construct\construct.db
   ```

2. **Verify WAL mode is enabled:**
   ```bash
   sqlite3 ~/Library/Application\ Support/construct/construct.db "PRAGMA journal_mode;"
   # Should return: wal
   ```

3. **Check disk space:**
   ```bash
   df -h  # macOS/Linux
   # Ensure at least 100MB free
   ```

4. **Check file permissions:**
   ```bash
   # macOS/Linux
   ls -la ~/Library/Application\ Support/construct/
   # Should be writable by current user
   ```

5. **Common causes:**
   - **WAL file too large:** The `.db-wal` file can grow large. Run:
     ```bash
     sqlite3 construct.db "PRAGMA wal_checkpoint(TRUNCATE); VACUUM;"
     ```
   - **Disk full:** Free up disk space
   - **Permission denied:** Fix ownership:
     ```bash
     sudo chown -R $(whoami) ~/.local/share/construct/
     ```

---

### LLM response is slow or times out

**Diagnosis steps:**

1. **Check which provider is being used:**
   ```bash
   curl http://127.0.0.1:8000/health
   ```

2. **Test the provider directly:**
   ```bash
   curl -X POST http://127.0.0.1:8000/llm/complete \
     -H "Content-Type: application/json" \
     -d '{"prompt": "Say hello", "model": "ollama"}'
   ```

3. **Solutions:**

   | Issue | Solution |
   |-------|----------|
   | Cloud provider slow | Use `model: "ollama"` for local, fast responses |
   | Ollama slow | Use a smaller model: `OLLAMA_MODEL=qwen2.5-coder:7b` |
   | Timeout on large prompts | Increase timeout in code or use `GOOGLE_MODEL=gemini-1.5-pro` for long context |
   | Rate limited | Add delays between requests or use a different provider |

---

## Autonomous Mode Issues

### Background worker not starting

**Symptoms:** Autonomous mode shows "Disabled" after clicking Enable.

**Solutions:**

1. **Check all services initialized:**
   ```bash
   curl http://127.0.0.1:8000/health
   # Should show autonomous.available: true
   ```

2. **Check Python logs for initialization errors:**
   - Look for errors in the uvicorn terminal output during startup

3. **Ensure all Python dependencies are installed:**
   ```bash
   cd agent-backend
   pip install -r requirements.txt
   ```

---

### Worker stops unexpectedly

**Symptoms:** Autonomous mode switches from "Running" to "Error".

**Common causes:**

| Cause | Solution |
|-------|----------|
| CPU limit exceeded | Increase `AGENT_MAX_CPU` in `.env` |
| Memory limit exceeded | Increase `AGENT_MAX_MEMORY` in `.env` |
| Safety trigger fired | Check `/autonomous/safety/stats` endpoint |
| Unhandled exception | Check Python logs for stack traces |

**Check resource usage:**
```bash
curl http://127.0.0.1:8000/autonomous/resources
```

**Check safety stats:**
```bash
curl http://127.0.0.1:8000/autonomous/safety/stats
```

**Reset safety counters:**
```bash
curl -X POST http://127.0.0.1:8000/autonomous/safety/reset
```

---

## MCP Connection Issues

### GitHub MCP fails

**Symptoms:** GitHub-related tools return authentication errors.

**Diagnosis steps:**

1. **Verify the GitHub token:**
   ```bash
   curl -H "Authorization: token YOUR_TOKEN" https://api.github.com/user
   ```

2. **Check token scopes:** The token needs at least `repo` and `read:user` scopes.

3. **Check rate limits:**
   ```bash
   curl -H "Authorization: token YOUR_TOKEN" https://api.github.com/rate_limit
   ```

4. **Solutions:**

   | Issue | Solution |
   |-------|----------|
   | Token invalid | Generate a new token at https://github.com/settings/tokens |
   | Rate limited | Wait for reset (1 hour for unauthenticated, 5000/hr for authenticated) |
   | Token expired | Regenerate the token |
   | Missing scopes | Create a new token with `repo` scope |

---

## Platform-Specific Issues

### macOS: App is damaged and can't be opened

**Cause:** macOS Gatekeeper blocks unsigned applications.

**Solution:**
```bash
xattr -cr /Applications/Construct.app
```

---

### Windows: Antivirus blocks the app

**Cause:** Windows Defender or third-party antivirus may flag the app.

**Solution:**
1. Add the Construct installation directory to your antivirus exclusion list
2. Or build from source to avoid pre-built binary detection

---

### Linux: AppImage won't run

**Solution:**
```bash
chmod +x construct_0.1.0_amd64.AppImage
./construct_0.1.0_amd64.AppImage --appimage-extract-and-run
```

If FUSE is not available:
```bash
./construct_0.1.0_amd64.AppImage --appimage-extract
./squashfs-root/AppRun
```

---

## Getting Help

If your issue is not listed here:

1. **Check the logs:**
   - Rust logs: Run with `RUST_LOG=debug npm run tauri:dev`
   - Python logs: Check the uvicorn terminal output
   - Frontend logs: Open DevTools (right-click → Inspect)

2. **Check the health endpoint:**
   ```bash
   curl http://127.0.0.1:8000/health
   ```

3. **File a bug report:** Use the [Bug Report Template](https://github.com/Razisafir/construct-ai-agent/issues/new?template=bug_report.md)

4. **Include in your report:**
   - OS and version
   - Construct version
   - Node.js, Rust, and Python versions
   - Relevant log excerpts
   - Steps to reproduce
