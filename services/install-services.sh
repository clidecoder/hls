#!/bin/bash

# Script to install and enable systemd services
# Run with sudo

set -e

echo "Installing GitHub webhook services..."

# Check if webhook binary exists
if ! command -v webhook &> /dev/null; then
    echo "Error: webhook binary not found. Please install it first:"
    echo "  Download from: https://github.com/adnanh/webhook/releases"
    echo "  Or: go install github.com/adnanh/webhook@latest"
    exit 1
fi

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo "Please run with sudo: sudo ./install-services.sh"
    exit 1
fi

# Copy service files
echo "Copying service files..."
cp /home/clide/hls/services/github-webhook.service /etc/systemd/system/
cp /home/clide/hls/services/hls-fastapi.service /etc/systemd/system/

# Reload systemd
echo "Reloading systemd daemon..."
systemctl daemon-reload

# Enable services
echo "Enabling services..."
systemctl enable github-webhook.service
systemctl enable hls-fastapi.service

# Start services
echo "Starting services..."
systemctl start github-webhook.service
systemctl start hls-fastapi.service

# Check status
echo -e "\nService status:"
systemctl status github-webhook.service --no-pager
echo ""
systemctl status hls-fastapi.service --no-pager

echo -e "\nServices installed successfully!"
echo "To check logs:"
echo "  journalctl -u github-webhook -f"
echo "  journalctl -u hls-fastapi -f"