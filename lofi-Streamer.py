#!/usr/bin/env python3
import os
import time
import random
import socket
import subprocess
from pathlib import Path
from typing import Iterable, Iterator, List, Optional

# -------------------------------------------------------
#  LOFI STREAMER v3.1 — GENDEMIK DIGITAL
#  Updated to ignore macOS junk files (._*, .DS_Store)
# -------------------------------------------------------

def _detect_base_dir() -> Path:
    """Return the root project directory regardless of install layout."""
    base = Path(__file__).resolve().parent
    if base.name.lower() == "servers":
        return base.parent
    return base

BASE_DIR = _detect_base_dir()

# -------------------------------------------------------

def _env_path(name: str, default: Path) -> Path:
    raw_path = Path(os.environ.get(name, str(default))).expanduser()
    try:
        return raw_path.resolve(strict=False)
    except FileNotFoundError:
        return raw_path

def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        print(f"⚠️ Invalid integer for {name!s}: {raw!r} — using {default}.")
        return default

def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}

# -------------------------------------------------------

PLAYLIST_DIR = _env_path("LOFI_PLAYLIST_DIR", BASE_DIR / "Sounds")
LOGO_DIR = _env_path("LOFI_BRAND_DIR", BASE_DIR / "Logo")
VIDEO_DIR = _env_path("LOFI_VIDEO_DIR", BASE_DIR / "Videos")
STREAM_URL_FILE = _env_path("LOFI_STREAM_URL_FILE", BASE_DIR / "stream_url.txt")

FFMPEG_LOGO = _env_path("LOFI_BRAND_IMAGE", LOGO_DIR / "LoFiLogo700.png")
VIDEO_FILE = _env_path("LOFI_VIDEO_FILE", VIDEO_DIR / "Lofi3.mp4")
STREAM_URL_ENV = os.environ.get("LOFI_YOUTUBE_URL", "")
CHECK_HOST = os.environ.get("LOFI_CHECK_HOST", "a.rtmp.youtube.com")
CHECK_PORT = _env_int("LOFI_CHECK_PORT", 1935)
FALLBACK_COLOR = os.environ.get("LOFI_FALLBACK_COLOR", "black")
FALLBACK_SIZE = os.environ.get("LOFI_FALLBACK_SIZE", "1280x720")
FALLBACK_FPS = os.environ.get("LOFI_FALLBACK_FPS", "30")
LOGO_PADDING = _env_int("LOFI_LOGO_PADDING", 40)
TRACK_EXIT_BUFFER = _env_int("LOFI_TRACK_EXIT_BUFFER", 5)
SKIP_NETWORK_CHECK = _env_bool("LOFI_SKIP_NETWORK_CHECK")

# -------------------------------------------------------

def load_stream_url():
    if STREAM_URL_ENV:
        print("🔐 Using stream URL from LOFI_YOUTUBE_URL environment variable.")
        return STREAM_URL_ENV.strip()

    if STREAM_URL_FILE.exists():
        return STREAM_URL_FILE.read_text().strip()

    print("❌ No stream URL configured! Set LOFI_YOUTUBE_URL or create stream_url.txt.")
    return ""

# -------------------------------------------------------
#   PATCHED: JUNK FILE IGNORING
# -------------------------------------------------------

JUNK_PREFIXES = ("._",)
JUNK_FILES = {".ds_store", "thumbs.db"}

def _is_valid_audio(track: Path) -> bool:
    """Reject macOS metadata and any hidden/system files."""
    name = track.name.lower()

    if track.name.startswith(JUNK_PREFIXES):
        return False
    if name in JUNK_FILES:
        return False
    if name.startswith("."):
        return False

    return track.suffix.lower() in [".mp3", ".wav", ".m4a", ".flac"]

def load_tracks() -> List[Path]:
    if not PLAYLIST_DIR.exists():
        print("❌ Sounds folder missing:", PLAYLIST_DIR)
        return []

    tracks = [
        t for t in PLAYLIST_DIR.iterdir()
        if t.is_file() and _is_valid_audio(t)
    ]

    print(f"🎶 Loaded {len(tracks)} clean tracks from playlist directory {PLAYLIST_DIR}.")
    return tracks

# -------------------------------------------------------

def load_video_file():
    if VIDEO_FILE.exists():
        return VIDEO_FILE
    print("⚠️ Video file not found at", VIDEO_FILE)
    return None

def check_network():
    if SKIP_NETWORK_CHECK:
        print("⚠️ Skipping network connectivity probe (LOFI_SKIP_NETWORK_CHECK set).")
        return True

    print(f"🌐 Checking network connectivity to {CHECK_HOST}:{CHECK_PORT}...")
    try:
        with socket.create_connection((CHECK_HOST, CHECK_PORT), timeout=3):
            print("✅ Network online — starting / continuing stream.")
            return True
    except OSError:
        pass
    print("❌ Network offline or RTMP host unreachable — waiting...")
    return False

# -------------------------------------------------------

def _video_input_args(video_file: Optional[Path]):
    if video_file and video_file.exists():
        return ["-stream_loop", "-1", "-re", "-i", str(video_file)], "[0:v]"

    fallback = f"color=c={FALLBACK_COLOR}:s={FALLBACK_SIZE}:r={FALLBACK_FPS}"
    return ["-f", "lavfi", "-re", "-i", fallback], "[0:v]"

def _logo_overlay_filter(video_ref: str) -> str:
    if not FFMPEG_LOGO.exists():
        print("⚠️ Logo image not found, streaming without overlay.")
        return f"{video_ref}scale=1280:720,format=yuv420p[v0]"
    pad = LOGO_PADDING
    return (
        f"{video_ref}scale=1280:720,format=yuv420p[v0];"
        f"[v0][2:v]overlay=W-w-{pad}:H-h-{pad}[vout]"
    )

def _playlist_cycle(tracks: Iterable[Path]) -> Iterator[Path]:
    ordered = list(tracks)
    if not ordered:
        return iter(())
    def generator():
        while True:
            random.shuffle(ordered)
            for track in ordered:
                yield track
    return generator()

# -------------------------------------------------------

def _track_duration(track: Path) -> int:
    try:
        import mutagen
        audio = mutagen.File(track)
        if audio and audio.info and getattr(audio.info, "length", None):
            return max(10, int(audio.info.length))
    except Exception:
        pass

    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(track)],
            capture_output=True, text=True, check=True,
        )
        seconds = float(result.stdout.strip())
        if seconds > 0:
            return max(10, int(seconds))
    except Exception:
        pass

    return 180

# -------------------------------------------------------

def _wait_for_track(process: subprocess.Popen, duration: int):
    timeout = max(1, duration + max(0, TRACK_EXIT_BUFFER))
    start = time.time()
    try:
        process.wait(timeout=timeout)
        elapsed = time.time() - start
        if process.returncode == 0:
            print(f"ℹ️ FFmpeg exited normally after {elapsed:.1f}s.")
        else:
            print(f"⚠️ FFmpeg exited early with code {process.returncode} at {elapsed:.1f}s.")
    except subprocess.TimeoutExpired:
        print("⚠️ FFmpeg hung — terminating.")
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
        print("✅ FFmpeg terminated.")

# -------------------------------------------------------

def start_stream(track, stream_url, video_file, duration):
    print(f"🎧 Now playing: {track.name} ({duration}s)")

    video_args, video_ref = _video_input_args(video_file)
    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel", "error",
        *video_args,
        "-i", str(track),
    ]

    filter_chain = f"{video_ref}scale=1280:720,format=yuv420p[v0]"
    map_args = ["-map", "[v0]", "-map", "1:a"]

    if FFMPEG_LOGO.exists():
        cmd += ["-loop", "1", "-i", str(FFMPEG_LOGO)]
        filter_chain = _logo_overlay_filter(video_ref)
        map_args = ["-map", "[vout]", "-map", "1:a"]

    cmd += [
        "-filter_complex", filter_chain,
        *map_args,
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-b:v", "2500k",
        "-c:a", "aac",
        "-b:a", "160k",
        "-pix_fmt", "yuv420p",
        "-shortest",
        "-f", "flv",
        stream_url,
    ]

    return subprocess.Popen(cmd)

# -------------------------------------------------------

def main():
    print("🌙 LOFI STREAMER v3.1 — GENDEMIK DIGITAL\n")

    stream_url = load_stream_url()
    if not stream_url:
        print("❌ Missing RTMP stream URL.")
        return

    tracks = load_tracks()
    if not tracks:
        print("❌ No audio tracks found!")
        return

    video_file = load_video_file()
    playlist = _playlist_cycle(tracks)

    for track in playlist:
        if not check_network():
            time.sleep(5)
            continue

        duration = _track_duration(track)
        process = start_stream(track, stream_url, video_file, duration)
        _wait_for_track(process, duration)

# -------------------------------------------------------

if __name__ == "__main__":
    main()
