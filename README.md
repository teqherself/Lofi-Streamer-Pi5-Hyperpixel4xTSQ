# 🌙 Lofi Streamer — Raspberry Pi Full Project README

## Overview

Lofi Streamer is a fully automated Raspberry Pi–based streaming system designed to broadcast 24/7 lofi-style music and visuals to YouTube, Twitch, or any RTMP-compatible platform. It includes:

* **Independent background streamer service** powered by `lofi-streamer.py`
* **A Flask-based dashboard** to monitor status, control playback, change stream settings, and manage the server
* **A stable RTMP ffmpeg pipeline** to push your chosen audio + video to your RTMP endpoint
* **Crash‑resistant behaviour** — dashboard and stream server are isolated so if one crashes the other continues
* **Autostart systemd support** for streaming and dashboard components

This README documents the full architecture, install process, folder layout, and detailed specifications of `lofi-streamer.py`.

---

## 📁 Project Structure

```
LofiStream/
 ├── Dashboard/
 │    ├── dashboard.py
 │    ├── static/style.css
 │    └── templates/index.html
 ├── Servers/
 │    └── lofi-streamer.py
 ├── Videos/
 │    └── (background mp4 loops)
 ├── Sounds/
 │    └── (mp3 playlist files)
 ├── Logo/
 │    ├── LoFiLogo500.png
 │    └── LoFiLogo700.png
 ├── start-kiosk.sh
 └── README.md (this file)
```

---

## ✔️ Features

### Lofi Streamer Core (lofi-streamer.py)

* Auto‑loads all `.mp3` files from the Sounds folder
* Random shuffle playback with auto‑next-track switching
* Reads video file from `Videos/` (e.g., loopable MP4 artwork)
* Keeps the stream online using ffmpeg
* Crash recovery: automatically restarts ffmpeg if connection drops
* Logs activity and "Now Playing" output
* Checks network connectivity before attempting stream
* Displays friendly terminal output with status icons

### Dashboard

* Browser-based interface (Flask)
* Shows current track, uptime, stream health
* Allows start/stop/restart of the streamer service
* Lets you change RTMP URL + Stream Key live
* Lets you update or switch video background
* Monitors the lofi service via logs and heartbeat

---
diff --git a/README.md b/README.md
index 68b867866ec9496460e9d782dfd08142495b4b09..2cf21244eacadad2de8c093a5a2623ee9ea3b47f 100644
--- a/README.md
+++ b/README.md
@@ -39,50 +39,79 @@ LofiStream/
 
 ## ✔️ Features
 
 ### Lofi Streamer Core (lofi-streamer.py)
 
 * Auto‑loads all `.mp3` files from the Sounds folder
 * Random shuffle playback with auto‑next-track switching
 * Reads video file from `Videos/` (e.g., loopable MP4 artwork)
 * Keeps the stream online using ffmpeg
 * Crash recovery: automatically restarts ffmpeg if connection drops
 * Logs activity and "Now Playing" output
 * Checks network connectivity before attempting stream
 * Displays friendly terminal output with status icons
 
 ### Dashboard
 
 * Browser-based interface (Flask)
 * Shows current track, uptime, stream health
 * Allows start/stop/restart of the streamer service
 * Lets you change RTMP URL + Stream Key live
 * Lets you update or switch video background
 * Monitors the lofi service via logs and heartbeat
 
 ---
 
## ⚙️ Runtime Overrides

`lofi-streamer.py` ships with sensible defaults for a Raspberry Pi install, but
every file path and connection target can be overridden at runtime using
environment variables. This makes it easy to test locally or run on a different
user account without editing the script.

| Variable | Default | Purpose |
| --- | --- | --- |
| `LOFI_PLAYLIST_DIR` | `/home/woo/LofiStream/Sounds` | Directory scanned for audio tracks |
| `LOFI_VIDEO_FILE` | `/home/woo/LofiStream/Videos/Lofi3.mp4` | Looping background video |
| `LOFI_BRAND_IMAGE` | `/home/woo/LofiStream/Logo/LoFiLogo700.png` | Overlay PNG logo |
| `LOFI_YOUTUBE_URL` | `rtmp://a.rtmp.youtube.com/live2/...` | Destination RTMP endpoint |
| `LOFI_TRACK_FILE` | `/tmp/current_track.txt` | Temporary file used by `drawtext` |
| `LOFI_PLAYLIST_FILE` | `/tmp/lofi_playlist.txt` | Generated concat file for audio |
| `LOFI_FONT_PATH` | `/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf` | Font used for track overlay |
| `LOFI_CHECK_HOST` | `a.rtmp.youtube.com` | Host probed before streaming |
| `LOFI_CHECK_PORT` | `1935` | TCP port probed before streaming |

+Example usage:

```bash
export LOFI_PLAYLIST_DIR="$HOME/Music/Lofi"
export LOFI_YOUTUBE_URL="rtmp://b.rtmp.youtube.com/live2/test-key"
python3 lofi-Streamer.py
```

 ## 🔧 Installation
 
 ### 1. Install dependencies
 
 ```bash
 sudo apt update
 sudo apt install -y python3 python3-pip ffmpeg
 pip3 install flask
 ```
 
 ### 2. Ensure folder layout exists
 
 ```bash
 mkdir -p ~/LofiStream/{Sounds,Videos,Servers,Dashboard,Logo}
 ```
 
 ### 3. Place your project files
 
 * Audio → `Sounds/`
 * Video loops → `Videos/`
 * Python streamer → `Servers/lofi-streamer.py`
 * Dashboard Flask app → `Dashboard/dashboard.py`
 
 ### 4. Test run manually

```bash
python3 ~/LofiStream/Servers/lofi-streamer.py
```

You should see something like:

```
🌙 LOFI STREAMER v3.0 — GENDEMIK DIGITAL
🌐 Checking network connectivity to RTMP host...
🎶 Loaded 71 tracks from playlist directory.
📡 Starting YouTube stream via ffmpeg...
🎧 Now playing: ExampleTrack.mp3 (180s)
```

---

## 🔥 Systemd Autostart

Create service file:

```
sudo nano /etc/systemd/system/lofi-streamer.service
```

Example service:

```
[Unit]
Description=Lofi Streamer (GendemiK Digital)
After=network-online.target

[Service]
ExecStart=/usr/bin/python3 /home/woo/LofiStream/Servers/lofi-streamer.py
WorkingDirectory=/home/woo/LofiStream/Servers
Restart=always
User=woo

[Install]
WantedBy=multi-user.target
```

Enable + start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable lofi-streamer
sudo systemctl start lofi-streamer
```

Check status:

```bash
systemctl status lofi-streamer
```

---

## 🧠 Detailed lofi-streamer.py Specs

### Version

```
LOFI STREAMER v3.0 — GENDEMIK DIGITAL
```

### Functional Breakdown

#### ✔ Network Check

* Pings the RTMP server host
* Retries until the network is online
* Prevents ffmpeg from starting if no Internet

#### ✔ Playlist Loader

* Scans `~/LofiStream/Sounds/` for `.mp3`
* Skips malformed or zero-byte files
* Builds internal playlist list

#### ✔ Random Track Sequencing

* Randomises track order on start
* Moves sequentially through tracks
* Auto‑loops playlist at end

#### ✔ Audio Playback Timing

* Automatically reads duration metadata via ffprobe
* Sleeps until track end
* Immediately switches to next track

#### ✔ FFmpeg Stream Pipeline

The module generates a command similar to:

```
ffmpeg -re -stream_loop -1 -i video.mp4 -i current_track.mp3 \
  -c:v libx264 -preset veryfast -b:v 4500k -c:a aac -b:a 160k \
  -pix_fmt yuv420p -f flv rtmp://<server>/<key>
```

#### ✔ Crash Protection

* If ffmpeg dies → restart it
* If a track fails → skip it
* If RTMP server disconnects → retry

#### ✔ Logging

Creates or updates:

```
~/LofiStream/Servers/lofi-stream.log
```

Log includes:

* Timestamps
* Track names
* Stream errors
* Restart events

#### ✔ Terminal Output

Examples:

```
🎧 Now playing: ._Muted - Belonging.mp3 (180s)
📡 Stream online via ffmpeg
❗ Lost connection — attempting restart...
```

---

## 🌐 Dashboard API Integration

The dashboard communicates using:

* `/status` — Get current track + streamer state
* `/start` — Start systemd streamer
* `/stop` — Stop systemd streamer
* `/restart` — Restart streamer
* `/set_rtmp` — Update stream URL/key
* `/logs` — Live log tail

Dashboard does **not** run inside the same process as the streamer. Isolation ensures reliability.

---

## 🚀 Start Dashboard

```bash
python3 ~/LofiStream/Dashboard/dashboard.py
```

Access in browser:

```
http://<pi-address>:5000
```

---

## 🟦 Kiosk Mode (optional)

If using a HyperPixel or touchscreen:

```bash
~/LofiStream/start-kiosk.sh
```

This launches Chromium in kiosk fullscreen showing the dashboard.

---

## 🎵 Adding Your Own Lofi Playlist

Drop any `.mp3` file into:

```
~/LofiStream/Sounds/
```

The streamer detects them automatically on next restart.

---

## 🎞 Adding New Background Videos

Place `.mp4` loop files into:

```
~/LofiStream/Videos/
```

The dashboard can be extended to switch videos on the fly.

---

## 🧩 Future Planned Features

* Web‑based playlist editor
* Real‑time audio spectrum overlays
* Animated lofi character loop generator
* Stream quality presets selector
* Remote control app (mobile)

---

## 👤 Author

**Ms. Stevie Woo (GendemiK Digital/Teqherself)**

Custom Raspberry Pi pipelines, creative streaming tools, and lofi engineering magic.

---

## 📜 Licence

MIT License — Free to use, modify, improve.
