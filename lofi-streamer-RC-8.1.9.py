#!/usr/bin/env python3
"""
---------------------------------------------------------
 LOFI STREAMER v8.1.9 — MASTER CONFIG EDITION
 GENDEMIK DIGITAL — Susan Build
---------------------------------------------------------

 Single Config File Controls Everything:
 ------------------------------------------------
 ~/LofiStream/stream_config.txt

 Accepted keys:
 STREAM_URL=
 FONT_SIZE=
 FONT_COLOR=
 FONT_SHADOW=
 LOGO=
 VIDEO=
 WIDTH=
 HEIGHT=
 VIDEO_BITRATE=
 AUDIO_BITRATE=
 LOGO_PADDING=
 TEXT_PADDING=

 Fallback defaults exist if file missing.
---------------------------------------------------------
"""

import os
import time
import random
import socket
import subprocess
from pathlib import Path
from typing import List

VERSION = "8.1.9-master-config"

# Default safe baseline
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


def detect_base():
    base = Path(__file__).resolve().parent
    if base.name.lower() == "servers":
        return base.parent
    return base


BASE_DIR = detect_base()
CONFIG_FILE = BASE_DIR / "stream_config.txt"

PLAYLIST_DIR = BASE_DIR / "Sounds"
LOGO_DIR = BASE_DIR / "Logo"
VIDEO_DIR = BASE_DIR / "Videos"
CONCAT_FILE = BASE_DIR / "lofi_concat.txt"
NOWPLAYING_FILE = Path("/tmp/nowplaying.txt")


def load_config():
    print("⚙️ Loading config...")

    if not CONFIG_FILE.exists():
        print("❌ No config found — using fallback defaults")
        return

    for line in CONFIG_FILE.read_text().splitlines():
        if "=" not in line or line.startswith("#"):
            continue

        key, val = line.split("=", 1)
        key = key.strip().upper()
        val = val.strip()

        if key in SETTINGS:
            SETTINGS[key] = val

    print("✨ Config applied:")
    for k, v in SETTINGS.items():
        print(f"   {k} = {v}")
    print("")


def wait_for_pi_ready():
    print("⏳ Checking system readiness...")

    for _ in range(30):
        if os.system("ping -c1 1.1.1.1 >/dev/null 2>&1") == 0:
            break
        time.sleep(2)

    print("💚 Pi Ready\n")


def load_tracks():
    valid = (".mp3", ".wav", ".flac", ".m4a")
    tracks = [t for t in PLAYLIST_DIR.iterdir() if t.suffix.lower() in valid]
    random.shuffle(tracks)
    print(f"🎶 Loaded {len(tracks)} tracks")
    return tracks


def write_nowplaying(track: Path):
    NOWPLAYING_FILE.write_text(track.stem.replace(":", r"\:"))


def build_concat(tracks):
    with open(CONCAT_FILE, "w") as f:
        for t in tracks:
            f.write(f"file '{t.as_posix()}'\n")


def build_ffmpeg_cmd():
    width = SETTINGS["WIDTH"]
    height = SETTINGS["HEIGHT"]

    video_bitrate = SETTINGS["VIDEO_BITRATE"]
    audio_bitrate = SETTINGS["AUDIO_BITRATE"]

    logo_padding = SETTINGS["LOGO_PADDING"]
    text_padding = SETTINGS["TEXT_PADDING"]

    font_size = SETTINGS["FONT_SIZE"]
    font_color = SETTINGS["FONT_COLOR"]
    font_shadow = SETTINGS["FONT_SHADOW"]

    logo_path = LOGO_DIR / SETTINGS["LOGO"]
    video_path = VIDEO_DIR / SETTINGS["VIDEO"] if SETTINGS["VIDEO"] else None

    vid_in = (
        ["-stream_loop", "-1", "-i", str(video_path)]
        if video_path and video_path.exists()
        else ["-f", "lavfi", "-i", f"color=black:s={width}x{height}:r=25"]
    )

    cmd = [
        "ffmpeg",
        "-nostdin",
        "-hide_banner",
        "-loglevel", "warning",
        *vid_in,
        "-re",
        "-f", "concat",
        "-safe", "0",
        "-i", str(CONCAT_FILE),
    ]

    if logo_path.exists():
        cmd += ["-loop", "1", "-i", str(logo_path)]

        logo_overlay = (
            f"[base][2:v]overlay=W-w-{logo_padding}:{logo_padding}[vlogo]"
        )
    else:
        logo_overlay = "[base]copy[vlogo]"

    filter_chain = f"""
        [0:v]scale={width}x{height},format=yuv420p[base];
        [1:a]asplit=2[a0][s];
        {logo_overlay};
        [s]showfreqs=s={int(width)//5}x120[bar];
        [vlogo][bar]overlay=45:{int(height)-140}[v2];
        [v2]drawtext=textfile='{NOWPLAYING_FILE}':reload=1:
            fontsize={font_size}:font=Arial:fontcolor={font_color}:
            shadowcolor=black:shadowx={font_shadow}:shadowy={font_shadow}:
            x=w-tw-{text_padding}:y={int(height)-int(font_size)-20}[vout]
    """

    cmd += [
        "-filter_complex", filter_chain.replace("\n", " "),
        "-map", "[vout]",
        "-map", "[a0]",
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-pix_fmt", "yuv420p",
        "-b:v", video_bitrate,
        "-g", "60",
        "-keyint_min", "60",
        "-sc_threshold", "0",
        "-c:a", "aac",
        "-b:a", audio_bitrate,
        "-f", "flv",
        SETTINGS["STREAM_URL"],  # now sourced from config!
    ]

    return cmd


def stream_forever():

    while True:
        tracks = load_tracks()
        build_concat(tracks)
        write_nowplaying(tracks[0])

        cmd = build_ffmpeg_cmd()
        proc = subprocess.Popen(cmd)
        proc.wait()

        print("⚠️ Streaming cycle ended — restarting\n")
        time.sleep(4)


def main():
    print(f"\n🌙 LOFI STREAMER v{VERSION}\n")
    load_config()
    wait_for_pi_ready()

    if not SETTINGS["STREAM_URL"]:
        print("❌ STREAM_URL missing — aborting")
        return

    stream_forever()


if __name__ == "__main__":
    main()
