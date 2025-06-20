# HLS - GitHub Webhook Handler with Claude Integration

HLS (GitHub Event Handler with Claude Integration) is a production-ready webhook processing system that uses nginx for SSL termination, adnanh/webhook for secure webhook handling, and Python/FastAPI for GitHub event processing with Claude AI integration.

## Architecture Overview

```
GitHub → nginx (SSL) → webhook service → Python dispatcher → Event handlers → Claude AI
         :443/hooks     :9000             webhook_dispatch.py   FastAPI        API calls
```

## Features

- 🔒 **Production-grade security** with nginx SSL termination and webhook signatures
- 🚀 **Fast webhook processing** with adnanh/webhook and Python async
- 🤖 **Claude AI integration** for intelligent analysis and responses
- 🏷️ **Automatic labeling** based on AI analysis
- 💬 **Smart commenting** on issues and pull requests
- 📊 **Built-in statistics** and monitoring
- 🎯 **Event filtering** by repository and event type
- 📝 **Customizable prompts** with Jinja2 templates
- ⚙️ **Flexible configuration** with YAML and environment variables

## Quick Start

### Prerequisites
- Python 3.8+ with virtual environment
- nginx with SSL certificates
- webhook service (adnanh/webhook)
- GitHub Personal Access Token
- Claude Code CLI or Anthropic API Key
- Public domain with SSL (e.g., clidecoder.com)

### Installation

#### 1. Install webhook service
```bash
# Install webhook service (adnanh/webhook)
# Option 1: Download binary from GitHub releases
wget https://github.com/adnanh/webhook/releases/download/2.8.0/webhook-linux-amd64.tar.gz
tar -xvf webhook-linux-amd64.tar.gz

# Option 2: Install with go
go install github.com/adnanh/webhook@latest
```

#### 2. Clone and setup HLS
```bash
# Clone the repository
git clone https://github.com/clidecoder/hls.git
cd hls

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Copy configuration
cp config/settings.example.yaml config/settings.yaml
```

#### 3. Configure nginx
Add to your nginx site configuration:
```nginx
server {
    server_name your-domain.com;
    
    # Webhook endpoint for GitHub
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
        proxy_set_header X-Hub-Signature-256 $http_x_hub_signature_256;
        
        # Increase timeout for Claude processing
        proxy_read_timeout 300s;
        client_max_body_size 10M;
    }
    
    listen 443 ssl;
    # SSL certificates configured by certbot or manually
}
```

### Configuration

#### 1. Edit `config/settings.yaml`:
```yaml
github:
  token: "ghp_your_github_token"
  webhook_secret: "generate_secure_secret_with_openssl"
  
claude:
  api_key: "claude-code"  # or your Anthropic API key

repositories:
  - name: "your-org/your-repo"
    enabled: true
    events: ["issues", "pull_request"]
    labels:
      auto_apply: true
    comments:
      auto_post: true

features:
  signature_validation: true
  auto_labeling: true
  auto_commenting: true
```

#### 2. Generate webhook secret:
```bash
# Generate secure webhook secret
openssl rand -hex 32
```

#### 3. Update webhook dispatch script shebang:
```bash
# Edit webhook_dispatch.py first line to use venv Python
#!/home/your-user/hls/venv/bin/python
```

#### 4. Set up GitHub webhook:
```bash
# Use the setup script
source venv/bin/activate
python setup_github_webhook.py

# Or manually in GitHub repository settings:
# - URL: https://your-domain.com/hooks/github-webhook
# - Content type: application/json
# - Secret: Same as webhook_secret in settings.yaml
# - Events: Issues, Pull requests, etc.
```

### Running

#### 1. Start webhook service:
```bash
# Run webhook service (port 9000)
webhook -hooks hooks.json -port 9000 -verbose

# Or run in background
webhook -hooks hooks.json -port 9000 -verbose > webhook.log 2>&1 &
```

#### 2. (Optional) Run FastAPI service:
```bash
# Only needed if you want direct API access
# The webhook service calls webhook_dispatch.py directly
source venv/bin/activate
python -m hls.src.hls_handler.main
```

#### 3. Monitor logs:
```bash
# Webhook service logs
tail -f webhook.log

# Application logs
tail -f logs/webhook.log
```

## Documentation

### Core Documentation
- **[Architecture Guide](ARCHITECTURE.md)** - Detailed system architecture and components
- **[Deployment Guide](DEPLOYMENT.md)** - Complete deployment instructions and options
- **[Limitations & Improvements](LIMITATIONS.md)** - Known issues and enhancement recommendations
- **[Claude Code Guide](CLAUDE.md)** - Instructions for Claude Code when working with this repository

### Configuration
- **[Example Configuration](config/settings.example.yaml)** - Comprehensive configuration template
- **[Environment Variables](.env.example)** - Environment variable template

## API Endpoints

- `GET /health` - Health check and service status
- `POST /webhook` - GitHub webhook receiver (configurable path)
- `GET /stats` - Processing statistics and metrics

## Supported GitHub Events

| Event Type | Description | Actions |
|------------|-------------|---------|
| `issues` | Issue lifecycle events | Analysis, labeling, commenting |
| `pull_request` | Pull request events | Review, labeling, size estimation |
| `pull_request_review` | PR review events | Response generation, analysis |
| `workflow_run` | GitHub Actions events | Failure analysis, reporting |
| `release` | Release events | Announcement generation |

## Project Structure

```
hls/
├── webhook_dispatch.py      # Entry point called by webhook service
├── hooks.json              # Webhook service configuration
├── setup_github_webhook.py # GitHub webhook setup script
├── ARCHITECTURE.md         # System architecture documentation
├── CLAUDE.md              # Claude Code guidance
├── DEPLOYMENT.md          # Deployment instructions
├── LIMITATIONS.md         # Known limitations and improvements
├── README.md             # This file
├── requirements.txt      # Python dependencies
├── venv/                # Python virtual environment
├── config/
│   ├── settings.yaml         # Main configuration
│   └── settings.example.yaml # Configuration template
├── prompts/             # Jinja2 prompt templates
│   ├── issues/         # Issue analysis prompts
│   ├── pull_requests/  # PR analysis prompts
│   ├── reviews/        # Review response prompts
│   ├── workflows/      # Workflow analysis prompts
│   └── releases/       # Release announcement prompts
├── outputs/            # Analysis output files
│   ├── issues/
│   ├── pull_requests/
│   └── ...
├── logs/              # Application logs
│   └── webhook.log
└── hls/src/hsl_handler/ # Core application code
    ├── main.py         # FastAPI application (optional)
    ├── webhook_processor.py # Core processing logic
    ├── handlers.py     # Event-specific handlers
    ├── clients.py      # API clients (Claude, GitHub)
    ├── config.py       # Configuration management
    ├── prompts.py      # Template management
    └── logging_config.py # Logging setup
```

## Processing Flow Example

When a new issue is created on GitHub:

1. **GitHub sends webhook** to `https://your-domain.com/hooks/github-webhook`
2. **nginx receives HTTPS request** and proxies to webhook service on port 9000
3. **webhook service validates** the request matches `hooks.json` rules
4. **webhook service executes** `webhook_dispatch.py` with:
   - JSON payload as command argument
   - GitHub headers as environment variables
5. **webhook_dispatch.py**:
   - Loads settings from `config/settings.yaml`
   - Validates webhook signature (HMAC-SHA256)
   - Checks repository and event configuration
   - Initializes WebhookProcessor
6. **WebhookProcessor routes** to appropriate handler (e.g., IssueHandler)
7. **Handler processes event**:
   - Loads Jinja2 prompt template
   - Sends prompt to Claude for analysis
   - Parses Claude's response for labels and actions
8. **GitHub API updates**:
   - Applies suggested labels
   - Posts analysis comment
   - Marks issue as analyzed
9. **Response returned** to GitHub with processing status

## Customization

### Custom Prompts
Edit templates in the `prompts/` directory to customize Claude's analysis:

```jinja2
{# prompts/issues/analyze.j2 #}
Analyze this GitHub issue for {{ repository.name }}:

Title: {{ issue.title }}
Body: {{ issue.body }}
Author: {{ issue.user.login }}

Provide:
1. Priority (high/medium/low)
2. Difficulty (easy/moderate/complex)
3. Component (frontend/backend/database)
4. Suggested labels
```

### Repository-Specific Configuration
Configure different behavior per repository:

```yaml
repositories:
  - name: "org/frontend-repo"
    events: ["issues", "pull_request"]
    labels:
      categories: ["bug", "enhancement", "ui-ux"]
  
  - name: "org/backend-repo"
    events: ["issues", "pull_request", "workflow_run"]
    labels:
      categories: ["bug", "enhancement", "performance", "security"]
```

## Monitoring

### Health Checks
```bash
curl http://localhost:8000/health
```

### Statistics
```bash
curl http://localhost:8000/stats
```

### Logs
```bash
tail -f logs/hsl.log
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Submit a pull request

## Security

- **SSL/TLS termination** by nginx for encrypted webhook delivery
- **Webhook signatures** validated using HMAC-SHA256
- **Process isolation** with webhook service running dispatch script
- **Virtual environment** isolates Python dependencies
- **API keys** stored in configuration files (use proper file permissions)
- **No sensitive data** logged by default
- **Rate limiting** prevents API abuse

## License

[Add your license here]

## Support

For issues and questions:
1. Check the [Limitations document](LIMITATIONS.md) for known issues
2. Review the [Architecture document](ARCHITECTURE.md) for system details
3. Consult the [Deployment guide](DEPLOYMENT.md) for setup help
4. Open an issue in this repository

## Roadmap

See [LIMITATIONS.md](LIMITATIONS.md) for planned improvements:
- Message queue integration for better scalability
- Webhook deduplication
- Cost management and budgeting
- Enhanced monitoring and alerting
- Context retention across related events