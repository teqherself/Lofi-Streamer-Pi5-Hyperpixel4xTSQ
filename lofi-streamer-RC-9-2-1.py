#!/usr/bin/env python3
"""
---------------------------------------------------------
 LOFI STREAMER v9.2.1 — HYPERPI CONTINUOUS (PATCHED)
 GENDEMIK DIGITAL — Clean, Safe, 24/7
---------------------------------------------------------
 * Background MP4 loop or black
 * Infinite concat audio playlist
 * Logo overlay (safe input index)
 * Live Now Playing text overlay
 * /tmp/current_track.txt for dashboard
 * Single FFmpeg pipeline
 * Robust restart logic
---------------------------------------------------------
"""

import signal
import random
import subprocess
import time
from pathlib import Path
from threading import Event, Thread
from typing import List

VERSION = "9.2.1-hyperpi-continuous-patched"

# -----------------------------------------------------
# SETTINGS / PATHS
# -----------------------------------------------------

SETTINGS = {
    "STREAM_URL": "",
    "LOGO": "picam.png",
    "VIDEO": "",
    "FONT_SIZE": "28",
    "FONT_COLOR": "white",
    "FONT_SHADOW": "2",
    "WIDTH": "1280",
    "HEIGHT": "720",
    "VIDEO_BITRATE": "2500k",
    "AUDIO_BITRATE": "160k",
    "LOGO_PADDING": "40",
    "TEXT_PADDING": "40",
    "FPS": "25",
    "GOP_SIZE": "60",
}

BASE = Path(__file__).resolve().parent.parent
CONFIG_FILE = BASE / "stream_config.txt"

TRACK_DIR = BASE / "Sounds"
VIDEO_DIR = BASE / "Videos"
LOGO_DIR = BASE / "Logo"
CONCAT_FILE = BASE / "lofi_concat.txt"

NOWPLAYING_FILE = Path("/tmp/nowplaying.txt")
CURRENT_TRACK_FILE = Path("/tmp/current_track.txt")

global_stop = False

# -----------------------------------------------------
# CONFIG
# -----------------------------------------------------
def load_config() -> None:
    if CONFIG_FILE.exists():
        for line in CONFIG_FILE.read_text().splitlines():
            if "=" not in line:
                continue
            key, val = line.split("=", 1)
            key = key.strip()
            val = val.strip()
            if key in SETTINGS:
                SETTINGS[key] = val

    for k in [
        "WIDTH",
        "HEIGHT",
        "FONT_SIZE",
        "FONT_SHADOW",
        "LOGO_PADDING",
        "TEXT_PADDING",
        "FPS",
        "GOP_SIZE",
    ]:
        SETTINGS[k] = int(SETTINGS[k])

    print("\n✨ CONFIG LOADED")
    for k, v in SETTINGS.items():
        if k == "STREAM_URL":
            print(f"   {k} = {v[:30]}...")
        else:
            print(f"   {k} = {v}")
    print("")

# -----------------------------------------------------
# TRACKS / METADATA
# -----------------------------------------------------
def load_tracks() -> List[Path]:
    TRACK_DIR.mkdir(parents=True, exist_ok=True)
    valid_exts = (".mp3", ".wav", ".flac", ".m4a")

    tracks = [
        t for t in TRACK_DIR.iterdir()
        if t.is_file()
        and t.suffix.lower() in valid_exts
        and t.stat().st_size > 1000
    ]

    random.shuffle(tracks)
    print(f"🎶 Loaded {len(tracks)} tracks")
    return tracks

def get_track_title(track: Path) -> str:
    try:
        import mutagen  # type: ignore
        m = mutagen.File(track, easy=True)
        if m:
            artist = m.get("artist", [""])[0]
            title = m.get("title", [""])[0]
            if artist and title:
                return f"{artist} - {title}"
            if title:
                return title
    except Exception:
        pass
    return track.stem

def write_nowplaying(track: Path) -> None:
    title = get_track_title(track)
    NOWPLAYING_FILE.write_text(title.replace(":", r"\:"), encoding="utf-8")
    CURRENT_TRACK_FILE.write_text(title, encoding="utf-8")
    print(f"🎧 Now playing: {title}")

def write_concat(tracks: List[Path]) -> None:
    with open(CONCAT_FILE, "w", encoding="utf-8") as f:
        for t in tracks:
            escaped = str(t).replace("'", "'\\''")
            f.write(f"file '{escaped}'\n")
    print(f"📝 Wrote concat playlist")

def get_track_durations(tracks: List[Path]) -> List[float]:
    durations = []
    for t in tracks:
        length = 0.0
        try:
            import mutagen  # type: ignore
            m = mutagen.File(t)
            if m and hasattr(m, "info") and getattr(m.info, "length", 0):
                length = float(m.info.length)
        except Exception:
            pass
        durations.append(length if length > 0 else 180.0)
    return durations

# -----------------------------------------------------
# FFMPEG COMMAND
# -----------------------------------------------------
def build_ffmpeg_cmd(tracks: List[Path]) -> list:
    w, h, fps = SETTINGS["WIDTH"], SETTINGS["HEIGHT"], SETTINGS["FPS"]
    video_path = VIDEO_DIR / SETTINGS["VIDEO"] if SETTINGS["VIDEO"] else None
    logo_path = LOGO_DIR / SETTINGS["LOGO"]

    cmd = ["ffmpeg", "-nostdin", "-y", "-loglevel", "info"]

    if video_path and video_path.exists():
        cmd += ["-stream_loop", "-1", "-i", str(video_path)]
        print(f"🎬 Using video background: {video_path.name}")
    else:
        cmd += ["-f", "lavfi", "-i", f"color=black:s={w}x{h}:r={fps}"]
        print("🎬 Using black background")

    cmd += [
        "-re",
        "-stream_loop", "-1",
        "-f", "concat",
        "-safe", "0",
        "-i", str(CONCAT_FILE),
    ]

    have_logo = logo_path.exists()
    if have_logo:
        cmd += ["-loop", "1", "-i", str(logo_path)]
        print(f"🖼 Using logo: {logo_path.name}")

    filter_chain = (
        f"[0:v]scale={w}:{h},format=yuv420p[base];"
        f"[base]drawtext=textfile='{NOWPLAYING_FILE}':reload=1:"
        f"font=Arial:fontsize={SETTINGS['FONT_SIZE']}:"
        f"x=W-tw-{SETTINGS['TEXT_PADDING']}:"
        f"y=H-{SETTINGS['FONT_SIZE']}-20:"
        f"fontcolor={SETTINGS['FONT_COLOR']}:"
        f"shadowcolor=black:shadowx={SETTINGS['FONT_SHADOW']}:"
        f"shadowy={SETTINGS['FONT_SHADOW']}[text]"
    )

    if have_logo:
        filter_chain += (
            f";[text][2:v]overlay="
            f"W-w-{SETTINGS['LOGO_PADDING']}:"
            f"{SETTINGS['LOGO_PADDING']}[vout]"
        )
    else:
        filter_chain += ";[text]copy[vout]"

    cmd += [
        "-filter_complex", filter_chain,
        "-map", "[vout]",
        "-map", "1:a",
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-profile:v", "baseline",
        "-pix_fmt", "yuv420p",
        "-g", str(SETTINGS["GOP_SIZE"]),
        "-keyint_min", str(SETTINGS["GOP_SIZE"]),
        "-b:v", SETTINGS["VIDEO_BITRATE"],
        "-c:a", "aac",
        "-b:a", SETTINGS["AUDIO_BITRATE"],
        "-ar", "44100",
        "-f", "flv",
        SETTINGS["STREAM_URL"],
    ]
    return cmd

# -----------------------------------------------------
# METADATA THREAD
# -----------------------------------------------------
def metadata_worker(tracks, durations, stop_event):
    time.sleep(2)
    idx = 0
    while not stop_event.is_set():
        write_nowplaying(tracks[idx])
        sleep_for = max(5.0, durations[idx] * 0.98)
        elapsed = 0.0
        while elapsed < sleep_for and not stop_event.is_set():
            time.sleep(1)
            elapsed += 1
        idx = (idx + 1) % len(tracks)

# -----------------------------------------------------
# RUN SESSION
# -----------------------------------------------------
def run_session(tracks: List[Path]) -> None:
    write_concat(tracks)
    durations = get_track_durations(tracks)

    # 🔒 CRITICAL FIX — create files BEFORE ffmpeg
    NOWPLAYING_FILE.write_text("Starting stream…", encoding="utf-8")
    CURRENT_TRACK_FILE.write_text("Starting stream…", encoding="utf-8")

    stop_event = Event()
    md_thread = Thread(
        target=metadata_worker,
        args=(tracks, durations, stop_event),
        daemon=True,
    )
    md_thread.start()

    cmd = build_ffmpeg_cmd(tracks)
    print("▶️ Launching FFmpeg...")
    proc = subprocess.Popen(cmd)

    try:
        while proc.poll() is None and not global_stop:
            time.sleep(1)
    finally:
        stop_event.set()
        md_thread.join(timeout=5)
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
        print(f"❌ FFmpeg exited with code {proc.returncode}")

# -----------------------------------------------------
# MAIN LOOP
# -----------------------------------------------------
def run_loop() -> None:
    while not global_stop:
        tracks = load_tracks()
        if not tracks:
            time.sleep(15)
            continue
        run_session(tracks)
        if not global_stop:
            print("🔄 Restarting stream in 12s…")
            time.sleep(12)

def handle_signal(sig, frame) -> None:
    global global_stop
    global_stop = True
    print("\n👋 Shutdown requested…")

def main() -> None:
    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    print(f"\n🌙 LOFI STREAMER {VERSION}\n")
    load_config()

    if not SETTINGS["STREAM_URL"]:
        print("❌ STREAM_URL missing in config")
        return

    run_loop()

if __name__ == "__main__":
    main()
