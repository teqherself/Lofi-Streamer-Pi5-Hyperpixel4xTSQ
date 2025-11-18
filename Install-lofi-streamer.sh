#!/usr/bin/env bash
set -euo pipefail

export DEBIAN_FRONTEND=noninteractive

if [[ $EUID -ne 0 ]]; then
  echo "❌ Please run this installer with sudo (root privileges required)."
  exit 1
fi

TARGET_USER="${LOFI_USER:-${SUDO_USER:-}}"
if [[ -z "$TARGET_USER" ]]; then
  echo "❌ Unable to detect the non-root user that should own the streamer."
  echo "   Re-run with sudo from that account or export LOFI_USER=<username>."
  exit 1
fi
if [[ "$TARGET_USER" == "root" ]]; then
  echo "❌ The streamer service should run as a non-root user."
  echo "   Please create a regular user and rerun the installer with sudo from that account"
  echo "   or set LOFI_USER to that username."
  exit 1
fi

HOME_DIR=$(getent passwd "$TARGET_USER" | cut -d: -f6)
if [[ -z "$HOME_DIR" || ! -d "$HOME_DIR" ]]; then
  echo "❌ Could not determine home directory for $TARGET_USER."
  exit 1
fi

BASE_DIR="$HOME_DIR/LofiStream"
REPO_URL="https://github.com/teqherself/Lofi-Streamer-Pi5-Hyperpixel4xTSQ.git"
REPO_DIR="$BASE_DIR/src"
SERVER_DIR="$BASE_DIR/Servers"
SOUNDS_DIR="$BASE_DIR/Sounds"
LOGO_DIR="$BASE_DIR/Logo"
VIDEOS_DIR="$BASE_DIR/Videos"
VENV_DIR="$BASE_DIR/venv"
SERVICE_FILE="/etc/systemd/system/lofi-streamer.service"
STREAM_URL_FILE="$BASE_DIR/stream_url.txt"

cat <<'BANNER'
----------------------------------------
  GENDEMIK DIGITAL — LOFI STREAMER SETUP
  Auto-user installer
----------------------------------------
BANNER

echo "👤 Target user: $TARGET_USER"
echo "🏠 Home directory: $HOME_DIR"
echo "📂 Install base: $BASE_DIR"

# --- SYSTEM DEPENDENCIES ---
echo "\n📦 Installing system dependencies..."
apt update
apt -y upgrade
apt install -y ffmpeg python3 python3-venv python3-pip git wget

# --- DIRECTORIES ---
echo "\n📁 Creating directory structure under $BASE_DIR ..."
mkdir -p "$SERVER_DIR" "$SOUNDS_DIR" "$LOGO_DIR" "$VIDEOS_DIR" "$REPO_DIR"

# --- REPO SYNC ---
echo "\n⬇️ Syncing Lofi Streamer repository..."
if [[ -d "$REPO_DIR/.git" ]]; then
  git -C "$REPO_DIR" fetch --depth=1 origin main
  git -C "$REPO_DIR" reset --hard FETCH_HEAD
else
  rm -rf "$REPO_DIR"
  git clone --depth=1 "$REPO_URL" "$REPO_DIR"
fi

install -m 755 "$REPO_DIR/lofi-streamer.py" "$SERVER_DIR/lofi-streamer.py"

# --- PYTHON VENV ---
echo "\n🐍 Creating virtual environment..."
python3 -m venv "$VENV_DIR"
"$VENV_DIR/bin/pip" install --upgrade pip
"$VENV_DIR/bin/pip" install mutagen

# --- STREAM URL FILE ---
if [[ ! -f "$STREAM_URL_FILE" ]]; then
  echo "⚠️ No stream_url.txt found — creating placeholder."
  echo "rtmp://a.rtmp.youtube.com/live2/YOUR_KEY_HERE" > "$STREAM_URL_FILE"
fi

# --- OWNERSHIP ---
chown -R "$TARGET_USER":"$TARGET_USER" "$BASE_DIR"

# --- SYSTEMD SERVICE ---
if systemctl is-active --quiet lofi-streamer.service; then
  echo "\n⏹ Stopping existing lofi-streamer.service before updating..."
  systemctl stop lofi-streamer.service || true
fi

echo "\n🛠 Writing systemd service..."
cat <<EOF2 > "$SERVICE_FILE"
[Unit]
Description=Lofi Streamer (GENDEMIK DIGITAL)
After=network-online.target
Wants=network-online.target

[Service]
User=$TARGET_USER
WorkingDirectory=$SERVER_DIR
ExecStart=$VENV_DIR/bin/python3 $SERVER_DIR/lofi-streamer.py
Restart=always
RestartSec=5
Environment=PYTHONUNBUFFERED=1
Environment=LOFI_STREAM_URL_FILE=$STREAM_URL_FILE

[Install]
WantedBy=multi-user.target
EOF2

# --- ENABLE SERVICE ---
systemctl daemon-reload
systemctl enable --now lofi-streamer.service

cat <<'DONE'

----------------------------------------
  🎉 INSTALL COMPLETE!
  Lofi Streamer is running as a service.

  ▶ Check status:
     sudo systemctl status lofi-streamer

  ▶ Logs:
     journalctl -u lofi-streamer -f

  ▶ Edit YouTube RTMP key:
     nano ~/LofiStream/stream_url.txt

----------------------------------------
