#!/usr/bin/env bash
set -e

echo "🔥 Uninstalling GENDEMIK DIGITAL - LOFI STREAMER"
echo ""

USER_NAME="woo"
USER_HOME="/home/$USER_NAME"
TARGET_DIR="$USER_HOME/LofiStream"
SERVICE_NAME="lofi-streamer.service"
SERVICE_PATH="/etc/systemd/system/$SERVICE_NAME"

# -------------------------
# STOP + DISABLE SERVICE
# -------------------------
if systemctl list-units --full -all | grep -Fq "$SERVICE_NAME"; then
    echo "🛑 Stopping service..."
    systemctl stop "$SERVICE_NAME" || true

    echo "🚫 Disabling service..."
    systemctl disable "$SERVICE_NAME" || true
else
    echo "ℹ️ Service not found, skipping stop/disable."
fi

# -------------------------
# REMOVE SERVICE FILE
# -------------------------
if [ -f "$SERVICE_PATH" ]; then
    echo "🗑 Removing systemd service file..."
    rm -f "$SERVICE_PATH"
else
    echo "ℹ️ Service file already removed."
fi

echo "🔄 Reloading systemd..."
systemctl daemon-reload

# -------------------------
# REMOVE STREAMER DIRECTORY
# -------------------------
if [ -d "$TARGET_DIR" ]; then
    echo "🗑 Removing LofiStreamer directory: $TARGET_DIR"
    rm -rf "$TARGET_DIR"
else
    echo "ℹ️ Streamer directory not found."
fi

# -------------------------
# CLEAN SYSTEMD LOGS (optional)
# -------------------------
echo "🧹 Cleaning old journal logs for this service..."
journalctl --vacuum-size=1M >/dev/null 2>&1 || true

# -------------------------
# DONE
# -------------------------
echo ""
echo "✅ LOFI STREAMER COMPLETELY REMOVED"
echo ""
echo "If you want to reinstall:"
echo "  sudo bash install-lofi-streamer.sh"
echo ""
