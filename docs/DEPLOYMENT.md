# Deployment Guide

This guide covers production deployment options for the HLS webhook handler system.

## Overview

The HLS webhook handler can be deployed in several configurations:

1. **Simple Deployment** - Direct webhook service + Python
2. **Production Deployment** - nginx + webhook service + systemd
3. **Container Deployment** - Docker/Podman containers
4. **Cloud Deployment** - AWS/GCP/Azure serverless

## Prerequisites

- Linux server (Ubuntu 20.04+ recommended)
- Python 3.8+
- nginx (for production)
- SSL certificate (Let's Encrypt recommended)
- Domain name with DNS configured
- GitHub Personal Access Token
- Claude Code CLI or Anthropic API access

## Simple Deployment

### Quick Setup

```bash
# 1. Clone repository
git clone https://github.com/clidecoder/hls.git
cd hls

# 2. Setup Python environment
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 3. Install webhook service
wget https://github.com/adnanh/webhook/releases/download/2.8.0/webhook-linux-amd64.tar.gz
tar -xvf webhook-linux-amd64.tar.gz
sudo mv webhook-linux-amd64/webhook /usr/local/bin/

# 4. Configure
cp config/settings.example.yaml config/settings.yaml
# Edit config/settings.yaml with your settings

# 5. Setup environment
cat > .env << 'EOF'
GITHUB_TOKEN=your_github_token
GITHUB_WEBHOOK_SECRET=your_webhook_secret
ANTHROPIC_API_KEY=claude-code
EOF

# 6. Start services
webhook -hooks services/hooks.json -port 9000 -verbose &
# Configure GitHub webhook to point to your-server:9000/hooks
```

### GitHub Webhook Configuration

In your GitHub repository settings:
- **URL**: `http://your-server.com:9000/hooks`
- **Content type**: `application/json`
- **Secret**: Same as `GITHUB_WEBHOOK_SECRET`
- **Events**: Issues, Pull requests, etc.

## Production Deployment

### System Requirements

**Minimum:**
- 1 CPU core
- 1 GB RAM
- 10 GB storage
- Ubuntu 20.04+

**Recommended:**
- 2 CPU cores
- 2 GB RAM
- 20 GB storage
- Ubuntu 22.04 LTS

### 1. Server Setup

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install dependencies
sudo apt install -y python3 python3-venv python3-pip nginx certbot python3-certbot-nginx git curl

# Create application user
sudo useradd -m -s /bin/bash hls
sudo usermod -aG sudo hls
```

### 2. Application Installation

```bash
# Switch to application user
sudo su - hls

# Clone repository
git clone https://github.com/clidecoder/hls.git
cd hls

# Setup Python environment
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Install webhook service
wget https://github.com/adnanh/webhook/releases/download/2.8.0/webhook-linux-amd64.tar.gz
tar -xvf webhook-linux-amd64.tar.gz
sudo mv webhook-linux-amd64/webhook /usr/local/bin/
sudo chmod +x /usr/local/bin/webhook
```

### 3. Configuration

```bash
# Application configuration
cp config/settings.example.yaml config/settings.yaml

# Edit configuration
nano config/settings.yaml
```

**Key settings for production:**

```yaml
server:
  host: "127.0.0.1"  # Only local connections
  port: 8000

github:
  token: "${GITHUB_TOKEN}"
  webhook_secret: "${GITHUB_WEBHOOK_SECRET}"

features:
  signature_validation: true
  async_processing: true

logging:
  level: "INFO"
  file: "/home/hls/hls/logs/webhook.log"

development:
  debug: false
  mock_claude: false
  mock_github: false
```

**Environment variables:**

```bash
# Create environment file
cat > /home/hls/hls/.env << 'EOF'
GITHUB_TOKEN=your_github_personal_access_token
GITHUB_WEBHOOK_SECRET=your_secure_webhook_secret
ANTHROPIC_API_KEY=claude-code
EOF

# Secure permissions
chmod 600 /home/hls/hls/.env
```

### 4. nginx Configuration

```bash
# Create nginx site configuration
sudo nano /etc/nginx/sites-available/hls
```

```nginx
server {
    server_name your-domain.com;
    
    # Webhook endpoint
    location /hooks {
        proxy_pass http://127.0.0.1:9000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # Preserve GitHub webhook headers
        proxy_set_header X-GitHub-Event $http_x_github_event;
        proxy_set_header X-GitHub-Delivery $http_x_github_delivery;
        proxy_set_header X-Hub-Signature-256 $http_x_hub_signature_256;
        
        # Timeouts for Claude processing
        proxy_read_timeout 300s;
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        
        # Body size for large payloads
        client_max_body_size 10M;
    }
    
    # Optional: API endpoints
    location /api {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
    
    # Health check
    location /health {
        proxy_pass http://127.0.0.1:8000/health;
    }
    
    # Default response
    location / {
        return 200 "HLS Webhook Handler";
        add_header Content-Type text/plain;
    }
}
```

```bash
# Enable site
sudo ln -s /etc/nginx/sites-available/hls /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

### 5. SSL Certificate

```bash
# Install SSL certificate with Let's Encrypt
sudo certbot --nginx -d your-domain.com

# Verify auto-renewal
sudo certbot renew --dry-run
```

### 6. Systemd Services

**Webhook Service:**

```bash
# Create webhook service
sudo nano /etc/systemd/system/hls-webhook.service
```

```ini
[Unit]
Description=HLS Webhook Handler
After=network.target

[Service]
Type=simple
User=hls
Group=hls
WorkingDirectory=/home/hls/hls
Environment=PATH=/home/hls/hls/venv/bin
ExecStart=/usr/local/bin/webhook -hooks services/hooks.json -port 9000 -verbose
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

**Optional FastAPI Service:**

```bash
# Create FastAPI service
sudo nano /etc/systemd/system/hls-api.service
```

```ini
[Unit]
Description=HLS FastAPI Service
After=network.target

[Service]
Type=simple
User=hls
Group=hls
WorkingDirectory=/home/hls/hls
Environment=PATH=/home/hls/hls/venv/bin
EnvironmentFile=/home/hls/hls/.env
ExecStart=/home/hls/hls/venv/bin/uvicorn hls.src.hls_handler.main:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

```bash
# Enable and start services
sudo systemctl daemon-reload
sudo systemctl enable hls-webhook
sudo systemctl start hls-webhook

# Optional: Enable FastAPI service
sudo systemctl enable hls-api
sudo systemctl start hls-api

# Check status
sudo systemctl status hls-webhook
sudo systemctl status hls-api
```

### 7. Cron Jobs

```bash
# Install cron jobs as hls user
sudo su - hls
cd hls
crontab config/crontab.txt

# Verify installation
crontab -l
```

### 8. Log Management

```bash
# Create log rotation configuration
sudo nano /etc/logrotate.d/hls
```

```
/home/hls/hls/logs/*.log {
    daily
    missingok
    rotate 30
    compress
    delaycompress
    notifempty
    create 644 hls hls
    postrotate
        systemctl reload hls-webhook
        systemctl reload hls-api
    endscript
}
```

### 9. Monitoring Setup

**Log monitoring with journald:**

```bash
# View webhook service logs
sudo journalctl -u hls-webhook -f

# View API service logs  
sudo journalctl -u hls-api -f

# View application logs
tail -f /home/hls/hls/logs/webhook.log
tail -f /home/hls/hls/logs/cron-analyze.log
```

**Health check script:**

```bash
# Create health check script
sudo nano /usr/local/bin/hls-health-check.sh
```

```bash
#!/bin/bash

# Health check endpoints
WEBHOOK_HEALTH="http://127.0.0.1:9000/"
API_HEALTH="http://127.0.0.1:8000/health"

# Check webhook service
if ! curl -f -s "$WEBHOOK_HEALTH" > /dev/null; then
    echo "ERROR: Webhook service down"
    systemctl restart hls-webhook
fi

# Check API service (if enabled)
if ! curl -f -s "$API_HEALTH" > /dev/null; then
    echo "ERROR: API service down"
    systemctl restart hls-api
fi
```

```bash
sudo chmod +x /usr/local/bin/hls-health-check.sh

# Add to cron (as root)
sudo crontab -e
# Add: */5 * * * * /usr/local/bin/hls-health-check.sh
```

## Container Deployment

### Docker Setup

**Dockerfile:**

```dockerfile
FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install webhook service
RUN curl -L https://github.com/adnanh/webhook/releases/download/2.8.0/webhook-linux-amd64.tar.gz \
    | tar -xz -C /usr/local/bin --strip-components=1

# Create app user
RUN useradd -m -s /bin/bash hls
USER hls
WORKDIR /home/hls/app

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --user -r requirements.txt

# Copy application
COPY --chown=hls:hls . .

# Expose ports
EXPOSE 8000 9000

# Start script
CMD ["./docker-start.sh"]
```

**docker-compose.yml:**

```yaml
version: '3.8'

services:
  hls-webhook:
    build: .
    ports:
      - "9000:9000"
      - "8000:8000"
    environment:
      - GITHUB_TOKEN=${GITHUB_TOKEN}
      - GITHUB_WEBHOOK_SECRET=${GITHUB_WEBHOOK_SECRET}
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
    volumes:
      - ./config:/home/hls/app/config
      - ./logs:/home/hls/app/logs
      - ./outputs:/home/hls/app/outputs
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/conf.d/default.conf
      - ./ssl:/etc/ssl/certs
    depends_on:
      - hls-webhook
    restart: unless-stopped
```

**Start script (docker-start.sh):**

```bash
#!/bin/bash
set -e

# Start webhook service in background
webhook -hooks services/hooks.json -port 9000 -verbose &

# Start FastAPI service
uvicorn hls.src.hls_handler.main:app --host 0.0.0.0 --port 8000
```

### Podman Setup

```bash
# Build image
podman build -t hls-webhook .

# Run container
podman run -d \
  --name hls-webhook \
  -p 9000:9000 \
  -p 8000:8000 \
  -e GITHUB_TOKEN="$GITHUB_TOKEN" \
  -e GITHUB_WEBHOOK_SECRET="$GITHUB_WEBHOOK_SECRET" \
  -v ./config:/home/hls/app/config:Z \
  -v ./logs:/home/hls/app/logs:Z \
  --restart=unless-stopped \
  hls-webhook

# Generate systemd unit
podman generate systemd --new --name hls-webhook > ~/.config/systemd/user/hls-webhook.service
systemctl --user enable hls-webhook
```

## Cloud Deployment

### AWS Lambda

**serverless.yml:**

```yaml
service: hls-webhook

provider:
  name: aws
  runtime: python3.11
  region: us-east-1
  environment:
    GITHUB_TOKEN: ${env:GITHUB_TOKEN}
    GITHUB_WEBHOOK_SECRET: ${env:GITHUB_WEBHOOK_SECRET}
    ANTHROPIC_API_KEY: ${env:ANTHROPIC_API_KEY}

functions:
  webhook:
    handler: lambda_handler.webhook_handler
    timeout: 300
    events:
      - http:
          path: /webhook
          method: post
          cors: true

plugins:
  - serverless-python-requirements
```

**lambda_handler.py:**

```python
import json
import asyncio
from hls.src.hsl_handler.webhook_processor import WebhookProcessor
from hls.src.hsl_handler.config import load_settings

def webhook_handler(event, context):
    """AWS Lambda handler for GitHub webhooks."""
    
    # Parse webhook data
    headers = event.get('headers', {})
    body = event.get('body', '')
    
    if isinstance(body, str):
        payload = json.loads(body)
    else:
        payload = body
    
    # Extract GitHub headers
    event_type = headers.get('X-GitHub-Event')
    delivery_id = headers.get('X-GitHub-Delivery')
    
    # Process webhook
    async def process():
        settings = load_settings()
        processor = WebhookProcessor(settings)
        return await processor.process_webhook(event_type, payload, delivery_id)
    
    # Run async function
    result = asyncio.run(process())
    
    return {
        'statusCode': 200,
        'body': json.dumps(result),
        'headers': {
            'Content-Type': 'application/json'
        }
    }
```

### Google Cloud Functions

**main.py:**

```python
import functions_framework
import json
from hls.src.hsl_handler.webhook_processor import WebhookProcessor
from hls.src.hsl_handler.config import load_settings

@functions_framework.http
def webhook_handler(request):
    """Google Cloud Function for GitHub webhooks."""
    
    # Parse request
    payload = request.get_json()
    event_type = request.headers.get('X-GitHub-Event')
    delivery_id = request.headers.get('X-GitHub-Delivery')
    
    # Process webhook
    settings = load_settings()
    processor = WebhookProcessor(settings)
    
    # Note: Cloud Functions don't support async/await directly
    # Consider using Cloud Run for async support
    
    return json.dumps({"status": "received"})
```

### Azure Functions

**function_app.py:**

```python
import azure.functions as func
import json
import asyncio
from hls.src.hsl_handler.webhook_processor import WebhookProcessor
from hls.src.hsl_handler.config import load_settings

app = func.FunctionApp(http_auth_level=func.AuthLevel.FUNCTION)

@app.route(route="webhook")
async def webhook_handler(req: func.HttpRequest) -> func.HttpResponse:
    """Azure Function for GitHub webhooks."""
    
    # Parse request
    payload = req.get_json()
    event_type = req.headers.get('X-GitHub-Event')
    delivery_id = req.headers.get('X-GitHub-Delivery')
    
    # Process webhook
    settings = load_settings()
    processor = WebhookProcessor(settings)
    result = await processor.process_webhook(event_type, payload, delivery_id)
    
    return func.HttpResponse(
        json.dumps(result),
        mimetype="application/json"
    )
```

## Security Considerations

### Network Security

```bash
# Firewall configuration
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow ssh
sudo ufw allow 'Nginx Full'
sudo ufw enable

# Optional: Restrict webhook access
sudo ufw allow from github-ip-ranges to any port 9000
```

### File Permissions

```bash
# Secure configuration files
chmod 600 /home/hls/hls/.env
chmod 600 /home/hls/hls/config/settings.yaml

# Secure service files
sudo chmod 644 /etc/systemd/system/hls-*.service

# Secure application directory
chown -R hls:hls /home/hls/hls
chmod -R 755 /home/hls/hls
chmod +x /home/hls/hls/webhook_dispatch.py
```

### Secret Management

**Using environment variables:**

```bash
# Store secrets securely
echo "GITHUB_TOKEN=ghp_..." | sudo tee /etc/environment
echo "GITHUB_WEBHOOK_SECRET=..." | sudo tee -a /etc/environment
```

**Using systemd credentials:**

```ini
[Service]
LoadCredential=github-token:/etc/secrets/github-token
LoadCredential=webhook-secret:/etc/secrets/webhook-secret
```

## Monitoring and Alerting

### Prometheus Metrics

Add metrics endpoint to FastAPI:

```python
# hls/src/hsl_handler/metrics.py
from prometheus_client import Counter, Histogram, generate_latest

webhook_requests = Counter('webhook_requests_total', 'Total webhook requests', ['event_type', 'status'])
processing_time = Histogram('webhook_processing_seconds', 'Webhook processing time')

@app.get("/metrics")
async def metrics():
    return Response(generate_latest(), media_type="text/plain")
```

### Log Aggregation

**With ELK Stack:**

```yaml
# docker-compose.monitoring.yml
version: '3.8'

services:
  elasticsearch:
    image: docker.elastic.co/elasticsearch/elasticsearch:8.5.0
    environment:
      - discovery.type=single-node
    ports:
      - "9200:9200"

  logstash:
    image: docker.elastic.co/logstash/logstash:8.5.0
    volumes:
      - ./logstash.conf:/usr/share/logstash/pipeline/logstash.conf

  kibana:
    image: docker.elastic.co/kibana/kibana:8.5.0
    ports:
      - "5601:5601"
    depends_on:
      - elasticsearch
```

### Alerting

**With Grafana:**

```yaml
# grafana/provisioning/alerting/rules.yml
groups:
  - name: hls-alerts
    rules:
      - alert: WebhookDown
        expr: up{job="hls-webhook"} == 0
        for: 5m
        annotations:
          summary: "HLS webhook service is down"
          
      - alert: HighErrorRate
        expr: rate(webhook_requests_total{status="error"}[5m]) > 0.1
        for: 2m
        annotations:
          summary: "High webhook error rate"
```

## Backup and Recovery

### Configuration Backup

```bash
#!/bin/bash
# backup.sh

BACKUP_DIR="/backup/hls/$(date +%Y%m%d)"
mkdir -p "$BACKUP_DIR"

# Backup configuration
cp -r /home/hls/hls/config "$BACKUP_DIR/"
cp /home/hls/hls/.env "$BACKUP_DIR/"

# Backup systemd services
cp /etc/systemd/system/hls-*.service "$BACKUP_DIR/"

# Backup nginx configuration
cp /etc/nginx/sites-available/hls "$BACKUP_DIR/"

# Create archive
tar -czf "$BACKUP_DIR.tar.gz" "$BACKUP_DIR"
rm -rf "$BACKUP_DIR"
```

### Data Backup

```bash
# Backup analysis outputs and logs
cp -r /home/hls/hls/outputs "$BACKUP_DIR/"
cp -r /home/hls/hls/logs "$BACKUP_DIR/"
```

## Troubleshooting

### Common Issues

1. **Webhook not receiving requests**
   ```bash
   # Check nginx logs
   sudo tail -f /var/log/nginx/error.log
   
   # Check webhook service
   sudo systemctl status hls-webhook
   sudo journalctl -u hls-webhook -f
   ```

2. **SSL certificate issues**
   ```bash
   # Renew certificate
   sudo certbot renew
   
   # Check certificate status
   sudo certbot certificates
   ```

3. **Permission denied errors**
   ```bash
   # Fix ownership
   sudo chown -R hls:hls /home/hls/hls
   
   # Fix permissions
   chmod +x /home/hls/hls/webhook_dispatch.py
   ```

4. **High memory usage**
   ```bash
   # Monitor memory
   free -h
   ps aux | grep -E "(webhook|python)"
   
   # Restart services
   sudo systemctl restart hls-webhook
   ```

### Performance Tuning

**nginx optimization:**

```nginx
# /etc/nginx/nginx.conf
worker_processes auto;
worker_connections 1024;

http {
    keepalive_timeout 65;
    client_max_body_size 10M;
    
    # Gzip compression
    gzip on;
    gzip_vary on;
    gzip_types text/plain application/json;
}
```

**System limits:**

```bash
# /etc/security/limits.conf
hls soft nofile 4096
hls hard nofile 8192
```

## Related Documentation

- [Main README](../README.md)
- [Configuration Reference](CONFIGURATION.md)
- [Development Guide](DEVELOPMENT.md)
- [Cron Jobs Documentation](CRON_JOBS.md)