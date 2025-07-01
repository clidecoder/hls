# HLS Docker Deployment

This directory contains the Docker configuration for deploying the HLS GitHub webhook handler.

## Architecture

Two-container setup:
- **nginx-proxy**: Reverse proxy with Let's Encrypt SSL support
- **app**: Python FastAPI + webhook service + Claude Code CLI

## Quick Start

1. **Configure environment**:
   ```bash
   cp .env.example .env
   # Edit .env with your values
   ```

2. **Configure HLS**:
   ```bash
   # Edit config/hls/settings.yaml with your repositories
   ```

3. **Build and run**:
   ```bash
   docker compose up -d
   ```

## Configuration

### Environment Variables (.env)
- `GITHUB_USERNAME`: Your GitHub username (for GHCR)
- `DOMAIN_NAME`: Your domain for SSL certificates
- `GITHUB_TOKEN`: GitHub personal access token
- `GITHUB_WEBHOOK_SECRET`: Webhook secret for validation
- `ANTHROPIC_API_KEY`: Claude API key (or "claude-code" for CLI)

### Directory Structure
```
containers/
├── config/               # Configuration files (read-only in containers)
│   ├── hls/             # HLS configuration
│   │   ├── settings.yaml # Main config file
│   │   └── hooks.json   # Webhook service config
│   ├── claude/          # Claude CLI config
│   │   └── .claude/     # Claude configuration files
│   └── nginx/           # Nginx additional configs
│       └── sites-enabled/
├── shared_state/        # Persistent data (host-mapped)
│   ├── sqlite/          # SQLite databases
│   ├── outputs/         # Analysis outputs
│   ├── logs/            # Application logs
│   └── docs/            # Planning/documentation
├── app/                 # Application container files
├── nginx/               # Nginx container files
└── docker-compose.yml   # Container orchestration
```

## Deployment

### Using GitHub Container Registry

1. **Login to GHCR**:
   ```bash
   docker login ghcr.io -u YOUR_USERNAME
   ```

2. **Build and push**:
   ```bash
   docker compose build
   docker compose push
   ```

3. **Deploy on server**:
   ```bash
   docker compose pull
   docker compose up -d
   ```

### First-time SSL Setup

For Let's Encrypt certificates:
```bash
# Start containers
docker compose up -d

# Get initial certificate
docker exec hls-nginx certbot --nginx -d your-domain.com -d www.your-domain.com
```

## GitHub Webhook Configuration

Configure your GitHub repository webhook:
- **URL**: `https://your-domain.com/hooks`
- **Content type**: `application/json`
- **Secret**: Same as `GITHUB_WEBHOOK_SECRET` in .env
- **Events**: Select events configured in settings.yaml

## Monitoring

View logs:
```bash
# All services
docker compose logs -f

# Specific service
docker compose logs -f app
docker compose logs -f nginx-proxy
```

Check health:
```bash
curl https://your-domain.com/health
```

## Volumes and Persistent Data

### Shared State Directory
All persistent application data is stored in the `shared_state/` directory, which is mapped to the host filesystem for easy access, backup, and migration:

```
shared_state/
├── sqlite/    # SQLite databases
├── outputs/   # Analysis outputs from Claude
├── logs/      # Application logs
└── docs/      # Planning documents and markdown files
```

### Docker Volumes
- `letsencrypt`: SSL certificates (Docker-managed)
- `certbot-www`: Certbot webroot (Docker-managed)

### Benefits of Shared State
- **Easy Backup**: All application data in one directory tree
- **Multi-container Ready**: Supports future scaling with shared state
- **Development Access**: Direct host access to SQLite databases and outputs
- **Documentation**: Central location for planning docs and notes

### Backup Instructions
To backup all application data:
```bash
# Backup shared state
tar -czf hls-backup-$(date +%Y%m%d).tar.gz shared_state/

# Restore from backup
tar -xzf hls-backup-YYYYMMDD.tar.gz
```