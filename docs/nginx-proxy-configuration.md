# Nginx Proxy Manager Configuration

This document describes the webhook configuration for Nginx Proxy Manager (NPM) integration.

## Overview

The HLS webhook handler is designed to work with Nginx Proxy Manager, which strips URL path prefixes. This requires specific configuration to ensure webhooks are properly routed.

## URL Path Flow

```
GitHub → NPM → Webhook Service
https://clidecoder.com/hooks/github-webhook → http://localhost:9000/github-webhook
```

### Path Transformation
1. **GitHub sends webhook to**: `https://clidecoder.com/hooks/github-webhook`
2. **NPM strips `/hooks` prefix**: Forwards to `http://localhost:9000/github-webhook`
3. **Webhook service receives**: `/github-webhook` (matches webhook ID)

## Required Configuration

### 1. Webhook Service Configuration

The webhook service must be configured with empty URL prefix to serve webhooks at root path:

**File**: `/etc/systemd/system/github-webhook.service`
```ini
[Service]
ExecStart=/usr/bin/webhook -hooks /home/clide/hls/hooks.json -port 9000 -verbose -urlprefix ""
```

**Key parameter**: `-urlprefix ""` (empty string) tells webhook service to serve at root instead of `/hooks/`

### 2. Hooks Configuration

**File**: `/home/clide/hls/hooks.json`
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
    ]
  }
]
```

**Key points**:
- `"id": "github-webhook"` matches the URL path after NPM stripping
- No special trigger rules needed for basic operation
- Headers are passed through for validation

### 3. Nginx Proxy Manager Setup

In NPM admin interface:

1. **Proxy Host Configuration**:
   - **Domain Names**: `clidecoder.com`
   - **Scheme**: `http`
   - **Forward Hostname/IP**: `localhost` or `127.0.0.1`
   - **Forward Port**: `9000`

2. **Advanced Configuration**:
   ```nginx
   location /hooks {
       proxy_pass http://localhost:9000;
       proxy_http_version 1.1;
       proxy_set_header Host $host;
       proxy_set_header X-Real-IP $remote_addr;
       proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
       proxy_set_header X-Forwarded-Proto $scheme;
       
       # Preserve GitHub webhook headers
       proxy_set_header X-GitHub-Event $http_x_github_event;
       proxy_set_header X-GitHub-Delivery $http_x_github_delivery;
       proxy_set_header X-Hub-Signature $http_x_hub_signature;
       proxy_set_header X-Hub-Signature-256 $http_x_hub_signature_256;
       
       # Webhook processing timeouts
       proxy_read_timeout 300s;
       proxy_connect_timeout 75s;
       
       # Support large payloads
       client_max_body_size 10M;
   }
   ```

### 4. GitHub Webhook Configuration

In GitHub repository settings → Webhooks:

- **Payload URL**: `https://clidecoder.com/hooks/github-webhook`
- **Content type**: `application/json`
- **Secret**: Value from `GITHUB_WEBHOOK_SECRET` environment variable
- **Events**: Select events (Issues, Pull requests, etc.)
- **Active**: ✓ Enabled

## Testing Configuration

### 1. Test Webhook Service Directly
```bash
# Test webhook endpoint
curl -X POST \
  -H "Content-Type: application/json" \
  -d '{"test": "payload"}' \
  http://localhost:9000/github-webhook

# Expected response: "Webhook received"
```

### 2. Test Through NPM (if accessible locally)
```bash
# Test through proxy (if NPM is accessible)
curl -X POST \
  -H "Content-Type: application/json" \
  -d '{"test": "payload"}' \
  https://clidecoder.com/hooks/github-webhook
```

### 3. Verify Service Status
```bash
# Check webhook service
sudo systemctl status github-webhook

# Monitor logs
sudo journalctl -u github-webhook -f
```

## Alternative Proxy Configurations

### Standard Nginx (Non-NPM)

If using standard nginx that preserves paths:

**Remove the `-urlprefix ""` flag**:
```ini
ExecStart=/usr/bin/webhook -hooks /home/clide/hls/hooks.json -port 9000 -verbose
```

**Nginx config**:
```nginx
location /hooks {
    proxy_pass http://localhost:9000;  # Preserves full path
    # ... other proxy settings
}
```

### Cloudflare Proxy

If using Cloudflare with path preservation:
- Remove `-urlprefix ""` flag
- Ensure Cloudflare forwards full paths
- Consider Cloudflare timeout limits for webhook processing

## Troubleshooting

### Common Issues

1. **404 Not Found**:
   - Check if `-urlprefix ""` flag is set
   - Verify NPM is stripping `/hooks` correctly
   - Test direct webhook service access

2. **Webhook Not Triggered**:
   - Verify GitHub webhook URL ends with `/github-webhook`
   - Check webhook secret matches
   - Review GitHub webhook delivery logs

3. **Service Configuration**:
   ```bash
   # Restart after config changes
   sudo systemctl restart github-webhook
   
   # Check service loads correctly
   sudo systemctl status github-webhook
   ```

### Debug Commands

```bash
# Check port binding
sudo lsof -i :9000

# Test webhook response
curl -v -X POST http://localhost:9000/github-webhook

# Check webhook service logs
sudo journalctl -u github-webhook --since "5 minutes ago"

# Monitor real-time processing
tail -f /home/clide/hls/logs/webhook.log
```

## Security Considerations

1. **Webhook Secret**: Always configure `GITHUB_WEBHOOK_SECRET` for signature validation
2. **Firewall**: Ensure port 9000 is not directly accessible from internet
3. **SSL/TLS**: Use HTTPS for webhook URLs
4. **Access Logs**: Monitor NPM and webhook service logs for suspicious activity

## Performance Tuning

1. **Timeouts**: Adjust proxy timeouts based on Claude processing time
2. **Payload Size**: Set appropriate `client_max_body_size` for large diffs
3. **Rate Limiting**: Consider implementing rate limiting in NPM
4. **Resource Limits**: Monitor webhook service resource usage

This configuration ensures reliable webhook processing through Nginx Proxy Manager while maintaining security and performance.