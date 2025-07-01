# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

This is a GitHub webhook handler service built with FastAPI that integrates with Claude AI to process GitHub events (issues, pull requests, reviews, etc.). The service receives webhooks from GitHub, validates them, and uses Claude to generate intelligent responses.

## Architecture

The codebase uses a webhook service intermediary architecture:

```
GitHub → Nginx Proxy Manager → webhook service → Python dispatch → Handler → Claude AI → GitHub API
         (strips /hooks)         (port 9000)      (webhook_dispatch.py)     ↓
              ↓                        ↓                    ↓          Prompt Loader
         Path Transform          Validation          Request Routing    (with repo context)
```

**Flow Components:**
- **Nginx Proxy Manager**: Routes `/hooks` to webhook service, strips path prefix
- **webhook service**: adnanh/webhook with `-urlprefix ""` for NPM compatibility
- **webhook_dispatch.py**: Python script that processes webhooks using existing modules
- **Repository Context**: Claude Code executes from local repository paths for proper context
- **FastAPI service**: Optional - can run on port 8000 for direct API access

**Key Configuration:**
- Webhook URL: `https://clidecoder.com/hooks/github-webhook`
- Local repository path: `/home/clide/hls` (configured in settings.yaml)
- Service configured for Nginx Proxy Manager path handling

### Key Modules

- **main.py**: FastAPI application entry point with webhook routing and validation
- **webhook_processor.py**: Core orchestration that coordinates handlers, clients, and prompts
- **handlers.py**: Event-specific handlers using Abstract Base Class pattern (IssueHandler, PullRequestHandler, etc.)
- **clients.py**: API clients for Claude (using subprocess) and GitHub (using PyGithub)
- **config.py**: Pydantic models for settings management with YAML configuration loading
- **prompts.py**: Jinja2 template loader for dynamic prompt generation
- **logging_config.py**: Structured logging with request correlation IDs

## Development Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Install webhook service (adnanh/webhook)
# Download from: https://github.com/adnanh/webhook/releases
# Or: go install github.com/adnanh/webhook@latest

# Run webhook service (production)
webhook -hooks hooks.json -port 9000 -verbose

# Test webhook dispatch script directly
echo '{"repository":{"full_name":"test/repo"}}' | GITHUB_EVENT=issues GITHUB_DELIVERY=123 ./webhook_dispatch.py

# Optional: Run FastAPI service for direct access
python -m hls.src.hls_handler.main
# Or: uvicorn hls.src.hls_handler.main:app --host 0.0.0.0 --port 8000

# Test Claude response parsing
python test_clide_response.py
```

## Configuration

The service uses layered configuration:

1. **Environment Variables** (.env file):
   - `GITHUB_TOKEN`: Personal access token for GitHub API
   - `GITHUB_WEBHOOK_SECRET`: Secret for webhook signature validation
   - `ANTHROPIC_API_KEY`: API key for Claude (defaults to "claude-code" for CLI)

2. **YAML Configuration** (config/settings.yaml):
   - Server settings (host, port, webhook_path)
   - Repository-specific configurations and feature flags
   - Prompt template mappings per event type

## API Endpoints

- `GET /health`: Health check endpoint
- `POST {webhook_path}`: GitHub webhook receiver (path from settings.yaml)
- `GET /stats`: Processing statistics endpoint

## Event Processing Flow

1. **nginx** receives webhook at `/hooks` and forwards to webhook service (port 9000)
2. **webhook service** validates request against `hooks.json` trigger rules
3. **webhook service** executes `webhook_dispatch.py` with GitHub headers and JSON payload
4. **webhook_dispatch.py** performs signature validation (if enabled)
5. Repository and event type filtering
6. Handler selection and processing using existing modules
7. Claude AI analysis using Jinja2 templates from `prompts/` directory  
8. GitHub API actions (labels, comments) based on Claude's response
9. JSON response returned to webhook service, which responds to GitHub

## Testing

When adding new features:
- Test webhook signatures with the provided `test_webhook_signature.py` script
- Verify Claude response parsing with `test_clide_response.py`
- Check handler logic by sending test payloads to the webhook endpoint

## Important Patterns

- **Abstract Base Classes**: All handlers inherit from `BaseHandler` in handlers.py
- **Webhook Service Integration**: Use `hooks.json` to configure webhook service routing
- **Direct Module Usage**: `webhook_dispatch.py` uses existing modules without FastAPI overhead
- **Structured Logging**: All logs include request_id for correlation
- **Template Customization**: Repository-specific prompts override defaults in settings.yaml
- **Repository Context**: Claude Code executes from local repository directories for full codebase access

## Configuration Files

- **hooks.json**: Webhook service configuration with trigger rules and dispatch settings
- **config/settings.yaml**: Repository configurations with local paths and event settings
- **services/github-webhook.service**: Systemd service with NPM-compatible configuration
- **webhook_dispatch.py**: Python script executed by webhook service for processing

## Documentation

- **[Startup Scripts](docs/startup-scripts.md)**: Service management and configuration
- **[Nginx Proxy Configuration](docs/nginx-proxy-configuration.md)**: NPM setup and troubleshooting
- **[Installation Guide](INSTALLATION.md)**: Quick setup instructions