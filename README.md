# KoalaIPTV - Linux Build

A lightweight, zero-bullshit IPTV client for Linux. Browse and download streams from Xtream Codes providers using yt-dlp.

```
       ___
     {~._.~}   KoalaIPTV v1.6
      ( Y )    Zero Bullshit. Just Streams.
     ()~*~()   Live  |  VOD  |  Series  |  yt-dlp Powered
     (_)-(_)
```

## Features

- 🎬 Live streams, VOD, and series support
- 🔍 Interactive search and browsing
- 📥 Batch download with automatic retry
- 🔄 Self-updating (from GitHub releases)
- 🐧 Portable Linux binary (PyInstaller)
- 🎯 Dependency auto-installation (ffmpeg, yt-dlp)

## Quick Start

### Prerequisites

- Python 3.7+
- Linux (Ubuntu, Debian, Fedora, Arch, etc.)

### Installation

```bash
# Build from source
git clone https://github.com/JustMrKoala/koalaiptv-linux
cd koalaiptv-linux

# Option 1: Using make
make build
make install

# Option 2: Using build.sh directly
bash build.sh

# The executable will be at: ./dist/koalaiptv
```

### Usage

```bash
# First-time setup (interactive wizard)
./dist/koalaiptv

# Or install to PATH and use globally
make install
koalaiptv                    # First-time setup
koalaiptv configure          # Reconfigure credentials
koalaiptv convert            # Build M3U playlist
koalaiptv search             # Browse and download interactively
koalaiptv download "Title"   # Non-interactive download
koalaiptv update             # Self-update to latest release
```

## Building

### Quick Build

```bash
make build
```

### Manual Build

```bash
# Install PyInstaller
pip install pyinstaller

# Build the executable
bash build.sh

# Result: ./dist/koalaiptv
```

### Build Output

The build produces a standalone, single-file executable at `dist/koalaiptv` that requires only:
- Python runtime (bundled)
- External CLI tools: `yt-dlp`, `ffmpeg` (auto-installed on first run)

## Configuration

Settings are stored in `~/.koala_iptv/config.json`:

```json
{
  "host": "https://iptv.example.com:8080",
  "username": "your_username",
  "password": "your_password",
  "output_dir": "/home/user/Videos/KoalaIPTV"
}
```

## Commands

### `configure`
Save or update Xtream provider credentials and download folder.

```bash
koalaiptv configure --host https://iptv.com:8080 --username user --password pass
```

### `convert`
Build an M3U playlist from your Xtream provider.

```bash
koalaiptv convert
```

### `search`
Interactive search and download UI.

```bash
koalaiptv search
koalaiptv -c search         # Save to current directory
```

### `download`
Scriptable download by name (no interactive prompts).

```bash
koalaiptv download "Breaking Bad" --first
koalaiptv -c download "CNN" --first
```

### `update`
Self-update the binary to the latest GitHub release.

```bash
koalaiptv update            # Auto-fetch from JustMrKoala/koalaiptv-linux
koalaiptv update --yes      # Skip confirmation
```

## Troubleshooting

### "ffmpeg not found"
The script will attempt to auto-install via `apt-get`. If that fails:

```bash
sudo apt-get install -y ffmpeg
```

### "yt-dlp not found"
The script will attempt to auto-install via `apt-get` or `pip`. If both fail:

```bash
sudo apt-get install -y yt-dlp
# or
pip install yt-dlp
```

### Build fails on certain distros
Ensure you have Python development headers:

```bash
# Ubuntu/Debian
sudo apt-get install python3-dev

# Fedora
sudo dnf install python3-devel

# Arch
sudo pacman -S python-devel
```

## License

MIT

## Support

Report issues on GitHub: [JustMrKoala/koalaiptv-linux](https://github.com/JustMrKoala/koalaiptv-linux)
