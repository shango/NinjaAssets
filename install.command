#!/bin/bash
# ============================================================
#   NinjaAssets Installer for macOS
#   Double-click this file to install NinjaAssets into Maya.
# ============================================================

# Move to the folder this script lives in (the NinjaAssets folder)
cd "$(dirname "$0")"

echo ""
echo "  =============================="
echo "   NinjaAssets Installer"
echo "  =============================="
echo ""

# Try mayapy first (ships with Maya, always available)
MAYAPY=""

for YEAR in 2026 2025 2024 2023 2022; do
    CANDIDATE="/Applications/Autodesk/maya${YEAR}/Maya.app/Contents/bin/mayapy"
    if [ -x "$CANDIDATE" ]; then
        MAYAPY="$CANDIDATE"
        echo "  Found Maya ${YEAR}"
        break
    fi
done

# Fall back to system Python
if [ -z "$MAYAPY" ]; then
    if command -v python3 &>/dev/null; then
        MAYAPY="python3"
        echo "  Using system Python3"
    elif command -v python &>/dev/null; then
        MAYAPY="python"
        echo "  Using system Python"
    else
        echo "  ERROR: Could not find Maya or Python on this computer."
        echo "  Please install Maya first, then try again."
        echo ""
        read -p "  Press Enter to close..." dummy
        exit 1
    fi
fi

echo ""
echo "  Installing NinjaAssets..."
echo ""

"$MAYAPY" -m ninja_assets.cli.install --copy

echo ""
if [ $? -eq 0 ]; then
    echo "  ----------------------------------------"
    echo "   Done! Restart Maya to start using"
    echo "   NinjaAssets."
    echo "  ----------------------------------------"
else
    echo "  Something went wrong. See the error above."
    echo "  If you need help, ask your pipeline TD."
fi
echo ""
read -p "  Press Enter to close..." dummy
