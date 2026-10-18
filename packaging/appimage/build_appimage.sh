#!/usr/bin/env bash
# Wraps the PyInstaller build into a single-file AppImage that runs on most Linux distros.
#
# Usage (from the project root, after running PyInstaller):
#     bash packaging/appimage/build_appimage.sh [path/to/dist/CryptoCheck]
#
# Output: dist/CryptoCheck-<version>-x86_64.AppImage
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
APP_ID="io.github.g0d1k.CryptoCheck"
BUNDLE="${1:-$ROOT/dist/CryptoCheck}"
OUT_DIR="${OUT_DIR:-$ROOT/dist}"
TOOLS="$ROOT/packaging/appimage/tools"
VERSION="$(sed -n 's/^__version__ = "\(.*\)"/\1/p' "$ROOT/crypto_check/__init__.py")"

if [[ ! -x "$BUNDLE/CryptoCheck" ]]; then
    echo "PyInstaller build not found at $BUNDLE - run: pyinstaller packaging/pyinstaller/crypto_check.spec" >&2
    exit 1
fi

# 1. Get appimagetool (cached after the first run).
mkdir -p "$TOOLS"
APPIMAGETOOL="$TOOLS/appimagetool-x86_64.AppImage"
if [[ ! -x "$APPIMAGETOOL" ]]; then
    curl -fsSL -o "$APPIMAGETOOL" \
        https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-x86_64.AppImage
    chmod +x "$APPIMAGETOOL"
fi

# 2. Lay out the AppDir.
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
APPDIR="$WORK/AppDir"
mkdir -p "$APPDIR/usr/lib" "$APPDIR/usr/share/applications" "$APPDIR/usr/share/metainfo"

cp -r "$BUNDLE" "$APPDIR/usr/lib/crypto-check"

cat > "$APPDIR/AppRun" <<'EOF'
#!/bin/sh
HERE="$(dirname "$(readlink -f "$0")")"
exec "$HERE/usr/lib/crypto-check/CryptoCheck" "$@"
EOF
chmod +x "$APPDIR/AppRun"

cp "$ROOT/packaging/linux/$APP_ID.desktop" "$APPDIR/$APP_ID.desktop"
cp "$ROOT/packaging/linux/$APP_ID.desktop" "$APPDIR/usr/share/applications/"
cp "$ROOT/packaging/linux/$APP_ID.metainfo.xml" "$APPDIR/usr/share/metainfo/$APP_ID.appdata.xml"
cp "$ROOT/packaging/linux/icons/256x256/$APP_ID.png" "$APPDIR/$APP_ID.png"
for dir in "$ROOT"/packaging/linux/icons/*/; do
    size="$(basename "$dir")"
    mkdir -p "$APPDIR/usr/share/icons/hicolor/$size/apps"
    cp "$dir/$APP_ID.png" "$APPDIR/usr/share/icons/hicolor/$size/apps/"
done

# 3. Build. APPIMAGE_EXTRACT_AND_RUN lets appimagetool work without FUSE (e.g. in CI).
mkdir -p "$OUT_DIR"
OUTPUT="$OUT_DIR/CryptoCheck-$VERSION-x86_64.AppImage"
APPIMAGE_EXTRACT_AND_RUN=1 ARCH=x86_64 "$APPIMAGETOOL" --no-appstream "$APPDIR" "$OUTPUT"
echo "Built $OUTPUT"
