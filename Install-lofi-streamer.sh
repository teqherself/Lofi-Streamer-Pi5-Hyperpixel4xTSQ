#!/usr/bin/env bash
set -e

echo "----------------------------------------"
echo "  GENDEMIK DIGITAL — LOFI STREAMER SETUP"
echo "  Auto-user installer"
echo "----------------------------------------"

# --- DETECT USER ---
USER_NAME=$(whoami)
HOME_DIR="/home/$USER_NAME"

echo "👤 Detected user: $USER_NAME"
echo "🏠 Home directory: $HOME_DIR"
echo ""

# --- DIRECTORIES ---
BASE_DIR="$HOME_DIR/LofiStream"
SERVER_DIR="$BASE_DIR/Servers"
SOUNDS_DIR="$BASE_DIR/Sounds"
LOGO_DIR="$BASE_DIR/Logo"
VIDEOS_DIR="$BASE_DIR/Videos"

echo "📁 Creating directory structure..."
mkdir -p "$SERVER_DIR" "$SOUNDS_DIR" "$LOGO_DIR" "$VIDEOS_DIR"

# --- SYSTEM DEPENDENCIES ---
echo "📦 Installing system dependencies..."
sudo apt update && upgrade
sudo apt install -y ffmpeg python3 python3-venv python3-pip python3-mutagen wget

# --- PYTHON VENV ---
echo "🐍 Creating virtual environment..."
python3 -m venv "$BASE_DIR/venv"
source "$BASE_DIR/venv/bin/activate"

pip install --upgrade pip
pip install python3-mutagen

deactivate

# --- DOWNLOAD STREAMER ---
echo "⬇️ Downloading latest lofi-streamer.py from GitHub..."
wget -O "$SERVER_DIR/lofi-streamer.py" \
  https://raw.githubusercontent.com/teqherself/Lofi-Streamer-Pi5-Hyperpixel4xTSQ/main/lofi-streamer.py

chmod +x "$SERVER_DIR/lofi-streamer.py"

# --- STREAM URL FILE ---
if [ ! -f "$BASE_DIR/stream_url.txt" ]; then
    echo "⚠️ No stream_url.txt found — creating placeholder."
    echo "rtmp://a.rtmp.youtube.com/live2/YOUR_KEY_HERE" > "$BASE_DIR/stream_url.txt"
fi

# --- SYSTEMD SERVICE ---
echo "🛠 Creating systemd service..."

SERVICE_FILE=/etc/systemd/system/lofi-streamer.service

sudo bash -c "cat > $SERVICE_FILE" <<EOF
[Unit]
Description=Lofi Streamer (GENDEMIK DIGITAL)
After=network-online.target
Wwants=network-online.target

[Service]
User=$USER_NAME
WorkingDirectory=$SERVER_DIR
ExecStart=$BASE_DIR/venv/bin/python3 $SERVER_DIR/lofi-streamer.py
Restart=always
RestartSec=5
Environment=LOFI_STREAM_URL_FILE=$BASE_DIR/stream_url.txt

[Install]
WantedBy=multi-user.target
EOF

# --- ENABLE SERVICE ---
sudo systemctl daemon-reload
sudo systemctl enable lofi-streamer.service

echo ""
echo "🚀 Starting Lofi Streamer..."
sudo systemctl start lofi-streamer.service

echo ""
echo "----------------------------------------"
echo "  🎉 INSTALL COMPLETE!"
echo "  Lofi Streamer is running as a service."
echo ""
echo "  ▶ Check status:"
echo "     sudo systemctl status lofi-streamer"
echo ""
echo "  ▶ Logs:"
echo "     journalctl -u lofi-streamer -f"
echo ""
echo "  ▶ Edit YouTube RTMP key:"
echo "     nano $BASE_DIR/stream_url.txt"
echo ""
echo "----------------------------------------"
