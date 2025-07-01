#!/bin/bash

# Test script for webhook services

echo "Testing webhook services..."

# Check if services are running
echo -e "\n1. Checking service status:"
if systemctl is-active --quiet github-webhook.service; then
    echo "✓ github-webhook.service is running"
else
    echo "✗ github-webhook.service is not running"
fi

if systemctl is-active --quiet hls-fastapi.service; then
    echo "✓ hls-fastapi.service is running"
else
    echo "✗ hls-fastapi.service is not running"
fi

# Check ports
echo -e "\n2. Checking ports:"
if ss -tlnp 2>/dev/null | grep -q ":9000"; then
    echo "✓ Port 9000 is listening (webhook service)"
else
    echo "✗ Port 9000 is not listening"
fi

if ss -tlnp 2>/dev/null | grep -q ":8000"; then
    echo "✓ Port 8000 is listening (FastAPI)"
else
    echo "✗ Port 8000 is not listening"
fi

# Test endpoints
echo -e "\n3. Testing endpoints:"
if curl -s -f http://localhost:8000/health > /dev/null 2>&1; then
    echo "✓ FastAPI health check passed"
else
    echo "✗ FastAPI health check failed"
fi

# Test webhook endpoint (should return 405 for GET request)
WEBHOOK_RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:9000/hooks)
if [ "$WEBHOOK_RESPONSE" = "405" ] || [ "$WEBHOOK_RESPONSE" = "404" ]; then
    echo "✓ Webhook service responding (HTTP $WEBHOOK_RESPONSE)"
else
    echo "✗ Webhook service not responding properly (HTTP $WEBHOOK_RESPONSE)"
fi

echo -e "\n4. Recent logs:"
echo "--- github-webhook logs ---"
journalctl -u github-webhook.service --no-pager -n 5
echo -e "\n--- hls-fastapi logs ---"
journalctl -u hls-fastapi.service --no-pager -n 5