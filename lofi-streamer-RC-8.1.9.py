#!/usr/bin/env python3
"""
---------------------------------------------------------
 LOFI STREAMER v8.2.8 — MASTER CONFIG STABLE RELEASE
 GENDEMIK DIGITAL — Improved Stability Build
---------------------------------------------------------
 ✔ Better error handling and recovery
 ✔ Improved watchdog with FFmpeg health monitoring
 ✔ Dynamic playlist updating
 ✔ Graceful shutdown handling
 ✔ Network connectivity checks
 ✔ Auto-restart with limits
---------------------------------------------------------
"""

import os
import time
import random
import subprocess
import signal
import sys
import socket
import threading
from pathlib import Path

VERSION = "8.2.8-master-stable"

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
    "FPS": "25",
    "GOP_SIZE": "60",
}

BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_FILE = BASE_DIR / "stream_config.txt"
PLAYLIST_DIR = BASE_DIR / "Sounds"
LOGO_DIR = BASE_DIR / "Logo"
VIDEO_DIR = BASE_DIR / "Videos"
CONCAT_FILE = BASE_DIR / "lofi_concat.txt"
NOWPLAYING_FILE = Path("/tmp/nowplaying.txt")
CURRENT_TRACK_FILE = Path("/tmp/current_track.txt")
WATCHDOG_FILE = Path("/tmp/stream_watchdog.txt")

# Stability settings
WATCHDOG_INTERVAL = 30  # Check every 30 seconds
WATCHDOG_STALL_THRESHOLD = 90  # Consider stalled after 90 seconds
MAX_RESTART_ATTEMPTS = 5
RESTART_COOLDOWN = 60
CHECK_HOST = "a.rtmp.youtube.com"
CHECK_PORT = 1935

# Global state
global_stop = False


def load_config():
    """Load configuration from file with validation"""
    if not CONFIG_FILE.exists():
        print("❌ Missing config — defaults used")
        return

    print(f"📄 Loading config from {CONFIG_FILE}")
    
    for line in CONFIG_FILE.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        
        key, val = line.split("=", 1)
        key, val = key.strip(), val.strip()
        
        if key in SETTINGS:
            SETTINGS[key] = val

    # Cast numeric settings
    try:
        SETTINGS["WIDTH"] = int(SETTINGS["WIDTH"])
        SETTINGS["HEIGHT"] = int(SETTINGS["HEIGHT"])
        SETTINGS["FONT_SIZE"] = int(SETTINGS["FONT_SIZE"])
        SETTINGS["FONT_SHADOW"] = int(SETTINGS["FONT_SHADOW"])
        SETTINGS["LOGO_PADDING"] = int(SETTINGS["LOGO_PADDING"])
        SETTINGS["TEXT_PADDING"] = int(SETTINGS["TEXT_PADDING"])
        SETTINGS["FPS"] = int(SETTINGS["FPS"])
        SETTINGS["GOP_SIZE"] = int(SETTINGS["GOP_SIZE"])
    except ValueError as e:
        print(f"⚠️ Config parsing error: {e}")

    print("\n✨ CONFIG LOADED:")
    for k, v in SETTINGS.items():
        if k == "STREAM_URL":
            # Mask the URL for security
            masked = v[:30] + "..." if len(v) > 30 else v
            print(f"   {k} = {masked}")
        else:
            print(f"   {k} = {v}")
    print("")


def check_network() -> bool:
    """Check if RTMP server is reachable"""
    try:
        with socket.create_connection((CHECK_HOST, CHECK_PORT), timeout=5):
            return True
    except (OSError, socket.timeout):
        return False


def load_tracks():
    """Load valid audio tracks from playlist directory"""
    if not PLAYLIST_DIR.exists():
        print(f"❌ Playlist directory not found: {PLAYLIST_DIR}")
        try:
            PLAYLIST_DIR.mkdir(parents=True, exist_ok=True)
            print("📁 Created playlist directory")
        except Exception as e:
            print(f"❌ Failed to create playlist directory: {e}")
        return []

    valid_exts = (".mp3", ".wav", ".flac", ".m4a")
    try:
        tracks = [
            t for t in PLAYLIST_DIR.iterdir() 
            if t.suffix.lower() in valid_exts 
            and not t.name.startswith(".")
            and not t.name.startswith("._")
        ]
        tracks = [t for t in tracks if t.stat().st_size > 1000]
        random.shuffle(tracks)
        print(f"🎶 Valid tracks: {len(tracks)}")
        return tracks
    except Exception as e:
        print(f"❌ Error loading tracks: {e}")
        return []


def get_track_metadata(track: Path) -> str:
    """Extract track metadata for display"""
    try:
        import mutagen
        m = mutagen.File(track, easy=True)
        title = m.get("title", [""])[0] if m else ""
        artist = m.get("artist", [""])[0] if m else ""
        
        if artist and title:
            return f"{artist} - {title}"
        elif title:
            return title
    except Exception:
        pass
    
    return track.stem


def write_nowplaying(track: Path):
    """Write now playing info to files (dual write for compatibility)"""
    display_name = get_track_metadata(track)
    # Escape colons for FFmpeg drawtext
    escaped = display_name.replace(":", r"\:")
    
    try:
        NOWPLAYING_FILE.write_text(escaped)
        CURRENT_TRACK_FILE.write_text(display_name)
    except Exception as e:
        print(f"⚠️ Failed to write now playing: {e}")
    
    # Update watchdog
    try:
        WATCHDOG_FILE.write_text(str(time.time()))
    except Exception:
        pass


def build_concat(tracks):
    """Build FFmpeg concat file"""
    try:
        with open(CONCAT_FILE, "w") as f:
            for t in tracks:
                # Escape single quotes in filenames
                escaped_path = str(t).replace("'", "'\\''")
                f.write(f"file '{escaped_path}'\n")
        return True
    except Exception as e:
        print(f"❌ Failed to build concat file: {e}")
        return False


def build_ffmpeg_cmd(tracks):
    """Build FFmpeg command with all filters and settings"""
    w = SETTINGS["WIDTH"]
    h = SETTINGS["HEIGHT"]
    fps = SETTINGS["FPS"]
    gop = SETTINGS["GOP_SIZE"]

    logo_path = LOGO_DIR / SETTINGS["LOGO"]
    video_path = VIDEO_DIR / SETTINGS["VIDEO"] if SETTINGS["VIDEO"] else None

    cmd = [
        "ffmpeg",
        "-nostdin",
        "-hide_banner",
        "-loglevel", "warning",
        "-stats",  # Show encoding stats
    ]

    # Video input
    if video_path and video_path.exists():
        cmd += [
            "-stream_loop", "-1",
            "-r", str(fps),
            "-i", str(video_path)
        ]
        vid_label = "0:v"
        print(f"🎬 Using video: {video_path.name}")
    else:
        cmd += [
            "-f", "lavfi",
            "-i", f"color=black:s={w}x{h}:r={fps}"
        ]
        vid_label = "0:v"
        print("🎬 Using black background")

    # Audio input (concat playlist)
    cmd += [
        "-re",
        "-f", "concat",
        "-safe", "0",
        "-i", str(CONCAT_FILE),
    ]

    have_logo = logo_path.exists()

    # Logo overlay
    if have_logo:
        cmd += ["-loop", "1", "-i", str(logo_path)]
        logo_chain = f"[base][2:v]overlay=W-w-{SETTINGS['LOGO_PADDING']}:{SETTINGS['LOGO_PADDING']}[vlogo]"
        print(f"🖼️ Using logo: {logo_path.name}")
    else:
        logo_chain = "[base]copy[vlogo]"

    # Visualizer dimensions
    viz_w = w // 5
    viz_h = 120
    viz_y = h - viz_h - 20

    # Build filter chain
    filter_chain = f"""
        [{vid_label}]scale={w}:{h},format=yuv420p[base];
        [1:a]asplit=2[a0][s];
        {logo_chain};
        [s]showfreqs=mode=bar:ascale=log:s={viz_w}x{viz_h}:colors=0xCCCCCC[bar];
        [vlogo][bar]overlay=45:{viz_y}[v2];
        [v2]drawtext=textfile='{NOWPLAYING_FILE}':reload=1:
            font=Arial:fontsize={SETTINGS['FONT_SIZE']}:
            x=w-tw-{SETTINGS['TEXT_PADDING']}:
            y={h-SETTINGS['FONT_SIZE']-20}:
            fontcolor={SETTINGS['FONT_COLOR']}:
            shadowcolor=black:shadowx={SETTINGS['FONT_SHADOW']}:
            shadowy={SETTINGS['FONT_SHADOW']}[vout]
    """.replace("\n", " ").strip()

    cmd += [
        "-filter_complex", filter_chain,
        "-map", "[vout]",
        "-map", "[a0]",
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-tune", "zerolatency",
        "-profile:v", "baseline",
        "-pix_fmt", "yuv420p",
        "-b:v", SETTINGS["VIDEO_BITRATE"],
        "-maxrate", SETTINGS["VIDEO_BITRATE"],
        "-bufsize", str(int(SETTINGS["VIDEO_BITRATE"].rstrip("k")) * 2) + "k",
        "-g", str(gop),
        "-keyint_min", str(gop),
        "-sc_threshold", "0",
        "-c:a", "aac",
        "-b:a", SETTINGS["AUDIO_BITRATE"],
        "-ar", "44100",
        "-f", "flv",
        SETTINGS["STREAM_URL"],
    ]

    return cmd


def check_ffmpeg_health(proc: subprocess.Popen) -> bool:
    """Check if FFmpeg process is healthy"""
    if proc.poll() is not None:
        return False  # Process has exited
    
    # Check watchdog timestamp
    try:
        if not WATCHDOG_FILE.exists():
            return True  # Give it time to start
        
        ts = float(WATCHDOG_FILE.read_text().strip())
        age = time.time() - ts
        
        if age > WATCHDOG_STALL_THRESHOLD:
            print(f"⚠️ Stream stalled ({age:.0f}s since last update)")
            return False
    except Exception:
        pass
    
    return True


def watchdog_monitor(proc: subprocess.Popen, stop_event: threading.Event, restart_callback):
    """Monitor FFmpeg health in background thread"""
    print("🐕 Watchdog started")
    
    consecutive_stalls = 0
    last_network_check = time.time()
    
    while not stop_event.is_set():
        time.sleep(WATCHDOG_INTERVAL)
        
        if stop_event.is_set():
            break
        
        # Check FFmpeg health
        if not check_ffmpeg_health(proc):
            consecutive_stalls += 1
            print(f"⚠️ Watchdog detected issue (count: {consecutive_stalls})")
            
            if consecutive_stalls >= 2:
                print("❌ Watchdog: Triggering restart")
                restart_callback()
                break
        else:
            consecutive_stalls = 0
        
        # Periodic network check (every 5 minutes)
        if time.time() - last_network_check > 300:
            if not check_network():
                print("⚠️ Watchdog: Network connectivity lost")
            last_network_check = time.time()
    
    print("🐕 Watchdog stopped")


def cleanup_process(proc: subprocess.Popen):
    """Gracefully terminate FFmpeg process"""
    if proc.poll() is None:
        print("🛑 Stopping FFmpeg...")
        try:
            proc.terminate()
            proc.wait(timeout=5)
            print("✓ FFmpeg terminated gracefully")
        except subprocess.TimeoutExpired:
            print("⚠️ FFmpeg didn't stop, killing...")
            proc.kill()
            try:
                proc.wait(timeout=2)
            except Exception:
                pass


def run_streaming_session(tracks, stop_event: threading.Event) -> bool:
    """Run one streaming session"""
    
    if not tracks:
        print("❌ No tracks available")
        return False
    
    # Build concat file
    if not build_concat(tracks):
        return False
    
    # Write initial now playing
    write_nowplaying(tracks[0])
    
    # Build and start FFmpeg
    cmd = build_ffmpeg_cmd(tracks)
    
    print("▶️ Starting FFmpeg stream...")
    try:
        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
    except Exception as e:
        print(f"❌ Failed to start FFmpeg: {e}")
        return False
    
    # Start watchdog
    should_restart = threading.Event()
    
    def restart_trigger():
        should_restart.set()
        stop_event.set()
    
    watchdog = threading.Thread(
        target=watchdog_monitor,
        args=(proc, stop_event, restart_trigger),
        daemon=True
    )
    watchdog.start()
    
    # Monitor process
    try:
        while not stop_event.is_set():
            ret = proc.poll()
            if ret is not None:
                print(f"❌ FFmpeg exited with code {ret}")
                
                # Try to read error output
                try:
                    stderr = proc.stderr.read().decode()
                    if stderr:
                        print(f"FFmpeg error: {stderr[-500:]}")
                except Exception:
                    pass
                
                should_restart.set()
                break
            
            time.sleep(1)
    
    except KeyboardInterrupt:
        print("\n👋 Interrupted by user")
        stop_event.set()
    
    finally:
        cleanup_process(proc)
        try:
            watchdog.join(timeout=2)
        except Exception:
            pass
    
    return should_restart.is_set()


def run_loop():
    """Main streaming loop with auto-restart"""
    global global_stop
    
    restart_count = 0
    last_restart_time = 0
    
    # Signal handlers
    def signal_handler(sig, frame):
        global global_stop
        print("\n👋 Shutdown signal received")
        global_stop = True
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    while not global_stop:
        print("\n" + "="*60)
        print("🚀 Starting streaming session")
        print("="*60 + "\n")
        
        # Load tracks
        tracks = load_tracks()
        if not tracks:
            print("⚠️ No tracks found. Waiting 30 seconds...")
            time.sleep(30)
            continue
        
        # Check network
        if not check_network():
            print("⚠️ RTMP server unreachable. Waiting...")
            while not check_network() and not global_stop:
                time.sleep(10)
            if global_stop:
                break
        
        # Run session
        stop_event = threading.Event()
        should_restart = run_streaming_session(tracks, stop_event)
        
        if global_stop:
            break
        
        if not should_restart:
            print("❌ Session ended without restart request")
            break
        
        # Check restart limits
        current_time = time.time()
        if current_time - last_restart_time < RESTART_COOLDOWN:
            restart_count += 1
        else:
            restart_count = 1
        
        last_restart_time = current_time
        
        if restart_count > MAX_RESTART_ATTEMPTS:
            print(f"❌ Max restart attempts ({MAX_RESTART_ATTEMPTS}) reached")
            print("❌ Giving up. Check your configuration and network.")
            break
        
        print(f"\n🔄 Restarting stream (attempt {restart_count}/{MAX_RESTART_ATTEMPTS})")
        print(f"⏳ Waiting {RESTART_COOLDOWN}s...")
        
        # Cooldown with interrupt check
        for _ in range(RESTART_COOLDOWN):
            if global_stop:
                break
            time.sleep(1)


def main():
    print(f"\n🌙 LOFI STREAMER v{VERSION}")
    print("="*60 + "\n")
    
    load_config()
    
    if not SETTINGS["STREAM_URL"]:
        print("❌ STREAM_URL missing in config")
        print("💡 Add it to stream_config.txt:")
        print("   STREAM_URL=rtmp://your-stream-url/app/key")
        return
    
    # Validate directories
    for dir_path, name in [
        (PLAYLIST_DIR, "Playlist"),
        (LOGO_DIR, "Logo"),
        (VIDEO_DIR, "Video")
    ]:
        if not dir_path.exists():
            print(f"⚠️ {name} directory not found: {dir_path}")
            try:
                dir_path.mkdir(parents=True, exist_ok=True)
                print(f"✓ Created {name} directory")
            except Exception as e:
                print(f"❌ Failed to create {name} directory: {e}")
    
    print("\n▶️ Starting main loop...\n")
    
    try:
        run_loop()
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n👋 Streamer shut down\n")


if __name__ == "__main__":
    main()
