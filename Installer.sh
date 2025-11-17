#!/usr/bin/env bash
set -e

echo "🌙 GENDEMIK DIGITAL — LOFI STREAMER INSTALLER"
echo "----------------------------------------------"
sleep 1

# ---------- VARIABLES ----------
PROJECT_DIR="/home/$USER/LofiStream"
SERVERS_DIR="$PROJECT_DIR/Servers"
SOUNDS_DIR="$PROJECT_DIR/Sounds"
VIDEOS_DIR="$PROJECT_DIR/Videos"
LOGO_DIR="$PROJECT_DIR/Logo"

SERVICE_FILE="/etc/systemd/system/lofi-streamer.service"

REPO_URL="https://raw.githubusercontent.com/teqherself/Lofi-Streamer-Pi5-Hyperpixel4xTSQ/main"

# ---------- UPDATE SYSTEM ----------
echo "🔄 Updating system packages..."
sudo apt update -y
sudo apt upgrade -y

# ---------- INSTALL DEPENDENCIES ----------
echo "📦 Installing dependencies..."
sudo apt install -y \
    ffmpeg \
    python3 \
    python3-pip \
    python3-venv \
    python3-mutagen \
    fonts-dejavu-core

# ---------- CREATE PROJECT STRUCTURE ----------
echo "📁 Creating LofiStream folder structure..."

mkdir -p "$SERVERS_DIR"
mkdir -p "$SOUNDS_DIR"
mkdir -p "$VIDEOS_DIR"
mkdir -p "$LOGO_DIR"

# ---------- DOWNLOAD MAIN SCRIPT ----------
echo "⬇️ Downloading lofi-streamer.py..."
curl -sSL "$REPO_URL/lofi-streamer.py" -o "$SERVERS_DIR/lofi-streamer.py"
chmod +x "$SERVERS_DIR/lofi-streamer.py"

# ---------- CREATE stream_url.txt IF MISSING ----------
if [ ! -f "$PROJECT_DIR/stream_url.txt" ]; then
    echo "📄 Creating stream_url.txt (blank)…"
    echo "" > "$PROJECT_DIR/stream_url.txt"
fi

# ---------- OPTIONAL: PLACEHOLDER LOGO ----------
if [ ! -f "$LOGO_DIR/LoFiLogo700.png" ]; then
    echo "⚠️ No logo found. Adding placeholder..."
    convert -size 700x200 xc:black "$LOGO_DIR/LoFiLogo700.png" 2>/dev/null || true
fi

# ---------- PYTHON VENV ----------
echo "🐍 Creating Python venv..."
python3 -m venv "$PROJECT_DIR/venv"
source "$PROJECT_DIR/venv/bin/activate"

echo "📦 Installing Python requirements..."
pip install --upgrade pip mutagen

deactivate

# ---------- SYSTEMD SERVICE ----------
echo "🛠 Creating systemd service: lofi-streamer.service"

sudo bash -c "cat > $SERVICE_FILE" <<EOF
[Unit]
Description=Gendemik Digital - Lofi Streamer
After=network-online.target
Wants=network-online.target

[Service]
User=$USER
WorkingDirectory=$PROJECT_DIR
Environment=PYTHONUNBUFFERED=1
ExecStart=$PROJECT_DIR/venv/bin/python3 $SERVERS_DIR/lofi-streamer.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable lofi-streamer

echo "🎉 Installer complete!"
echo ""
echo "To START the streamer now:"
echo "   sudo systemctl start lofi-streamer"
echo ""
echo "To check logs:"
echo "   journalctl -u lofi-streamer -f"
echo ""
echo "⚙️ IMPORTANT: Edit your RTMP stream key at:"
echo "   $PROJECT_DIR/stream_url.txt"
echo ""
echo "❤️ Gendemik Digital — Crafted for you, Stevie."
