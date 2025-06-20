# HLS GitHub Webhook Handler - Architecture Documentation

## Overview

The HLS (GitHub Event Handler with Claude Integration) is a FastAPI-based service that processes GitHub webhooks and uses Claude AI to analyze and respond to various GitHub events like issues, pull requests, reviews, and workflow runs.

## High-Level Architecture

```
GitHub Repository → Webhook → HLS Service → Claude API → GitHub API
                                    ↓
                            Background Processing
                                    ↓
                              Statistics & Logs
```

## Core Components

### 1. **FastAPI Application** (`main.py`)
- **Purpose**: Entry point for webhook reception and validation
- **Key Features**:
  - Webhook signature validation using HMAC-SHA256
  - Request ID generation for tracking
  - Repository and event type filtering
  - Asynchronous background task scheduling
  - Health check and statistics endpoints

### 2. **Webhook Processor** (`webhook_processor.py`)
- **Purpose**: Orchestrates event processing workflow
- **Key Features**:
  - Event routing to appropriate handlers
  - Statistics collection and processing time tracking
  - Repository configuration validation
  - Error handling and logging
  - Health check for all components

### 3. **Event Handlers** (`handlers.py`)
- **Purpose**: Event-specific processing logic
- **Handlers Available**:
  - `IssueHandler`: Processes issue events (opened, edited, closed, etc.)
  - `PullRequestHandler`: Processes PR events (opened, synchronize, closed, etc.)
  - `ReviewHandler`: Processes PR review events
  - `WorkflowHandler`: Processes GitHub Actions workflow events
- **Common Features**:
  - Label extraction from Claude analysis
  - Priority and difficulty assessment
  - Automated GitHub API interactions (commenting, labeling)

### 4. **API Clients** (`clients.py`)

#### Claude Client
- **Purpose**: Interface with Anthropic's Claude API
- **Features**:
  - Basic rate limiting (1 request/second)
  - Request counting and timing
  - Async/await pattern with thread pool execution
  - Error handling and logging

#### GitHub Client  
- **Purpose**: Interface with GitHub's REST API
- **Features**:
  - Repository management (labels, issues, PRs)
  - Comment posting and label application
  - Rate limit monitoring
  - Statistics tracking for API usage

### 5. **Configuration Management** (`config.py`)
- **Purpose**: YAML-based configuration with Pydantic validation
- **Configuration Classes**:
  - `ServerConfig`: Host, port, webhook path
  - `GitHubConfig`: API tokens, webhook secrets
  - `ClaudeConfig`: API keys and model settings
  - `RepositoryConfig`: Per-repo settings and event filters
  - `LoggingConfig`: Structured logging configuration
  - `FeaturesConfig`: Feature flags and toggles

### 6. **Prompt Management** (`prompts.py`)
- **Purpose**: Jinja2-based template system for Claude prompts
- **Features**:
  - Event-specific prompt templates
  - Context variable injection
  - Template inheritance and composition
  - Dynamic prompt loading

### 7. **Logging System** (`logging_config.py`)
- **Purpose**: Structured logging with request tracking
- **Features**:
  - Request ID correlation across log entries
  - JSON-structured log output
  - Configurable log levels
  - Integration with FastAPI request lifecycle

## Data Flow

### Webhook Processing Flow

1. **Webhook Reception**
   ```
   GitHub → POST /webhook → Signature Validation → Request ID Generation
   ```

2. **Initial Filtering**
   ```
   Event Type Check → Repository Config Check → Event Enabled Check
   ```

3. **Processing Decision**
   ```
   Async Enabled? → Background Task OR Synchronous Processing
   ```

4. **Event Processing**
   ```
   Handler Selection → Claude Analysis → GitHub Actions → Response
   ```

5. **Statistics & Logging**
   ```
   Processing Time → Success/Failure Tracking → Request Correlation
   ```

## Directory Structure

```
/home/clide/hls/
├── ARCHITECTURE.md          # This file
├── CLAUDE.md               # Claude Code guidance
├── requirements.txt        # Python dependencies
├── prompts/               # Jinja2 templates
│   ├── issues/           # Issue-related prompts
│   ├── pull_requests/    # PR-related prompts
│   ├── reviews/          # Review-related prompts
│   ├── workflows/        # Workflow-related prompts
│   └── releases/         # Release-related prompts
└── hls/src/hls_handler/  # Core application
    ├── main.py           # FastAPI application
    ├── webhook_processor.py # Core processing logic
    ├── handlers.py       # Event handlers
    ├── clients.py        # API clients
    ├── config.py         # Configuration management
    ├── prompts.py        # Template management
    └── logging_config.py # Logging setup
```

## API Endpoints

### `GET /health`
- **Purpose**: Health check endpoint
- **Response**: Service status and component health

### `POST /webhook` (configurable path)
- **Purpose**: GitHub webhook receiver
- **Headers Required**:
  - `X-GitHub-Event`: Event type
  - `X-GitHub-Delivery`: Delivery ID
  - `X-Hub-Signature-256`: HMAC signature
- **Response**: Processing status or queued confirmation

### `GET /stats`
- **Purpose**: Processing statistics
- **Response**: Metrics on webhook processing, API usage, success rates

## Configuration System

### Settings File (`config/settings.yaml`)
```yaml
server:
  host: "0.0.0.0"
  port: 8000
  webhook_path: "/webhook"

github:
  token: "${GITHUB_TOKEN}"
  webhook_secret: "${GITHUB_WEBHOOK_SECRET}"

claude:
  api_key: "${ANTHROPIC_API_KEY}"
  model: "claude-3-5-sonnet-20241022"
  max_tokens: 4000

repositories:
  - name: "owner/repo"
    enabled: true
    events:
      - "issues"
      - "pull_request"
      - "pull_request_review"

features:
  signature_validation: true
  async_processing: true

logging:
  level: "INFO"
  format: "json"
```

## Prompt Template System

### Template Structure
- **Location**: `prompts/{event_type}/`
- **Format**: Jinja2 templates
- **Context Variables**: Event payload, repository config, metadata

### Example Template (`prompts/issues/analyze.j2`)
```jinja2
You are analyzing a GitHub issue for repository {{ repository.name }}.

Issue Details:
- Title: {{ issue.title }}
- Body: {{ issue.body }}
- Author: {{ issue.user.login }}
- Labels: {{ issue.labels | map(attribute='name') | list }}

Please analyze this issue and provide:
1. Priority assessment (high/medium/low)
2. Difficulty estimate (easy/moderate/complex)
3. Component classification (frontend/backend/database)
4. Suggested labels
5. Recommended response or action
```

## Deployment Considerations

### Environment Variables
```bash
export GITHUB_TOKEN="ghp_xxxxxxxxxxxxxxxxxxxx"
export GITHUB_WEBHOOK_SECRET="your_webhook_secret"
export ANTHROPIC_API_KEY="sk-ant-xxxxxxxxxxxxxxxxxxxx"
```

### System Requirements
- Python 3.8+
- Accessible webhook endpoint (public URL)
- GitHub webhook configuration
- Claude API access

### Running the Service
```bash
# Install dependencies
pip install -r requirements.txt

# Start the service
python -m hls.src.hls_handler.main

# Or with uvicorn
uvicorn hls.src.hls_handler.main:app --host 0.0.0.0 --port 8000
```

## Security Features

### Webhook Signature Validation
- HMAC-SHA256 verification of GitHub payloads
- Configurable webhook secrets per repository
- Protection against replay attacks

### API Key Management
- Environment variable-based secret storage
- No hardcoded credentials in source code
- Separate tokens for different services

### Input Validation
- Pydantic-based configuration validation
- JSON payload validation
- Event type and repository filtering

## Performance Characteristics

### Strengths
- Asynchronous processing with FastAPI
- Background task execution for non-blocking responses
- Request ID correlation for debugging
- Built-in rate limiting for Claude API

### Limitations
- Single-instance deployment (no horizontal scaling)
- In-memory statistics (lost on restart)
- Basic rate limiting (no sophisticated throttling)
- No webhook deduplication

## Monitoring and Observability

### Logging
- Structured JSON logging with request correlation
- Processing time tracking
- Error logging with stack traces
- API usage statistics

### Metrics Available
- Total webhook count
- Success/failure rates
- Processing times (average, distribution)
- Events by type and repository
- API rate limit status

### Health Checks
- Component health validation
- Dependency availability checks
- Service uptime tracking