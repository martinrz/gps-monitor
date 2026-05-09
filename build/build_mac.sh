#!/usr/bin/env bash
# ============================================================
# build_mac.sh — Build GPS Monitor for macOS
#
# Produces:
#   dist/GPS Monitor.app          — standalone macOS app bundle
#   dist/GPS_Monitor_1.0_macOS.dmg — drag-to-install disk image
#
# Prerequisites (all installable via pip / Homebrew):
#   pip install pyinstaller Pillow
#   brew install create-dmg       (optional; falls back to hdiutil)
#
# Usage:
#   cd <project root>
#   bash build/build_mac.sh
# ============================================================
set -euo pipefail

APP_NAME="GPS Monitor"
VERSION="1.0"
BUNDLE_ID="com.martinreynolds.gpsmonitor"
DMG_OUT="dist/GPS_Monitor_${VERSION}_macOS.dmg"

cd "$(dirname "$0")/.."
echo "=== GPS Monitor — macOS build ==="
echo "  Working dir: $(pwd)"
echo "  Python:      $(python3 --version)"
echo ""

# ── Step 1: Generate icons ──────────────────────────────────
echo "[1/4] Generating icons …"
python3 build/make_icons.py

# ── Step 2: PyInstaller ─────────────────────────────────────
echo "[2/4] Running PyInstaller …"
pyinstaller build/gps_monitor.spec --clean --noconfirm

APP_PATH="dist/${APP_NAME}.app"
if [ ! -d "$APP_PATH" ]; then
    echo "ERROR: $APP_PATH not found after build." >&2
    exit 1
fi
echo "  Built: $APP_PATH"
echo "  Size:  $(du -sh "$APP_PATH" | cut -f1)"

# ── Step 3: Optional ad-hoc code signing ────────────────────
echo "[3/4] Signing (ad-hoc) …"
# Ad-hoc signing (-) lets the app run on the build machine without a
# paid Developer ID.  For distribution outside your own machine,
# replace '-' with your Developer ID certificate name:
#   codesign --deep --force --sign "Developer ID Application: Name (TEAMID)" ...
codesign --deep --force --sign '-' \
         --entitlements build/entitlements.plist \
         "$APP_PATH" 2>/dev/null || {
    echo "  codesign not available or entitlements missing — skipping."
}

# ── Step 4: Create DMG ──────────────────────────────────────
echo "[4/4] Creating DMG …"
rm -f "$DMG_OUT"

if command -v create-dmg &>/dev/null; then
    create-dmg \
        --volname "$APP_NAME $VERSION" \
        --volicon "build/icons/icon.icns" \
        --window-pos 200 120 \
        --window-size 600 340 \
        --icon-size 128 \
        --icon "${APP_NAME}.app" 160 160 \
        --hide-extension "${APP_NAME}.app" \
        --app-drop-link 440 160 \
        --no-internet-enable \
        "$DMG_OUT" \
        "dist/${APP_NAME}.app"
else
    # Fallback: plain hdiutil DMG (no custom layout)
    echo "  create-dmg not found; using hdiutil fallback."
    echo "  Install for a prettier DMG:  brew install create-dmg"
    TMP_DMG="dist/_tmp_gps.dmg"
    hdiutil create \
        -volname "$APP_NAME $VERSION" \
        -srcfolder "dist/${APP_NAME}.app" \
        -ov -format UDBZ \
        "$TMP_DMG"
    hdiutil convert "$TMP_DMG" -format UDZO -imagekey zlib-level=9 -o "$DMG_OUT"
    rm -f "$TMP_DMG"
fi

echo ""
echo "=== Done ==="
echo "  App:  $APP_PATH"
echo "  DMG:  $DMG_OUT  ($(du -sh "$DMG_OUT" | cut -f1))"
echo ""
echo "To distribute without a Developer ID the recipient must:"
echo "  Right-click the app → Open → Open (to bypass Gatekeeper once)"
echo "For fully trusted distribution, sign + notarize with an Apple Developer ID."
