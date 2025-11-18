#!/usr/bin/env python3
import os
import time
import random
import socket
import subprocess
from pathlib import Path
from typing import Iterator, List, Optional

# -------------------------------------------------------
#  LOFI STREAMER v7.8 — Picamera2 Edition (540p Stable)
#  + Live Picamera2 video (960×540)
#  + Auto-position top-right logo
#  + Bottom-Hugging Right-Aligned Now Playing
#  + Pi4-Safe encoding (1.8 Mbps)
#  + YouTube-compliant GOP (4 seconds)
# -------------------------------------------------------

VERSION = "7.8-picam-540p"

# ---------------- OUTPUT SETTINGS ----------------

OUTPUT_W = 960
OUTPUT_H = 540

LOGO_PADDING = 40
TEXT_PADDING = 40
TRACK_EXIT_BUFFER = 5

CAM_FIFO = Path("/tmp/camfifo.ts")

# ---------------- PICAMERA2 IMPORT ----------------

try:
    from picamera2 import Picamera2
    from picamera2.encoders import MJPEGEncoder
    from picamera2.outputs import FileOutput
    PICAMERA2_AVAILABLE = True
except ImportError:
    PICAMERA2_AVAILABLE = False

# ---------------- BASE DIR ----------------

def _detect_base_dir() -> Path:
    base = Path(__file__).resolve().parent
    return base.parent if base.name.lower() == "servers" else base

BASE_DIR = _detect_base_dir()

# ---------------- ENV HELPERS ----------------

def _env_path(name: str, default: Path) -> Path:
    raw = Path(os.environ.get(name, str(default))).expanduser()
    try:
        return raw.resolve(strict=False)
    except Exception:
        return raw

def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except:
        return default

def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.lower() in {"1", "true", "yes", "on"}

# ---------------- PATHS ----------------

PLAYLIST_DIR = _env_path("LOFI_PLAYLIST_DIR", BASE_DIR / "Sounds")
LOGO_DIR = _env_path("LOFI_BRAND_DIR", BASE_DIR / "Logo")

STREAM_URL_FILE = _env_path("LOFI_STREAM_URL_FILE", BASE_DIR / "stream_url.txt")
STREAM_URL_ENV = os.environ.get("LOFI_YOUTUBE_URL", "")

FFMPEG_LOGO = _env_path("LOFI_BRAND_IMAGE", LOGO_DIR / "LoFiLogo700.png")

FALLBACK_FPS = _env_int("LOFI_FALLBACK_FPS", 25)

CHECK_HOST = os.environ.get("LOFI_CHECK_HOST", "a.rtmp.youtube.com")
CHECK_PORT = _env_int("LOFI_CHECK_PORT", 1935)

SKIP_NETWORK_CHECK = _env_bool("LOFI_SKIP_NETWORK_CHECK")

# ---------------- BOOT WAIT ----------------

def wait_for_pi_ready():
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
        except:
            print("⏳ Waiting for DNS…")
            time.sleep(2)

    while True:
        try:
            yr = int(subprocess.check_output(["date", "+%Y"]).decode().strip())
        except:
            yr = 1970
        if yr >= 2023:
            print("⏱ Time synced")
            break
        print("⏳ Waiting for NTP…")
        time.sleep(2)

    print("✅ Pi Ready!\n")

# ---------------- TRACK FILTER ----------------

def _is_valid_audio(t: Path) -> bool:
    lower = t.name.lower()
    if lower.startswith("._") or lower.startswith("."):
        return False
    return t.suffix.lower() in [".mp3", ".wav", ".flac", ".m4a"]

# ---------------- LOADERS ----------------

def load_stream_url() -> str:
    if STREAM_URL_ENV:
        print("🔐 Using RTMP URL from environment.")
        return STREAM_URL_ENV.strip()
    if STREAM_URL_FILE.exists():
        print(f"📄 Loaded RTMP URL from {STREAM_URL_FILE}")
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
    except:
        return False

# ---------------- FIFO ----------------

def ensure_fifo():
    if CAM_FIFO.exists():
        try:
            CAM_FIFO.unlink()
        except:
            pass
    os.mkfifo(CAM_FIFO)
    print(f"✓ FIFO ready: {CAM_FIFO}")

# ---------------- METADATA ----------------

def _escape(s: str) -> str:
    return s.replace(":", r"\:")

def _get_now_playing(t: Path) -> str:
    title = ""
    artist = ""
    try:
        import mutagen
        m = mutagen.File(t, easy=True)
        if m:
            title = m.get("title", [""])[0]
            artist = m.get("artist", [""])[0]
    except:
        pass

    if not title:
        title = t.stem
    return _escape(f"{artist} - {title}" if artist else title)

# ---------------- FILTER CHAIN ----------------

def _build_filter_chain(video_ref: str, nowplaying: str) -> str:
    """
    Auto-position logo in top-right:
        x = W - overlay_w - LOGO_PADDING
        y = LOGO_PADDING
    Bottom-right now playing.
    """
    text_y = OUTPUT_H - 25 - 24  # consistent with 540p
    logo_x = f"W-w-{LOGO_PADDING}"
    logo_y = LOGO_PADDING

    if FFMPEG_LOGO.exists():
        return (
            f"{video_ref}scale={OUTPUT_W}:{OUTPUT_H}:flags=bicubic,format=yuv420p[v0];"
            f"[v0][2:v]overlay={logo_x}:{logo_y}[v1];"
            f"[v1]drawtext=text='Now Playing\\: {nowplaying}':"
            f"fontcolor=white:fontsize=24:x=w-tw-{TEXT_PADDING}:y={text_y}[vout]"
        )
    else:
        return (
            f"{video_ref}scale={OUTPUT_W}:{OUTPUT_H}:flags=bicubic,format=yuv420p[v1];"
            f"[v1]drawtext=text='Now Playing\\: {nowplaying}':"
            f"fontcolor=white:fontsize=24:x=w-tw-{TEXT_PADDING}:y={text_y}[vout]"
        )

# ---------------- TRACK DURATION ----------------

def _track_duration(t: Path) -> int:
    try:
        import mutagen
        m = mutagen.File(t)
        if m and m.info:
            return int(m.info.length)
    except:
        pass
    try:
        r = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                str(t),
            ],
            capture_output=True,
            text=True,
        )
        return int(float(r.stdout.strip()))
    except:
        return 180

# ---------------- CAMERA ----------------

def start_camera() -> Optional["Picamera2"]:
    if not PICAMERA2_AVAILABLE:
        print("❌ Picamera2 not available.")
        return None

    print("📸 Initialising Picamera2…")
    picam = Picamera2()

    video_config = picam.create_video_configuration(
        main={"size": (OUTPUT_W, OUTPUT_H)},
        controls={"FrameRate": FALLBACK_FPS}
    )
    picam.configure(video_config)

    encoder = MJPEGEncoder()
    output = FileOutput(str(CAM_FIFO))

    picam.start_recording(encoder, output)
    print(f"📸 Picamera2 → {CAM_FIFO}")
    return picam

def stop_camera(picam: Optional["Picamera2"]):
    if not picam:
        return
    print("📷 Stopping Picamera2…")
    try:
        picam.stop_recording()
    except:
        pass
    try:
        picam.close()
    except:
        pass
    print("📷 Camera stopped.")

# ---------------- START STREAM ----------------

def start_stream(track: Path, stream_url: str, duration: int):
    nowp = _get_now_playing(track)
    print(f"🎧 Now playing: {nowp}")

    ensure_fifo()

    cmd = [
        "ffmpeg", "-hide_banner", "-loglevel", "error",
        "-thread_queue_size", "512",
        "-f", "mjpeg", "-re", "-i", str(CAM_FIFO),   # CAMERA
        "-thread_queue_size", "512",
        "-i", str(track),                            # AUDIO
    ]

    if FFMPEG_LOGO.exists():
        cmd += ["-loop", "1", "-i", str(FFMPEG_LOGO)]  # LOGO

    filter_chain = _build_filter_chain("[0:v]", nowp)

    cmd += [
        "-filter_complex", filter_chain,
        "-map", "[vout]", "-map", "1:a",
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-b:v", "1800k",
        "-maxrate", "1800k",
        "-bufsize", "2400k",
        "-g", "100", "-keyint_min", "100",  # 25 fps × 4 sec = 100 frames
        "-sc_threshold", "0",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "128k",
        "-shortest",
        "-f", "flv", stream_url,
    ]

    p = subprocess.Popen(cmd)
    picam = start_camera()

    if not picam:
        p.terminate()
        return p, None

    return p, picam

# ---------------- MAIN LOOP ----------------

def main():
    print(f"🌙 LOFI STREAMER v{VERSION} — Picamera2 540p Edition\n")

    if not PICAMERA2_AVAILABLE:
        print("❌ Install Picamera2 first: sudo apt install python3-picamera2")
        return

    wait_for_pi_ready()

    stream_url = load_stream_url()
    if not stream_url:
        print("❌ Missing RTMP URL!")
        return

    tracks = load_tracks()
    if not tracks:
        print("❌ No tracks found!")
        return

    for t in _playlist_iterator(tracks):

        if not check_network():
            print("🌐 Offline, retrying in 5s…")
            time.sleep(5)
            continue

        dur = _track_duration(t)
        p, picam = start_stream(t, stream_url, dur)

        if picam is None:
            print("❌ Camera failed.")
            return

        try:
            p.wait(timeout=dur + TRACK_EXIT_BUFFER)
        except subprocess.TimeoutExpired:
            p.terminate()
            try:
                p.wait(timeout=5)
            except subprocess.TimeoutExpired:
                p.kill()
        finally:
            stop_camera(picam)
            time.sleep(1)

if __name__ == "__main__":
    main()
