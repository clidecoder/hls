# Installation Guide

Quick start guide for installing the HLS webhook handler.

## Prerequisites

- Python 3.8+
- Git
- sudo access (for production installation)
- nginx (for webhook routing)

## Quick Install

### Development Mode
```bash
# Clone repository (if needed)
git clone <repository-url> hls
cd hls

# Run installer in development mode
./install.sh --dev
```

### Production Mode
```bash
# Clone repository (if needed)
git clone <repository-url> hls
cd hls

# Run installer with sudo for production mode
sudo ./install.sh --prod
```

### Interactive Mode
```bash
# Let the installer guide you
./install.sh
```

## Installation Options

The installer supports several command-line options:

- `--dev` - Install for development (pm2/nohup)
- `--prod` - Install for production (systemd services)
- `--skip-webhook-binary` - Skip webhook binary installation
- `--skip-systemd` - Skip systemd service setup
- `--skip-pm2` - Skip pm2 setup
- `--help` - Show help message

## What Gets Installed

1. **Python Dependencies** - All packages from requirements.txt
2. **Webhook Binary** - adnanh/webhook for receiving GitHub webhooks
3. **Configuration Files** - .env template and permissions
4. **Directories** - logs/, data/, config/, prompts/
5. **Startup Method** - Either pm2/nohup (dev) or systemd (prod)
6. **Cron Job** (optional) - Automatic issue analysis

## Post-Installation

1. **Configure Environment**
   ```bash
   # Edit .env file with your tokens
   nano .env
   ```
   Required values:
   - `GITHUB_TOKEN` - Personal access token with repo permissions
   - `GITHUB_WEBHOOK_SECRET` - Secret for webhook validation

2. **Start Services**
   
   Development:
   ```bash
   ./start-webhook.sh
   ```
   
   Production:
   ```bash
   sudo systemctl start github-webhook
   sudo systemctl start hls-fastapi  # Optional
   ```

3. **Configure GitHub Webhook**
   
   In your GitHub repository settings:
   - Payload URL: `https://your-domain.com/hooks`
   - Content type: `application/json`
   - Secret: Your `GITHUB_WEBHOOK_SECRET`
   - Events: Issues, Pull requests, Issue comments, etc.

4. **Verify Installation**
   ```bash
   # Check service status
   ./services/test-services.sh
   
   # Monitor logs
   tail -f logs/webhook.log
   ```

## Manual Installation

If you prefer to install components manually:

```bash
# 1. Install Python dependencies
pip install -r requirements.txt

# 2. Install webhook binary
wget https://github.com/adnanh/webhook/releases/download/2.8.1/webhook-linux-amd64.tar.gz
tar -xzf webhook-linux-amd64.tar.gz
sudo mv webhook-linux-amd64/webhook /usr/local/bin/
sudo chmod +x /usr/local/bin/webhook

# 3. Set up configuration
cp .env.example .env  # If exists
nano .env  # Add your tokens

# 4. Make scripts executable
chmod +x *.sh
chmod +x scripts/*.sh
chmod +x services/*.sh

# 5. Create directories
mkdir -p logs data config prompts

# 6. Start service
./start-webhook.sh
```

## Troubleshooting

### Installation Fails
- Check Python version: `python3 --version`
- Ensure you have pip: `python3 -m pip --version`
- For systemd installation, use sudo: `sudo ./install.sh --prod`

### Service Won't Start
- Check port 9000 is available: `sudo lsof -i :9000`
- Verify webhook binary: `which webhook`
- Check logs: `tail -f logs/webhook.log`

### Webhook Not Processing
- Verify nginx is routing to port 9000
- Check webhook secret matches GitHub
- Test with: `./services/test-services.sh`

## Uninstallation

To remove the services:

```bash
# Stop services
./stop-webhook.sh  # or: sudo systemctl stop github-webhook

# Remove systemd services (if installed)
sudo systemctl disable github-webhook hls-fastapi
sudo rm /etc/systemd/system/github-webhook.service
sudo rm /etc/systemd/system/hls-fastapi.service
sudo systemctl daemon-reload

# Remove from pm2 (if used)
pm2 delete github-webhook
pm2 save

# Remove cron job
crontab -e  # Remove the cron_analyze_issues.sh line
```

## Support

For detailed documentation, see:
- [Startup Scripts Documentation](docs/startup-scripts.md)
- [Main README](README.md)
- [Architecture Overview](CLAUDE.md)