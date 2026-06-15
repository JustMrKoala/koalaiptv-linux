#!/bin/bash
# KoalaIPTV Linux PyInstaller Build Script

set -e

echo "[*] KoalaIPTV Linux Build"
echo "======================================"

# Install PyInstaller if not present
if ! command -v pyinstaller &> /dev/null; then
    echo "[*] Installing PyInstaller..."
    pip install pyinstaller>=6.0.0
fi

# Clean previous builds
echo "[*] Cleaning previous builds..."
rm -rf build dist *.spec

# Build the standalone executable
echo "[*] Building koalaiptv executable..."
pyinstaller \
    --onefile \
    --console \
    --name koalaiptv \
    --distpath dist \
    --specpath build \
    --buildpath build/temp \
    koalaiptv_linux.py

# Verify the build
if [ -f "dist/koalaiptv" ]; then
    echo "[+] Build successful!"
    echo "[+] Executable: dist/koalaiptv"
    chmod +x dist/koalaiptv
    echo "[+] Made executable"
    
    # Show size
    SIZE=$(du -h dist/koalaiptv | cut -f1)
    echo "[+] Size: $SIZE"
    
    # Test run
    echo "[*] Testing executable..."
    ./dist/koalaiptv --version
    echo "[+] Build verification passed!"
else
    echo "[-] Build failed!"
    exit 1
fi
