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
#  LOFI STREAMER v7.9 — CONTINUOUS EDITION
#  + Single ffmpeg pipeline (no per-track restarts)
#  + Grey LOFI Audio Bar (showfreqs)
#  + Bottom-Hugging Right-Aligned Now Playing (textfile)
#  + Top Right Logo
#  + Pi-Safe Filters
# -------------------------------------------------------

VERSION = "7.9-continuous"

OUTPUT_W = 1280
OUTPUT_H = 720

VU_SEG_WIDTH = 16
VU_HEIGHT = 120

LOGO_PADDING = 40
TEXT_PADDING = 40
TRACK_EXIT_BUFFER = 5

DEFAULT_NOWPLAYING_FILE = Path("/tmp/nowplaying.txt")


def _detect_base_dir() -> Path:
    base = Path(__file__).resolve().parent
    return base.parent if base.name.lower() == "servers" else base


BASE_DIR = _detect_base_dir()

# -------------------------------------------------------
# ENV HELPERS
# -------------------------------------------------------

def _env_path(name: str, default: Path) -> Path:
    raw = Path(os.environ.get(name, str(default))).expanduser()
    try:
        return raw.resolve(strict=False)
    except FileNotFoundError:
        return raw


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except Exception:
        return default


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.lower() in {"1", "true", "yes", "on"}

# -------------------------------------------------------
# PATHS
# -------------------------------------------------------

PLAYLIST_DIR = _env_path("LOFI_PLAYLIST_DIR", BASE_DIR / "Sounds")
LOGO_DIR = _env_path("LOFI_BRAND_DIR", BASE_DIR / "Logo")
VIDEO_DIR = _env_path("LOFI_VIDEO_DIR", BASE_DIR / "Videos")

STREAM_URL_FILE = _env_path("LOFI_STREAM_URL_FILE", BASE_DIR / "stream_url.txt")
STREAM_URL_ENV = os.environ.get("LOFI_YOUTUBE_URL", "")

FFMPEG_LOGO = _env_path("LOFI_BRAND_IMAGE", LOGO_DIR / "LoFiLogo700.png")
VIDEO_FILE = _env_path("LOFI_VIDEO_FILE", VIDEO_DIR / "Lofi3.mp4")

FALLBACK_COLOR = os.environ.get("LOFI_FALLBACK_COLOR", "black")
FALLBACK_FPS = _env_int("LOFI_FALLBACK_FPS", 30)

CHECK_HOST = os.environ.get("LOFI_CHECK_HOST", "a.rtmp.youtube.com")
CHECK_PORT = _env_int("LOFI_CHECK_PORT", 1935)

SKIP_NETWORK_CHECK = _env_bool("LOFI_SKIP_NETWORK_CHECK")

NOWPLAYING_FILE = _env_path("LOFI_NOWPLAYING_FILE", DEFAULT_NOWPLAYING_FILE)
CONCAT_PLAYLIST_FILE = _env_path("LOFI_CONCAT_FILE", BASE_DIR / "lofi_concat.txt")

# -------------------------------------------------------
# BOOT WAIT
# -------------------------------------------------------

def wait_for_pi_ready():
    print("⏳ Waiting for Pi to be fully ready...")

    # Network up
    while os.system("ping -c1 1.1.1.1 > /dev/null 2>&1") != 0:
        print("⏳ Waiting for network…")
        time.sleep(2)
    print("🌐 Internet OK")

    # DNS
    while True:
        try:
            socket.gethostbyname("google.com")
            print("🔍 DNS OK")
            break
        except Exception:
            print("⏳ Waiting for DNS…")
            time.sleep(2)

    # NTP
    while True:
        try:
            yr = int(subprocess.check_output(["date", "+%Y"]).decode().strip())
        except Exception:
            yr = 1970
        if yr >= 2023:
            print("⏱ Time synced")
            break
        print("⏳ Waiting for NTP…")
        time.sleep(2)

    print("✅ Pi Ready!\n")

# -------------------------------------------------------
# TRACK FILTER
# -------------------------------------------------------

def _is_valid_audio(t: Path) -> bool:
    lower = t.name.lower()
    if lower.startswith("._"):
        return False
    if lower.startswith("."):
        return False
    return t.suffix.lower() in [".mp3", ".wav", ".flac", ".m4a"]

# -------------------------------------------------------
# LOADERS
# -------------------------------------------------------

def load_stream_url() -> str:
    if STREAM_URL_ENV:
        print("🔐 Using RTMP URL from environment.")
        return STREAM_URL_ENV.strip()
    if STREAM_URL_FILE.exists():
        url = STREAM_URL_FILE.read_text().strip()
        print(f"📄 Loaded RTMP URL from {STREAM_URL_FILE}")
        return url
    print("❌ No RTMP URL found!")
    return ""


def load_tracks() -> List[Path]:
    if not PLAYLIST_DIR.exists():
        print("❌ Sounds folder missing:", PLAYLIST_DIR)
        return []
    tracks = [t for t in PLAYLIST_DIR.iterdir() if _is_valid_audio(t)]
    print(f"🎶 Loaded {len(tracks)} tracks.")
    return tracks


def load_video_file() -> Optional[Path]:
    if VIDEO_FILE.exists():
        print(f"🎥 Background video: {VIDEO_FILE}")
        return VIDEO_FILE
    print("🎥 Using solid colour fallback.")
    return None

# -------------------------------------------------------
# NETWORK CHECK
# -------------------------------------------------------

def check_network() -> bool:
    if SKIP_NETWORK_CHECK:
        return True
    try:
        with socket.create_connection((CHECK_HOST, CHECK_PORT), timeout=3):
            return True
    except Exception:
        return False

# -------------------------------------------------------
# METADATA
# -------------------------------------------------------

def _escape_drawtext(s: str) -> str:
    return s.replace(":", r"\:")


def _get_now_playing_str(t: Path) -> str:
    title = ""
    artist = ""
    try:
        import mutagen
        m = mutagen.File(t, easy=True)
        if m:
            title = m.get("title", [""])[0]
            artist = m.get("artist", [""])[0]
    except Exception:
        pass

    if not title:
        title = t.stem

    disp = f"{artist} - {title}" if artist else title
    return _escape_drawtext(disp)


def write_nowplaying_file(track: Path):
    text = _get_now_playing_str(track)
    try:
        NOWPLAYING_FILE.write_text(text, encoding="utf-8")
        print(f"🎧 Now playing: {text}")
    except Exception as e:
        print(f"⚠️ Failed to write nowplaying file: {e}")

# -------------------------------------------------------
# TRACK DURATIONS
# -------------------------------------------------------

def _track_duration(t: Path) -> int:
    try:
        import mutagen
        m = mutagen.File(t)
        if m and m.info and getattr(m.info, "length", None):
            return max(1, int(m.info.length))
    except Exception:
        pass

    # ffprobe fallback
    try:
        r = subprocess.run(
            [
                "ffprobe",
                "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                str(t),
            ],
            capture_output=True,
            text=True,
        )
        val = r.stdout.strip()
        if val:
            return max(1, int(float(val)))
    except Exception:
        pass

    return 180

def build_track_schedule(tracks: List[Path]) -> List[Tuple[Path, int]]:
    schedule = []
    for t in tracks:
        d = _track_duration(t)
        schedule.append((t, d))
    total = sum(d for _, d in schedule)
    print(f"⏱ Total playlist = {total/60:.1f} min")
    return schedule

# -------------------------------------------------------
# CONCAT PLAYLIST FILE
# -------------------------------------------------------

def build_concat_file(tracks: List[Path], concat_file: Path):
    order = list(tracks)
    random.shuffle(order)

    concat_file.parent.mkdir(parents=True, exist_ok=True)

    with concat_file.open("w", encoding="utf-8") as f:
        for t in order:
            # Fixed safe quoting
            san = str(t).replace("'", "'\\''")
            line = f"file '{san}'\n"
            f.write(line)

    print(f"📝 Built concat playlist at {concat_file}")
    return order

# -------------------------------------------------------
# FILTER CHAIN
# -------------------------------------------------------

def _build_filter_chain(has_logo: bool) -> str:
    total_w = VU_SEG_WIDTH * 8
    vh = VU_HEIGHT

    logo_x = 540
    logo_y = 40

    bar_x = 45
    bar_y = OUTPUT_H - vh - 25

    text_y = OUTPUT_H - 25 - 28

    np_path = NOWPLAYING_FILE.as_posix()

    if has_logo:
        logo = (
            f"[0:v]scale={OUTPUT_W}x{OUTPUT_H},format=yuv420p[v0];"
            f"[v0][2:v]overlay={logo_x}:{logo_y}[vbase]"
        )
    else:
        logo = f"[0:v]scale={OUTPUT_W}x{OUTPUT_H},format=yuv420p[vbase]"

    bar = (
        f"[1:a]asplit=2[a_raw][a_vis];"
        f"[a_raw]loudnorm=I=-16:LRA=11:TP=-1.5[aout];"
        f"[a_vis]showfreqs=s={total_w}x{vh}[vf];"
        f"[vf]format=rgba,colorchannelmixer="
        f"rr=0.6:gg=0.6:bb=0.6:aa=1[vbar];"
        f"[vbase][vbar]overlay={bar_x}:{bar_y}[vstrip]"
    )

    text = (
        f"[vstrip]drawtext="
        f"textfile='{np_path}':"
        f"reload=1:"
        f"fontcolor=white:fontsize=28:"
        f"shadowcolor=black:shadowx=2:shadowy=2:"
        f"x=w-tw-{TEXT_PADDING}:y={text_y}[vout]"
    )

    return f"{logo};{bar};{text}"

# -------------------------------------------------------
# METADATA THREAD
# -------------------------------------------------------

def metadata_loop(schedule: List[Tuple[Path, int]]):
    print("🧠 Metadata updater started.")
    while True:
        for track, dur in schedule:
            write_nowplaying_file(track)
            time.sleep(max(1, dur - 1))

# -------------------------------------------------------
# FFMPEG COMMAND BUILDER
# -------------------------------------------------------

def _video_input_args(vf: Optional[Path]):
    if vf and vf.exists():
        return ["-stream_loop", "-1", "-re", "-i", str(vf)]
    return [
        "-f", "lavfi", "-re",
        "-i", f"color=c={FALLBACK_COLOR}:s={OUTPUT_W}x{OUTPUT_H}:r={FALLBACK_FPS}"
    ]


def build_ffmpeg_cmd(stream_url: str, video_file: Optional[Path], has_logo: bool):
    video_args = _video_input_args(video_file)
    filter_chain = _build_filter_chain(has_logo)

    cmd = [
        "ffmpeg", "-hide_banner", "-loglevel", "error",
        *video_args,
        "-re", "-stream_loop", "-1",
        "-f", "concat", "-safe", "0",
        "-i", str(CONCAT_PLAYLIST_FILE),
    ]

    if has_logo:
        cmd += ["-loop", "1", "-i", str(FFMPEG_LOGO)]

    cmd += [
        "-filter_complex", filter_chain,
        "-map", "[vout]", "-map", "[aout]",
        "-c:v", "libx264", "-preset", "veryfast", "-b:v", "2500k",
        "-g", "60", "-keyint_min", "60", "-sc_threshold", "0",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "160k",
        "-f", "flv", stream_url,
    ]

    return cmd

# -------------------------------------------------------
# MAIN LOOP
# -------------------------------------------------------

def main():
    print(f"🌙 LOFI STREAMER v{VERSION} — Continuous RTMP Pipeline\n")

    wait_for_pi_ready()

    stream_url = load_stream_url()
    if not stream_url:
        print("❌ Missing RTMP URL — exiting.")
        return

    tracks = load_tracks()
    if not tracks:
        print("❌ No audio tracks — exiting.")
        return

    # Build playlist
    ordered_tracks = build_concat_file(tracks, CONCAT_PLAYLIST_FILE)
    schedule = build_track_schedule(ordered_tracks)

    # Initial now playing
    write_nowplaying_file(schedule[0][0])

    # Start metadata thread
    threading.Thread(
        target=metadata_loop,
        args=(schedule,),
        daemon=True
    ).start()

    video_file = load_video_file()
    has_logo = FFMPEG_LOGO.exists()
    if has_logo:
        print(f"🖼 Logo: {FFMPEG_LOGO}")

    # Main ffmpeg loop
    while True:
        if not check_network():
            print("🌐 RTMP offline, retry in 5s…")
            time.sleep(5)
            continue

        cmd = build_ffmpeg_cmd(stream_url, video_file, has_logo)

        print("🚀 Starting continuous ffmpeg pipeline…")
        proc = subprocess.Popen(cmd)

        try:
            rc = proc.wait()
        except KeyboardInterrupt:
            print("🛑 Interrupted. Stopping.")
            proc.terminate()
            break

        print(f"⚠️ ffmpeg exited (code {rc}). Restarting in 5s…")
        time.sleep(5)


if __name__ == "__main__":
    main()