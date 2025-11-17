#!/usr/bin/env bash
set -e

echo "🌙 Installing LOFI STREAMER — GENDEMIK DIGITAL"
echo "For Raspberry Pi 4/5 + HyperPixel (or HDMI)"
echo ""

# -------------------------
# VARIABLES
# -------------------------
USER_NAME="woo"
USER_HOME="/home/$USER_NAME"
TARGET_DIR="$USER_HOME/LofiStream"
REPO_URL="https://github.com/teqherself/Lofi-Streamer-Pi5-Hyperpixel4xTSQ.git"
SERVICE_NAME="lofi-streamer.service"
VENV_DIR="$TARGET_DIR/venv"
PY_SCRIPT="$TARGET_DIR/lofi-streamer.py"

# -------------------------
# INSTALL PACKAGES
# -------------------------
echo "📦 Updating system + installing dependencies..."
apt update -y
apt install -y ffmpeg python3 python3-pip python3-venv git

echo "📦 Installing Python dependencies (mutagen)..."

# -------------------------
# CLONE / UPDATE REPO
# -------------------------
if [ ! -d "$TARGET_DIR" ]; then
    echo "📥 Cloning repository..."
    git clone "$REPO_URL" "$TARGET_DIR"
else
    echo "🔄 Repository exists — updating..."
    cd "$TARGET_DIR"
    git pull
fi

# -------------------------
# VIRTUAL ENV SETUP
# -------------------------
echo "🐍 Creating Python venv..."
python3 -m venv "$VENV_DIR"

echo "🐍 Installing Python requirements..."
"$VENV_DIR/bin/pip" install --upgrade pip mutagen

# -------------------------
# PERMISSIONS
# -------------------------
echo "🔐 Fixing file permissions..."
chown -R "$USER_NAME":"$USER_NAME" "$TARGET_DIR"
chmod +x "$PY_SCRIPT"

# -------------------------
# SYSTEMD SERVICE
# -------------------------
echo "🛠 Creating systemd service..."

SERVICE_PATH="/etc/systemd/system/$SERVICE_NAME"

cat <<EOF > "$SERVICE_PATH"
[Unit]
Description=GENDEMIK DIGITAL - Lofi Streamer
After=network-online.target time-sync.target
Wants=network-online.target

[Service]
User=$USER_NAME
WorkingDirectory=$TARGET_DIR
Environment="PYTHONUNBUFFERED=1"
ExecStart=$VENV_DIR/bin/python3 $PY_SCRIPT
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

# -------------------------
# ENABLE SERVICE
# -------------------------
echo "🚀 Enabling & starting service..."
systemctl daemon-reload
systemctl enable $SERVICE_NAME
systemctl start $SERVICE_NAME

# -------------------------
# DONE
# -------------------------
echo ""
echo "✨ LOFI STREAMER INSTALLED!"
echo "📡 It now starts automatically at boot."
echo ""
echo "Check status with:"
echo "   sudo systemctl status $SERVICE_NAME"
echo ""
echo "Logs live at:"
echo "   journalctl -fu $SERVICE_NAME"
echo ""
echo "Your streamer files live in:"
echo "   $TARGET_DIR"
