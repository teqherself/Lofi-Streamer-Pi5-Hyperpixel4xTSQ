#!/usr/bin/env python3
"""
---------------------------------------------------------
 LOFI STREAMER v8.1 — CONTINUOUS EDITION  (GENDEMIK DIGITAL)
---------------------------------------------------------

This streamer:

✓ Streams continuously without restarting FFmpeg per track  
✓ Randomises track order on each start  
✓ Displays a "Now Playing" text overlay  
✓ Shows an audio frequency bar visualisation  
✓ Supports a static looping video background  
✓ Supports a static overlay logo image in top-right position  
✓ Designed for Raspberry Pi continuous streaming  

---------------------------------------------------------
           CUSTOM LOGO INFORMATION FOR END-USERS
---------------------------------------------------------

Default logo used:
    /home/<USER>/LofiStream/Logo/picam.png

How to change logo:
1. Replace picam.png with your own PNG.
   For example: mybrand.png

2. Rename your file to:
       picam.png
   OR modify this line below:
       FFMPEG_LOGO = <path>

Recommended logo file format:
✓ PNG with transparency  
✓ Square or near-square aspect looks best  
✓ Avoid JPG (no transparency)

RECOMMENDED MAX SIZE:
→ 600px width or height (FFmpeg will scale internally if needed)

LOGO SAFETY RULE:
If the logo is extremely large (e.g. >2000px), FFmpeg may consume
excess memory. Resize to under 1000px on longest side before use.

----------------------------------------------------------------
"""

import os
import time
import random
import socket
import threading
import subprocess
from pathlib import Path
from typing import List


# -------------------------------------------------------
# VERSION
# -------------------------------------------------------
VERSION = "8.1-continuous"


# -------------------------------------------------------
# RESOLUTION + VISUAL CONSTANTS
# -------------------------------------------------------
OUTPUT_W = 1280
OUTPUT_H = 720

VU_SEG_WIDTH = 16
VU_HEIGHT = 120

LOGO_PADDING = 40
TEXT_PADDING = 40

DEFAULT_NOWPLAYING_FILE = Path("/tmp/nowplaying.txt")


# -------------------------------------------------------
# BASE DIRECTORY DISCOVERY
# -------------------------------------------------------
def _detect_base_dir() -> Path:
    base = Path(__file__).resolve().parent
    return base.parent if base.name.lower() == "servers" else base


BASE_DIR = _detect_base_dir()


# -------------------------------------------------------
# ENV HELPERS
# -------------------------------------------------------
def _env_path(name: str, default: Path) -> Path:
    raw = Path(os.environ.get(name, str(default))).expanduser()
    try:
        return raw.resolve(strict=False)
    except Exception:
        return raw


# -------------------------------------------------------
# FILE PATHS
# -------------------------------------------------------
PLAYLIST_DIR = _env_path("LOFI_PLAYLIST_DIR", BASE_DIR / "Sounds")
LOGO_DIR = _env_path("LOFI_BRAND_DIR", BASE_DIR / "Logo")
VIDEO_DIR = _env_path("LOFI_VIDEO_DIR", BASE_DIR / "Videos")

STREAM_URL_FILE = _env_path("LOFI_STREAM_URL_FILE", BASE_DIR / "stream_url.txt")
STREAM_URL_ENV = os.environ.get("LOFI_YOUTUBE_URL", "")

# >>> DEFAULT LOGO CHANGED HERE <<<
FFMPEG_LOGO = _env_path("LOFI_BRAND_IMAGE", LOGO_DIR / "picam.png") # >>> DEFAULT LOGO CHANGED HERE <<<

VIDEO_FILE = _env_path("LOFI_VIDEO_FILE", VIDEO_DIR / "Lofi3.mp4")
NOWPLAYING_FILE = _env_path("LOFI_NOWPLAYING_FILE", DEFAULT_NOWPLAYING_FILE)
CONCAT_PLAYLIST_FILE = _env_path("LOFI_CONCAT_FILE", BASE_DIR / "lofi_concat.txt")

CHECK_HOST = "a.rtmp.youtube.com"
CHECK_PORT = 1935


# -------------------------------------------------------
# RASPBERRY PI READINESS CHECK
# -------------------------------------------------------
def wait_for_pi_ready():
    print("⏳ Waiting for Pi to be fully ready...")

    for _ in range(60):
        if os.system("ping -c1 1.1.1.1 >/dev/null") == 0:
            print("🌐 Internet OK")
            break
        time.sleep(2)

    for _ in range(60):
        try:
            socket.gethostbyname("google.com")
            print("🔍 DNS OK")
            break
        except:
            time.sleep(2)

    for _ in range(120):
        try:
            yr = int(subprocess.check_output(["date", "+%Y"]).decode().strip())
        except:
            yr = 1970
        if yr >= 2023:
            print("⏱ Time synced")
            break
        time.sleep(2)

    print("✅ Pi Ready\n")


# -------------------------------------------------------
# TRACKS
# -------------------------------------------------------
def _is_valid_audio(t: Path):
    if t.name.startswith("."):
        return False
    return t.suffix.lower() in (".mp3", ".wav", ".flac", ".m4a")


def load_tracks():
    if not PLAYLIST_DIR.exists():
        print("❌ Playlist folder missing")
        return []
    tracks = [t for t in PLAYLIST_DIR.iterdir() if _is_valid_audio(t)]
    print(f"🎶 Loaded {len(tracks)} tracks")
    return tracks


# -------------------------------------------------------
# STREAM URL LOADING
# -------------------------------------------------------
def load_stream_url():
    if STREAM_URL_ENV:
        print("🔐 Using RTMP from env")
        return STREAM_URL_ENV.strip()

    if STREAM_URL_FILE.exists():
        url = STREAM_URL_FILE.read_text().strip()
        print(f"📄 RTMP URL = {url}")
        return url

    print("❌ No RTMP URL found")
    return ""


# -------------------------------------------------------
# NOW PLAYING TEXT
# -------------------------------------------------------
def _escape_drawtext(s: str):
    return s.replace(":", r"\:")


def write_nowplaying(track):
    try:
        NOWPLAYING_FILE.write_text(_escape_drawtext(track.stem))
    except:
        pass


# -------------------------------------------------------
# CONCAT FILE
# -------------------------------------------------------
def build_concat(tracks, out):
    random.shuffle(tracks)
    safe_lines = []
    for t in tracks:
        safe = str(t).replace("'", "'\\''")
        safe_lines.append(f"file '{safe}'")
    out.write_text("\n".join(safe_lines))
    print(f"📝 Playlist compiled: {out}")


# -------------------------------------------------------
# VISUAL FILTER CHAIN
# -------------------------------------------------------
def _filter_chain(has_logo):
    total_w = VU_SEG_WIDTH * 8
    bar_x = 45
    bar_y = OUTPUT_H - VU_HEIGHT - 25
    text_y = OUTPUT_H - 28 - 5

    np_path = NOWPLAYING_FILE.as_posix()

    base = f"[0:v]scale={OUTPUT_W}x{OUTPUT_H},format=yuv420p[v0]"

    if has_logo:
        base += f";[v0][2:v]overlay=W-w-{LOGO_PADDING}:{LOGO_PADDING}[vb]"
    else:
        base += "[vb]"

    return (
        f"{base};"
        f"[1:a]asplit=2[a0][avis];"
        f"[avis]showfreqs=s={total_w}x{VU_HEIGHT}[vf];"
        f"[vf]format=rgba,colorchannelmixer=rr=0.6:gg=0.6:bb=0.6:aa=1[vbar];"
        f"[vb][vbar]overlay={bar_x}:{bar_y}[v1];"
        f"[v1]drawtext=textfile='{np_path}':reload=1:"
        f"fontcolor=white:fontsize=28:shadowcolor=black:shadowx=2:shadowy=2:"
        f"x=w-tw-{TEXT_PADDING}:y={text_y}[vout]"
    )


# -------------------------------------------------------
# WATCHDOG
# -------------------------------------------------------
def watchdog_ffmpeg(cmd):
    print("🚀 FFmpeg starting…")
    proc = subprocess.Popen(cmd)

    while True:
        if proc.poll() is not None:
            print(f"⚠️ ffmpeg exited")
            return
        time.sleep(5)


# -------------------------------------------------------
# COMMAND BUILD
# -------------------------------------------------------
def build_ffmpeg_cmd(url, video_file, has_logo):

    video_in = (
        ["-stream_loop", "-1", "-i", str(video_file)]
        if video_file
        else ["-f", "lavfi", "-i", f"color=black:s={OUTPUT_W}x{OUTPUT_H}:r=25"]
    )

    filters = _filter_chain(has_logo)

    cmd = [
        "ffmpeg",
        "-nostdin",
        "-hide_banner",
        "-loglevel", "warning",

        *video_in,

        "-re",
        "-f", "concat",
        "-safe", "0",
        "-i", str(CONCAT_PLAYLIST_FILE),
    ]

    if has_logo:
        cmd += ["-loop", "1", "-i", str(FFMPEG_LOGO)]

    cmd += [
        "-filter_complex", filters,
        "-map", "[vout]",
        "-map", "[a0]",

        "-c:v", "libx264",
        "-preset", "veryfast",
        "-pix_fmt", "yuv420p",
        "-b:v", "2500k",
        "-g", "60",
        "-keyint_min", "60",
        "-sc_threshold", "0",

        "-c:a", "aac",
        "-b:a", "160k",

        "-f", "flv",
        url,
    ]

    return cmd


# -------------------------------------------------------
# MAIN LOOP
# -------------------------------------------------------
def main():
    print(f"\n🌙 LOFI STREAMER v{VERSION}\n")

    wait_for_pi_ready()
    url = load_stream_url()
    if not url:
        return

    tracks = load_tracks()
    if not tracks:
        return

    build_concat(tracks, CONCAT_PLAYLIST_FILE)
    write_nowplaying(tracks[0])

    video = VIDEO_FILE if VIDEO_FILE.exists() else None
    has_logo = FFMPEG_LOGO.exists()

    threading.Thread(
        target=lambda: [write_nowplaying(t) or time.sleep(180) for t in tracks],
        daemon=True
    ).start()

    while True:
        cmd = build_ffmpeg_cmd(url, video, has_logo)
        watchdog_ffmpeg(cmd)
        time.sleep(5)


if __name__ == "__main__":
    main()
