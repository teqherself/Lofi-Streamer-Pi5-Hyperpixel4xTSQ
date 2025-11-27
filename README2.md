🎧 GENDEMIK DIGITAL — Lofi Streamer + Dashboard Suite UPCOMING UPDATE
Raspberry Pi 4 / 5 • Picamera2 • YouTube RTMP Streaming

Maintainer: Ms Stevie Woo — Manchester, UK
Brand: GENDEMIK DIGITAL

<p align="center">
  <img src="https://img.shields.io/badge/Platform-Raspberry%20Pi-red?style=for-the-badge&logo=raspberrypi">
  <img src="https://img.shields.io/badge/Python-3.11-blue?style=for-the-badge&logo=python">
  <img src="https://img.shields.io/badge/Picamera2-Video%20First-purple?style=for-the-badge">
  <img src="https://img.shields.io/badge/Streaming-YouTube%20RTMP-yellow?style=for-the-badge&logo=youtube">
  <img src="https://img.shields.io/badge/Service-systemd-orange?style=for-the-badge">
</p>

## Overview

Picture a tiny Pi on your shelf, quietly breathing life into a 24/7 lo-fi chill stream: the camera frames your space, the audio deck rotates your playlist, and a protective audio chain keeps the vibe smooth. If the network wobbles, the stream stitches itself back together; if you want visibility or remote control, a web dashboard gives you a cockpit. That is the GENDEMIK DIGITAL Lofi Streamer Suite.

The suite combines two pieces:

- **Lofi Streamer (core engine)** — a self-healing RTMP pipeline that captures Picamera2 video, blends in overlays, normalizes audio, and keeps broadcasting without human babysitting.
- **Dashboard Add-On (web controller)** — a minimal, passworded web UI to start/stop the streamer, check system health, and see what track is playing.

## Features

### 🎥 Lofi Streamer (core)

- Stable Picamera2 pipeline (Video-First): 960×540 MJPEG capture → ffmpeg → H.264 RTMP output
- Audio playlist from `~/LofiStream/Sounds/*.mp3` with auto-refresh when new tracks are added
- Safe Audio Engine: `dynaudnorm` smoothing + `alimiter=limit=0.95` hard protection
- Overlays: Now Playing text, mini audio bar, top-right transparent logo
- Network watchdog and fallback logic to keep the stream alive
- Designed for set-and-forget weekend vibes—once you start it, it looks after itself

### 🖥️ Dashboard Add-On (optional)

- Password-protected login (PBKDF2 SHA-256)
- Start/Stop/Restart the streamer systemd service
- Live system metrics and recent streamer logs (last 40 lines)
- Camera + service status indicators and safe system reboot button
- Shows the currently playing track with an auto-updating interface

## Installation Options

Choose one path below depending on whether you want the dashboard.

### ▶️ Option A — Install only the streamer

Use this if you don’t want a dashboard.

```bash
bash <(wget -qO- https://raw.githubusercontent.com/teqherself/Lofi-Streamer/main/install.sh)
```

This installs:

- `~/LofiStream/`
  - `Servers/lofi-streamer.py`
  - `Sounds/`
  - `Videos/`
  - `Logo/`
  - `stream_url.txt`

And registers the `lofi-streamer.service` systemd unit.

### ▶️ Option B — Install only the dashboard add-on

Use this **after** you have installed the streamer.

```bash
bash <(wget -qO- https://raw.githubusercontent.com/teqherself/Lofi-Streamer-Pi4-dashboard/main/install.sh)
```

This installs:

- `~/LofiStream/Dashboard/`
  - `dashboard.py`
  - `system_helper.sh`
  - `templates/`
  - `static/`
- `lofi-dashboard.service`
- `/etc/sudoers.d/lofi-dashboard`

Dashboard opens at `http://<Pi-IP>:4455`.

### ▶️ Option C — Install both (streamer first, then dashboard)

1️⃣ Install streamer

2️⃣ Install dashboard

Done.

## Directory Layout

```
LofiStream/
├── Servers/
│   └── lofi-streamer.py
├── Sounds/
│   ├── *.mp3
├── Logo/
│   └── TestLogo200.png
├── stream_url.txt
└── Dashboard/        (optional)
    ├── dashboard.py
    ├── system_helper.sh
    ├── templates/
    │   ├── index.html
    │   └── login.html
    └── static/
        └── style.css
```

## Systemd Services

**Streamer**

```bash
sudo systemctl start lofi-streamer
sudo systemctl stop lofi-streamer
sudo systemctl restart lofi-streamer
journalctl -u lofi-streamer -n 40 --no-pager
```

**Dashboard**

```bash
sudo systemctl restart lofi-dashboard
sudo systemctl status lofi-dashboard
journalctl -u lofi-dashboard -n 50 --no-pager
```

## Using the Dashboard

1. Open `http://<pi-ip>:4455`.
2. Log in with your configured credentials.
3. Use the controls to:
   - Start / Stop / Restart the streamer
   - Reboot the system safely
   - View the live track, metrics, and recent logs
4. Monitor your stream and Pi health in real time.

## Troubleshooting

- ❌ Dashboard won’t load → `sudo systemctl status lofi-dashboard`
- ❌ Buttons don’t work → check sudoers file with `cat /etc/sudoers.d/lofi-dashboard`
- ❌ Streamer not running → `sudo systemctl status lofi-streamer`
- ❌ No camera → ensure nothing else is using `/dev/media*` or `/dev/video*`:

  ```bash
  sudo lsof /dev/video* /dev/media*
  ```

## Uninstall

**Remove Dashboard**

```bash
sudo systemctl stop lofi-dashboard
sudo systemctl disable lofi-dashboard
sudo rm /etc/systemd/system/lofi-dashboard.service
sudo rm /etc/sudoers.d/lofi-dashboard
rm -rf ~/LofiStream/Dashboard
sudo systemctl daemon-reload
```

**Remove Streamer**

```bash
sudo systemctl stop lofi-streamer
sudo systemctl disable lofi-streamer
sudo rm /etc/systemd/system/lofi-streamer.service
rm -rf ~/LofiStream
sudo systemctl daemon-reload
```

## Roadmap

- Multi-stream YouTube channel selector
- Dark mode dashboard
- Camera preview tile
- On-Pi settings editor (no SSH needed)
- Over-the-air streamer updater
- Remote config sync
- Touch-friendly control mode

## Support

If this project helps you, consider supporting GENDEMIK DIGITAL.
