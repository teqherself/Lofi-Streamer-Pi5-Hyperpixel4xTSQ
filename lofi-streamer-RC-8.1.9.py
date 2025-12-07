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


def build_ffmpeg_cmd(tracks):
    width = SETTINGS["WIDTH"]
    height = SETTINGS["HEIGHT"]

    logo_path = LOGO_DIR / SETTINGS["LOGO"]
    video_path = VIDEO_DIR / SETTINGS["VIDEO"]

    # ----------------------------
    # INPUT SETUP IN SAFE ORDER
    # ----------------------------
    cmd = [
        "ffmpeg",
        "-nostdin",
        "-hide_banner",
        "-loglevel", "warning",
    ]

    # #1 VIDEO INPUT
    if video_path.exists():
        cmd += ["-stream_loop", "-1", "-i", str(video_path)]
        video_label = "0:v"
    else:
        cmd += ["-f", "lavfi", "-i", f"color=black:s={width}x{height}:r=25"]
        video_label = "0:v"

    # #2 AUDIO INPUT
    cmd += [
        "-re",
        "-f", "concat",
        "-safe", "0",
        "-i", str(CONCAT_FILE),
    ]

    # #3 LOGO INPUT (optional)
    have_logo = logo_path.exists()
    if have_logo:
        cmd += ["-loop", "1", "-i", str(logo_path)]

    # ----------------------------
    # FILTERS (LOGIC CHANGES BELOW)
    # ----------------------------
    if have_logo:
        # logo is on index 2:v
        logo_chain = (
            f"[base][2:v]overlay=W-w-{SETTINGS['LOGO_PADDING']}:{SETTINGS['LOGO_PADDING']}[vlogo]"
        )
    else:
        logo_chain = "[base]copy[vlogo]"

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

    # NOW MAP STREAMS — AFTER inputs declared
    cmd += [
        "-filter_complex", filter_chain,

        # output selection
        "-map", "[vout]",
        "-map", "[a0]",

        # encoding
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-pix_fmt", "yuv420p",
        "-b:v", SETTINGS["VIDEO_BITRATE"],
        "-g", "60",
        "-keyint_min", "60",
        "-sc_threshold", "0",

        "-c:a", "aac",
        "-b:a", SETTINGS["AUDIO_BITRATE"],

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
