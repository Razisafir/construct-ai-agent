#!/bin/bash
# =============================================================================
# build-all.sh
# =============================================================================
# Cross-platform build convenience script for Construct.
#
# This script triggers Tauri builds for all supported platforms.
# NOTE: You can only build for the platform you're currently running on.
#       Use GitHub Actions for true cross-platform builds.
#
# Supported platforms (from current host):
#   - macOS   -> builds .dmg (universal or x86_64/arm64)
#   - Windows -> builds .exe, .msi (NSIS)
#   - Linux   -> builds .AppImage, .deb, .rpm
#
# Usage:
#   ./scripts/build-all.sh [options]
#
# Options:
#   --target <target>   Build for specific target only
#                       (universal-apple-darwin, x86_64-pc-windows-msvc,
#                        x86_64-unknown-linux-gnu, aarch64-apple-darwin)
#   --release           Build in release mode (default)
#   --debug             Build in debug mode
#   --skip-build        Skip the frontend build step
#   --verbose           Enable verbose output
#
# Examples:
#   ./scripts/build-all.sh                          # Build for current platform
#   ./scripts/build-all.sh --target universal-apple-darwin   # macOS universal
#   ./scripts/build-all.sh --debug                  # Debug build
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_ROOT"

# Default values
TARGET=""
RELEASE_MODE="--release"
SKIP_BUILD=false
VERBOSE=false

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --target)
            TARGET="$2"
            shift 2
            ;;
        --debug)
            RELEASE_MODE=""
            shift
            ;;
        --release)
            RELEASE_MODE="--release"
            shift
            ;;
        --skip-build)
            SKIP_BUILD=true
            shift
            ;;
        --verbose)
            VERBOSE=true
            shift
            ;;
        -h|--help)
            echo "Construct Cross-Platform Build Script"
            echo ""
            echo "Usage: ./scripts/build-all.sh [options]"
            echo ""
            echo "Options:"
            echo "  --target <target>   Build for specific target"
            echo "  --release           Release build (default)"
            echo "  --debug             Debug build"
            echo "  --skip-build        Skip frontend build"
            echo "  --verbose           Verbose output"
            echo "  -h, --help          Show this help"
            echo ""
            echo "Targets:"
            echo "  universal-apple-darwin      macOS Universal (Intel + Apple Silicon)"
            echo "  x86_64-apple-darwin         macOS Intel"
            echo "  aarch64-apple-darwin        macOS Apple Silicon"
            echo "  x86_64-pc-windows-msvc      Windows 64-bit"
            echo "  x86_64-unknown-linux-gnu    Linux 64-bit"
            echo ""
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Run with --help for usage information."
            exit 1
            ;;
    esac
done

# Determine host platform
HOST_OS=""
case "$(uname -s)" in
    Darwin*)  HOST_OS="macos" ;;
    Linux*)   HOST_OS="linux" ;;
    CYGWIN*|MINGW*|MSYS*) HOST_OS="windows" ;;
    *)        HOST_OS="unknown" ;;
esac

echo "=========================================="
echo "Construct Cross-Platform Build"
echo "=========================================="
echo "Host OS:    $HOST_OS"
echo "Project:    $PROJECT_ROOT"
if [ -n "$TARGET" ]; then
    echo "Target:     $TARGET"
else
    echo "Target:     native ($HOST_OS)"
fi
echo "Mode:       $(if [ -n "$RELEASE_MODE" ]; then echo "release"; else echo "debug"; fi)"
echo "=========================================="
echo ""

# Check prerequisites
echo "[1/3] Checking prerequisites..."

if ! command -v cargo &> /dev/null; then
    echo "ERROR: Rust/Cargo not found. Install from https://rustup.rs/"
    exit 1
fi

if ! command -v npm &> /dev/null; then
    echo "ERROR: npm not found. Install Node.js from https://nodejs.org/"
    exit 1
fi

# Check for Tauri CLI
if ! cargo tauri --version &> /dev/null; then
    echo "Installing Tauri CLI..."
    cargo install tauri-cli
fi

RUST_VERSION=$(rustc --version)
NODE_VERSION=$(node --version)
TAURI_VERSION=$(cargo tauri --version 2>/dev/null || echo "unknown")

echo "  Rust:     $RUST_VERSION"
echo "  Node:     $NODE_VERSION"
echo "  Tauri:    $TAURI_VERSION"
echo ""

# Install frontend dependencies
echo "[2/3] Installing frontend dependencies..."
npm install
echo ""

# Run frontend build if not skipped
if [ "$SKIP_BUILD" = false ]; then
    echo "[3/3] Building frontend..."
    npm run build
else
    echo "[3/3] Skipping frontend build (--skip-build)"
fi
echo ""

# =============================================================================
# Build
# =============================================================================
echo "=========================================="
echo "Building Tauri Application"
echo "=========================================="

TAURI_ARGS=""

# Add target if specified
if [ -n "$TARGET" ]; then
    TAURI_ARGS="$TAURI_ARGS --target $TARGET"
fi

# Add release/debug mode
if [ -n "$RELEASE_MODE" ]; then
    TAURI_ARGS="$TAURI_ARGS $RELEASE_MODE"
fi

# Verbose
if [ "$VERBOSE" = true ]; then
    TAURI_ARGS="$TAURI_ARGS --verbose"
fi

echo "Running: cargo tauri build $TAURI_ARGS"
echo ""

cd "$PROJECT_ROOT/src/main"
cargo tauri build $TAURI_ARGS

echo ""
echo "=========================================="
echo "Build Complete"
echo "=========================================="
echo ""

# Show output artifacts
BUNDLE_DIR="$PROJECT_ROOT/src/main/target/release/bundle"
if [ -d "$BUNDLE_DIR" ]; then
    echo "Generated bundles:"
    find "$BUNDLE_DIR" -type f \( \
        -name "*.dmg" -o -name "*.app" -o \
        -name "*.exe" -o -name "*.msi" -o \
        -name "*.AppImage" -o -name "*.deb" -o -name "*.rpm" \
    \) -exec ls -lh {} \; 2>/dev/null || echo "  (no bundles found)"
else
    echo "Bundle directory not found: $BUNDLE_DIR"
fi

echo ""
echo "Done."
