#!/usr/bin/env python3
# ============================================================================
# 🌙 LOFI YOUTUBE STREAMER v3.1 — Pi Stable Edition
# ----------------------------------------------------------------------------
# Author:  Ms Stevie Woo (GENDEMIK DIGITAL)
# Year:    2025
#
# PURPOSE:
#   Streams a looping *silent* background MP4 video to YouTube RTMP while
#   playing shuffled lofi background audio. Logo & text overlays included.
#
# NOTES:
#   • Positions of logo & track text overlay EXACTLY as provided
#   • Audio comes ONLY from playlist, not the video
#   • Filters out macOS “._” ghost files that break ffmpeg
#   • Clean, stable, restart-safe streaming engine
# ============================================================================

import os
import random
import time
import socket
import subprocess
from mutagen.easyid3 import EasyID3
from mutagen import File as MutagenFile

# === USER CONFIG ===
PLAYLIST_DIR   = "/home/woo/LofiStream/Sounds"
VIDEO_FILE     = "/home/woo/LofiStream/Videos/Lofi3.mp4"
BRAND_IMAGE    = "/home/woo/LofiStream/Logo/LoFiLogo700.png"
YOUTUBE_URL    = "rtmp://a.rtmp.youtube.com/live2/1824-q94y-xac0-zjru-7z04"

TRACK_FILE     = "/tmp/current_track.txt"
PLAYLIST_FILE  = "/tmp/lofi_playlist.txt"
FONT_PATH      = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

CHECK_HOST     = "a.rtmp.youtube.com"
CHECK_PORT     = 1935

# ============================================================================
# NETWORK WATCHDOG
# ============================================================================

def wait_for_network():
    print("🌐 Checking network connectivity to RTMP host...")
    while True:
        try:
            socket.create_connection((CHECK_HOST, CHECK_PORT), timeout=5)
            print("✅ Network online — starting / continuing stream.")
            return
        except OSError:
            print("⚠️ RTMP host unreachable — retrying in 5 seconds...")
            time.sleep(5)

# ============================================================================
# FILE HELPERS
# ============================================================================

def require_file(path, description):
    if not os.path.isfile(path):
        raise FileNotFoundError(f"{description} not found: {path}")

def get_audio_tracks(directory):
    """Load all playlist files, ignoring macOS resource forks."""
    exts = (".mp3", ".m4a", ".aac", ".wav", ".ogg")
    tracks = []
    for root, _, files in os.walk(directory):
        for f in files:
            if f.startswith("._"):
                continue  # Skip MacOS junk files
            if f.lower().endswith(exts):
                tracks.append(os.path.join(root, f))
    return tracks

def get_track_name(path):
    """Return clean Artist – Title overlay text."""
    try:
        audio = EasyID3(path)
        artist = audio.get("artist", ["Unknown Artist"])[0]
        title  = audio.get("title", [os.path.basename(path)])[0]
        return f"{artist} – {title}"
    except Exception:
        return os.path.basename(path)

def write_track_name(track_path):
    """Write current track name to the text file used by ffmpeg drawtext."""
    name = get_track_name(track_path)
    with open(TRACK_FILE, "w", encoding="utf-8") as f:
        f.write(name)

def create_concat_file(tracks):
    """Create ffmpeg concat list for audio playlist."""
    with open(PLAYLIST_FILE, "w", encoding="utf-8") as f:
        for t in tracks:
            f.write(f"file '{t}'\n")
    return PLAYLIST_FILE

def get_track_duration(path):
    """Read track length via mutagen, fall back to 180s."""
    try:
        audio = MutagenFile(path)
        if audio and audio.info and hasattr(audio.info, "length"):
            return float(audio.info.length)
    except:
        pass
    return 180.0

# ============================================================================
# STREAM ENGINE
# ============================================================================

def stream_forever():
    print("🌙 LOFI STREAMER v3.1 — GENDEMIK DIGITAL")

    # Validate essential files once
    try:
        require_file(VIDEO_FILE, "Background video")
        require_file(BRAND_IMAGE, "Overlay logo")
        require_file(FONT_PATH, "Font file")
    except FileNotFoundError as e:
        print(f"❌ Startup error: {e}")
        return

    while True:
        wait_for_network()

        tracks = get_audio_tracks(PLAYLIST_DIR)
        if not tracks:
            print("⚠️ No audio tracks found — retrying in 10 seconds...")
            time.sleep(10)
            continue

        random.shuffle(tracks)
        create_concat_file(tracks)
        write_track_name(tracks[0])

        print(f"🎶 Loaded {len(tracks)} tracks.")

        # --- FILTER COMPLEX (positions unchanged) ---
        filter_complex = (
            f"[0:v][1:v]overlay=(W-w)/2+200:(H-h)/2-280:format=auto[vtmp];"
            f"[vtmp]drawtext=fontfile={FONT_PATH}:"
            f"textfile={TRACK_FILE}:reload=1:"
            f"fontcolor=white:fontsize=16:"
            f"x=w-tw-(w*0.10):y=h-th-20:"
            f"box=1:boxcolor=black@0.4:boxborderw=5:"
            f"alpha='if(lt(t,3),t/3,1)'[vout]"
        )

        # --- FFMPEG COMMAND ---
        ffmpeg_cmd = [
            "ffmpeg",
            "-re",

            "-stream_loop", "-1", "-i", VIDEO_FILE,    # silent looping video
            "-loop", "1", "-i", BRAND_IMAGE,           # PNG logo
            "-f", "concat", "-safe", "0", "-i", PLAYLIST_FILE,  # playlist audio

            # Updated YouTube keyframe interval
            "-g", "60",
            "-keyint_min", "60",
            "-sc_threshold", "0",
            "-force_key_frames", "expr:gte(t,n_forced*2)",

            "-filter_complex", filter_complex,
            "-map", "[vout]",
            "-map", "2:a",

            # Video
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-b:v", "2500k",
            "-pix_fmt", "yuv420p",

            # Audio
            "-c:a", "aac",
            "-b:a", "192k",

            "-f", "flv", YOUTUBE_URL
        ]

        print("📡 Starting YouTube stream…")
        ffmpeg_proc = subprocess.Popen(ffmpeg_cmd)

        try:
            # Loop through playlist while ffmpeg runs
            for track in tracks:
                write_track_name(track)
                duration = get_track_duration(track)
                print(f"🎧 Now playing: {get_track_name(track)} ({int(duration)}s)")
                elapsed = 0
                step = 5

                while elapsed < duration:
                    time.sleep(step)
                    elapsed += step

                    if ffmpeg_proc.poll() is not None:
                        raise RuntimeError("ffmpeg exited unexpectedly")

            print("🔁 Playlist finished — reshuffling and restarting…")
            ffmpeg_proc.terminate()
            try:
                ffmpeg_proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                ffmpeg_proc.kill()

        except KeyboardInterrupt:
            print("🛑 Stream manually stopped.")
            ffmpeg_proc.terminate()
            return

        except Exception as e:
            print(f"⚠️ Stream error: {e}")
            ffmpeg_proc.terminate()
            try:
                ffmpeg_proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                ffmpeg_proc.kill()
            print("🔄 Retrying in 10 seconds…")
            time.sleep(10)

# ============================================================================
if __name__ == "__main__":
    stream_forever()

