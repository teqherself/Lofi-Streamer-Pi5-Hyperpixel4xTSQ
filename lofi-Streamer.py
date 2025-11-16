#!/usr/bin/env python3
import os
import time
import random
import socket
import subprocess
from pathlib import Path
from typing import Optional

# -------------------------------------------------------
#  LOFI STREAMER v3.0 — GENDEMIK DIGITAL
#  Self-contained file: NO absolute /home/woo/ paths
# -------------------------------------------------------

def _detect_base_dir() -> Path:
    """Return the root project directory regardless of install layout."""

    base = Path(__file__).resolve().parent
    # When the file lives in LofiStream/Servers/ we need to pop one level up.
    if base.name.lower() == "servers":
        return base.parent
    return base


BASE_DIR = _detect_base_dir()


def _env_path(name: str, default: Path) -> Path:
    """Read a path from the environment while keeping defaults as Path objects."""

    raw_path = Path(os.environ.get(name, str(default))).expanduser()
    try:
        return raw_path.resolve(strict=False)
    except FileNotFoundError:
        return raw_path


PLAYLIST_DIR = _env_path("LOFI_PLAYLIST_DIR", BASE_DIR / "Sounds")
LOGO_DIR = _env_path("LOFI_BRAND_DIR", BASE_DIR / "Logo")
VIDEO_DIR = _env_path("LOFI_VIDEO_DIR", BASE_DIR / "Videos")
STREAM_URL_FILE = _env_path("LOFI_STREAM_URL_FILE", BASE_DIR / "stream_url.txt")

FFMPEG_LOGO = _env_path("LOFI_BRAND_IMAGE", LOGO_DIR / "LoFiLogo700.png")
VIDEO_FILE = _env_path("LOFI_VIDEO_FILE", VIDEO_DIR / "Lofi3.mp4")
STREAM_URL_ENV = os.environ.get("LOFI_YOUTUBE_URL", "")
CHECK_HOST = os.environ.get("LOFI_CHECK_HOST", "a.rtmp.youtube.com")
CHECK_PORT = int(os.environ.get("LOFI_CHECK_PORT", "1935"))

# -------------------------------------------------------

def load_stream_url():
    if STREAM_URL_ENV:
        print("🔐 Using stream URL from LOFI_YOUTUBE_URL environment variable.")
        return STREAM_URL_ENV.strip()

    if STREAM_URL_FILE.exists():
        return STREAM_URL_FILE.read_text().strip()

    print("❌ No stream URL configured! Set LOFI_YOUTUBE_URL or create stream_url.txt.")
    return ""

def load_tracks():
    if not PLAYLIST_DIR.exists():
        print("❌ Sounds folder missing:", PLAYLIST_DIR)
        return []

    tracks = [
        t
        for t in PLAYLIST_DIR.iterdir()
        if t.suffix.lower() in [".mp3", ".wav", ".m4a", ".flac"]
    ]

    print(f"🎶 Loaded {len(tracks)} tracks from playlist directory {PLAYLIST_DIR}.")
    return tracks


def load_video_file():
    if VIDEO_FILE.exists():
        return VIDEO_FILE

    print("⚠️ Video file not found at", VIDEO_FILE)
    return None

def check_network():
    print(f"🌐 Checking network connectivity to {CHECK_HOST}:{CHECK_PORT}...")
    try:
        with socket.create_connection((CHECK_HOST, CHECK_PORT), timeout=3):
            print("✅ Network online — starting / continuing stream.")
            return True
    except OSError:
        pass

    print("❌ Network offline or RTMP host unreachable — waiting...")
    return False

def _video_input_args(video_file: Optional[Path]):
    if video_file and video_file.exists():
        return ["-stream_loop", "-1", "-re", "-i", str(video_file)], "[0:v]"

    # Fall back to a generated black background if no video file is available.
    return ["-f", "lavfi", "-re", "-i", "color=c=black:s=1280x720:r=30"], "[0:v]"


def start_stream(track, stream_url, video_file):
    print(f"🎧 Now playing: {track.name}")

    video_args, video_ref = _video_input_args(video_file)
    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        *video_args,
        "-i",
        str(track),
    ]

    filter_chain = f"{video_ref}scale=1280:720,format=yuv420p[v0]"
    map_args = ["-map", "[v0]", "-map", "1:a"]

    if FFMPEG_LOGO.exists():
        cmd += ["-loop", "1", "-i", str(FFMPEG_LOGO)]
        filter_chain = f"{video_ref}scale=1280:720,format=yuv420p[v0];[v0][2:v]overlay=W-w-40:H-h-40[vout]"
        map_args = ["-map", "[vout]", "-map", "1:a"]
    else:
        print("⚠️ Logo image not found, streaming without overlay.")

    cmd += [
        "-filter_complex",
        filter_chain,
        *map_args,
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-b:v",
        "2500k",
        "-c:a",
        "aac",
        "-b:a",
        "160k",
        "-pix_fmt",
        "yuv420p",
        "-f",
        "flv",
        stream_url,
    ]

    return subprocess.Popen(cmd)

# -------------------------------------------------------

def main():
    print("🌙 LOFI STREAMER v3.0 — GENDEMIK DIGITAL\n")

    stream_url = load_stream_url()
    if stream_url == "":
        print("❌ Missing RTMP stream URL. Add it to stream_url.txt!")
        return

    tracks = load_tracks()
    if not tracks:
        print("❌ No audio tracks found! Add MP3s to the Sounds/ folder.")
        return

    video_file = load_video_file()

    while True:
        if not check_network():
            time.sleep(5)
            continue

        track = random.choice(tracks)
        process = start_stream(track, stream_url, video_file)

        # Wait for track to finish (approx)
        track_length = 180  # default fallback if unknown
        try:
            import mutagen
            audio = mutagen.File(track)
            if audio and audio.info:
                track_length = int(audio.info.length)
        except Exception:
            pass  # ignore if mutagen not installed

        time.sleep(track_length)

        # Kill FFmpeg (if still running)
        if process.poll() is None:
            process.terminate()

# -------------------------------------------------------

if __name__ == "__main__":
    main()
