#!/usr/bin/env python3
import os
import time
import random
import socket
import subprocess
from pathlib import Path
from typing import Iterator, List, Optional

# -------------------------------------------------------
#  LOFI STREAMER v7.4 — GENDEMIK DIGITAL
#  + Grey LOFI Audio Bar (showfreqs)
#  + Double Height Visual Bar
#  + Bottom-Hugging Right-Aligned Now Playing
#  + Top Right Logo
#  + Pi-Safe Filters
# -------------------------------------------------------

OUTPUT_W = 1280
OUTPUT_H = 720

VU_SEG_WIDTH = 16
VU_HEIGHT = 120

LOGO_PADDING = 40
TEXT_PADDING = 40
TRACK_EXIT_BUFFER = 5

def _detect_base_dir() -> Path:
    base = Path(__file__).resolve().parent
    return base.parent if base.name.lower() == "servers" else base

BASE_DIR = _detect_base_dir()

# ---------------- ENV HELPERS ----------------

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
    try: return int(raw)
    except: return default

def _env_bool(name: str, default=False):
    raw = os.environ.get(name)
    if raw is None: return default
    return raw.lower() in {"1","true","yes","on"}

# ---------------- PATHS ----------------

PLAYLIST_DIR = _env_path("LOFI_PLAYLIST_DIR", BASE_DIR / "Sounds")
LOGO_DIR = _env_path("LOFI_BRAND_DIR", BASE_DIR / "Logo")
VIDEO_DIR = _env_path("LOFI_VIDEO_DIR", BASE_DIR / "Videos")

STREAM_URL_FILE = _env_path("LOFI_STREAM_URL_FILE", BASE_DIR / "stream_url.txt")
STREAM_URL_ENV = os.environ.get("LOFI_YOUTUBE_URL", "")

FFMPEG_LOGO = _env_path("LOFI_BRAND_IMAGE", LOGO_DIR / "LoFiLogo700.png")
VIDEO_FILE = _env_path("LOFI_VIDEO_FILE", VIDEO_DIR / "Lofi3.mp4")

FALLBACK_COLOR = os.environ.get("LOFI_FALLBACK_COLOR", "black")
FALLBACK_FPS = _env_int("LOFI_FALLBACK_FPS", 30)

CHECK_HOST = os.environ.get("LOFI_CHECK_HOST", "a.rtmp.youtube.com")
CHECK_PORT = _env_int("LOFI_CHECK_PORT", 1935)

SKIP_NETWORK_CHECK = _env_bool("LOFI_SKIP_NETWORK_CHECK")

# ---------------- BOOT WAIT ----------------

def wait_for_pi_ready():
    print("⏳ Waiting for Pi to be fully ready...")

    while os.system("ping -c1 1.1.1.1 > /dev/null 2>&1") != 0:
        print("⏳ Waiting for network…")
        time.sleep(2)
    print("🌐 Internet OK")

    while True:
        try:
            socket.gethostbyname("google.com")
            print("🔍 DNS OK")
            break
        except:
            print("⏳ Waiting for DNS…")
            time.sleep(2)

    while True:

        yr = int(subprocess.check_output(["date","+%Y"]).decode().strip())
        if yr >= 2023:
            print("⏱ Time synced")
            break
        print("⏳ Waiting for NTP…")
        time.sleep(2)

    print("✅ Pi Ready!\n")

# ---------------- TRACK FILTER ----------------

def _is_valid_audio(t: Path) -> bool:
    lower = t.name.lower()
    if lower.startswith("._"): return False
    if lower.startswith("."): return False
    return t.suffix.lower() in [".mp3",".wav",".flac",".m4a"]

# ---------------- LOADERS ----------------

def load_stream_url():
    if STREAM_URL_ENV:
        print("🔐 Using RTMP URL from environment.")
        return STREAM_URL_ENV.strip()
    if STREAM_URL_FILE.exists():
        return STREAM_URL_FILE.read_text().strip()
    print("❌ No RTMP URL found!")
    return ""

def load_tracks():
    if not PLAYLIST_DIR.exists():
        print("❌ Sounds folder missing:", PLAYLIST_DIR)
        return []
    tracks = [t for t in PLAYLIST_DIR.iterdir() if _is_valid_audio(t)]
    print(f"🎶 Loaded {len(tracks)} tracks.")
    return tracks

def load_video_file():
    if VIDEO_FILE.exists():
        return VIDEO_FILE
    print(f"⚠️ Video file missing, fallback color feed will be used: {VIDEO_FILE}")
    return None

def _playlist_iterator(tracks):
    while True:
        cycle = list(tracks)
        random.shuffle(cycle)
        for t in cycle:
            yield t

# ---------------- NETWORK CHECK ----------------

def check_network():
    if SKIP_NETWORK_CHECK:
        return True
    try:
        with socket.create_connection((CHECK_HOST, CHECK_PORT), timeout=3):
            return True
    except:
        return False

# ---------------- VIDEO INPUT ----------------

def _video_input_args(vf):
    if vf and vf.exists():
        return ["-stream_loop","-1","-re","-i",str(vf)], "[0:v]"
    return [
@@ -252,63 +255,65 @@ def start_stream(track, stream_url, video_file, duration):

    cmd = [
        "ffmpeg","-hide_banner","-loglevel","error",
        *video_args, "-i", str(track)
    ]

    if FFMPEG_LOGO.exists():
        cmd += ["-loop","1","-i",str(FFMPEG_LOGO)]

    filter_chain = _build_filter_chain(video_ref, nowp)

    cmd += [
        "-filter_complex", filter_chain,
        "-map","[vout]","-map","[aout]",
        "-c:v","libx264","-preset","veryfast","-b:v","2500k",
        "-g","60","-keyint_min","60",
        "-sc_threshold","0","-pix_fmt","yuv420p",
        "-c:a","aac","-b:a","160k",
        "-shortest","-f","flv",stream_url
    ]

    return subprocess.Popen(cmd)

# ---------------- MAIN LOOP ----------------

def main() -> int:
    print("🌙 LOFI STREAMER v7.3 — Bottom-Hugging Text + Cinematic Bar\n")

    stream_url = load_stream_url()
    if not stream_url:
        print("❌ Missing RTMP URL!")
        return 1

    tracks = load_tracks()
    if not tracks:
        print("❌ No tracks found!")
        return 1

    video_file = load_video_file()

    wait_for_pi_ready()

    for t in _playlist_iterator(tracks):

        if not check_network():
            print("🌐 Offline, retrying in 5s…")
            time.sleep(5)
            continue

        dur = _track_duration(t)
        p = start_stream(t, stream_url, video_file, dur)

        try:
            p.wait(timeout=dur + TRACK_EXIT_BUFFER)
        except subprocess.TimeoutExpired:
            p.terminate()
            try: p.wait(timeout=5)
            except subprocess.TimeoutExpired:
                p.kill()

    return 0

if __name__ == "__main__":
    raise SystemExit(main())
