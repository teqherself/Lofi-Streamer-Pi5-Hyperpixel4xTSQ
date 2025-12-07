#!/usr/bin/env python3
"""
---------------------------------------------------------
 LOFI STREAMER v8.2.7 — MASTER CONFIG FINAL BUILD
 GENDEMIK DIGITAL — Susan Logging Edition
---------------------------------------------------------
"""

import os
import time
import random
import subprocess
from pathlib import Path

VERSION = "8.2.7-master-logging"

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
LOG_FILE = BASE_DIR / "ffmpeg.log"


def load_config():
    if CONFIG_FILE.exists():
        for line in CONFIG_FILE.read_text().strip().splitlines():
            if "=" not in line or line.startswith("#"):
                continue
            key, val = line.split("=", 1)
            key = key.strip()
            val = val.strip()
            if key in SETTINGS:
                SETTINGS[key] = val

    for k in ["WIDTH", "HEIGHT", "FONT_SIZE", "FONT_SHADOW", "LOGO_PADDING", "TEXT_PADDING"]:
        SETTINGS[k] = int(SETTINGS[k])

    print("\n✨ CONFIG LOADED:")
    for k, v in SETTINGS.items():
        print(f"   {k} = {v}")
    print("")


def load_tracks():
    valid_ext = (".mp3", ".wav", ".flac", ".m4a")
    tracks = [t for t in PLAYLIST_DIR.glob("*") if t.suffix.lower() in valid_ext]
    tracks = [t for t in tracks if t.stat().st_size > 1000]
    random.shuffle(tracks)
    print(f"🎶 Valid tracks: {len(tracks)}")
    return tracks


def write_nowplaying(track):
    NOWPLAYING_FILE.write_text(track.stem.replace(":", r"\:"))
    WATCHDOG_FILE.write_text(str(time.time()))


def build_concat(tracks):
    with open(CONCAT_FILE, "w") as f:
        for t in tracks:
            f.write(f"file '{t}'\n")


def build_ffmpeg_cmd():
    w = SETTINGS["WIDTH"]
    h = SETTINGS["HEIGHT"]
    logo = LOGO_DIR / SETTINGS["LOGO"]
    video = VIDEO_DIR / SETTINGS["VIDEO"]

    cmd = ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "warning", "-re"]

    # ===== INPUT 0: VIDEO OR BLACK CANVAS =====
    if video.exists():
        cmd += ["-stream_loop", "-1", "-i", str(video)]
    else:
        cmd += ["-f", "lavfi", "-i", f"color=black:s={w}x{h}:r=25"]

    # ===== INPUT 1: AUDIO CONCAT =====
    cmd += ["-f", "concat", "-safe", "0", "-i", str(CONCAT_FILE)]

    # ===== INPUT 2: LOGO IF EXISTS =====
    has_logo = logo.exists()
    if has_logo:
        cmd += ["-loop", "1", "-i", str(logo)]

    # ------------------------------------------------------
    # FILTERS
    # ------------------------------------------------------

    filter_parts = []

    # scale base
    filter_parts.append(f"[0:v]scale={w}:{h},format=yuv420p[base]")

    # split audio
    filter_parts.append("[1:a]asplit=2[a_main][a_vis]")

    # visualiser
    filter_parts.append(f"[a_vis]showfreqs=s={w//4}x120[bar]")

    # logo
    if has_logo:
        filter_parts.append(
            f"[base][2:v]overlay=W-w-{SETTINGS['LOGO_PADDING']}:{SETTINGS['LOGO_PADDING']}[withlogo]"
        )
        base = "[withlogo]"
    else:
        base = "[base]"

    # bar
    filter_parts.append(f"{base}[bar]overlay=45:{h-160}[afterbar]")

    # text
    filter_parts.append(
        f"[afterbar]drawtext="
        f"textfile='{NOWPLAYING_FILE}':reload=1:"
        f"fontsize={SETTINGS['FONT_SIZE']}:"
        f"fontcolor={SETTINGS['FONT_COLOR']}:"
        f"x=w-tw-{SETTINGS['TEXT_PADDING']}:"
        f"y={h-SETTINGS['FONT_SIZE']-20}:"
        f"shadowx={SETTINGS['FONT_SHADOW']}:"
        f"shadowy={SETTINGS['FONT_SHADOW']}[vout]"
    )

    filter_complex = ";".join(filter_parts)

    cmd += [
        "-filter_complex", filter_complex,
        "-map", "[vout]",
        "-map", "[a_main]",
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-pix_fmt", "yuv420p",
        "-b:v", SETTINGS["VIDEO_BITRATE"],
        "-g", "50",
        "-keyint_min", "50",
        "-sc_threshold", "0",
        "-c:a", "aac",
        "-b:a", SETTINGS["AUDIO_BITRATE"],
        "-f", "flv",
        SETTINGS["STREAM_URL"],
    ]

    return cmd


def stalled():
    try:
        t = float(WATCHDOG_FILE.read_text())
        return (time.time() - t) > 90
    except:
        return True


def run_loop():
    while True:
        tracks = load_tracks()
        if not tracks:
            print("⚠ No audio files found. Waiting...")
            time.sleep(5)
            continue

        build_concat(tracks)
        write_nowplaying(tracks[0])

        cmd = build_ffmpeg_cmd()

        print("▶ Launching ffmpeg…")

        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True
        )

        # STREAM LIVE LOG
        LOG_FILE.write_text("")  # reset log
        while process.poll() is None:
            line = process.stdout.readline().strip()
            if line != "":
                print("🪵 FF:", line)
                LOG_FILE.open("a").write(line + "\n")

            time.sleep(1)

            if stalled():
                print("⚠️ Pipeline stalled — restarting encoder")
                process.kill()
                break

        time.sleep(2)


def main():
    print(f"\n🌙 LOFI STREAMER v{VERSION}\n")
    load_config()

    if not SETTINGS["STREAM_URL"]:
        print("❌ Missing STREAM_URL in stream_config.txt")
        return

    run_loop()


if __name__ == "__main__":
    main()
