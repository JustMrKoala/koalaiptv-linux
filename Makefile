.PHONY: build clean test help

help:
	@echo "KoalaIPTV Linux Build Commands"
	@echo "======================================"
	@echo "  make build    - Build PyInstaller executable"
	@echo "  make clean    - Remove build artifacts"
	@echo "  make test     - Test the built executable"
	@echo "  make help     - Show this help message"

build:
	@bash build.sh

clean:
	@echo "[*] Cleaning build artifacts..."
	@rm -rf build dist *.spec
	@echo "[+] Cleaned"

test: build
	@echo "[*] Running tests..."
	@./dist/koalaiptv --version
	@echo "[+] Tests passed"

install: build
	@echo "[*] Installing koalaiptv..."
	@mkdir -p ~/.local/bin
	@cp dist/koalaiptv ~/.local/bin/
	@chmod +x ~/.local/bin/koalaiptv
	@echo "[+] Installed to ~/.local/bin/koalaiptv"
	@echo "[!] Make sure ~/.local/bin is in your PATH"
