#!/usr/bin/env python3
import os
import time
import random
import socket
import subprocess
from pathlib import Path
from typing import Iterator, List, Optional

# -------------------------------------------------------
#  LOFI STREAMER v4.2 — GENDEMIK DIGITAL
#  + Top-Right Logo
#  + Bottom-Right Now Playing Text
#  + macOS Junk Filter
#  + KEYFRAME-STABLE STREAMING
# -------------------------------------------------------

def _detect_base_dir() -> Path:
    base = Path(__file__).resolve().parent
    if base.name.lower() == "servers":
        return base.parent
    return base

BASE_DIR = _detect_base_dir()

# -------------------------------------------------------
#  ENV VAR HELPERS
# -------------------------------------------------------

def _env_path(name: str, default: Path) -> Path:
    raw = Path(os.environ.get(name, str(default))).expanduser()
    try:
        return raw.resolve(strict=False)
    except FileNotFoundError:
        return raw

def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except:
        print(f"⚠️ Invalid integer for {name}: {raw}")
        return default

def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}

# -------------------------------------------------------
#  PATHS
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
FALLBACK_FPS = _env_int("LOFI_FALLBACK_FPS", 30)

LOGO_PADDING = _env_int("LOFI_LOGO_PADDING", 40)
TEXT_PADDING = _env_int("LOFI_TEXT_PADDING", 40)
TRACK_EXIT_BUFFER = _env_int("LOFI_TRACK_EXIT_BUFFER", 5)

SKIP_NETWORK_CHECK = _env_bool("LOFI_SKIP_NETWORK_CHECK")

# -------------------------------------------------------
#  FILTER macOS JUNK FILES
# -------------------------------------------------------

JUNK_PREFIXES = ("._",)
JUNK_FILES = {".ds_store", "thumbs.db"}

def _is_valid_audio(track: Path) -> bool:
    """Filter junk files + valid extensions."""
    name = track.name.lower()
    if name.startswith(JUNK_PREFIXES):
        return False
    if name in JUNK_FILES:
        return False
    if name.startswith("."):
        return False
    return track.suffix.lower() in [".mp3", ".wav", ".flac", ".m4a"]

# -------------------------------------------------------
#  LOADING
# -------------------------------------------------------

def load_stream_url():
    if STREAM_URL_ENV:
        print("🔐 Using RTMP URL from environment.")
        return STREAM_URL_ENV.strip()
    if STREAM_URL_FILE.exists():
        return STREAM_URL_FILE.read_text().strip()
    print("❌ No RTMP URL found!")
    return ""

def load_tracks() -> List[Path]:
    if not PLAYLIST_DIR.exists():
        print("❌ Missing Sounds folder:", PLAYLIST_DIR)
        return []
    tracks = [t for t in PLAYLIST_DIR.iterdir() if t.is_file() and _is_valid_audio(t)]
    print(f"🎶 Loaded {len(tracks)} clean tracks.")
    return tracks

def load_video_file():
    if VIDEO_FILE.exists():
        return VIDEO_FILE
    print("⚠️ Video file missing:", VIDEO_FILE)
    return None

# -------------------------------------------------------
#  PLAYLIST ITERATOR
# -------------------------------------------------------

def _playlist_iterator(tracks: List[Path]) -> Iterator[Path]:
    """Yield tracks forever, shuffle each loop."""
    while True:
        cycle = list(tracks)
        if len(cycle) > 1:
            random.shuffle(cycle)
            print(f"🔀 Shuffled {len(cycle)} tracks.")
        for track in cycle:
            yield track

# -------------------------------------------------------
#  NETWORK CHECK
# -------------------------------------------------------

def check_network():
    if SKIP_NETWORK_CHECK:
        print("⚠️ Skipping network check.")
        return True
    print(f"🌐 Checking {CHECK_HOST}:{CHECK_PORT}...")
    try:
        with socket.create_connection((CHECK_HOST, CHECK_PORT), timeout=3):
            print("✅ Network OK.")
            return True
    except:
        print("❌ RTMP host unreachable.")
        return False

# -------------------------------------------------------
#  FFMPEG INPUT SETUP
# -------------------------------------------------------

def _video_input_args(video_file: Optional[Path]):
    if video_file and video_file.exists():
        return ["-stream_loop", "-1", "-re", "-i", str(video_file)], "[0:v]"
    fallback = f"color=c={FALLBACK_COLOR}:s={FALLBACK_SIZE}:r={FALLBACK_FPS}"
    return ["-f", "lavfi", "-re", "-i", fallback], "[0:v]"

# -------------------------------------------------------
#  LOGO OVERLAY (TOP RIGHT)
# -------------------------------------------------------

def _logo_filter(video_ref: str) -> str:
    if not FFMPEG_LOGO.exists():
        return f"{video_ref}scale=1280:720,format=yuv420p[vlog]"
    pad = LOGO_PADDING
    return (
        f"{video_ref}scale=1280:720,format=yuv420p[v0];"
        f"[v0][2:v]overlay=W-w-{pad}:{pad}[vlog]"
    )

# -------------------------------------------------------
#  NOW PLAYING TEXT (BOTTOM RIGHT)
# -------------------------------------------------------

def _escape(text: str) -> str:
    return text.replace(":", "\\:").replace("'", "\\'")

def _get_now_playing(track: Path) -> str:
    title = ""
    artist = ""

    try:
        import mutagen
        t = mutagen.File(track, easy=True)
        if t:
            title = t.get("title", [""])[0]
            artist = t.get("artist", [""])[0]
    except:
        pass

    if not title:
        title = track.stem

    if artist:
        return _escape(f"{artist} - {title}")
    return _escape(title)

def _text_filter(nowplaying: str) -> str:
    pad = TEXT_PADDING
    return (
        f"[vlog]drawtext=text='Now Playing\\: {nowplaying}':"
        f"fontcolor=white:fontsize=28:"
        f"shadowcolor=black:shadowx=2:shadowy=2:"
        f"x=W-tw-{pad}:y=H-th-{pad}[vout]"
    )

# -------------------------------------------------------
#  TRACK DURATIONS
# -------------------------------------------------------

def _track_duration(track: Path) -> int:
    try:
        import mutagen
        a = mutagen.File(track)
        if a and a.info and getattr(a.info, "length", None):
            return int(a.info.length)
    except:
        pass

    try:
        r = subprocess.run(
            ["ffprobe","-v","error","-show_entries","format=duration",
             "-of","default=noprint_wrappers=1:nokey=1",str(track)],
            capture_output=True, text=True
        )
        return int(float(r.stdout.strip()))
    except:
        return 180

# -------------------------------------------------------
#  STOP / CLEANUP
# -------------------------------------------------------

def _wait_for_track(p: subprocess.Popen, duration: int):
    try:
        p.wait(timeout=duration + TRACK_EXIT_BUFFER)
    except subprocess.TimeoutExpired:
        p.terminate()
        try:
            p.wait(timeout=5)
        except subprocess.TimeoutExpired:
            p.kill()

# -------------------------------------------------------
#  START FFMPEG PIPELINE
# -------------------------------------------------------

def start_stream(track, stream_url, video_file, duration):
    nowplaying = _get_now_playing(track)
    print(f"🎧 Now playing: {nowplaying}")

    video_args, video_ref = _video_input_args(video_file)

    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel", "error",
        *video_args,
        "-i", str(track),
    ]

    if FFMPEG_LOGO.exists():
        cmd += ["-loop", "1", "-i", str(FFMPEG_LOGO)]
        logo_filter = _logo_filter(video_ref)
    else:
        logo_filter = f"{video_ref}scale=1280:720,format=yuv420p[vlog]"

    text_filter = _text_filter(nowplaying)

    filter_chain = f"{logo_filter};{text_filter}"

    cmd += [
        "-filter_complex", filter_chain,
        "-map", "[vout]",
        "-map", "1:a",

        # ------------------------------
        # KEYFRAME-STABLE SETTINGS
        # ------------------------------
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-b:v", "2500k",

        "-g", "60",
        "-keyint_min", "60",
        "-sc_threshold", "0",
        "-force_key_frames", "expr:gte(t,n_forced*2)",

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
    print("🌙 LOFI STREAMER v4.2 — GENDEMIK DIGITAL\n")

    stream_url = load_stream_url()
    if not stream_url:
        print("❌ Missing RTMP URL.")
        return

    tracks = load_tracks()
    if not tracks:
        print("❌ No audio files found!")
        return

    video_file = load_video_file()

    for track in _playlist_iterator(tracks):
        if not check_network():
            time.sleep(5)
            continue
        duration = _track_duration(track)
        p = start_stream(track, stream_url, video_file, duration)
        _wait_for_track(p, duration)

# -------------------------------------------------------

if __name__ == "__main__":
    main()
