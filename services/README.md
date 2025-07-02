# Services Directory

This directory contains all service-related configuration files and scripts for the HLS webhook handler.

## Directory Structure

### hooks.json
Configuration file for the adnanh/webhook service that defines webhook endpoints and execution rules.

### systemd/
Contains systemd service unit files for running the webhook handler as a system service.

- **hls-webhook.service** - Main webhook service (adnanh/webhook on port 9000)
- **github-webhook.service** - Alternative service configuration
- **hls-fastapi.service** - FastAPI service (optional, for direct API access)

### pm2/
Contains PM2 process manager configuration files.

- **ecosystem.config.js** - PM2 configuration for running the webhook service

### scripts/
Contains shell scripts for managing services.

- **start-webhook.sh** - Start the webhook service
- **stop-webhook.sh** - Stop the webhook service
- **install-services.sh** - Install systemd services
- **test-services.sh** - Test service configuration

## Usage

### Systemd Service

```bash
# Copy service file to systemd
sudo cp services/systemd/hls-webhook.service /etc/systemd/system/

# Reload systemd
sudo systemctl daemon-reload

# Enable and start service
sudo systemctl enable hls-webhook
sudo systemctl start hls-webhook

# Check status
sudo systemctl status hls-webhook
```

### PM2 Service

```bash
# Start with PM2
pm2 start services/pm2/ecosystem.config.js

# Save PM2 configuration
pm2 save

# Setup startup script
pm2 startup
```

### Manual Scripts

```bash
# Start webhook service
./services/scripts/start-webhook.sh

# Stop webhook service
./services/scripts/stop-webhook.sh
```

## Service Architecture

The main service runs the adnanh/webhook tool on port 9000, which:
1. Receives webhooks from GitHub (via Nginx Proxy Manager)
2. Validates the webhook against configured rules
3. Executes webhook_dispatch.py with the payload
4. Returns response to GitHub

## Logs

- Systemd logs: `journalctl -u hls-webhook -f`
- PM2 logs: `pm2 logs hls-webhook`
- Manual logs: `logs/webhook.log`