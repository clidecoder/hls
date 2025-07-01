# Startup Scripts Documentation

This document describes all startup scripts and service files for the HLS webhook handler.

## Overview

The HLS webhook handler can be started in several ways:
1. **Development**: Using `start-webhook.sh` with pm2 or nohup
2. **Production**: Using systemd services via `install-services.sh`
3. **Manual**: Direct webhook command execution

## Scripts

### Main Control Scripts

#### start-webhook.sh
- **Purpose**: Start the webhook service on port 9000
- **Location**: `/home/clide/hls/start-webhook.sh`
- **Features**:
  - Checks if service is already running
  - Prefers pm2 if available (better process management)
  - Falls back to nohup for background execution
  - Creates log files in `logs/` directory

#### stop-webhook.sh
- **Purpose**: Stop the running webhook service
- **Location**: `/home/clide/hls/stop-webhook.sh`
- **Features**:
  - Handles both pm2 and direct process termination
  - Verifies service is running before attempting stop
  - Provides clear status messages

### Service Installation Scripts

#### services/install-services.sh
- **Purpose**: Install and configure systemd services
- **Location**: `/home/clide/hls/services/install-services.sh`
- **Requires**: sudo privileges
- **Actions**:
  1. Copies service files to `/etc/systemd/system/`
  2. Reloads systemd daemon
  3. Enables services for auto-start on boot
  4. Starts both github-webhook and hls-fastapi services
  5. Shows service status and log commands

#### services/test-services.sh
- **Purpose**: Verify services are running correctly
- **Location**: `/home/clide/hls/services/test-services.sh`
- **Checks**:
  - Systemd service status
  - Port availability (9000 and 8000)
  - Health endpoint responses
  - Recent log entries

### Utility Scripts

#### scripts/cron_analyze_issues.sh
- **Purpose**: Cron job wrapper for analyzing missed issues
- **Location**: `/home/clide/hls/scripts/cron_analyze_issues.sh`
- **Features**:
  - Sets up proper environment
  - Activates virtual environment
  - Implements lock file to prevent concurrent runs
  - Comprehensive logging
  - Runs `analyze_missed_issues.py`

## Service Files

### github-webhook.service
- **Purpose**: Main webhook receiver service
- **Port**: 9000
- **Features**:
  - Enhanced security (ProtectSystem, PrivateTmp)
  - Automatic restart on failure
  - Logs to systemd journal
  - Runs as user 'clide'

### hls-fastapi.service
- **Purpose**: Optional FastAPI service for direct API access
- **Port**: 8000
- **Features**:
  - Uses uvicorn ASGI server
  - Provides REST API endpoints
  - Health check at `/health`
  - Optional component (not required for webhook processing)

## Configuration Files

### hooks.json
- **Purpose**: Webhook service configuration
- **Key Settings**:
  - Trigger rules for different GitHub events
  - Executes `webhook_dispatch.py` on receipt
  - Passes GitHub headers as environment variables
  - Stdin receives full JSON payload

### ecosystem.config.js
- **Purpose**: pm2 process manager configuration
- **Alternative to**: systemd services
- **Features**:
  - Process monitoring and auto-restart
  - Log rotation
  - Resource monitoring

## Startup Methods

### 1. Development Mode (Recommended for testing)
```bash
cd /home/clide/hls
./start-webhook.sh
```

### 2. Production Mode (Recommended for deployment)
```bash
cd /home/clide/hls
sudo ./services/install-services.sh
```

### 3. Manual Mode (For debugging)
```bash
cd /home/clide/hls
webhook -hooks hooks.json -port 9000 -verbose
```

### 4. Docker Mode (If using containers)
```bash
docker-compose up -d
```

## Process Flow

```
GitHub Webhook → Nginx Proxy Manager → Port 9000 → webhook service → webhook_dispatch.py
    (https://clidecoder.com/hooks/github-webhook)    (/github-webhook)           ↓
                                                                         Python handlers
                                                                                ↓
                                                                          Claude AI
                                                                      (with repo context)
                                                                                ↓
                                                                          GitHub API
```

## Nginx Proxy Manager Configuration

The webhook service is configured to work with Nginx Proxy Manager (NPM) which strips URL prefixes:

### URL Path Handling
- **GitHub webhook URL**: `https://clidecoder.com/hooks/github-webhook`
- **NPM strips `/hooks`**: Forwards to `http://localhost:9000/github-webhook`
- **Webhook service**: Configured with `-urlprefix ""` to serve at root path

### Service Configuration
The webhook service uses the `-urlprefix ""` flag to handle path stripping:
```bash
/usr/bin/webhook -hooks /home/clide/hls/hooks.json -port 9000 -verbose -urlprefix ""
```

**Important**: If using a different proxy setup that preserves paths, remove the `-urlprefix ""` flag.

## Repository Configuration

### Local Repository Paths
The webhook handler executes Claude Code from within specific repository directories to provide proper code context.

#### Configuration (config/settings.yaml)
```yaml
repositories:
  - name: "clidecoder/hls"
    enabled: true
    local_path: "/home/clide/hls"  # Local repository directory
    events:
      - "issues"
      - "pull_request"
    labels:
      auto_apply: true
    comments:
      auto_post: true
```

#### Benefits of Local Paths
- **Repository Context**: Claude Code has access to the full codebase
- **CLAUDE.md Files**: Project-specific instructions are loaded
- **Multi-Project Support**: Different repositories can have different local paths

#### Adding New Repositories
To add support for additional repositories:

1. **Clone the repository locally**:
   ```bash
   git clone https://github.com/owner/repo-name /path/to/local/repo
   ```

2. **Add to config/settings.yaml**:
   ```yaml
   repositories:
     - name: "owner/repo-name"
       enabled: true
       local_path: "/path/to/local/repo"
       events: ["issues", "pull_request"]
   ```

3. **Restart the service**:
   ```bash
   sudo systemctl restart github-webhook
   ```

4. **Configure GitHub webhook** to point to:
   ```
   https://clidecoder.com/hooks/github-webhook
   ```

## Monitoring

### Check Service Status
```bash
# For systemd services
sudo systemctl status github-webhook
sudo systemctl status hls-fastapi

# For pm2
pm2 status

# For manual processes
ps aux | grep webhook
```

### View Logs
```bash
# Systemd logs
sudo journalctl -u github-webhook -f
sudo journalctl -u hls-fastapi -f

# pm2 logs
pm2 logs github-webhook

# File logs
tail -f logs/webhook.log
tail -f logs/webhook.err
```

### Test Endpoints
```bash
# Webhook service (no direct HTTP endpoint)
curl http://localhost:9000/hooks  # Will return 405 without proper webhook

# FastAPI service (if running)
curl http://localhost:8000/health
```

## Troubleshooting

### Service Won't Start
1. Check if port is already in use: `sudo lsof -i :9000`
2. Verify webhook binary exists: `which webhook`
3. Check permissions on scripts: `ls -la *.sh`
4. Review logs for errors

### Webhook Not Processing
1. **Check URL Configuration**:
   - GitHub webhook URL: `https://clidecoder.com/hooks/github-webhook`
   - Verify NPM strips `/hooks` correctly
   - Test locally: `curl -X POST http://localhost:9000/github-webhook`

2. **Verify Service Configuration**:
   - Ensure `-urlprefix ""` flag is set for NPM
   - Check webhook secret matches GitHub
   - Verify repository is configured in settings.yaml

3. **Test Repository Context**:
   ```bash
   # Verify local path exists and is accessible
   ls -la /home/clide/hls
   
   # Check if Claude Code works from the directory
   cd /home/clide/hls && claude --version
   ```

4. **Check Logs**:
   ```bash
   # Service logs
   sudo journalctl -u github-webhook -f
   
   # Webhook processing logs
   tail -f logs/webhook.log
   ```

### Permission Issues
1. Ensure scripts are executable: `chmod +x *.sh`
2. Service files need root to install
3. Log directories must be writable by service user
4. Repository local_path must be readable by service user

### GitHub Webhook Issues
1. **Webhook Secret Mismatch**:
   - Verify `GITHUB_WEBHOOK_SECRET` in .env matches GitHub
   - Check signature validation in logs

2. **Path Issues**:
   - Ensure URL ends with `/github-webhook`
   - Verify Content-Type is `application/json`

3. **Repository Not Configured**:
   - Add repository to config/settings.yaml
   - Restart service after configuration changes

## Cron Jobs

To set up automatic issue analysis:
```bash
# Add to crontab
crontab -e

# Run every 6 hours
0 */6 * * * /home/clide/hls/scripts/cron_analyze_issues.sh
```

## Security Considerations

1. **Webhook Secret**: Always use GITHUB_WEBHOOK_SECRET in production
2. **File Permissions**: Keep service files readable only by root
3. **API Keys**: Store in .env file, never commit to repository
4. **Network**: Consider firewall rules for webhook endpoint
5. **Logs**: May contain sensitive data, secure appropriately