#!/usr/bin/env python3
import os
import time
import random
import socket
import threading
import subprocess
from pathlib import Path
from typing import List, Optional, Tuple

# -------------------------------------------------------
#  LOFI STREAMER v8.1 — CONTINUOUS EDITION
#  + No ffmpeg restart per track
#  + Deadlock-proof RTMP pipeline
#  + Overnight latency safe
#  + Timestamp corrected
# -------------------------------------------------------

VERSION = "8.1-continuous"

OUTPUT_W = 1280
OUTPUT_H = 720

VU_SEG_WIDTH = 16
VU_HEIGHT = 120

LOGO_PADDING = 40
TEXT_PADDING = 40

DEFAULT_NOWPLAYING_FILE = Path("/tmp/nowplaying.txt")

def _detect_base_dir() -> Path:
    base = Path(__file__).resolve().parent
    return base.parent if base.name.lower() == "servers" else base

BASE_DIR = _detect_base_dir()

# ---------- ENV VAR LOADING ----------
def _env_path(name: str, default: Path) -> Path:
    raw = Path(os.environ.get(name, str(default))).expanduser()
    try:
        return raw.resolve(strict=False)
    except Exception:
        return raw

def _env_int(name, default):
    try:
        return int(os.environ.get(name, default))
    except:
        return default

def _env_bool(name, default=False):
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.lower() in ("1", "true", "yes", "on")

# ---------- PATHS ----------
PLAYLIST_DIR = _env_path("LOFI_PLAYLIST_DIR", BASE_DIR / "Sounds")
LOGO_DIR = _env_path("LOFI_BRAND_DIR", BASE_DIR / "Logo")
VIDEO_DIR = _env_path("LOFI_VIDEO_DIR", BASE_DIR / "Videos")

STREAM_URL_FILE = _env_path("LOFI_STREAM_URL_FILE", BASE_DIR / "stream_url.txt")
STREAM_URL_ENV = os.environ.get("LOFI_YOUTUBE_URL", "")

FFMPEG_LOGO = _env_path("LOFI_BRAND_IMAGE", LOGO_DIR / "LoFiLogo700.png")
VIDEO_FILE = _env_path("LOFI_VIDEO_FILE", VIDEO_DIR / "Lofi3.mp4")

NOWPLAYING_FILE = _env_path("LOFI_NOWPLAYING_FILE", DEFAULT_NOWPLAYING_FILE)
CONCAT_PLAYLIST_FILE = _env_path("LOFI_CONCAT_FILE", BASE_DIR / "lofi_concat.txt")

CHECK_HOST = "a.rtmp.youtube.com"
CHECK_PORT = 1935


# ---------- PI-READY ----------
def wait_for_pi_ready():
    print("⏳ Waiting for Pi to be fully ready...")

    # Internet
    for _ in range(60):
        if os.system("ping -c1 1.1.1.1 >/dev/null 2>&1") == 0:
            print("🌐 Internet OK")
            break
        time.sleep(2)

    # DNS
    for _ in range(60):
        try:
            socket.gethostbyname("google.com")
            print("🔍 DNS OK")
            break
        except:
            time.sleep(2)

    # Time / Year
    for _ in range(120):
        try:
            yr = int(subprocess.check_output(["date", "+%Y"]).decode().strip())
        except Exception:
            yr = 1970
        if yr >= 2023:
            print("⏱ Time synced")
            break
        time.sleep(2)

    print("✅ Pi Ready\n")


# ---------- TRACK FILTER ----------
def _is_valid_audio(t: Path):
    if t.name.startswith("._") or t.name.startswith("."):
        return False
    return t.suffix.lower() in (".mp3", ".wav", ".flac", ".m4a")


# ---------- LOADERS ----------
def load_stream_url():
    if STREAM_URL_ENV:
        print("🔐 Using RTMP URL from environment")
        return STREAM_URL_ENV.strip()

    if STREAM_URL_FILE.exists():
        url = STREAM_URL_FILE.read_text().strip()
        print(f"📄 RTMP URL = {url}")
        return url

    print("❌ No RTMP URL found!")
    return ""

def load_tracks() -> List[Path]:
    if not PLAYLIST_DIR.exists():
        print("❌ No playlist folder:", PLAYLIST_DIR)
        return []
    tracks = [t for t in PLAYLIST_DIR.iterdir() if _is_valid_audio(t)]
    print(f"🎶 Loaded {len(tracks)} tracks")
    return tracks

def load_video_file():
    if VIDEO_FILE.exists():
        print(f"🎥 Background video: {VIDEO_FILE}")
        return VIDEO_FILE
    print("🎥 Using fallback solid")
    return None


# ---------- NETWORK ----------
def check_network():
    try:
        with socket.create_connection((CHECK_HOST, CHECK_PORT), timeout=3):
            return True
    except:
        return False


# ---------- NOW PLAYING ----------
def _escape_drawtext(s: str) -> str:
    return s.replace(":", r"\:")

def _get_text(t: Path):
    try:
        import mutagen
        m = mutagen.File(t, easy=True)
        title = m.get("title", [""])[0]
        artist = m.get("artist", [""])[0]
    except:
        title = ""
        artist = ""

    if not title:
        title = t.stem

    return _escape_drawtext(f"{artist} - {title}" if artist else title)

def write_nowplaying(track: Path):
    try:
        NOWPLAYING_FILE.write_text(_get_text(track))
    except:
        pass


# ---------- BUILD CONCAT ----------
def build_concat(tracks, out):
    random.shuffle(tracks)
    safe_lines = []
for t in tracks:
    safe = str(t).replace("'", "'\\''")
    safe_lines.append(f"file '{safe}'")

out.write_text("\n".join(safe_lines))

    print(f"📝 Playlist compiled: {out}")


# ---------- FILTER CHAIN ----------
def _filter_chain(has_logo: bool):
    total_w = VU_SEG_WIDTH * 8
    vh = VU_HEIGHT

    bar_x = 45
    bar_y = OUTPUT_H - vh - 25

    text_y = OUTPUT_H - 28 - 5

    np_path = NOWPLAYING_FILE.as_posix()

    base = f"[0:v]scale={OUTPUT_W}x{OUTPUT_H},format=yuv420p[v0]"

    if has_logo:
        base += ";[v0][2:v]overlay=540:40[vb]"
    else:
        base += "[vb]"

    chain = (
        f"{base};"
        f"[1:a]asplit=2[a0][avis];"
        f"[avis]showfreqs=s={total_w}x{vh}[vf];"
        f"[vf]format=rgba,colorchannelmixer=rr=0.6:gg=0.6:bb=0.6:aa=1[vbar];"
        f"[vb][vbar]overlay={bar_x}:{bar_y}[v1];"
        f"[v1]drawtext=textfile='{np_path}':reload=1:"
        "fontcolor=white:fontsize=28:shadowcolor=black:shadowx=2:shadowy=2:"
        f"x=w-tw-{TEXT_PADDING}:y={text_y}[vout]"
    )

    return chain


# ---------- WATCHDOG ----------
def watchdog_ffmpeg(cmd):
    print("🚀 FFmpeg starting…")
    proc = subprocess.Popen(cmd)

    while True:
        rc = proc.poll()
        if rc is not None:
            print(f"⚠️ ffmpeg exited {rc}")
            return

        if not check_network():
            print("🌐 RTMP dropped — restarting…")
            proc.terminate()
            time.sleep(2)
            return

        time.sleep(5)


# ---------- FFmpeg CMD ----------
def build_ffmpeg_cmd(stream_url, video_file, has_logo):

    # Video input
    video = (
        ["-stream_loop", "-1", "-i", str(video_file)]
        if video_file
        else ["-f", "lavfi", "-i", f"color=c=black:s={OUTPUT_W}x{OUTPUT_H}:r=30"]
    )

    filters = _filter_chain(has_logo)

    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel", "warning",

        "-use_wallclock_as_timestamps", "1",
        "-avoid_negative_ts", "make_zero",
        "-max_muxing_queue_size", "4096",

        "-fflags", "+flush_packets+nobuffer",
        "-flush_packets", "1",

        *video,

        "-re",
        "-f", "concat", "-safe", "0", "-i", str(CONCAT_PLAYLIST_FILE),
    ]

    if has_logo:
        cmd += ["-loop", "1", "-i", str(FFMPEG_LOGO)]

    cmd += [
        "-filter_complex", filters,
        "-map", "[vout]",
        "-map", "[a0]",

        "-c:v", "libx264",
        "-preset", "veryfast",
        "-b:v", "2500k",
        "-g", "60",
        "-keyint_min", "60",
        "-sc_threshold", "0",
        "-pix_fmt", "yuv420p",

        "-c:a", "aac",
        "-b:a", "160k",

        "-af", "aresample=async=1000",  # 🔥 RE-TIME AUDIO

        "-f", "flv", stream_url,
    ]

    return cmd


# ---------- MAIN ----------
def main():
    print(f"\n🌙 LOFI STREAMER v{VERSION}\n")

    wait_for_pi_ready()

    url = load_stream_url()
    if not url:
        return

    tracks = load_tracks()
    if not tracks:
        return

    build_concat(tracks, CONCAT_PLAYLIST_FILE)
    write_nowplaying(tracks[0])

    video = load_video_file()
    has_logo = FFMPEG_LOGO.exists()

    threading.Thread(target=lambda:
        [write_nowplaying(t) or time.sleep(180) for t in tracks],
        daemon=True
    ).start()

    while True:
        if not check_network():
            time.sleep(5)
            continue

        cmd = build_ffmpeg_cmd(url, video, has_logo)
        watchdog_ffmpeg(cmd)
        time.sleep(5)


if __name__ == "__main__":
    main()
