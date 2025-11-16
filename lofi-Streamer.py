#!/usr/bin/env python3
import os
import time
import random
import socket
import subprocess
from pathlib import Path
from typing import Iterator, List, Optional

# -------------------------------------------------------
#  LOFI STREAMER v4.1 — GENDEMIK DIGITAL
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
@@ -94,50 +94,61 @@ def _is_valid_audio(track: Path) -> bool:
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


def _playlist_iterator(tracks: List[Path]) -> Iterator[Path]:
    """Yield tracks forever, shuffling between each full pass."""
    while True:
        cycle = list(tracks)
        if len(cycle) > 1:
            random.shuffle(cycle)
            print(f"🔀 Shuffled playlist order for {len(cycle)} tracks.")
        for track in cycle:
            yield track

# -------------------------------------------------------

def check_network():
    if SKIP_NETWORK_CHECK:
        print("⚠️ Skipping network check.")
        return True
    print(f"🌐 Checking connection to {CHECK_HOST}:{CHECK_PORT}...")
    try:
        with socket.create_connection((CHECK_HOST, CHECK_PORT), timeout=3):
            print("✅ Network OK.")
            return True
    except:
        print("❌ RTMP host unreachable.")
        return False

# -------------------------------------------------------

def _video_input_args(video_file: Optional[Path]):
    if video_file and video_file.exists():
        return ["-stream_loop", "-1", "-re", "-i", str(video_file)], "[0:v]"
    fallback = f"color=c={FALLBACK_COLOR}:s={FALLBACK_SIZE}:r={FALLBACK_FPS}"
    return ["-f", "lavfi", "-re", "-i", fallback], "[0:v]"

# -------------------------------------------------------
#  LOGO OVERLAY TOP-RIGHT
@@ -272,38 +283,37 @@ def start_stream(track, stream_url, video_file, duration):
        "-pix_fmt", "yuv420p",
        "-shortest",
        "-f", "flv",
        stream_url,
    ]

    return subprocess.Popen(cmd)

# -------------------------------------------------------

def main():
    print("🌙 LOFI STREAMER v4.1 — GendEmik Digital (Keyframe Edition)\n")

    stream_url = load_stream_url()
    if not stream_url:
        print("❌ Missing RTMP URL.")
        return

    tracks = load_tracks()
    if not tracks:
        print("❌ No audio tracks found!")
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
