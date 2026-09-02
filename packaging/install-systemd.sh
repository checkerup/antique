#!/usr/bin/env bash
# ============================================================
#  antique - Linux systemd installer
#
#  Installs antique as a hardened systemd service under /opt/antique.
#  Creates a dedicated 'antique' system user with no shell login.
#
#  Usage (as root or via sudo):
#    sudo bash packaging/install-systemd.sh
#
#  After install:
#    sudo systemctl enable --now antique
#    curl http://127.0.0.1:8080/health
# ============================================================
set -euo pipefail

INSTALL_DIR="/opt/antique"
DATA_DIR="/var/lib/antique"
SERVICE_USER="antique"
SERVICE_GROUP="antique"
SERVICE_FILE="/etc/systemd/system/antique.service"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "=== antique systemd installer ==="

# --- Check root ---
if [ "$(id -u)" -ne 0 ]; then
    echo "[ERROR] Run this script as root: sudo bash $0"
    exit 1
fi

# --- Check Python ---
if ! command -v python3 &>/dev/null; then
    echo "[ERROR] python3 not found. Install Python 3.10+."
    exit 1
fi
PY_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
echo "[info] Python version: $PY_VERSION"

# --- Create service user ---
if ! id -u "$SERVICE_USER" &>/dev/null; then
    echo "[install] Creating system user: $SERVICE_USER"
    useradd --system --no-create-home --shell /usr/sbin/nologin "$SERVICE_USER"
else
    echo "[install] User $SERVICE_USER already exists"
fi

# --- Create directories ---
echo "[install] Creating directories ..."
mkdir -p "$INSTALL_DIR"
mkdir -p "$DATA_DIR"

# --- Copy application files ---
echo "[install] Copying application to $INSTALL_DIR ..."
rsync -a --exclude='.venv' --exclude='data' --exclude='.git' \
    --exclude='dist' --exclude='build' --exclude='__pycache__' \
    --exclude='*.egg-info' \
    "$REPO_DIR/" "$INSTALL_DIR/"

# --- Create venv ---
if [ ! -f "$INSTALL_DIR/.venv/bin/python" ]; then
    echo "[install] Creating virtualenv ..."
    python3 -m venv "$INSTALL_DIR/.venv"
fi

# --- Install dependencies (pinned) ---
echo "[install] Installing dependencies (pinned via lock file) ..."
"$INSTALL_DIR/.venv/bin/pip" install --upgrade pip -q
if [ -f "$INSTALL_DIR/packaging/requirements-lock.txt" ]; then
    "$INSTALL_DIR/.venv/bin/pip" install -c "$INSTALL_DIR/packaging/requirements-lock.txt" \
        -r "$INSTALL_DIR/requirements.txt"
else
    "$INSTALL_DIR/.venv/bin/pip" install -r "$INSTALL_DIR/requirements.txt"
fi
"$INSTALL_DIR/.venv/bin/pip" install -e "$INSTALL_DIR" --no-deps

# --- Install Playwright Chromium + system deps ---
echo "[install] Installing Playwright system dependencies ..."
python3 -m playwright install-deps chromium 2>/dev/null || true
"$INSTALL_DIR/.venv/bin/python" -m playwright install chromium

# --- Set ownership ---
chown -R "$SERVICE_USER:$SERVICE_GROUP" "$INSTALL_DIR"
chown -R "$SERVICE_USER:$SERVICE_GROUP" "$DATA_DIR"
chmod 750 "$INSTALL_DIR"
chmod 700 "$DATA_DIR"

# --- Install systemd unit ---
echo "[install] Installing systemd unit ..."
cp "$SCRIPT_DIR/antique.service" "$SERVICE_FILE"
chmod 644 "$SERVICE_FILE"

# --- Reload + enable ---
systemctl daemon-reload
echo "[install] Enabling antique.service ..."
systemctl enable antique

echo ""
echo "  ==============================================="
echo "   Install complete!"
echo "   Start:    sudo systemctl start antique"
echo "   Status:   sudo systemctl status antique"
echo "   Health:   curl http://127.0.0.1:8080/health"
echo "   Logs:     sudo journalctl -u antique -f"
echo "  ==============================================="
echo ""
echo "  Edit $SERVICE_FILE to set ANTIQUE_API_TOKEN before"
echo "  exposing the API port beyond localhost."
echo ""

exit 0
