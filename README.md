# Installation Guide — Lofi Streamer Pi5 + HyperPixel 4" TSQ

This guide explains how to deploy the automated **Lofi Streamer** service on a Raspberry Pi using the bundled `Install-lofi-streamer.sh` script. Follow these steps from a fresh Raspberry Pi OS (64-bit) install connected to the internet.

---
## 1. Prep the Pi
1. Update the system packages and install git.
   ```bash
   sudo apt update && sudo apt install -y git
   ```
2. Obtain the installer script:
   - **Option A:** Clone the repo for full access to all files.
   - **Option B:** Download just the script directly from GitHub:
     ```bash
     wget https://raw.githubusercontent.com/teqherself/Lofi-Streamer-Pi5-Hyperpixel4xTSQ/main/Install-lofi-streamer.sh
     ```

---
## 2. Review script defaults
The installer assumes a dedicated user account:

| Variable | Default | Description |
| --- | --- | --- |
| `USER_NAME` | `woo` | Account that will own/run the streamer |
| `USER_HOME` | `/home/$USER_NAME` | Home directory for the service files |
| `TARGET_DIR` | `$USER_HOME/LofiStream` | Installation root |
| `REPO_URL` | `https://github.com/teqherself/Lofi-Streamer-Pi5-Hyperpixel4xTSQ.git` | Source repo |
| `SERVICE_NAME` | `lofi-streamer.service` | systemd unit name |
| `VENV_DIR` | `$TARGET_DIR/venv` | Python virtualenv location |
| `PY_SCRIPT` | `$TARGET_DIR/lofi-streamer.py` | Streamer entry point |

Adjust the `USER_NAME` (and optionally paths) inside the script if your Pi uses a different account.

---
## 3. Run the installer
1. Make the script executable:
   ```bash
   chmod +x Install-lofi-streamer.sh
   ```
2. Execute with sudo so it can install packages and configure systemd:
   ```bash
   sudo ./Install-lofi-streamer.sh
   ```

The script performs the following actions:
- Installs required packages (`ffmpeg`, Python 3, venv tooling, git)
- Clones or updates the repo into `$TARGET_DIR`
- Creates a Python virtual environment and installs `mutagen`
- Fixes ownership/permissions so the target user controls the files
- Creates `/etc/systemd/system/lofi-streamer.service`
- Enables and starts the service so it launches on boot

---
## 4. Verify the service
Check that the streamer started successfully:
```bash
sudo systemctl status lofi-streamer.service
```
Follow the logs live:
```bash
sudo journalctl -fu lofi-streamer.service
```
If you need to restart or stop the service:
```bash
sudo systemctl restart lofi-streamer.service
sudo systemctl stop lofi-streamer.service
```

---
## 5. Customize your content
After installation, your project files live in `$HOME/LofiStream`. Populate the directories used by `lofi-streamer.py`:
- `Sounds/` — MP3 playlist
- `Videos/` — Looping MP4 background
- `Logo/` — Overlay graphics

Restart the service after making major changes so it reloads assets.

---
## 6. Updating later
To pull the latest code, rerun the installer or manually `git pull` inside `$TARGET_DIR`. The script is idempotent: it will update the repo, refresh the virtualenv, and restart the service when executed again.

---
## Troubleshooting tips
- Ensure the specified user exists and can access `/home/$USER_NAME`.
- Confirm your RTMP destination (YouTube, Twitch, etc.) is reachable from the Pi network.
- Use the environment variables documented in `README.md` to override audio/video directories or RTMP endpoints without editing the script.

Enjoy your always-on lofi stream! 🌙
