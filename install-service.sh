#!/bin/bash
# Installs deskinfopoint as a systemd service that starts on boot.
# Run once on the Raspberry Pi: bash install-service.sh
set -e

SERVICE_NAME="deskinfopoint"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"
PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_PYTHON="${PROJECT_DIR}/.venv/bin/python"
CONFIG="${PROJECT_DIR}/config.yaml"
RUN_USER="$(whoami)"

echo "Project dir : $PROJECT_DIR"
echo "Python      : $VENV_PYTHON"
echo "Config      : $CONFIG"
echo "Service user: $RUN_USER"
echo ""

if [ ! -f "$VENV_PYTHON" ]; then
    echo "ERROR: venv not found at $VENV_PYTHON" >&2
    echo "Run: python3 -m venv --system-site-packages .venv && .venv/bin/pip install -e ." >&2
    exit 1
fi

if [ ! -f "$CONFIG" ]; then
    echo "ERROR: config.yaml not found at $CONFIG" >&2
    echo "Run: cp config.example.yaml config.yaml and edit it first." >&2
    exit 1
fi

echo "Writing $SERVICE_FILE ..."
sudo tee "$SERVICE_FILE" > /dev/null << EOF
[Unit]
Description=deskinfopoint — desk info display
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=${RUN_USER}
WorkingDirectory=${PROJECT_DIR}
ExecStart=${VENV_PYTHON} -m deskinfopoint --config ${CONFIG}
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable "$SERVICE_NAME"
echo "Enabled. Starting service..."
sudo systemctl restart "$SERVICE_NAME"
echo ""
echo "=== Status ==="
sudo systemctl status "$SERVICE_NAME" --no-pager -l
