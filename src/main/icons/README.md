# Construct App Icons

This directory contains all icon assets used by the Tauri application bundler.

## Required Icon Files

The following icon files are required by `tauri.conf.json` and must be present in `src/main/icons/`:

| File | Size | Platform | Description |
|------|------|----------|-------------|
| `32x32.png` | 32x32 | All | Small app icon for taskbars, window decorations |
| `128x128.png` | 128x128 | All | Standard app icon for launchers, installers |
| `128x128@2x.png` | 256x256 | macOS, Linux | Retina/HiDPI display icon |
| `icon.icns` | Multi | macOS | Apple Icon Image format (contains multiple sizes) |
| `icon.ico` | Multi | Windows | Windows Icon format (contains multiple resolutions) |

## Source Image Requirements

- **Format**: PNG with transparency (RGBA)
- **Size**: 1024x1024 pixels (minimum)
- **Aspect Ratio**: 1:1 (square)
- **Design**: Keep the main design within the center safe area (~80% of the canvas) to avoid clipping when rounded corners are applied by the OS
- **Color Space**: sRGB

## Generating Icons

### Method 1: Using the Tauri CLI (Recommended)

Place your 1024x1024 source icon at `icons/source.png`, then run:

```bash
npm run icons:generate
```

This uses the built-in `cargo tauri icon` command which handles all formats automatically.

### Method 2: Using the Shell Script

For more control over the generated sizes and formats:

```bash
# Generate from default source (icons/source.png)
./scripts/generate-icons.sh

# Generate from a custom image
./scripts/generate-icons.sh path/to/your/icon.png
```

**Prerequisites**: ImageMagick must be installed:

- **macOS**: `brew install imagemagick`
- **Ubuntu/Debian**: `sudo apt install imagemagick`
- **Windows**: Download from [ImageMagick website](https://imagemagick.org/script/download.php#windows)

### Method 3: Manual Generation

#### macOS (.icns)

```bash
mkdir icon.iconset
sips -z 16 16   source.png --out icon.iconset/icon_16x16.png
sips -z 32 32   source.png --out icon.iconset/icon_16x16@2x.png
sips -z 32 32   source.png --out icon.iconset/icon_32x32.png
sips -z 64 64   source.png --out icon.iconset/icon_32x32@2x.png
sips -z 128 128 source.png --out icon.iconset/icon_128x128.png
sips -z 256 256 source.png --out icon.iconset/icon_128x128@2x.png
sips -z 256 256 source.png --out icon.iconset/icon_256x256.png
sips -z 512 512 source.png --out icon.iconset/icon_256x256@2x.png
sips -z 512 512 source.png --out icon.iconset/icon_512x512.png
sips -z 1024 1024 source.png --out icon.iconset/icon_512x512@2x.png
iconutil -c icns icon.iconset -o icon.icns
rm -rf icon.iconset
```

#### Windows (.ico)

```bash
convert source.png -resize 256x256 icon.ico
```

Or use a tool like [icoconvert.com](https://icoconvert.com/) or [RealWorld Icon Editor](http://www.rw-designer.com/icon-editor).

#### Linux PNG Sizes

```bash
convert source.png -resize 32x32 32x32.png
convert source.png -resize 128x128 128x128.png
convert source.png -resize 256x256 128x128@2x.png
```

## Icon Design Guidelines

1. **Simplicity**: Use simple, recognizable shapes that work at small sizes (16x16)
2. **Contrast**: Ensure sufficient contrast against both light and dark backgrounds
3. **Safe Area**: Keep the main design within 80% of the canvas to avoid OS clipping
4. **Transparency**: Use transparency (not solid backgrounds) for professional appearance
5. **Testing**: Preview your icon at 16x16, 32x32, and 128x128 before finalizing

## Icon Verification

After generating icons, verify they are correctly placed:

```bash
# Check all required icons exist
ls -la src/main/icons/
```

All files listed in the "Required Icon Files" table above should be present.
