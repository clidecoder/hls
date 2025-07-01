# Nginx Proxy Manager Configuration

## For GitHub Webhooks

### Proxy Host Configuration:

1. **Domain Names**: `webhooks.yourdomain.com` (or your preferred subdomain)
2. **Scheme**: `http`
3. **Forward Hostname / IP**: `localhost` or `127.0.0.1`
4. **Forward Port**: `9000`
5. **Block Common Exploits**: ✓ Enable
6. **Websockets Support**: Not required

### Custom Nginx Configuration (Advanced tab):
```nginx
# GitHub webhook specific settings
proxy_set_header X-Real-IP $remote_addr;
proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
proxy_set_header X-Forwarded-Proto $scheme;

# Pass GitHub headers
proxy_pass_header X-GitHub-Event;
proxy_pass_header X-GitHub-Delivery;
proxy_pass_header X-Hub-Signature-256;

# Increase body size for large payloads
client_max_body_size 10M;

# Timeout settings for webhook processing
proxy_read_timeout 300s;
proxy_connect_timeout 75s;
```

### SSL Configuration:
- **SSL Certificate**: Let's Encrypt (recommended)
- **Force SSL**: ✓ Enable
- **HTTP/2 Support**: ✓ Enable
- **HSTS Enabled**: ✓ Enable
- **HSTS Subdomains**: Optional

## For FastAPI Service (Optional)

### Proxy Host Configuration:

1. **Domain Names**: `api.yourdomain.com` (or your preferred subdomain)
2. **Scheme**: `http`
3. **Forward Hostname / IP**: `localhost` or `127.0.0.1`
4. **Forward Port**: `8000`
5. **Block Common Exploits**: ✓ Enable
6. **Websockets Support**: ✓ Enable (for FastAPI)

### Custom Nginx Configuration (Advanced tab):
```nginx
# FastAPI specific settings
proxy_set_header Host $http_host;
proxy_set_header X-Real-IP $remote_addr;
proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
proxy_set_header X-Forwarded-Proto $scheme;

# For Swagger UI
location /docs {
    proxy_pass http://localhost:8000/docs;
}

location /openapi.json {
    proxy_pass http://localhost:8000/openapi.json;
}
```

## GitHub Webhook URL

After configuration, your webhook URL will be:
- `https://webhooks.yourdomain.com/hooks`

Add this URL to your GitHub repository settings:
1. Go to Settings → Webhooks
2. Add webhook with the URL above
3. Content type: `application/json`
4. Secret: (use the value from your GITHUB_WEBHOOK_SECRET)
5. Events: Choose which events to receive