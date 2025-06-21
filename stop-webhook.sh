#!/bin/bash
#
# Stop the HLS webhook service
#

# Check if using pm2
if pm2 list | grep -q "hls-webhook"; then
    echo "Stopping webhook service via pm2..."
    pm2 stop hls-webhook
    exit 0
fi

# Otherwise kill the process
if pgrep -f "webhook.*hooks.json" > /dev/null; then
    echo "Stopping webhook service..."
    pkill -f "webhook.*hooks.json"
    echo "Webhook service stopped."
else
    echo "Webhook service is not running."
fi