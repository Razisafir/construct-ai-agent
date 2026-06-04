# Installation Guide

> **Version:** 0.1.0  
> **Last Updated:** 2026-05-28

---

## Prerequisites

| Requirement | Minimum Version | Recommended |
|-------------|-----------------|-------------|
| Node.js | 18.x | 20.x LTS |
| Rust | 1.70+ | Latest stable |
| Python | 3.10+ | 3.12+ |
| Tauri CLI | v2 | v2 latest |

Before installing, ensure your system meets the [Tauri prerequisites](https://tauri.app/start/prerequisites/) for your platform.

---

## macOS

### 1. Install Prerequisites

```bash
# Using Homebrew (recommended)
brew install node python3 rustup-init

# Initialize Rust
rustup-init -y
source $HOME/.cargo/env

# Verify installations
node --version    # v18+ 
rustc --version   # 1.70+
python3 --version # 3.10+
```

### 2. Clone the Repository

```bash
git clone https://github.com/Razisafir/construct-ai-agent.git
cd construct-ai-agent
```

### 3. Install Frontend Dependencies

```bash
npm install
```

### 4. Install Python Backend

```bash
cd agent-backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cd ..
```

### 5. Configure Environment

```bash
cp agent-backend/.env.example agent-backend/.env
# Edit .env with your API keys (see docs/CONFIGURATION.md)
```

### 6. Build the Application

```bash
npm run tauri:build
```

The compiled `.app` bundle will be in `src/main/target/release/bundle/macos/`.

---

## Windows

### 1. Install Prerequisites

```powershell
# Install Node.js from https://nodejs.org (LTS version)
# Install Python from https://python.org (check "Add to PATH")
# Install Rust via rustup
Invoke-WebRequest https://win.rustup.rs -OutFile rustup-init.exe
.\rustup-init.exe -y

# Verify installations
node --version
rustc --version
python --version
```

### 2. Clone the Repository

```powershell
git clone https://github.com/Razisafir/construct-ai-agent.git
cd construct-ai-agent
```

### 3. Install Frontend Dependencies

```bash
npm install
```

### 4. Install Python Backend

```powershell
cd agent-backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
cd ..
```

### 5. Configure Environment

```powershell
copy agent-backend\.env.example agent-backend\.env
# Edit .env with your API keys
```

### 6. Build the Application

```bash
npm run tauri:build
```

The compiled `.msi` installer will be in `src/main/target/release/bundle/msi/`.

---

## Linux (Ubuntu/Debian)

### 1. Install System Dependencies

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install build essentials and libraries required by Tauri
sudo apt install -y \
  libwebkit2gtk-4.1-dev \
  build-essential \
  curl \
  wget \
  file \
  libssl-dev \
  libgtk-3-dev \
  libayatana-appindicator3-dev \
  librsvg2-dev \
  javascriptcoregtk-4.1 \
  libsoup-3.0 \
  libjavascriptcoregtk-4.1-0 \
  libsoup-3.0-0

# Install Node.js (via NodeSource)
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs

# Install Rust
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
source $HOME/.cargo/env

# Install Python 3.12
sudo apt install -y python3.12 python3.12-venv python3-pip

# Verify
node --version
rustc --version
python3 --version
```

### 2. Clone the Repository

```bash
git clone https://github.com/Razisafir/construct-ai-agent.git
cd construct-ai-agent
```

### 3. Install Frontend Dependencies

```bash
npm install
```

### 4. Install Python Backend

```bash
cd agent-backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cd ..
```

### 5. Configure Environment

```bash
cp agent-backend/.env.example agent-backend/.env
# Edit .env with your API keys
```

### 6. Build the Application

```bash
npm run tauri:build
```

The compiled `.deb` or `.AppImage` will be in `src/main/target/release/bundle/`.

---

## Development Mode

For active development, run the backend and frontend in separate terminals:

### Terminal 1: Python Backend

```bash
cd agent-backend
source .venv/bin/activate  # Windows: .venv\Scripts\activate
python -m uvicorn app:app --reload --port 8000
```

The API will be available at `http://127.0.0.1:8000`. View interactive docs at `/docs`.

### Terminal 2: Tauri Dev Server

```bash
npm run tauri:dev
```

This starts the Vite dev server and the Tauri app with hot-reload enabled.

### Terminal 3: Vite Only (Frontend Development)

If you want to work on just the frontend without Tauri:

```bash
npm run dev
```

The app will be available at `http://localhost:5173`.

---

## Platform-Specific Build Targets

| Target | Command | Output |
|--------|---------|--------|
| macOS Universal | `npm run build:mac` | `.app` bundle |
| Windows x64 | `npm run build:win` | `.msi` installer |
| Linux x64 | `npm run build:linux` | `.deb` / `.AppImage` |
| All platforms | `npm run build:all` | All of the above |

Build outputs are located at `src/main/target/release/bundle/`.

---

## Verifying the Installation

After building, verify the installation:

1. **Launch the app** — Open the built bundle or run `npm run tauri:dev`
2. **Check the version** — The version is displayed in the UI title bar
3. **Test the backend** — Visit `http://127.0.0.1:8000/health` in a browser
4. **Test memory** — Send a message in the chat panel and check the Memory panel

---

## Next Steps

- Read the [Architecture Overview](ARCHITECTURE.md) to understand how the system works
- Review the [API Reference](API.md) for all available commands and endpoints
- Configure your environment variables in [Configuration Guide](CONFIGURATION.md)
- If you encounter issues, see [Troubleshooting](TROUBLESHOOTING.md)
