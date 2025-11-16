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
diff --git a/lofi-Streamer.py b/lofi-Streamer.py
index 5f271d3ae48825bb19082992fd78def9b4cd95ae..f3c5eb12b4cd0fcf036288e4d73d16f41bdc3418 100644
--- a/lofi-Streamer.py
+++ b/lofi-Streamer.py
@@ -2,62 +2,75 @@
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
 
+
+def env_path(var_name, default):
+    """Return an expanded path from an environment override if present."""
+    value = os.environ.get(var_name)
+    if value:
+        return os.path.expanduser(value)
+    return default
+
+
+def env_value(var_name, default):
+    """Return an environment override value (non-path)."""
+    return os.environ.get(var_name, default)
+
 # === USER CONFIG ===
-PLAYLIST_DIR   = "/home/woo/LofiStream/Sounds"
-VIDEO_FILE     = "/home/woo/LofiStream/Videos/Lofi3.mp4"
-BRAND_IMAGE    = "/home/woo/LofiStream/Logo/LoFiLogo700.png"
-YOUTUBE_URL    = "rtmp://a.rtmp.youtube.com/live2/1824-q94y-xac0-zjru-7z04"
+PLAYLIST_DIR   = env_path("LOFI_PLAYLIST_DIR", "/home/woo/LofiStream/Sounds")
+VIDEO_FILE     = env_path("LOFI_VIDEO_FILE", "/home/woo/LofiStream/Videos/Lofi3.mp4")
+BRAND_IMAGE    = env_path("LOFI_BRAND_IMAGE", "/home/woo/LofiStream/Logo/LoFiLogo700.png")
+YOUTUBE_URL    = env_value("LOFI_YOUTUBE_URL", "rtmp://a.rtmp.youtube.com/live2/1824-q94y-xac0-zjru-7z04")
 
-TRACK_FILE     = "/tmp/current_track.txt"
-PLAYLIST_FILE  = "/tmp/lofi_playlist.txt"
-FONT_PATH      = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
+TRACK_FILE     = env_path("LOFI_TRACK_FILE", "/tmp/current_track.txt")
+PLAYLIST_FILE  = env_path("LOFI_PLAYLIST_FILE", "/tmp/lofi_playlist.txt")
+FONT_PATH      = env_path("LOFI_FONT_PATH", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")
 
-CHECK_HOST     = "a.rtmp.youtube.com"
-CHECK_PORT     = 1935
+CHECK_HOST     = env_value("LOFI_CHECK_HOST", "a.rtmp.youtube.com")
+CHECK_PORT     = int(env_value("LOFI_CHECK_PORT", "1935"))
 
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
