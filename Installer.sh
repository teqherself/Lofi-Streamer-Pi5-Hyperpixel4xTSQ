#!/bin/bash
set -e

echo "🌙 Lofi Streamer Installer — Pi 5 + HyperPixel 4.0 Square"
echo "----------------------------------------------------------"

# --- VARIABLES ---
USER_NAME="woo"
HOME_DIR="/home/$USER_NAME"
BASE_DIR="$HOME_DIR/LofiStream"
VENV_DIR="$BASE_DIR/venv"
SERVICE_FILE="/etc/systemd/system/lofi-streamer.service"
REPO_URL="https://github.com/teqherself/Lofi-Streamer-Pi5-Hyperpixel4xTSQ.git"

# --- CHECK USER ---
if [ "$(whoami)" != "root" ]; then
    echo "❌ Please run with sudo:"
    echo "   sudo ./install-lofi-streamer.sh"
    exit 1
fi

# --- UPDATE SYSTEM ---
echo "📦 Updating system..."
apt update -y
apt upgrade -y

# --- INSTALL DEPENDENCIES ---
echo "📦 Installing dependencies..."
apt install -y python3 python3-pip python3-venv ffmpeg git

# --- CREATE PROJECT FOLDER ---
echo "📁 Creating project directory: $BASE_DIR"
mkdir -p "$BASE_DIR"

# --- CLONE GITHUB REPO ---
echo "📥 Cloning Lofi Streamer repo..."
if [ -d "$BASE_DIR/.git" ]; then
    echo "🔄 Repo exists — pulling latest..."
    git -C "$BASE_DIR" pull
else
    git clone "$REPO_URL" "$BASE_DIR"
fi

# --- CREATE FOLDER STRUCTURE ---
echo "📁 Ensuring required folders exist..."
mkdir -p "$BASE_DIR/Sounds"
mkdir -p "$BASE_DIR/Videos"
mkdir -p "$BASE_DIR/Logo"

# --- CREATE VENV ---
echo "🐍 Creating Python virtual environment..."
python3 -m venv "$VENV_DIR"
source "$VENV_DIR/bin/activate"

# --- INSTALL PYTHON PACKAGES ---
echo "🐍 Installing Python libraries..."
pip install --upgrade pip
pip install mutagen

deactivate

# --- CREATE STREAM URL FILE ---
if [ ! -f "$BASE_DIR/stream_url.txt" ]; then
    echo "📝 Creating stream_url.txt (empty)"
    echo "" > "$BASE_DIR/stream_url.txt"
fi

# --- FIX PERMISSIONS ---
echo "🔧 Fixing permissions..."
chown -R "$USER_NAME:$USER_NAME" "$BASE_DIR"

# --- SYSTEMD SERVICE ---
echo "⚙️ Creating systemd service: lofi-streamer.service"
cat > "$SERVICE_FILE" <<EOF
[Unit]
Description=Lofi YouTube Streamer
After=network-online.target

[Service]
Type=simple
User=$USER_NAME
WorkingDirectory=$BASE_DIR
ExecStart=$VENV_DIR/bin/python3 $BASE_DIR/lofi-streamer.py
Restart=always
RestartSec=5
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF

# --- ENABLE SERVICE ---
echo "🔧 Enabling service..."
systemctl daemon-reload
systemctl enable lofi-streamer.service

echo ""
echo "🎉 Installation complete!"
echo "-----------------------------------------"
echo "To start streaming now:"
echo "   sudo systemctl start lofi-streamer"
echo ""
echo "To check status:"
echo "   systemctl status lofi-streamer"
echo ""
echo "Add your YouTube RTMP URL to:"
echo "   $BASE_DIR/stream_url.txt"
echo ""
echo "Add MP3 files to:"
echo "   $BASE_DIR/Sounds"
echo ""
echo "Add your background video to:"
echo "   $BASE_DIR/Videos/Lofi3.mp4"
echo ""
echo "Add your PNG logo to:"
echo "   $BASE_DIR/Logo/LoFiLogo700.png"
echo ""
echo "🔥 You're ready to stream!"
echo "-----------------------------------------"
