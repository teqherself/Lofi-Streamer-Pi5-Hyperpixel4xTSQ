#!/usr/bin/env python3
"""
---------------------------------------------------------
 LOFI STREAMER v8.2.4 — MASTER CONFIG + WATCHDOG EDITION
 GENDEMIK DIGITAL — Susan Build
---------------------------------------------------------
"""

import os
import time
import random
import subprocess
from pathlib import Path
from typing import List

VERSION = "8.2.4-master-config-watchdog"

SETTINGS = {
    "STREAM_URL": "",
    "LOGO": "picam.png",
    "VIDEO": "",
    "FONT_SIZE": "36",
    "FONT_COLOR": "white",
    "FONT_SHADOW": "2",
    "WIDTH": "1280",
    "HEIGHT": "720",
    "VIDEO_BITRATE": "2500k",
    "AUDIO_BITRATE": "160k",
    "LOGO_PADDING": "40",
    "TEXT_PADDING": "40",
}

BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_FILE = BASE_DIR / "stream_config.txt"
PLAYLIST_DIR = BASE_DIR / "Sounds"
LOGO_DIR = BASE_DIR / "Logo"
VIDEO_DIR = BASE_DIR / "Videos"
CONCAT_FILE = BASE_DIR / "lofi_concat.txt"
NOWPLAYING_FILE = Path("/tmp/nowplaying.txt")
WATCHDOG_FILE = Path("/tmp/stream_watchdog.txt")


def load_config():
    if not CONFIG_FILE.exists():
        print("❌ Missing config — using defaults")
        return

    for line in CONFIG_FILE.read_text().splitlines():
        if "=" not in line or line.startswith("#"):
            continue
        key, val = line.split("=", 1)
        key, val = key.strip(), val.strip()
        if key in SETTINGS:
            SETTINGS[key] = val

    print("\n✨ CONFIG LOADED:")
    for k, v in SETTINGS.items():
        print("   ", k, "=", v)
    print("")


def load_tracks():
    valid_exts = (".mp3", ".wav", ".flac", ".m4a")
    tracks = [t for t in PLAYLIST_DIR.iterdir() if t.suffix.lower() in valid_exts]

    tracks = [t for t in tracks if t.stat().st_size > 1000]  # filter corrupt audio

    random.shuffle(tracks)
    print(f"🎶 Valid tracks: {len(tracks)}")

    return tracks


def write_nowplaying(track: Path):
    txt = track.stem.replace(":", r"\:")
    NOWPLAYING_FILE.write_text(txt)
    WATCHDOG_FILE.write_text(str(time.time()))


def build_concat(tracks):
    with open(CONCAT_FILE, "w") as f:
        for t in tracks:
            f.write(f"file '{t}'\n")


def build_ffmpeg_cmd(tracks):
    width = SETTINGS["WIDTH"]
    height = SETTINGS["HEIGHT"]
    logo_path = LOGO_DIR / SETTINGS["LOGO"]
    video_path = VIDEO_DIR / SETTINGS["VIDEO"]

    # -------- VIDEO INPUT --------
    if video_path.exists():
        video_input = ["-stream_loop", "-1", "-i", str(video_path)]
        video_label = "0:v"
    else:
        video_input = ["-f", "lavfi", "-i", f"color=black:s={width}x{height}:r=25"]
        video_label = "0:v"

    cmd = [
        "ffmpeg",
        "-nostdin",
        "-hide_banner",
        "-loglevel", "warning",
        *video_input,
        "-thread_queue_size", "1024",
        "-re",
        "-f", "concat",
        "-safe", "0",
        "-i", str(CONCAT_FILE),
    ]

    # ---------------------------------------------------------
    # Build filter chain SAFELY depending on whether logo exists
    # ---------------------------------------------------------

    have_logo = logo_path.exists()
    if have_logo:
        cmd += ["-loop", "1", "-i", str(logo_path)]

        logo_chain = f"[base][2:v]overlay=W-w-{SETTINGS['LOGO_PADDING']}:{SETTINGS['LOGO_PADDING']}[vlogo]"
        map_video = "[vout]"
    else:
        logo_chain = "[base]copy[vlogo]"
        map_video = "[vout]"

    filter_chain = f"""
        [{video_label}]scale={width}:{height},format=yuv420p[base];
        [1:a]asplit=2[a0][s];
        {logo_chain};
        [s]showfreqs=s={int(width)//5}x120[bar];
        [vlogo][bar]overlay=45:{int(height)-140}[v2];
        [v2]drawtext=textfile='{NOWPLAYING_FILE}':reload=1:
            font=Arial:fontsize={SETTINGS['FONT_SIZE']}:
            x=w-tw-{SETTINGS['TEXT_PADDING']}:
            y={int(height)-int(SETTINGS['FONT_SIZE'])-20}:
            fontcolor={SETTINGS['FONT_COLOR']}:
            shadowcolor=black:shadowx={SETTINGS['FONT_SHADOW']}:
            shadowy={SETTINGS['FONT_SHADOW']}[vout]
    """.replace("\n", " ")

    cmd += [
        "-filter_complex", filter_chain,
        "-map", map_video,
        "-map", "[a0]",
        "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p",
        "-b:v", SETTINGS["VIDEO_BITRATE"],
        "-g", "60", "-keyint_min", "60", "-sc_threshold", "0",
        "-c:a", "aac", "-b:a", SETTINGS["AUDIO_BITRATE"],
        "-f", "flv",
        SETTINGS["STREAM_URL"],
    ]

    return cmd


def stall_watchdog():
    """
    If audio isn’t progressing, nowplaying never updates.
    If timestamp > 120 seconds old → reset stream.
    """
    try:
        ts = float(WATCHDOG_FILE.read_text().strip())
        return time.time() - ts < 120
    except:
        return False


def run_loop():
    while True:
        tracks = load_tracks()
        if not tracks:
            print("❌ NO TRACKS FOUND — sleeping")
            time.sleep(10)
            continue

        build_concat(tracks)
        write_nowplaying(tracks[0])

        cmd = build_ffmpeg_cmd(tracks)
        print("▶ Starting ffmpeg…\n")

        proc = subprocess.Popen(cmd)

        while proc.poll() is None:
            time.sleep(5)

            if not stall_watchdog():
                print("⚠️ AUDIO STALL DETECTED — restarting cleanly")
                proc.kill()
                break

        print("🔄 Restarting pipeline\n")
        time.sleep(3)


def main():
    print(f"\n🌙 LOFI STREAMER v{VERSION}")
    load_config()

    if not SETTINGS["STREAM_URL"]:
        print("❌ STREAM_URL missing — aborting.")
        return

    run_loop()


if __name__ == "__main__":
    main()
