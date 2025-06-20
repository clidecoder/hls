# HLS - GitHub Webhook Handler with Claude Integration

HLS (GitHub Event Handler with Claude Integration) is a FastAPI-based service that processes GitHub webhooks and uses Anthropic's Claude AI to analyze and respond to various GitHub events like issues, pull requests, reviews, and workflow runs.

## Features

- 🚀 **Fast webhook processing** with FastAPI and async/await
- 🤖 **Claude AI integration** for intelligent analysis and responses
- 🏷️ **Automatic labeling** based on AI analysis
- 💬 **Smart commenting** on issues and pull requests
- 🔒 **Secure webhook validation** with HMAC signatures
- 📊 **Built-in statistics** and monitoring
- 🎯 **Event filtering** by repository and event type
- 📝 **Customizable prompts** with Jinja2 templates
- ⚙️ **Flexible configuration** with YAML and environment variables

## Quick Start

### Prerequisites
- Python 3.8+
- GitHub Personal Access Token
- Anthropic API Key
- Public-facing server for webhooks

### Installation
```bash
# Clone the repository
git clone <repository-url>
cd hsl

# Install dependencies
pip install -r requirements.txt

# Copy configuration files
cp .env.example .env
cp config/settings.example.yaml config/settings.yaml

# Edit configuration files with your tokens and settings
nano .env
nano config/settings.yaml
```

### Configuration
1. **Set environment variables** in `.env`:
   ```bash
   GITHUB_TOKEN=your_github_token
   GITHUB_WEBHOOK_SECRET=your_webhook_secret
   ANTHROPIC_API_KEY=your_claude_api_key
   ```

2. **Configure repositories** in `config/settings.yaml`:
   ```yaml
   repositories:
     - name: "your-org/your-repo"
       enabled: true
       events: ["issues", "pull_request"]
   ```

3. **Set up GitHub webhook** in your repository settings:
   - URL: `https://your-domain.com/webhook`
   - Content type: `application/json`
   - Secret: Same as `GITHUB_WEBHOOK_SECRET`
   - Events: Issues, Pull requests, etc.

### Running
```bash
# Start the service
python -m hls.src.hls_handler.main

# Or with uvicorn
uvicorn hls.src.hls_handler.main:app --host 0.0.0.0 --port 8000
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
hsl/
├── ARCHITECTURE.md          # System architecture documentation
├── CLAUDE.md               # Claude Code guidance
├── DEPLOYMENT.md           # Deployment instructions
├── LIMITATIONS.md          # Known limitations and improvements
├── README.md              # This file
├── requirements.txt       # Python dependencies
├── .env.example          # Environment variables template
├── config/
│   └── settings.example.yaml  # Configuration template
├── prompts/              # Jinja2 prompt templates
│   ├── issues/          # Issue analysis prompts
│   ├── pull_requests/   # PR analysis prompts
│   ├── reviews/         # Review response prompts
│   ├── workflows/       # Workflow analysis prompts
│   └── releases/        # Release announcement prompts
└── hls/src/hls_handler/ # Core application code
    ├── main.py          # FastAPI application entry point
    ├── webhook_processor.py  # Core processing logic
    ├── handlers.py      # Event-specific handlers
    ├── clients.py       # API clients (Claude, GitHub)
    ├── config.py        # Configuration management
    ├── prompts.py       # Template management
    └── logging_config.py # Logging setup
```

## Example Workflow

1. **Developer opens an issue** in configured repository
2. **GitHub sends webhook** to HLS service
3. **HLS validates signature** and filters event
4. **Claude analyzes** issue content using custom prompts
5. **HLS applies labels** based on Claude's analysis
6. **HLS posts comment** (optional) with analysis summary
7. **Statistics updated** and event logged

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

- Webhook signatures are validated using HMAC-SHA256
- API keys are stored in environment variables
- No sensitive data is logged by default
- Rate limiting prevents API abuse

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