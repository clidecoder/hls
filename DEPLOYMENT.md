# HLS Deployment Guide

## Prerequisites

### System Requirements
- Python 3.8 or higher
- Internet connectivity for API access
- Public-facing server with accessible webhook endpoint
- Minimum 1GB RAM, 1 CPU core
- 5GB disk space for logs and outputs

### Required Accounts & Tokens
1. **GitHub Personal Access Token** with permissions:
   - `repo` (for private repositories)
   - `public_repo` (for public repositories)
   - `write:repo_hook` (for webhook management)

2. **Anthropic API Key** with Claude access
   - Sign up at [console.anthropic.com](https://console.anthropic.com)
   - Generate API key from dashboard

3. **GitHub Webhook Secret**
   - Generate secure random string (32+ characters)
   - Will be configured in GitHub repository settings

## Installation Steps

### 1. Clone and Setup Project
```bash
# Clone the repository
git clone <repository-url>
cd hsl

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Environment Configuration
Create `.env` file in project root:
```bash
# GitHub Configuration
GITHUB_TOKEN=ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
GITHUB_WEBHOOK_SECRET=your_super_secure_webhook_secret_here

# Anthropic Configuration  
ANTHROPIC_API_KEY=sk-ant-api03-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# Optional: Override default settings
HLS_HOST=0.0.0.0
HLS_PORT=8000
HLS_WEBHOOK_PATH=/webhook
```

### 3. Configuration File Setup
Create `config/settings.yaml`:
```yaml
server:
  host: "${HLS_HOST:-0.0.0.0}"
  port: ${HLS_PORT:-8000}
  webhook_path: "${HLS_WEBHOOK_PATH:-/webhook}"

github:
  token: "${GITHUB_TOKEN}"
  webhook_secret: "${GITHUB_WEBHOOK_SECRET}"

claude:
  api_key: "${ANTHROPIC_API_KEY}"
  model: "claude-3-5-sonnet-20241022"
  max_tokens: 4000
  temperature: 0.1

repositories:
  - name: "your-org/your-repo"
    enabled: true
    events:
      - "issues"
      - "pull_request"
      - "pull_request_review"
      - "workflow_run"
    labels:
      auto_apply: true
      categories:
        - "bug"
        - "enhancement" 
        - "question"
        - "documentation"

features:
  signature_validation: true
  async_processing: true
  auto_labeling: true
  auto_commenting: false

logging:
  level: "INFO"
  format: "json"
  file: "logs/hsl.log"

outputs:
  base_dir: "outputs"
  save_analyses: true
```

### 4. Directory Structure Setup
```bash
# Create required directories
mkdir -p config
mkdir -p logs
mkdir -p outputs

# Ensure proper permissions
chmod 755 logs outputs
```

## GitHub Webhook Configuration

### 1. Repository Webhook Setup
1. Go to your GitHub repository settings
2. Navigate to "Webhooks" section
3. Click "Add webhook"
4. Configure webhook:
   - **Payload URL**: `https://your-domain.com/webhook`
   - **Content type**: `application/json`
   - **Secret**: Use the same value as `GITHUB_WEBHOOK_SECRET`
   - **Events**: Select individual events:
     - Issues
     - Pull requests
     - Pull request reviews
     - Workflow runs
   - **Active**: ✅ Checked

### 2. Webhook Testing
```bash
# Test webhook delivery
curl -X POST https://your-domain.com/webhook \
  -H "Content-Type: application/json" \
  -H "X-GitHub-Event: ping" \
  -H "X-GitHub-Delivery: 12345678-1234-1234-1234-123456789012" \
  -d '{"zen": "Non-blocking is better than blocking."}'
```

## Deployment Options

### Option 1: Direct Python Execution
```bash
# Start the service
python -m hls.src.hls_handler.main

# Or with uvicorn for production
uvicorn hls.src.hls_handler.main:app \
  --host 0.0.0.0 \
  --port 8000 \
  --workers 1 \
  --access-log
```

### Option 2: Docker Deployment
Create `Dockerfile`:
```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create necessary directories
RUN mkdir -p logs outputs config

# Expose port
EXPOSE 8000

# Run the application
CMD ["uvicorn", "hls.src.hls_handler.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

Build and run:
```bash
# Build image
docker build -t hsl-webhook-handler .

# Run container
docker run -d \
  --name hsl-service \
  -p 8000:8000 \
  -v $(pwd)/config:/app/config \
  -v $(pwd)/logs:/app/logs \
  -v $(pwd)/outputs:/app/outputs \
  --env-file .env \
  hsl-webhook-handler
```

### Option 3: Docker Compose
Create `docker-compose.yml`:
```yaml
version: '3.8'

services:
  hsl-service:
    build: .
    ports:
      - "8000:8000"
    volumes:
      - ./config:/app/config
      - ./logs:/app/logs
      - ./outputs:/app/outputs
    env_file:
      - .env
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
```

Deploy with:
```bash
docker-compose up -d
```

### Option 4: Systemd Service (Linux)
Create `/etc/systemd/system/hsl-webhook.service`:
```ini
[Unit]
Description=HLS GitHub Webhook Handler
After=network.target

[Service]
Type=simple
User=hsl
WorkingDirectory=/opt/hsl
Environment=PATH=/opt/hsl/venv/bin
ExecStart=/opt/hsl/venv/bin/python -m hls.src.hls_handler.main
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl daemon-reload
sudo systemctl enable hsl-webhook
sudo systemctl start hsl-webhook
```

## Reverse Proxy Configuration (Recommended)

**Important**: Using nginx significantly improves reliability by handling network-level issues, rate limiting, and SSL termination. See `nginx.conf.example` for a complete production configuration.

### Key Reliability Benefits:
- **Request buffering** for large GitHub webhook payloads
- **Extended timeouts** for Claude API processing (up to 5 minutes)
- **Rate limiting** to prevent webhook flooding attacks
- **Connection pooling** and automatic failover
- **SSL termination** with proper security headers

### Basic Nginx Configuration
```nginx
upstream hsl_backend {
    server 127.0.0.1:8000 max_fails=3 fail_timeout=30s;
    keepalive 32;
}

server {
    listen 443 ssl http2;
    server_name your-domain.com;
    
    location /webhook {
        limit_req zone=webhook burst=20 nodelay;
        client_max_body_size 10M;
        
        proxy_pass http://hsl_backend;
        proxy_read_timeout 300s;  # 5 minutes for Claude processing
        proxy_buffering on;
        proxy_buffer_size 64k;
    }
}
```

**Note**: This addresses network-level reliability but doesn't solve core application issues like webhook deduplication or persistent queuing. For full production reliability, combine with Redis/Celery queue system.

### Apache Configuration
```apache
<VirtualHost *:80>
    ServerName your-domain.com
    
    ProxyPreserveHost On
    ProxyRequests Off
    ProxyPass / http://127.0.0.1:8000/
    ProxyPassReverse / http://127.0.0.1:8000/
    
    # Increase timeout for webhook processing
    ProxyTimeout 300
</VirtualHost>
```

## SSL/TLS Configuration (Recommended)

### Using Let's Encrypt with Certbot
```bash
# Install certbot
sudo apt-get install certbot python3-certbot-nginx

# Generate certificate
sudo certbot --nginx -d your-domain.com

# Auto-renewal
sudo crontab -e
# Add: 0 2 * * * certbot renew --quiet
```

## Monitoring and Logging

### Log Rotation Setup
Create `/etc/logrotate.d/hsl`:
```
/opt/hsl/logs/*.log {
    daily
    rotate 30
    compress
    delaycompress
    missingok
    notifempty
    create 0644 hsl hsl
    postrotate
        systemctl reload hsl-webhook
    endscript
}
```

### Health Check Monitoring
```bash
# Create monitoring script
cat > /opt/hsl/health-check.sh << 'EOF'
#!/bin/bash
HEALTH_URL="http://localhost:8000/health"
RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" $HEALTH_URL)

if [ $RESPONSE -eq 200 ]; then
    echo "Service is healthy"
    exit 0
else
    echo "Service is unhealthy (HTTP $RESPONSE)"
    exit 1
fi
EOF

chmod +x /opt/hsl/health-check.sh

# Add to crontab for monitoring
*/5 * * * * /opt/hsl/health-check.sh >> /var/log/hsl-health.log 2>&1
```

## Troubleshooting

### Common Issues

1. **Webhook Signature Validation Fails**
   - Verify `GITHUB_WEBHOOK_SECRET` matches GitHub webhook config
   - Check for extra whitespace in environment variables

2. **Claude API Rate Limits**
   - Monitor API usage in logs
   - Adjust rate limiting in client configuration
   - Consider implementing exponential backoff

3. **GitHub API Rate Limits**
   - Use authenticated requests (token provided)
   - Monitor rate limit headers in responses
   - Implement request queuing for high-volume repos

4. **Memory Usage Issues**
   - Monitor statistics collection (limited to 100 recent items)
   - Consider implementing log rotation
   - Use external monitoring for large deployments

### Debug Mode
Enable debug logging in `config/settings.yaml`:
```yaml
logging:
  level: "DEBUG"
  format: "json"
```

### Service Status Checks
```bash
# Check service status
curl http://localhost:8000/health

# Check processing statistics
curl http://localhost:8000/stats

# View recent logs
tail -f logs/hsl.log
```

## Security Considerations

### Firewall Configuration
```bash
# Allow only necessary ports
sudo ufw allow 22    # SSH
sudo ufw allow 80    # HTTP
sudo ufw allow 443   # HTTPS
sudo ufw deny 8000   # Block direct access to app
sudo ufw enable
```

### Environment Security
- Store sensitive data in environment variables
- Use `.env` files with proper permissions (600)
- Never commit secrets to version control
- Rotate API keys regularly

### Network Security
- Use HTTPS for all webhook endpoints
- Implement webhook signature validation
- Consider IP whitelisting for GitHub webhooks
- Use reverse proxy for additional security headers

## Scaling Considerations

For high-volume deployments, consider:
1. **Horizontal scaling** with load balancer
2. **Message queue** for webhook processing (Redis/RabbitMQ)
3. **Database** for persistent statistics and configuration
4. **Caching layer** for frequently accessed data
5. **Container orchestration** (Kubernetes/Docker Swarm)