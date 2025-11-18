#!/usr/bin/env bash
set -euo pipefail

if [[ $EUID -ne 0 ]]; then
  echo "❌ Please run this uninstaller with sudo/root privileges."
  exit 1
fi

TARGET_USER="${LOFI_USER:-${SUDO_USER:-}}"
if [[ -z "$TARGET_USER" ]]; then
  echo "❌ Unable to detect the non-root user that owns the streamer files."
  echo "   Re-run with sudo from that account or export LOFI_USER=<username>."
  exit 1
fi
if [[ "$TARGET_USER" == "root" ]]; then
  echo "❌ The streamer service should be installed under a non-root account."
  echo "   Please set LOFI_USER to the original username (e.g. woo) and rerun."
  exit 1
fi

HOME_DIR=$(getent passwd "$TARGET_USER" | cut -d: -f6)
if [[ -z "$HOME_DIR" || ! -d "$HOME_DIR" ]]; then
  echo "❌ Could not determine home directory for $TARGET_USER."
  exit 1
fi

BASE_DIR="${LOFI_BASE_DIR:-$HOME_DIR/LofiStream}"
TARGET_DIR="$BASE_DIR"
SERVICE_NAME="${LOFI_SERVICE_NAME:-lofi-streamer.service}"
SERVICE_PATH="/etc/systemd/system/$SERVICE_NAME"

echo "🔥 Uninstalling GENDEMIK DIGITAL - LOFI STREAMER"
echo "👤 Target user: $TARGET_USER"
echo "📂 Install base: $BASE_DIR"
echo "🛠 Service name: $SERVICE_NAME"
echo ""

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
echo "  sudo ./Install-lofi-streamer.sh"
echo ""
