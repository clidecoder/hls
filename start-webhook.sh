#!/bin/bash
#
# Start the HLS webhook service using pm2 or direct execution
#

cd /home/clide/hls

# Check if webhook is already running
if pgrep -f "webhook.*hooks.json" > /dev/null; then
    echo "Webhook service is already running!"
    ps aux | grep "webhook.*hooks.json" | grep -v grep
    exit 0
fi

# Option 1: Use pm2 if available (preferred)
if command -v pm2 &> /dev/null; then
    echo "Starting webhook service with pm2..."
    pm2 start ecosystem.config.js
    pm2 save
    echo "Webhook service started with pm2. Use 'pm2 status' to check."
    echo "To enable startup on reboot: pm2 startup"
    exit 0
fi

# Option 2: Start in background with nohup
echo "Starting webhook service in background..."
nohup webhook -hooks hooks.json -port 9000 -verbose > logs/webhook.log 2>&1 &
echo "Webhook service started with PID: $!"
echo "Logs: tail -f logs/webhook.log"