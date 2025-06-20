# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

This is a GitHub webhook handler service built with FastAPI that integrates with Claude AI to process GitHub events (issues, pull requests, etc.). The service is designed to receive webhooks from GitHub, validate them, and use Claude to generate intelligent responses.

## Architecture

The codebase follows a modular architecture with these key components:

- **main.py**: FastAPI application entry point that handles webhook validation and routing
- **webhook_processor.py**: Core processing logic that coordinates between handlers, clients, and prompts

### Complete Module Structure

The codebase now includes all necessary modules:

- **config.py**: Settings management with YAML configuration loading (Settings, ServerConfig, GitHubConfig, etc.)
- **clients.py**: ClaudeClient and GitHubClient implementations for API interactions  
- **handlers.py**: Event-specific handlers (IssueHandler, PullRequestHandler, ReviewHandler, WorkflowHandler)
- **prompts.py**: PromptLoader class for template management
- **logging_config.py**: Structured logging setup with RequestIDProcessor

## Development Commands

Install dependencies:
```bash
pip install -r requirements.txt
```

To run the service:
```bash
# The application expects to be run as a module
python -m hls.src.hls_handler.main

# Or with uvicorn directly (as shown in main.py)
uvicorn hls.src.hls_handler.main:app --host 0.0.0.0 --port 8000
```

## Configuration

The service expects:
- A `config/settings.yaml` file containing:
  - Server configuration (host, port, webhook_path)
  - GitHub configuration (webhook_secret, API credentials)
  - Claude configuration (API key)
  - Repository-specific configurations
  - Feature flags (signature_validation, async_processing)
  - Logging configuration

## API Endpoints

- `GET /health`: Health check endpoint
- `POST {webhook_path}`: GitHub webhook receiver (path from settings.yaml)
- `GET /stats`: Processing statistics endpoint

## Webhook Processing Flow

1. Webhook received at configured path
2. Signature validation (if enabled)
3. Repository and event type filtering
4. Asynchronous or synchronous processing based on configuration
5. Event-specific handler invoked
6. Claude AI generates response
7. GitHub API updates (labels, comments)

## Additional Resources

- **prompts/**: Template directory containing Jinja2 templates for different event types (issues, pull_requests, reviews, workflows, releases)
- **requirements.txt**: All Python dependencies needed to run the application

## Next Steps

To complete the setup:
1. Create the `config/settings.yaml` file with appropriate configuration
2. Set environment variables for API keys (GitHub token, Anthropic API key)
3. Add tests for the webhook processing logic