#!/bin/bash
# =============================================================================
# generate-icons.sh
# =============================================================================
# Generate all icon formats from a single 1024x1024 PNG source for Tauri.
#
# Prerequisites:
#   - ImageMagick (convert, identify) — install via: brew install imagemagick
#   - iconutil (macOS only — for .icns generation)
#
# Usage:
#   ./scripts/generate-icons.sh [source_image]
#
#   If no source_image is provided, defaults to icons/source.png
#
#   The source image should be 1024x1024 PNG with a square design.
#   The script will generate macOS .icns, Windows .ico, and Linux .png sizes.
# =============================================================================

set -euo pipefail

SOURCE="${1:-icons/source.png}"
OUTDIR="src/main/icons"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

SOURCE="$PROJECT_ROOT/$SOURCE"
OUTDIR="$PROJECT_ROOT/$OUTDIR"

echo "=========================================="
echo "Construct Icon Generator"
echo "=========================================="
echo "Source: $SOURCE"
echo "Output: $OUTDIR"
echo ""

# Verify source image exists
if [ ! -f "$SOURCE" ]; then
    echo "ERROR: Source image not found: $SOURCE"
    echo ""
    echo "Please provide a 1024x1024 PNG icon file at that path, or pass a different path:"
    echo "  ./scripts/generate-icons.sh path/to/your/icon.png"
    exit 1
fi

# Verify ImageMagick is installed
if ! command -v convert &> /dev/null; then
    echo "ERROR: ImageMagick 'convert' not found."
    echo "Install it:  brew install imagemagick    (macOS)"
    echo "             sudo apt install imagemagick (Ubuntu)"
    exit 1
fi

# Get source dimensions
SRC_W=$(identify -format "%w" "$SOURCE")
SRC_H=$(identify -format "%h" "$SOURCE")
echo "Source image: ${SRC_W}x${SRC_H}"

# Ensure source is square
if [ "$SRC_W" -ne "$SRC_H" ]; then
    echo "WARNING: Source image is not square (${SRC_W}x${SRC_H}). Icons may look distorted."
fi

# Create output directory
mkdir -p "$OUTDIR"
echo "Output directory created: $OUTDIR"
echo ""

# =============================================================================
# macOS .icns (Apple Icon Image format)
# =============================================================================
echo "[1/4] Generating macOS .icns icon set..."

ICONSET_DIR="$OUTDIR/icon.iconset"
mkdir -p "$ICONSET_DIR"

# macOS icon sizes
MACOS_SIZES=(16 32 64 128 256 512)
for SIZE in "${MACOS_SIZES[@]}"; do
    SIZE2X=$((SIZE * 2))
    convert "$SOURCE" -resize "${SIZE}x${SIZE}" "$ICONSET_DIR/icon_${SIZE}x${SIZE}.png"
    if [ "$SIZE2X" -le 1024 ]; then
        convert "$SOURCE" -resize "${SIZE2X}x${SIZE2X}" "$ICONSET_DIR/icon_${SIZE}x${SIZE}@2x.png"
    fi
done

# Build .icns using iconutil (macOS only)
if command -v iconutil &> /dev/null; then
    iconutil -c icns "$ICONSET_DIR" -o "$OUTDIR/icon.icns"
    echo "  icon.icns  -> generated"
else
    echo "  icon.icns  -> SKIPPED (iconutil not available — only on macOS)"
    echo "    To generate .icns, run this script on macOS or use a tool like:"
    echo "    https://github.com/jamf/icnsConverter"
fi

# Clean up iconset
rm -rf "$ICONSET_DIR"

# =============================================================================
# Windows .ico
# =============================================================================
echo "[2/4] Generating Windows .ico icon..."

# Windows requires specific icon sizes embedded in the .ico
WIN_SIZES=(16 20 24 32 40 48 64 96 128 256)
WIN_ICON_ARGS=()
for SIZE in "${WIN_SIZES[@]}"; do
    convert "$SOURCE" -resize "${SIZE}x${SIZE}" "$OUTDIR/win_${SIZE}.png"
    WIN_ICON_ARGS+=("$OUTDIR/win_${SIZE}.png")
done

# Combine into multi-resolution .ico
convert "${WIN_ICON_ARGS[@]}" "$OUTDIR/icon.ico"
echo "  icon.ico   -> generated"

# Clean up temp Windows PNGs
rm -f "$OUTDIR"/win_*.png

# =============================================================================
# Linux / General PNG sizes
# =============================================================================
echo "[3/4] Generating Linux PNG icon sizes..."

LINUX_SIZES=(32 128)
for SIZE in "${LINUX_SIZES[@]}"; do
    convert "$SOURCE" -resize "${SIZE}x${SIZE}" "$OUTDIR/${SIZE}x${SIZE}.png"
    echo "  ${SIZE}x${SIZE}.png  -> generated"
done

# Retina @2x version
convert "$SOURCE" -resize "256x256" "$OUTDIR/128x128@2x.png"
echo "  128x128@2x.png  -> generated"

# Also create a high-res fallback
convert "$SOURCE" -resize "512x512" "$OUTDIR/512x512.png"
echo "  512x512.png  -> generated"

# =============================================================================
# Summary
# =============================================================================
echo ""
echo "=========================================="
echo "Icon Generation Complete"
echo "=========================================="
echo ""
echo "Generated files in $OUTDIR:"
ls -lh "$OUTDIR"
echo ""
echo "Required by tauri.conf.json:"
echo "  - icons/32x32.png"
echo "  - icons/128x128.png"
echo "  - icons/128x128@2x.png"
echo "  - icons/icon.icns   (macOS)"
echo "  - icons/icon.ico    (Windows)"
echo ""
echo "=========================================="
echo "Next Steps"
echo "=========================================="
echo "1. Ensure the generated icons look correct at all sizes"
echo "2. If .icns was not generated, run on macOS or use an online converter"
echo "3. Tauri will automatically use the correct format per platform"
echo ""
