#!/usr/bin/env python3
"""
╔════════════════════════════════════════════════════════════════════════════╗
║       ___                                                                    ║
║     {~._.~}   KoalaIPTV v1.6 (Linux optimized)                              ║
║      ( Y )    Zero Bullshit. Just Streams.                                  ║
║     ()~*~()   Live • VOD • Series • yt-dlp Powered                          ║
║     (_)-(_)                                                                 ║
╚════════════════════════════════════════════════════════════════════════════╝
"""

import sys
import json
import re
import argparse
import subprocess
import urllib.request
import shutil
import os
import stat
import tempfile
import zipfile
from pathlib import Path
from typing import Optional, Dict, List, Tuple
import textwrap

VERSION = "1.6"

# ────────────────────────────────────────────────────────────────────────────
# ANSI Color codes for better CLI UX (Linux-optimized)
# ────────────────────────────────────────────────────────────────────────────

class Colors:
    """ANSI color codes for terminal output."""
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    CYAN = "\033[36m"
    GREEN = "\033[32m"
    RED = "\033[31m"
    YELLOW = "\033[33m"
    MAGENTA = "\033[35m"
    BLUE = "\033[34m"
    WHITE = "\033[37m"
    
    @staticmethod
    def disable():
        """Disable colors if output is not a TTY."""
        for attr in dir(Colors):
            if not attr.startswith('_'):
                setattr(Colors, attr, "")

# Disable colors if not a TTY (piped output)
if not sys.stdout.isatty():
    Colors.disable()


HELP_BANNER = f"""
{Colors.CYAN}{Colors.BOLD}
       ___
     {{~._.~}}   KoalaIPTV v{VERSION}
      ( Y )    Zero Bullshit. Just Streams.
     ()~*~()   Live  |  VOD  |  Series  |  yt-dlp Powered
     (_)-(_)
{Colors.RESET}
"""

class KoalaHelpFormatter(argparse.RawDescriptionHelpFormatter):
    """Custom help formatter with banner."""
    def format_help(self):
        return HELP_BANNER + "\n" + super().format_help()


HELP_EPILOG = """
{b}commands:{r}
  configure   Save Xtream provider credentials and download folder
  convert     Build an M3U playlist from your provider
  search      Interactive search and download
  download    Search by name and download (scriptable)
  update      Self-update this portable Linux build

{b}download location (search / download):{r}
  (default)   Uses the folder from configure (or ./koala_downloads)
  -c          Save to the current directory you run the command from
  --output-dir <path>   Override with a specific folder

{b}examples:{r}
  koalaiptv search
  koalaiptv -c search
  koalaiptv download "Breaking Bad" --first
  koalaiptv -c download "CNN" --first
  koalaiptv convert
  koalaiptv configure
  koalaiptv update
""".format(b=Colors.BOLD, r=Colors.RESET).strip()

CONFIG_PATH = Path.home() / ".koala_iptv" / "config.json"
M3U_CACHE_PATH = Path.home() / ".koala_iptv" / "playlist.m3u"


# ────────────────────────────────────────────────────────────────────────────
# Logging & Progress utilities (Linux CLI optimized)
# ────────────────────────────────────────────────────────────────────────────

def log_info(msg: str) -> None:
    """Print info message."""
    print(f"{Colors.CYAN}[*]{Colors.RESET} {msg}")

def log_success(msg: str) -> None:
    """Print success message."""
    print(f"{Colors.GREEN}[+]{Colors.RESET} {msg}")

def log_error(msg: str) -> None:
    """Print error message."""
    print(f"{Colors.RED}[-]{Colors.RESET} {msg}")

def log_warning(msg: str) -> None:
    """Print warning message."""
    print(f"{Colors.YELLOW}[!]{Colors.RESET} {msg}")

def log_debug(msg: str, verbose: bool = False) -> None:
    """Print debug message if verbose."""
    if verbose:
        print(f"{Colors.DIM}[DEBUG]{Colors.RESET} {msg}")

def progress_bar(current: int, total: int, label: str = "", width: int = 40) -> None:
    """Display a progress bar for terminal."""
    if total <= 0:
        return
    
    percent = current / total
    filled = int(width * percent)
    bar = "█" * filled + "░" * (width - filled)
    pct_str = f"{percent*100:.1f}%"
    
    # Use \r to overwrite line
    print(f"\r{label} {Colors.CYAN}{bar}{Colors.RESET} {pct_str}", end="", flush=True)


# ────────────────────────────────────────────────────────────────────────────
# Dependency auto-install (apt + pip fallback)
# ────────────────────────────────────────────────────────────────────────────

def _apt_install(package: str) -> bool:
    """Try to install a package via apt-get. Returns True on success."""
    try:
        log_info(f"Installing {Colors.BOLD}{package}{Colors.RESET} via apt-get (may ask for sudo password)...")
        result = subprocess.run(
            ["sudo", "apt-get", "install", "-y", package],
            check=True,
            timeout=120,
            capture_output=True,
        )
        return result.returncode == 0
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired) as e:
        log_error(f"apt-get install {package} failed: {e}")
        return False


def _pip_install(package: str) -> bool:
    """Try to install a package via pip. Returns True on success."""
    try:
        log_info(f"Installing {Colors.BOLD}{package}{Colors.RESET} via pip...")
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "--quiet", package],
            check=True,
            timeout=120,
            capture_output=True,
        )
        return result.returncode == 0
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired) as e:
        log_error(f"pip install {package} failed: {e}")
        return False


def ensure_dependencies(require_download: bool = False) -> None:
    """Auto-install yt-dlp and ffmpeg if they are missing."""
    
    # ── ffmpeg ──────────────────────────────────────────────────────────
    if not shutil.which("ffmpeg"):
        log_warning("ffmpeg not found. Attempting automatic installation...")
        ok = _apt_install("ffmpeg")
        if not ok:
            log_warning("Could not auto-install ffmpeg via apt. Install manually:")
            print(f"  {Colors.BOLD}sudo apt-get install -y ffmpeg{Colors.RESET}")
            if require_download:
                log_warning("ffmpeg is required for merged video+audio downloads. Continuing without it.")
        else:
            if shutil.which("ffmpeg"):
                log_success("ffmpeg installed successfully.")
            else:
                log_warning("ffmpeg installation reported success but binary not found in PATH.")

    # ── yt-dlp ──────────────────────────────────────────────────────────
    if not shutil.which("yt-dlp"):
        log_warning("yt-dlp not found. Attempting automatic installation...")
        ok = _apt_install("yt-dlp")
        if not ok or not shutil.which("yt-dlp"):
            ok = _pip_install("yt-dlp")
        if shutil.which("yt-dlp"):
            log_success("yt-dlp installed successfully.")
        else:
            log_error("Could not auto-install yt-dlp. Install manually:")
            print(f"  {Colors.BOLD}sudo apt-get install -y yt-dlp{Colors.RESET}")
            print(f"  {Colors.BOLD}or: pip install yt-dlp{Colors.RESET}")
            if require_download:
                log_error("yt-dlp is required to download streams.")
                sys.exit(1)


# ────────────────────────────────────────────────────────────────────────────
# Config helpers
# ────────────────────────────────────────────────────────────────────────────

def ensure_config_dir() -> None:
    """Ensure config directory exists."""
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)


def load_config() -> Dict:
    """Load configuration from disk."""
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH) as f:
                return json.load(f)
        except json.JSONDecodeError:
            log_error(f"Invalid JSON in {CONFIG_PATH}")
            return {}
    return {}


def save_config(cfg: Dict) -> None:
    """Save configuration to disk."""
    ensure_config_dir()
    with open(CONFIG_PATH, "w") as f:
        json.dump(cfg, f, indent=2)


def get_executable_path() -> Path:
    """Returns the true path of the running executable or script."""
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).resolve()
    return Path(__file__).resolve()


def ensure_executable_permissions(path: Path) -> None:
    """Ensure a file has execute permission for the owner."""
    try:
        current = path.stat().st_mode
        path.chmod(current | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    except Exception as e:
        log_warning(f"Could not set execute permissions on {path}: {e}")


def ensure_output_dir_writable(path: Path) -> Path:
    """Create output directory and verify we can write to it."""
    try:
        path.mkdir(parents=True, exist_ok=True)
    except PermissionError:
        log_error(f"Cannot create output directory (permission denied): {path}")
        fallback = Path.home() / "KoalaIPTV"
        log_warning(f"Falling back to: {fallback}")
        fallback.mkdir(parents=True, exist_ok=True)
        return fallback
    
    # Quick write test
    test_file = path / ".koala_write_test"
    try:
        test_file.write_text("test")
        test_file.unlink()
    except PermissionError:
        log_error(f"Output directory is not writable: {path}")
        fallback = Path.home() / "KoalaIPTV"
        log_warning(f"Falling back to: {fallback}")
        fallback.mkdir(parents=True, exist_ok=True)
        return fallback
    
    return path


def setup_system_path(quiet: bool = False) -> None:
    """Create a symlink in ~/.local/bin/koalaiptv so the tool is on the user's PATH."""
    exe_path = get_executable_path()
    local_bin = Path.home() / ".local" / "bin"
    local_bin.mkdir(parents=True, exist_ok=True)
    symlink_path = local_bin / "koalaiptv"

    try:
        if symlink_path.exists() or symlink_path.is_symlink():
            symlink_path.unlink()
        symlink_path.symlink_to(exe_path)
        ensure_executable_permissions(exe_path)
        
        if not quiet:
            log_success(f"Symlink created: {Colors.BOLD}{symlink_path}{Colors.RESET} → {Colors.DIM}{exe_path}{Colors.RESET}")

        if str(local_bin) not in os.environ.get("PATH", ""):
            if not quiet:
                log_warning(f"{local_bin} is not in your PATH.")
                print(f"  Add this line to your {Colors.BOLD}~/.bashrc{Colors.RESET} or {Colors.BOLD}~/.zshrc{Colors.RESET}:")
                print(f"  {Colors.CYAN}export PATH=\"$HOME/.local/bin:$PATH\"{Colors.RESET}")
    except Exception as e:
        if not quiet:
            log_error(f"Could not create symlink: {e}")


# ────────────────────────────────────────────────────────────────────────────
# Download helper with progress
# ────────────────────────────────────────────────────────────────────────────

def download_file(url: str, dest: Path, show_progress: bool = True) -> bool:
    """Download a file with progress bar."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": f"KoalaIPTV-Updater/{VERSION}"})
        with urllib.request.urlopen(req, timeout=60) as resp:
            total = int(resp.headers.get("Content-Length", 0))
            downloaded = 0
            block_size = 8192
            dest.parent.mkdir(parents=True, exist_ok=True)
            
            with open(dest, "wb") as f:
                while True:
                    chunk = resp.read(block_size)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
                    
                    if show_progress and total > 0:
                        progress_bar(downloaded, total, "Downloading")
            
            if show_progress:
                print()  # Newline after progress bar
                log_success("Download complete.")
        
        return True
    except Exception as e:
        log_error(f"Download failed: {e}")
        return False


# ────────────────────────────────────────────────────────────────────────────
# Linux self-updater
# ────────────────────────────────────────────────────────────────────────────

def find_linux_binary(search_dir: Path) -> Path:
    """Locate the koalaiptv binary inside an extracted archive."""
    candidates = list(search_dir.rglob("koalaiptv"))
    if not candidates:
        raise FileNotFoundError("koalaiptv binary not found inside the archive.")
    
    for p in candidates:
        if p.is_file() and os.access(p, os.X_OK):
            return p
    
    return candidates[0]


def cmd_update(args) -> None:
    """Self-update the portable Linux binary in-place."""
    exe_path = get_executable_path()
    
    if not getattr(sys, "frozen", False):
        log_error("Update is only supported for the PyInstaller-built binary distribution.")
        print(f"  Run from the installed koalaiptv binary (not from source .py)")
        return

    log_info(f"Current binary: {Colors.BOLD}{exe_path}{Colors.RESET}")
    log_info(f"Current version: {Colors.BOLD}{VERSION}{Colors.RESET}")

    url = getattr(args, "url", None)
    repo = getattr(args, "repo", None) or load_config().get("update_repo") or "JustMrKoala/koalaiptv-linux"

    if not url and repo:
        log_info(f"Checking GitHub for latest release in {Colors.BOLD}{repo}{Colors.RESET}...")
        api = f"https://api.github.com/repos/{repo}/releases/latest"
        
        try:
            req = urllib.request.Request(
                api,
                headers={
                    "User-Agent": f"KoalaIPTV-Updater/{VERSION}",
                    "Accept": "application/vnd.github+json",
                },
            )
            with urllib.request.urlopen(req, timeout=30) as r:
                rel = json.loads(r.read().decode())
            
            tag = rel.get("tag_name", "unknown")
            log_success(f"Latest release: {Colors.BOLD}{tag}{Colors.RESET}")
            
            assets = rel.get("assets", [])

            def _score(n: str) -> int:
                n = n.lower()
                s = 0
                if "koalaiptv" in n: s += 10
                if "linux" in n: s += 8
                if n.endswith(".zip"): s += 3
                if any(x in n for x in ("src", "source", "win", "mac", "darwin", "code")): s -= 20
                return s

            candidates = [a for a in assets if a.get("name", "")]
            if candidates:
                scored = sorted(candidates, key=lambda a: _score(a.get("name", "")), reverse=True)
                best = scored[0]
                url = best.get("browser_download_url")
                log_info(f"Selected asset: {Colors.BOLD}{best.get('name')}{Colors.RESET}")
            else:
                log_error("No suitable asset found in the latest release.")
        
        except Exception as e:
            log_error(f"GitHub check failed: {e}")

    if not url:
        log_warning("No update URL available.")
        print(f"  Provide one explicitly:")
        print(f"    {Colors.CYAN}koalaiptv update --url https://github.com/JustMrKoala/koalaiptv-linux/releases/download/{VERSION}/koalaiptv-linux.zip{Colors.RESET}")
        print(f"  Or run without --url to auto-use the default repo.")
        return

    log_info(f"Update package: {Colors.BOLD}{url}{Colors.RESET}")

    if not getattr(args, "yes", False):
        confirm = input(f"{Colors.YELLOW}Download and apply this update now? [y/N]:{Colors.RESET} ").strip().lower()
        if confirm not in ("y", "yes"):
            log_error("Update cancelled.")
            return

    tmp_zip = Path(tempfile.gettempdir()) / f"koalaiptv_update_{os.getpid()}.zip"
    tmp_extract = Path(tempfile.mkdtemp(prefix="koalaiptv_new_"))

    log_info("Downloading...")
    if not download_file(url, tmp_zip):
        shutil.rmtree(tmp_extract, ignore_errors=True)
        return

    # Check if the asset is a raw binary (not a zip)
    is_zip = False
    try:
        with open(tmp_zip, "rb") as f:
            magic = f.read(4)
        is_zip = magic == b"PK\x03\x04"
    except Exception:
        pass

    if is_zip:
        log_info("Extracting archive...")
        try:
            with zipfile.ZipFile(tmp_zip) as z:
                z.extractall(tmp_extract)
        except Exception as e:
            log_error(f"Extract failed: {e}")
            shutil.rmtree(tmp_extract, ignore_errors=True)
            tmp_zip.unlink(missing_ok=True)
            return

        try:
            new_binary = find_linux_binary(tmp_extract)
            log_info(f"New binary found at: {Colors.BOLD}{new_binary}{Colors.RESET}")
        except FileNotFoundError as e:
            log_error(str(e))
            shutil.rmtree(tmp_extract, ignore_errors=True)
            tmp_zip.unlink(missing_ok=True)
            return
    else:
        new_binary = tmp_zip

    # Atomic replace
    new_path = exe_path.with_suffix(".new")
    try:
        shutil.copy2(str(new_binary), str(new_path))
        ensure_executable_permissions(new_path)
        os.replace(str(new_path), str(exe_path))
        ensure_executable_permissions(exe_path)
        log_success(f"Binary updated in place: {Colors.BOLD}{exe_path}{Colors.RESET}")
        print(f"  Run {Colors.CYAN}'koalaiptv'{Colors.RESET} again to use the new version.")
    except PermissionError:
        log_error(f"Permission denied replacing {exe_path}")
        print(f"  Try: {Colors.CYAN}sudo cp {new_binary} {exe_path} && sudo chmod +x {exe_path}{Colors.RESET}")
    except Exception as e:
        log_error(f"Update failed: {e}")
        print(f"  New binary is at: {Colors.BOLD}{new_binary}{Colors.RESET}")
        print(f"  Copy manually: {Colors.CYAN}cp {new_binary} {exe_path} && chmod +x {exe_path}{Colors.RESET}")
    finally:
        if is_zip:
            shutil.rmtree(tmp_extract, ignore_errors=True)
        tmp_zip.unlink(missing_ok=True)
        new_path_obj = exe_path.with_suffix(".new")
        if new_path_obj.exists():
            new_path_obj.unlink(missing_ok=True)

    try:
        setup_system_path(quiet=True)
    except Exception:
        pass


# ────────────────────────────────────────────────────────────────────────────
# Xtream / M3U helpers
# ────────────────────────────────────────────────────────────────────────────

def fetch_url(url: str) -> Dict | List:
    """Fetch JSON from URL."""
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        log_error(f"API Fetch Error: {e}")
        return []


def xtream_to_m3u(host: str, username: str, password: str, output: Optional[Path] = None) -> Path:
    """Convert Xtream credentials to M3U playlist."""
    host = host.rstrip("/")
    base = f"{host}/player_api.php?username={username}&password={password}"

    log_info("🐨 Fetching live streams...")
    live_cats = fetch_url(f"{base}&action=get_live_categories")
    live_streams = fetch_url(f"{base}&action=get_live_streams")

    log_info("🐨 Fetching VOD...")
    vod_cats = fetch_url(f"{base}&action=get_vod_categories")
    vod_streams = fetch_url(f"{base}&action=get_vod_streams")

    log_info("🐨 Fetching series...")
    series_cats = fetch_url(f"{base}&action=get_series_categories")
    series_list = fetch_url(f"{base}&action=get_series")

    def cat_name(cats, cid):
        for c in cats:
            if isinstance(c, dict) and str(c.get("category_id")) == str(cid):
                return c.get("category_name", "Uncategorized")
        return "Uncategorized"

    lines = ["#EXTM3U"]

    if isinstance(live_streams, list):
        for s in live_streams:
            name = s.get("name", "Unknown")
            logo = s.get("stream_icon", "")
            cat = cat_name(live_cats, s.get("category_id", ""))
            sid = s.get("stream_id")
            url = f"{host}/live/{username}/{password}/{sid}.ts"
            lines.append(f'#EXTINF:-1 tvg-logo="{logo}" group-title="{cat}",{name}')
            lines.append(url)

    if isinstance(vod_streams, list):
        for s in vod_streams:
            name = s.get("name", "Unknown")
            logo = s.get("stream_icon", "")
            cat = cat_name(vod_cats, s.get("category_id", ""))
            sid = s.get("stream_id")
            ext = s.get("container_extension", "mp4")
            url = f"{host}/movie/{username}/{password}/{sid}.{ext}"
            lines.append(f'#EXTINF:-1 tvg-logo="{logo}" group-title="VOD: {cat}",{name}')
            lines.append(url)

    if isinstance(series_list, list):
        for s in series_list:
            name = s.get("name", "Unknown")
            logo = s.get("cover", "")
            cat = cat_name(series_cats, s.get("category_id", ""))
            sid = s.get("series_id")
            url = f"xtream://series/{sid}"
            lines.append(f'#EXTINF:-1 tvg-logo="{logo}" group-title="Series: {cat}" series-id="{sid}",{name}')
            lines.append(url)

    dest = output or M3U_CACHE_PATH
    ensure_config_dir()
    with open(dest, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    live_count = len(live_streams) if isinstance(live_streams, list) else 0
    vod_count = len(vod_streams) if isinstance(vod_streams, list) else 0
    series_count = len(series_list) if isinstance(series_list, list) else 0

    log_success(f"Playlist saved to {Colors.BOLD}{dest}{Colors.RESET}")
    print(f"  {Colors.GREEN}Live:{Colors.RESET} {live_count} | {Colors.MAGENTA}VOD:{Colors.RESET} {vod_count} | {Colors.BLUE}Series:{Colors.RESET} {series_count}")
    
    return dest


def parse_m3u(path: Path) -> List[Dict]:
    """Parse M3U playlist file."""
    entries = []
    current = {}
    
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if line.startswith("#EXTINF"):
                m_logo = re.search(r'tvg-logo="([^"]*)"', line)
                m_group = re.search(r'group-title="([^"]*)"', line)
                m_name = re.search(r",(.+)$", line)
                m_series = re.search(r'series-id="([^"]*)"', line)
                
                current = {
                    "name": m_name.group(1).strip() if m_name else "Unknown",
                    "logo": m_logo.group(1) if m_logo else "",
                    "group": m_group.group(1) if m_group else "",
                    "series_id": m_series.group(1) if m_series else None,
                    "url": "",
                }
            elif line and not line.startswith("#") and current:
                current["url"] = line
                entries.append(current)
                current = {}
    
    return entries


def search_channels(entries: List[Dict], query: str, group_filter: Optional[str] = None) -> List[Dict]:
    """Search channels by name and optional group."""
    q = query.lower()
    results = []
    
    for e in entries:
        name_match = q in e["name"].lower()
        group_match = not group_filter or group_filter.lower() in e["group"].lower()
        
        if name_match and group_match:
            results.append(e)
    
    return results


def display_results(results: List[Dict], page: int = 0, page_size: int = 20) -> None:
    """Display search results with pagination."""
    total = len(results)
    start = page * page_size
    end = min(start + page_size, total)
    
    print(f"\n{Colors.CYAN}{'═'*70}{Colors.RESET}")
    print(f"{Colors.BOLD}Results {start+1}-{end} of {total}{Colors.RESET}")
    print(f"{Colors.CYAN}{'═'*70}{Colors.RESET}")
    
    for i, e in enumerate(results[start:end], start=start):
        tag = f"{Colors.MAGENTA}[Series]{Colors.RESET}" if e.get("series_id") else ""
        group = f"{Colors.DIM}[{e['group']}]{Colors.RESET}" if e["group"] else ""
        print(f" {i+1:>4}. {Colors.BOLD}{e['name']}{Colors.RESET} {tag} {group}")
    
    print(f"{Colors.CYAN}{'═'*70}{Colors.RESET}\n")


def check_yt_dlp() -> bool:
    """Check if yt-dlp is available."""
    return shutil.which("yt-dlp") is not None


def find_ffmpeg() -> Optional[str]:
    """Find ffmpeg executable."""
    path = shutil.which("ffmpeg")
    if path:
        return path
    
    common = [
        Path("/usr/bin/ffmpeg"),
        Path("/usr/local/bin/ffmpeg"),
        Path("/snap/bin/ffmpeg"),
    ]
    
    for p in common:
        if p.exists():
            return str(p)
    
    return None


def sanitize(name: str) -> str:
    """Sanitize filename."""
    return re.sub(r'[\\/*?:"<>|]', "_", str(name)).strip("_ ")


def download_episode(
    host: str,
    username: str,
    password: str,
    series_name: str,
    season: str,
    ep: Dict,
    ep_index: int,
    output_root: Path,
    fmt: Optional[str] = None,
) -> None:
    """Download a single episode."""
    ep_num = ep.get("episode_num") or (ep_index + 1)
    title = ep.get("title", f"Episode {ep_num}")
    stream_id = ep.get("id")
    ext = ep.get("container_extension", "mp4")
    url = f"{host}/series/{username}/{password}/{stream_id}.{ext}"
    out_name = f"{series_name} S{int(season):02d}E{int(ep_num):02d} - {title}"

    try:
        season_num = int(season)
        season_folder = f"Season {season_num:02d}"
    except (ValueError, TypeError):
        season_folder = f"Season {season}"

    safe_show = sanitize(series_name)
    season_dir = output_root / safe_show / season_folder
    download_stream(url, out_name, season_dir, fmt)


def download_stream(url: str, output_name: str, output_dir: Path, format_opts: Optional[str] = None) -> None:
    """Download a stream using yt-dlp."""
    output_dir = ensure_output_dir_writable(output_dir)
    safe_name = sanitize(output_name)
    out_path = output_dir / f"{safe_name}.mp4"

    ffmpeg = find_ffmpeg()

    cmd = [
        "yt-dlp",
        "--no-playlist",
        "--merge-output-format", "mp4",
        "--output", str(out_path),
        "--socket-timeout", "30",
        "--retries", "20",
        "--fragment-retries", "20",
        "--retry-sleep", "3",
        "--hls-use-mpegts",
        "--user-agent", "VLC/3.0.9 LibVLC/3.0.9",
    ]

    if ffmpeg:
        cmd += ["--ffmpeg-location", ffmpeg]
        cmd += ["-f", format_opts if format_opts else "bestvideo+bestaudio/best"]
    else:
        log_warning("ffmpeg not found — downloading best single-file stream.")
        cmd += ["-f", format_opts if format_opts else "best"]

    cmd += ["--", url]

    log_info(f"🐨 Downloading: {Colors.BOLD}{output_name}{Colors.RESET}")
    print(f"  URL: {Colors.DIM}{url}{Colors.RESET}")
    print(f"  Output: {Colors.BOLD}{out_path}{Colors.RESET}\n")

    try:
        subprocess.run(cmd, check=True)
        log_success(f"Saved to: {Colors.BOLD}{out_path}{Colors.RESET}")
    except subprocess.CalledProcessError as e:
        log_error(f"Download failed: {e}")


def browse_series(entry: Dict, output_dir: Path) -> None:
    """Browse and download episodes from a series."""
    cfg = load_config()
    host = cfg.get("host", "").rstrip("/")
    username = cfg.get("username", "")
    password = cfg.get("password", "")

    if not all([host, username, password]):
        log_error("Credentials missing. Run 'koalaiptv configure'.")
        return

    series_id = entry["series_id"]
    log_info(f"Fetching episodes for: {Colors.BOLD}{entry['name']}{Colors.RESET}...")

    try:
        data = fetch_url(
            f"{host}/player_api.php?username={username}&password={password}"
            f"&action=get_series_info&series_id={series_id}"
        )
        if not isinstance(data, dict):
            data = {}
    except Exception as e:
        log_error(f"Could not fetch series info: {e}")
        return

    episodes_by_season: Dict[str, List] = {}
    raw_episodes = data.get("episodes", {})

    if isinstance(raw_episodes, dict):
        for season_num, eps in raw_episodes.items():
            episodes_by_season[str(season_num)] = eps
    elif isinstance(raw_episodes, list):
        episodes_by_season["1"] = raw_episodes

    if not episodes_by_season:
        log_error("No episodes found for this series.")
        return

    seasons = sorted(episodes_by_season.keys(), key=lambda x: int(x) if x.isdigit() else 0)

    while True:
        print(f"\n{Colors.BOLD}Seasons for: {entry['name']}{Colors.RESET}")
        print(f" {Colors.CYAN}{'─'*50}{Colors.RESET}")
        
        for i, s in enumerate(seasons, 1):
            count = len(episodes_by_season[s])
            print(f"  {i}. Season {s} ({count} episodes)")
        
        print(f" {Colors.CYAN}{'─'*50}{Colors.RESET}")

        pick = input(f" {Colors.YELLOW}Season number (or [b]ack, or all):{Colors.RESET} ").strip().lower()
        
        if pick == "b":
            return

        if pick == "all":
            fmt = input(f" {Colors.YELLOW}Format override (leave blank for best):{Colors.RESET} ").strip() or None
            log_info(f"Downloading ALL episodes for {Colors.BOLD}{entry['name']}{Colors.RESET} sequentially...")
            
            for season_key in seasons:
                eps = episodes_by_season[season_key]
                print(f"\n{Colors.MAGENTA}─── Season {season_key} ───{Colors.RESET}")
                
                for idx, ep in enumerate(eps):
                    download_episode(host, username, password, entry["name"], season_key, ep, idx, output_dir, fmt)
            
            log_success(f"Entire series download complete: {Colors.BOLD}{entry['name']}{Colors.RESET}")
            return

        if pick.isdigit():
            idx = int(pick) - 1
            if 0 <= idx < len(seasons):
                season_key = seasons[idx]
                browse_episodes(entry["name"], season_key, episodes_by_season[season_key], host, username, password, output_dir)
            else:
                log_error("Invalid season.")


def browse_episodes(
    series_name: str,
    season: str,
    episodes: List,
    host: str,
    username: str,
    password: str,
    output_dir: Path,
) -> None:
    """Browse and download episodes from a season."""
    while True:
        print(f"\n{Colors.BOLD}Season {season} episodes:{Colors.RESET}")
        print(f" {Colors.CYAN}{'─'*50}{Colors.RESET}")
        
        for i, ep in enumerate(episodes, 1):
            ep_num = ep.get("episode_num", i)
            title = ep.get("title", f"Episode {ep_num}")
            print(f"  {i}. Ep {ep_num}: {title}")
        
        print(f" {Colors.CYAN}{'─'*50}{Colors.RESET}")

        pick = input(f" {Colors.YELLOW}Episode number to download (or [b]ack, or all):{Colors.RESET} ").strip().lower()
        
        if pick == "b":
            return

        if pick == "all":
            fmt = input(f" {Colors.YELLOW}Format override (leave blank for best):{Colors.RESET} ").strip() or None
            log_info(f"Downloading all {len(episodes)} episodes sequentially...")
            
            for idx, ep in enumerate(episodes):
                download_episode(host, username, password, series_name, season, ep, idx, output_dir, fmt)
            
            log_success("Season download complete.")
            return

        if pick.isdigit():
            idx = int(pick) - 1
            if 0 <= idx < len(episodes):
                ep = episodes[idx]
                fmt = input(f" {Colors.YELLOW}Format override (leave blank for best):{Colors.RESET} ").strip() or None
                download_episode(host, username, password, series_name, season, ep, idx, output_dir, fmt)
            else:
                log_error("Invalid episode.")


def interactive_search(m3u_path: Path, output_dir: Path) -> None:
    """Interactive search and download interface."""
    log_info(f"Loading M3U from {Colors.BOLD}{m3u_path}{Colors.RESET}...")
    entries = parse_m3u(m3u_path)
    log_success(f"Loaded {Colors.BOLD}{len(entries)}{Colors.RESET} entries.\n")
    print(f"Just type to search. Commands: {Colors.CYAN}groups{Colors.RESET}, {Colors.CYAN}quit{Colors.RESET}\n")

    while True:
        raw = input(f"{Colors.CYAN}koalaiptv>{Colors.RESET} ").strip()
        
        if not raw:
            continue

        if raw.lower() in ("quit", "exit", "q"):
            log_success("Catch ya later! 🐨")
            break

        if raw.lower() == "groups":
            groups = sorted(set(e["group"] for e in entries if e["group"]))
            for g in groups:
                print(f"  {Colors.BLUE}{g}{Colors.RESET}")
            print()
            continue

        query = raw[7:].strip() if raw.lower().startswith("search ") else raw
        group_filter = None

        if " in:" in query:
            parts = query.split(" in:", 1)
            query = parts[0].strip()
            group_filter = parts[1].strip()

        results = search_channels(entries, query, group_filter)

        if not results:
            log_error("No results found.\n")
            continue

        page = 0
        page_size = 20

        while True:
            display_results(results, page, page_size)
            total_pages = (len(results) - 1) // page_size

            nav = input(f"{Colors.YELLOW}Enter number to select, [n]ext, [p]rev, [b]ack:{Colors.RESET} ").strip().lower()

            if nav == "b":
                break
            if nav == "n" and page < total_pages:
                page += 1
                continue
            if nav == "p" and page > 0:
                page -= 1
                continue

            if nav.isdigit():
                idx = int(nav) - 1
                if 0 <= idx < len(results):
                    chosen = results[idx]
                    print(f"\n{Colors.GREEN}[+] Selected: {Colors.BOLD}{chosen['name']}{Colors.RESET}")
                    print(f"    Group: {Colors.BLUE}{chosen['group']}{Colors.RESET}")

                    if chosen.get("series_id"):
                        browse_series(chosen, output_dir)
                    else:
                        print(f"    URL: {Colors.DIM}{chosen['url']}{Colors.RESET}")
                        fmt = input(f"{Colors.YELLOW}Format override (leave blank for best):{Colors.RESET} ").strip() or None
                        download_stream(chosen["url"], chosen["name"], output_dir, fmt)
                else:
                    log_error("Invalid number.")


def prompt(label: str, current: Optional[str] = None, required: bool = True) -> Optional[str]:
    """Prompt for user input."""
    hint = f" {Colors.DIM}[{current}]{Colors.RESET}" if current else ""
    suffix = " (leave blank to keep)" if current else (" (required)" if required else " (optional, press Enter to skip)")
    display = f"{Colors.CYAN}{label}{Colors.RESET}{hint}{suffix}: "
    
    while True:
        value = input(display).strip()
        if value:
            return value
        if current:
            return current
        if not required:
            return None
        log_error("This field is required.")


def run_wizard(cfg: Dict, fresh: bool = False) -> Dict:
    """Interactive configuration wizard."""
    if fresh:
        print(f"\n{Colors.CYAN}{'═'*60}{Colors.RESET}")
        print(f"{Colors.BOLD}{Colors.GREEN} Welcome to KoalaIPTV -- first-time setup 🐨{Colors.RESET}")
        print(f"{Colors.CYAN}{'═'*60}{Colors.RESET}\n")
        setup_system_path()
        print(f"\n{Colors.BOLD}Please configure your Xtream Codes provider details:{Colors.RESET}\n")
    else:
        print(f"\n{Colors.CYAN}{'═'*60}{Colors.RESET}")
        print(f"{Colors.BOLD}{Colors.YELLOW} KoalaIPTV -- reconfigure{Colors.RESET}")
        print(f"{Colors.CYAN}{'═'*60}{Colors.RESET}\n")

    print(f"{Colors.BOLD}Step 1/4 Provider host{Colors.RESET}")
    print(f" The base URL of your Xtream provider, e.g.")
    print(f" {Colors.DIM}http://myiptv.com:8080 or https://streams.example.com{Colors.RESET}\n")
    cfg["host"] = prompt("Host", current=cfg.get("host"))

    print(f"\n{Colors.BOLD}Step 2/4 Username{Colors.RESET}")
    cfg["username"] = prompt("Username", current=cfg.get("username"))

    print(f"\n{Colors.BOLD}Step 3/4 Password{Colors.RESET}")
    cfg["password"] = prompt("Password", current=cfg.get("password"))

    print(f"\n{Colors.BOLD}Step 4/4 Download folder{Colors.RESET}")
    print(f" Where finished MP4 files will be saved.\n")
    default_dir = cfg.get("output_dir", str(Path.home() / "Videos" / "KoalaIPTV"))
    cfg["output_dir"] = prompt("Output dir", current=default_dir)

    ensure_output_dir_writable(Path(cfg["output_dir"]))

    save_config(cfg)
    log_success("Configuration saved.")
    print(f"  Config file: {Colors.DIM}{CONFIG_PATH}{Colors.RESET}\n")

    fetch_now = input(f"{Colors.YELLOW}Fetch M3U playlist now? [Y/n]:{Colors.RESET} ").strip().lower()
    if fetch_now in ("", "y", "yes"):
        print()
        xtream_to_m3u(cfg["host"], cfg["username"], cfg["password"])

    print()
    return cfg


# ────────────────────────────────────────────────────────────────────────────
# Command handlers
# ────────────────────────────────────────────────────────────────────────────

def cmd_configure(args) -> None:
    """Handle configure command."""
    cfg = load_config()
    flags = [args.host, args.username, args.password,
             getattr(args, "output_dir", None), getattr(args, "update_repo", None)]
    
    if any(flags):
        if args.host:
            cfg["host"] = args.host
        if args.username:
            cfg["username"] = args.username
        if args.password:
            cfg["password"] = args.password
        if getattr(args, "output_dir", None):
            cfg["output_dir"] = args.output_dir
        if getattr(args, "update_repo", None):
            cfg["update_repo"] = args.update_repo
        
        save_config(cfg)
        log_success("Configuration saved.")
    else:
        run_wizard(cfg, fresh=not CONFIG_PATH.exists())


def cmd_convert(args) -> None:
    """Handle convert command."""
    cfg = load_config()
    host = args.host or cfg.get("host")
    username = args.username or cfg.get("username")
    password = args.password or cfg.get("password")
    
    if not all([host, username, password]):
        log_error("Provide --host, --username, --password or run configure first.")
        sys.exit(1)
    
    out = Path(args.output) if args.output else None
    xtream_to_m3u(host, username, password, out)


def resolve_output_dir(args, cfg: Dict) -> Path:
    """Resolve output directory from args and config."""
    if getattr(args, "current", False):
        return Path.cwd().resolve()
    if getattr(args, "output_dir", None):
        return Path(args.output_dir).resolve()
    return Path(cfg.get("output_dir", "./koala_downloads")).resolve()


def cmd_search(args) -> None:
    """Handle search command."""
    ensure_dependencies(require_download=True)
    cfg = load_config()
    m3u = Path(args.m3u) if args.m3u else M3U_CACHE_PATH
    
    if not m3u.exists():
        log_error(f"M3U not found at {m3u}. Run 'convert' first or pass --m3u.")
        sys.exit(1)
    
    out_dir = resolve_output_dir(args, cfg)
    if getattr(args, "current", False):
        log_info(f"Download folder: current directory ({Colors.BOLD}{out_dir}{Colors.RESET})")
    
    interactive_search(m3u, out_dir)


def cmd_download(args) -> None:
    """Handle download command."""
    ensure_dependencies(require_download=True)
    cfg = load_config()
    m3u = Path(args.m3u) if args.m3u else M3U_CACHE_PATH
    
    if not m3u.exists():
        log_error(f"M3U not found at {m3u}. Run 'convert' first or pass --m3u.")
        sys.exit(1)

    entries = parse_m3u(m3u)
    results = search_channels(entries, args.query, args.group)

    if not results:
        log_error("No matches found.")
        sys.exit(1)

    if len(results) == 1 or args.first:
        chosen = results[0]
    else:
        display_results(results, page_size=50)
        raw = input(f"{Colors.YELLOW}Enter number to download:{Colors.RESET} ").strip()
        if not raw.isdigit():
            log_error("Cancelled.")
            sys.exit(0)
        idx = int(raw) - 1
        if not (0 <= idx < len(results)):
            log_error("Invalid number.")
            sys.exit(1)
        chosen = results[idx]

    out_dir = resolve_output_dir(args, cfg)
    if getattr(args, "current", False):
        log_info(f"Download folder: current directory ({Colors.BOLD}{out_dir}{Colors.RESET})")

    if chosen.get("series_id"):
        browse_series(chosen, out_dir)
    else:
        download_stream(chosen["url"], chosen["name"], out_dir, args.format)


# ────────────────────────────────────────────────────────────────────────────
# Version checking
# ────────────────────────────────────────────────────────────────────────────

def get_latest_version(repo: str = "JustMrKoala/koalaiptv-linux") -> Optional[str]:
    """Check for latest version from GitHub."""
    try:
        api = f"https://api.github.com/repos/{repo}/releases/latest"
        req = urllib.request.Request(
            api,
            headers={"User-Agent": f"KoalaIPTV/{VERSION}", "Accept": "application/vnd.github+json"},
        )
        with urllib.request.urlopen(req, timeout=6) as r:
            data = json.loads(r.read().decode())
            tag = (data.get("tag_name") or "").lstrip("vV")
            return tag or None
    except Exception:
        return None


def _is_newer_version(latest: str, current: str) -> bool:
    """Compare version strings."""
    def _t(s: str) -> Tuple:
        try:
            return tuple(int(x) for x in s.split(".") if x.strip().isdigit())
        except Exception:
            return (0,)
    
    try:
        return _t(latest) > _t(current)
    except Exception:
        return False


# ────────────────────────────────────────────────────────────────────────────
# Entry point
# ────────────────────────────────────────────────────────────────────────────

def main() -> None:
    """Main entry point."""
    first_run = not CONFIG_PATH.exists()
    no_args = len(sys.argv) == 1

    try:
        setup_system_path(quiet=True)
    except Exception:
        pass

    if first_run and no_args:
        log_warning("First run detected. Starting setup wizard...")
        ensure_dependencies(require_download=False)
        run_wizard({}, fresh=True)
        print(f"\n {Colors.GREEN}Run{Colors.RESET} {Colors.CYAN}'koalaiptv search'{Colors.RESET} {Colors.GREEN}to start browsing.{Colors.RESET}\n")
        sys.exit(0)

    parser = argparse.ArgumentParser(
        prog="koalaiptv",
        description="Xtream-to-M3U conversion and yt-dlp powered downloading.",
        epilog=HELP_EPILOG,
        formatter_class=KoalaHelpFormatter,
    )
    parser.add_argument("--version", action="version", version=f"KoalaIPTV {VERSION}")
    parser.add_argument(
        "-c", "--current",
        action="store_true",
        help="download to the current working directory (search / download)",
    )

    sub = parser.add_subparsers(dest="command", metavar="<command>")

    p_cfg = sub.add_parser("configure", help="Save connection settings")
    p_cfg.add_argument("--host")
    p_cfg.add_argument("--username")
    p_cfg.add_argument("--password")
    p_cfg.add_argument("--output-dir")
    p_cfg.add_argument("--update-repo", help="GitHub owner/repo for update checks (e.g. yourname/iptvcli)")
    p_cfg.set_defaults(func=cmd_configure)

    p_conv = sub.add_parser("convert", help="Convert Xtream credentials to M3U playlist")
    p_conv.add_argument("--host")
    p_conv.add_argument("--username")
    p_conv.add_argument("--password")
    p_conv.add_argument("--output", help="Destination .m3u file (default: ~/.koala_iptv/playlist.m3u)")
    p_conv.set_defaults(func=cmd_convert)

    p_search = sub.add_parser("search", help="Interactive search and download from M3U")
    p_search.add_argument("--m3u", help="Path to .m3u file")
    p_search.add_argument("--output-dir", help="Where to save downloaded files")
    p_search.add_argument("-c", "--current", action="store_true", help="Save to current working directory")
    p_search.set_defaults(func=cmd_search)

    p_dl = sub.add_parser("download", help="Non-interactive: search and download by query")
    p_dl.add_argument("query", help="Search term")
    p_dl.add_argument("--m3u", help="Path to .m3u file")
    p_dl.add_argument("--group", help="Filter by group name")
    p_dl.add_argument("--output-dir", help="Where to save downloaded files")
    p_dl.add_argument("-c", "--current", action="store_true", help="Save to current working directory")
    p_dl.add_argument("--format", help="yt-dlp format string (default: bestvideo+bestaudio/best)")
    p_dl.add_argument("--first", action="store_true", help="Auto-select first result without prompting")
    p_dl.set_defaults(func=cmd_download)

    p_up = sub.add_parser("update", help="Self-update this portable Linux build")
    p_up.add_argument("--url", help="Direct download URL to a new build (.zip or raw binary)")
    p_up.add_argument("--repo", help="GitHub repo (owner/repo) to fetch latest release asset from automatically")
    p_up.add_argument("--yes", "-y", action="store_true", help="Apply without interactive confirmation")
    p_up.set_defaults(func=cmd_update)

    if no_args:
        repo = load_config().get("update_repo") or "JustMrKoala/koalaiptv-linux"
        latest = get_latest_version(repo)
        
        if latest and _is_newer_version(latest, VERSION):
            print(f"\n{Colors.YELLOW}[!] New version available:{Colors.RESET} {Colors.GREEN}{latest}{Colors.RESET}  (you are on {VERSION})")
            print(f"    Run:  {Colors.CYAN}koalaiptv update{Colors.RESET}\n")
            
            try:
                ans = input(f"{Colors.YELLOW}Update to the latest version now? [Y/n]:{Colors.RESET} ").strip().lower()
            except EOFError:
                ans = ""
            
            if ans in ("", "y", "yes"):
                class _UpdArgs:
                    url = None
                    repo = None
                    yes = True
                
                try:
                    cmd_update(_UpdArgs())
                    return
                except SystemExit:
                    return
        
        parser.print_help()
        sys.exit(0)

    args = parser.parse_args()
    if getattr(args, "current", False) and getattr(args, "command", None) not in ("search", "download"):
        log_error("-c / --current only applies to search and download commands.")
        sys.exit(2)

    if hasattr(args, "func"):
        args.func(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
