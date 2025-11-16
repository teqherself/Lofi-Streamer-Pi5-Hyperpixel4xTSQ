#!/usr/bin/env python3
import os
import time
import random
import subprocess
from pathlib import Path

# -------------------------------------------------------
#  LOFI STREAMER v3.0 — GENDEMIK DIGITAL
#  Self-contained file: NO absolute /home/woo/ paths
# -------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent.parent  # ~/LofiStream
PLAYLIST_DIR = BASE_DIR / "Sounds"
LOGO_DIR = BASE_DIR / "Logo"
VIDEO_DIR = BASE_DIR / "Videos"
STREAM_URL_FILE = BASE_DIR / "stream_url.txt"

FFMPEG_LOGO = LOGO_DIR / "LoFiLogo700.png"

# -------------------------------------------------------

def load_stream_url():
    if STREAM_URL_FILE.exists():
        return STREAM_URL_FILE.read_text().strip()
    print("❌ No stream_url.txt found!")
    return ""

def load_tracks():
    if not PLAYLIST_DIR.exists():
        print("❌ Sounds folder missing:", PLAYLIST_DIR)
        return []
    tracks = [t for t in PLAYLIST_DIR.iterdir() if t.suffix.lower() in [".mp3", ".wav"]]
    print(f"🎶 Loaded {len(tracks)} tracks from playlist directory.")
    return tracks

def check_network():
    print("🌐 Checking network connectivity to RTMP host...")
    result = subprocess.run(["ping", "-c", "1", "8.8.8.8"], stdout=subprocess.DEVNULL)
    if result.returncode == 0:
        print("✅ Network online — starting / continuing stream.")
        return True
    print("❌ Network offline — waiting...")
    return False

def start_stream(track, stream_url):
    print(f"🎧 Now playing: {track.name}")

    # Build FFmpeg command
    cmd = [
        "ffmpeg",
        "-re",
        "-i", str(track),
        "-loop", "1",
        "-i", str(FFMPEG_LOGO),
        "-filter_complex",
        "scale=1280:720,format=yuv420p",
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-b:v", "2500k",
        "-c:a", "aac",
        "-b:a", "160k",
        "-f", "flv",
        stream_url
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

    while True:
        if not check_network():
            time.sleep(5)
            continue

        track = random.choice(tracks)
        process = start_stream(track, stream_url)

        # Wait for track to finish (approx)
        track_length = 180  # default fallback if unknown
        try:
            import mutagen
            audio = mutagen.File(track)
            if audio and audio.info:
                track_length = int(audio.info.length)
        except:
            pass  # ignore if mutagen not installed

        time.sleep(track_length)

        # Kill FFmpeg (if still running)
        if process.poll() is None:
            process.terminate()

# -------------------------------------------------------

if __name__ == "__main__":
    main()
