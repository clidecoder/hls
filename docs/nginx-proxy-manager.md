# HLS Webhook System + Nginx Proxy Manager Setup Guide

This guide shows how to configure Nginx Proxy Manager to proxy your existing HLS webhook system, maintaining the simple architecture: **GitHub → NPM → adnanh/webhook → webhook_dispatch.py**

## Architecture Overview

```
GitHub Webhook
     ↓
Nginx Proxy Manager (SSL termination, domain routing)
     ↓ 
adnanh/webhook service (port 9000)
     ↓
webhook_dispatch.py (processes GitHub events with Claude AI)
```

## Prerequisites

- Existing HLS webhook system from https://github.com/clidecoder/hls
- Nginx Proxy Manager instance running
- Domain clidecoder.com with DNS pointing to your NPM server
- SSL certificate (Let's Encrypt through NPM)

## Step 1: Configure Nginx Proxy Manager

### Create Proxy Host via NPM Web Interface

1. **Login to NPM**: Navigate to `https://clidecoder.com:81` (or `http://clidecoder.com:81` if SSL not configured for admin port)
2. **Go to Proxy Hosts**: Click "Proxy Hosts" in the dashboard
3. **Add Proxy Host**: Click "Add Proxy Host"

### Proxy Host Configuration

**Details Tab:**
```
Domain Names: clidecoder.com
Scheme: http
Forward Hostname/IP: localhost (or your webhook server IP)
Forward Port: 9000
Cache Assets: OFF
Block Common Exploits: ON
Websockets Support: OFF
```

**SSL Tab:**
```
SSL Certificate: Request a new SSL Certificate
Force SSL: ON
HTTP/2 Support: ON
HSTS Enabled: ON
```

**Advanced Tab:**
```nginx
# GitHub webhook specific headers
location /hooks {
    proxy_set_header X-GitHub-Event $http_x_github_event;
    proxy_set_header X-GitHub-Delivery $http_x_github_delivery;
    proxy_set_header X-Hub-Signature-256 $http_x_hub_signature_256;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header Host $host;
    
    # Increase timeout for Claude AI processing
    proxy_connect_timeout 30s;
    proxy_send_timeout 30s;
    proxy_read_timeout 300s;  # 5 minutes for AI analysis
    
    # Handle large PR payloads
    client_max_body_size 10M;
    client_body_buffer_size 128k;
    
    # Pass to webhook service
    proxy_pass http://localhost:9000;
}
```

## Step 2: Verify adnanh/webhook Configuration

Your existing `services/hooks.json` should remain unchanged:

```json
[
  {
    "id": "github-webhook",
    "execute-command": "/home/clide/hls/webhook_dispatch.py",
    "command-working-directory": "/home/clide/hls",
    "response-message": "Webhook received",
    "pass-arguments-to-command": [
      {
        "source": "entire-payload"
      }
    ],
    "pass-environment-to-command": [
      {
        "source": "header",
        "name": "X-GitHub-Event",
        "envname": "GITHUB_EVENT"
      },
      {
        "source": "header",
        "name": "X-GitHub-Delivery",
        "envname": "GITHUB_DELIVERY"
      },
      {
        "source": "header",
        "name": "X-Hub-Signature-256",
        "envname": "GITHUB_SIGNATURE"
      }
    ],
    "trigger-rule": {
      "match": {
        "type": "value",
        "value": "application/json",
        "parameter": {
          "source": "header",
          "name": "Content-Type"
        }
      }
    }
  }
]
```

## Step 3: Update GitHub Webhook URL

In your GitHub repository settings:

```
Payload URL: https://clidecoder.com/hooks/github-webhook
Content type: application/json
Secret: (your existing webhook secret)
Events: Issues, Pull requests, etc.
```

## Step 4: Service Management

### Start adnanh/webhook service
```bash
# Start webhook service on port 9000
webhook -hooks services/hooks.json -port 9000 -verbose

# Or with systemd/pm2 (as per your existing setup)
pm2 start services/pm2/ecosystem.config.js
```

### Verify the chain is working
```bash
# Test NPM → webhook connection
curl -X POST https://clidecoder.com/hooks/github-webhook \
  -H "Content-Type: application/json" \
  -H "X-GitHub-Event: ping" \
  -d '{"zen": "test"}'

# Check webhook service logs
tail -f logs/webhook.log

# Check HLS processing logs
tail -f logs/webhook.log
```

## Step 5: DNS Configuration

Your domain clidecoder.com should already be pointing to your NPM server. If not:

```
Type: A
Name: @ (root domain)
Value: YOUR_NPM_SERVER_IP
TTL: 300 (or your preference)
```

## Benefits of This Setup

1. **SSL Termination**: NPM handles Let's Encrypt certificates automatically
2. **Domain Management**: Clean webhook URLs instead of IP:port
3. **Header Preservation**: All GitHub webhook headers passed through correctly
4. **Timeout Handling**: Extended timeouts for Claude AI processing
5. **Logging**: NPM access logs + webhook service logs + HLS application logs
6. **Security**: SSL encryption for webhook payloads
7. **Scalability**: Easy to add multiple webhook endpoints later

## Troubleshooting

### Common Issues

**1. 502 Bad Gateway**
- Check if webhook service is running on port 9000
- Verify firewall allows NPM → localhost:9000 communication

**2. Webhook signature validation fails**
- Ensure NPM preserves `X-Hub-Signature-256` header
- Check webhook secret matches in GitHub and HLS config

**3. Timeouts**
- Increase `proxy_read_timeout` if Claude processing takes longer
- Monitor HLS logs for processing bottlenecks

**4. SSL certificate issues**
- Verify DNS propagation before requesting Let's Encrypt cert
- Check NPM logs for certificate renewal issues

### Verification Commands

```bash
# Test NPM proxy
curl -I https://clidecoder.com/hooks/github-webhook

# Check webhook service
curl -X POST http://localhost:9000/hooks/github-webhook \
  -H "Content-Type: application/json" \
  -d '{"test": true}'

# Monitor processing chain
tail -f /var/log/nginx/access.log    # NPM logs
tail -f logs/webhook.log                  # webhook service logs
tail -f logs/webhook.log             # HLS processing logs
```

## Configuration Summary

| Component | Purpose | Port/URL |
|-----------|---------|----------|
| GitHub | Sends webhooks | → https://clidecoder.com/hooks/github-webhook |
| NPM | SSL termination, proxy | Port 443 → localhost:9000 |
| adnanh/webhook | Webhook router | Port 9000 → webhook_dispatch.py |
| HLS System | AI analysis | webhook_dispatch.py → Claude AI |

This setup maintains your existing HLS webhook processing while adding professional SSL-enabled domain routing through Nginx Proxy Manager.
