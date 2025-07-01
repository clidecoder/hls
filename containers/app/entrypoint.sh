#!/bin/bash
set -e

# Function to wait for a service to be ready
wait_for_service() {
    local host=$1
    local port=$2
    local service=$3
    echo "Waiting for $service to be ready..."
    while ! nc -z $host $port; do
        sleep 1
    done
    echo "$service is ready!"
}

# Copy mounted config to appropriate locations if they exist
if [ -d "/config/hls" ]; then
    echo "Copying HLS configuration..."
    cp -r /config/hls/* /app/config/ 2>/dev/null || true
fi

if [ -d "/config/claude" ]; then
    echo "Copying Claude configuration..."
    cp -r /config/claude/.claude/* /home/app/.claude/ 2>/dev/null || true
fi

# Ensure webhook_dispatch.py is executable
chmod +x /app/webhook_dispatch.py

# Update hooks.json with correct paths
if [ -f "/app/config/hooks.json" ]; then
    sed -i 's|/home/clide/hls|/app|g' /app/config/hooks.json
fi

# Start webhook service in background
echo "Starting webhook service on port 9000..."
webhook -hooks /app/config/hooks.json -port 9000 -verbose &
WEBHOOK_PID=$!

# Start FastAPI application
echo "Starting FastAPI application on port 8000..."
cd /app
uvicorn hls.src.hsl_handler.main:app --host 0.0.0.0 --port 8000 &
FASTAPI_PID=$!

# Function to handle shutdown
shutdown() {
    echo "Shutting down services..."
    kill -TERM $WEBHOOK_PID $FASTAPI_PID 2>/dev/null
    wait $WEBHOOK_PID $FASTAPI_PID
    exit 0
}

# Set up signal handlers
trap shutdown SIGTERM SIGINT

# Wait for both processes
echo "Services started. Webhook service PID: $WEBHOOK_PID, FastAPI PID: $FASTAPI_PID"
wait $WEBHOOK_PID $FASTAPI_PID