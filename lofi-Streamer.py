#!/usr/bin/env python3
import argparse
import os
import time
import random
import socket
import subprocess
from pathlib import Path
from typing import Iterator, List, Optional, Tuple

# -------------------------------------------------------
#  LOFI STREAMER v7.4 — GENDEMIK DIGITAL
#  + Grey LOFI Audio Bar (showfreqs)
#  + Double Height Visual Bar
#  + Bottom-Hugging Right-Aligned Now Playing
#  + Top Right Logo
#  + Pi-Safe Filters
# -------------------------------------------------------

VERSION = "7.4"

OUTPUT_W = 1280
OUTPUT_H = 720

VU_SEG_WIDTH = 16
VU_HEIGHT = 120

LOGO_PADDING = 40
TEXT_PADDING = 40
TRACK_EXIT_BUFFER = 5

def _detect_base_dir() -> Path:
    base = Path(__file__).resolve().parent
    return base.parent if base.name.lower() == "servers" else base

BASE_DIR = _detect_base_dir()

# ---------------- ENV HELPERS ----------------

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
    except (TypeError, ValueError):
        return default

def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.lower() in {"1","true","yes","on"}

# ---------------- PATHS ----------------

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
SKIP_PI_READY_WAIT = _env_bool("LOFI_SKIP_READY_WAIT")

# ---------------- CLI ----------------

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Launch the Hyperpixel LoFi streamer with Pi-safe defaults."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the resolved configuration and exit without launching ffmpeg.",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Stream only a single shuffled track instead of running forever.",
    )
    return parser.parse_args()

def _mask_stream_url(url: str) -> str:
    if not url:
        return ""
    scheme_split = url.split("://", 1)
    if len(scheme_split) == 2:
        scheme, rest = scheme_split
        prefix = f"{scheme}://"
    else:
        prefix = ""
        rest = url
    if len(rest) <= 8:
        masked = "*" * len(rest)
    else:
        masked = f"{rest[:4]}…{rest[-4:]}"
    return f"{prefix}{masked}"

def _print_config_summary(
    stream_url: str,
    tracks: List[Path],
    video_file: Optional[Path],
    logo_file: Optional[Path],
) -> None:
    print("\n🔧 Configuration preview:")
    print(f" • Stream URL: {_mask_stream_url(stream_url) or 'missing!'}")
    print(f" • Tracks folder: {PLAYLIST_DIR}")
    print(f"   ↳ {len(tracks)} playable files detected.")
    print(f" • Video layer: {video_file if video_file else 'color fallback'}")
    print(f" • Logo overlay: {logo_file if logo_file else 'disabled'}")
    print(f" • Network check target: {CHECK_HOST}:{CHECK_PORT}")
    print(f" • Skip Pi readiness: {'yes' if SKIP_PI_READY_WAIT else 'no'}")
    print(f" • Skip network check: {'yes' if SKIP_NETWORK_CHECK else 'no'}\n")

# ---------------- BOOT WAIT ----------------

def wait_for_pi_ready() -> None:
    print("⏳ Waiting for Pi to be fully ready...")

    while os.system("ping -c1 1.1.1.1 > /dev/null 2>&1") != 0:
        print("⏳ Waiting for network…")
        time.sleep(2)
    print("🌐 Internet OK")

    while True:
        try:
            socket.gethostbyname("google.com")
            print("🔍 DNS OK")
            break
        except socket.gaierror:
            print("⏳ Waiting for DNS…")
            time.sleep(2)

    while True:
        try:
            yr = int(subprocess.check_output(["date", "+%Y"]).decode().strip())
        except (subprocess.CalledProcessError, ValueError, FileNotFoundError):
            yr = 0

        if yr >= 2023:
            print("⏱ Time synced")
            break

        print("⏳ Waiting for system clock…")
        time.sleep(2)

def _is_valid_audio(t: Path) -> bool:
    lower = t.name.lower()
    if lower.startswith("._"): return False
    if lower.startswith("."): return False
    return t.suffix.lower() in [".mp3",".wav",".flac",".m4a"]

# ---------------- LOADERS ----------------

def load_stream_url() -> str:
    if STREAM_URL_ENV:
        print("🔐 Using RTMP URL from environment.")
        return STREAM_URL_ENV.strip()
    if STREAM_URL_FILE.exists():
        return STREAM_URL_FILE.read_text().strip()
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
        return VIDEO_FILE
    print(f"⚠️ Video file missing, fallback color feed will be used: {VIDEO_FILE}")
    return None

def load_logo_file() -> Optional[Path]:
    if FFMPEG_LOGO.exists():
        return FFMPEG_LOGO
    print(f"⚠️ Logo image missing, overlay will be skipped: {FFMPEG_LOGO}")
    return None

def _playlist_iterator(tracks: List[Path]) -> Iterator[Path]:
    while True:
        cycle = list(tracks)
        random.shuffle(cycle)
        for t in cycle:
            yield t

# ---------------- NETWORK CHECK ----------------

def check_network() -> bool:
    if SKIP_NETWORK_CHECK:
        return True
    try:
        with socket.create_connection((CHECK_HOST, CHECK_PORT), timeout=3):
            return True
    except OSError:
        return False

# ---------------- VIDEO INPUT ----------------

def _video_input_args(vf: Optional[Path]) -> Tuple[List[str], str]:
    if vf and vf.exists():
        return ["-stream_loop","-1","-re","-i",str(vf)], "[0:v]"
    return [
        "-f","lavfi","-re",
        "-i",f"color=c={FALLBACK_COLOR}:s={OUTPUT_W}x{OUTPUT_H}:r={FALLBACK_FPS}"
    ], "[0:v]"

# ---------------- METADATA ----------------

def _escape(s: str) -> str:
    return s.replace(":", "\\:")

def _get_now_playing(t: Path) -> str:
    title = ""; artist = ""
    try:
        import mutagen
        m = mutagen.File(t, easy=True)
        if m:
            title = m.get("title",[""])[0]
            artist = m.get("artist",[""])[0]
    except Exception:
        pass

    if not title: title = t.stem
    return _escape(f"{artist} - {title}" if artist else title)

# ---------------- FILTER CHAIN ----------------

def _build_filter_chain(video_ref: str, nowplaying: str, include_logo: bool) -> str:

    total_w = VU_SEG_WIDTH * 8
    vh = VU_HEIGHT

    logo_x = 540
    logo_y = 40

    bar_x = 45
    bar_y = OUTPUT_H - vh - 25   # = 580 on 720p

    # Bottom hugging position for text:
    text_y = OUTPUT_H - 25 - 28   # 720 - 20 - fontsize

    if include_logo:
        logo = (
            f"{video_ref}scale={OUTPUT_W}x{OUTPUT_H},format=yuv420p[v0];"
            f"[v0][2:v]overlay={logo_x}:{logo_y}[vbase]"
        )
    else:
        logo = f"{video_ref}scale={OUTPUT_W}x{OUTPUT_H},format=yuv420p[vbase]"

    bar = (
        f"[1:a]asplit=2[a_raw][a_vis];"
        f"[a_raw]loudnorm=I=-16:LRA=11:TP=-1.5[aout];"
        f"[a_vis]showfreqs=s={total_w}x{vh}[vf];"
        f"[vf]format=rgba,colorchannelmixer="
        f"rr=0.6:gg=0.6:bb=0.6:aa=1[vbar];"
        f"[vbase][vbar]overlay={bar_x}:{bar_y}[vstrip]"
    )

    text = (
        f"[vstrip]drawtext=text='Now Playing\\: {nowplaying}':"
        f"fontcolor=white:fontsize=28:"
        f"shadowcolor=black:shadowx=2:shadowy=2:"
        f"x=w-tw-{TEXT_PADDING}:y={text_y}[vout]"
    )

    return f"{logo};{bar};{text}"

# ---------------- TRACK DURATION ----------------

def _track_duration(t: Path) -> int:
    try:
        import mutagen
        m = mutagen.File(t)
        if m and m.info:
            return int(m.info.length)
    except Exception:
        pass

    try:
        r = subprocess.run(
            ["ffprobe","-v","error","-show_entries","format=duration",
             "-of","default=noprint_wrappers=1:nokey=1",str(t)],
            capture_output=True,text=True
        )
        return int(float(r.stdout.strip()))
    except Exception:
        return 180

# ---------------- START STREAM ----------------

def start_stream(
    track: Path,
    stream_url: str,
    video_file: Optional[Path],
    duration: int,
    logo_file: Optional[Path]
) -> subprocess.Popen:

    nowp = _get_now_playing(track)
    print(f"🎧 {nowp}")

    video_args, video_ref = _video_input_args(video_file)

    cmd: List[str] = [
        "ffmpeg","-hide_banner","-loglevel","error",
        *video_args, "-i", str(track)
    ]

    include_logo = logo_file is not None
    if include_logo:
        cmd += ["-loop","1","-i",str(logo_file)]

    filter_chain = _build_filter_chain(video_ref, nowp, include_logo)

    cmd += [
        "-filter_complex", filter_chain,
        "-map","[vout]","-map","[aout]",
        "-c:v","libx264","-preset","veryfast","-b:v","2500k",
        "-g","60","-keyint_min","60",
        "-sc_threshold","0","-pix_fmt","yuv420p",
        "-c:a","aac","-b:a","160k",
        "-shortest","-f","flv",stream_url
    ]

    return subprocess.Popen(cmd)

# ---------------- MAIN LOOP ----------------

def main() -> int:
    args = _parse_args()
    print(f"🌙 LOFI STREAMER v{VERSION} — Bottom-Hugging Text + Cinematic Bar\n")

    stream_url = load_stream_url()
    if not stream_url:
        print("❌ Missing RTMP URL!")
        return 1

    tracks = load_tracks()
    if not tracks:
        print("❌ No tracks found!")
        return 1

    video_file = load_video_file()
    logo_file = load_logo_file()

    if args.dry_run:
        _print_config_summary(stream_url, tracks, video_file, logo_file)
        return 0

    if SKIP_PI_READY_WAIT:
        print("⚡️ Skipping Pi readiness wait (LOFI_SKIP_READY_WAIT=1).")
    else:
        wait_for_pi_ready()

    for idx, t in enumerate(_playlist_iterator(tracks), start=1):

        if not check_network():
            print("🌐 Offline, retrying in 5s…")
            time.sleep(5)
            continue

        dur = _track_duration(t)
        p = start_stream(t, stream_url, video_file, dur, logo_file)

        try:
            p.wait(timeout=dur + TRACK_EXIT_BUFFER)
        except subprocess.TimeoutExpired:
            p.terminate()
            try: p.wait(timeout=5)
            except subprocess.TimeoutExpired:
                p.kill()

        if args.once and idx == 1:
            print("✅ Single-track mode complete.")
            break

    return 0

if __name__ == "__main__":
    raise SystemExit(main())
