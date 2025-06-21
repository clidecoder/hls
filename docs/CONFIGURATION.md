# Configuration Reference

This document provides a comprehensive reference for configuring the HLS webhook handler system.

## Configuration Files

### Main Configuration: `config/settings.yaml`

The primary configuration file that controls all aspects of the system.

```yaml
# Server settings
server:
  host: "0.0.0.0"
  port: 8000
  webhook_path: "/webhook"

# GitHub API configuration
github:
  token: "${GITHUB_TOKEN}"                    # GitHub Personal Access Token
  webhook_secret: "${GITHUB_WEBHOOK_SECRET}"  # Webhook signature secret
  base_url: "https://api.github.com"          # GitHub API base URL

# Claude AI configuration
claude:
  api_key: "claude-code"                      # API key or "claude-code" for CLI
  model: "claude-3-5-sonnet-20241022"        # Claude model to use
  max_tokens: 4000                           # Maximum tokens per request
  temperature: 0.1                           # Response creativity (0.0-1.0)
  timeout: 60                                # Request timeout in seconds

# Repository configuration
repositories:
  - name: "org/repo"                         # GitHub repository name
    enabled: true                            # Enable processing for this repo
    events: ["issues", "pull_request"]       # Events to process
    settings:                                # Repository-specific settings
      apply_labels: true                     # Auto-apply AI-suggested labels
      post_analysis_comments: true           # Post AI analysis as comments
      auto_close_invalid: false              # Auto-close invalid issues

# Feature flags
features:
  signature_validation: true                 # Validate webhook signatures
  async_processing: false                    # Enable async processing
  auto_labeling: true                       # Enable automatic labeling
  auto_commenting: true                     # Enable automatic commenting
  save_analyses: true                       # Save analysis files

# Prompt configuration
prompts:
  base_dir: "prompts"                       # Base directory for prompt templates
  templates:
    issues:
      opened: "issues/analyze.j2"           # Single-step analysis
      analyze: "issues/analyze.md"          # Chained: Step 1 - Analysis  
      respond: "issues/respond.md"          # Chained: Step 2 - Response
    pull_request:
      opened: "pull_requests/analyze.j2"    # PR analysis template

# Output configuration
outputs:
  base_dir: "outputs"                       # Base directory for output files
  directories:
    issues: "issues"                        # Issue analysis outputs
    pull_requests: "pull_requests"          # PR analysis outputs
    reviews: "reviews"                      # Review outputs
    workflows: "workflows"                  # Workflow outputs

# Logging configuration
logging:
  level: "INFO"                             # Log level (DEBUG, INFO, WARNING, ERROR)
  format: "json"                            # Log format (json, text)
  file: "logs/webhook.log"                  # Log file path
  max_size_mb: 10                          # Max log file size
  backup_count: 5                          # Number of backup files

# Cron job configuration for missed issues
cron_analysis:
  enabled: true                             # Enable cron analysis
  min_age_minutes: 30                       # Minimum issue age to process
  max_issues_per_repo: 10                   # Safety limit per repository
  delay_between_issues: 2                   # Seconds between processing
  analyzed_label: "clide-analyzed"          # Label marking analyzed issues
  log_level: "INFO"                         # Cron job log level

# Development settings
development:
  debug: false                              # Enable debug mode
  skip_signature_validation: false          # Skip webhook signature validation
  mock_claude: false                        # Use mock Claude responses
  mock_github: false                        # Use mock GitHub API
```

### Environment Variables: `.env`

Sensitive configuration stored in environment variables:

```bash
# GitHub Configuration
GITHUB_TOKEN=ghp_your_github_personal_access_token
GITHUB_WEBHOOK_SECRET=your_webhook_secret_generated_with_openssl

# Claude Configuration  
ANTHROPIC_API_KEY=claude-code  # or your Anthropic API key

# Optional: Override configuration
LOG_LEVEL=INFO
WEBHOOK_PORT=9000
```

### Webhook Service: `hooks.json`

Configuration for the adnanh/webhook service:

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

### Cron Jobs: `config/crontab.txt`

Cron job definitions for backup processing:

```bash
# Analyze missed issues every hour at 15 minutes past the hour
15 * * * * /home/clide/hls/scripts/cron_analyze_issues.sh

# Optional: Health check every 30 minutes
# */30 * * * * /home/clide/hls/scripts/health_check.sh

# Optional: Clean up logs weekly
# 0 2 * * 0 find /home/clide/hls/logs -name "*.log" -mtime +7 -delete
```

## Configuration Sections

### GitHub Configuration

```yaml
github:
  token: "${GITHUB_TOKEN}"
  webhook_secret: "${GITHUB_WEBHOOK_SECRET}"
  base_url: "https://api.github.com"
```

**Required Settings:**
- `token`: GitHub Personal Access Token with repository access
- `webhook_secret`: Secret for validating webhook signatures

**Token Permissions Required:**
- `repo` - Repository access
- `issues` - Issue management
- `pull_requests` - PR management  
- `metadata` - Repository metadata

### Claude Configuration

```yaml
claude:
  api_key: "claude-code"
  model: "claude-3-5-sonnet-20241022"
  max_tokens: 4000
  temperature: 0.1
  timeout: 60
```

**API Key Options:**
- `"claude-code"` - Use Claude Code CLI (recommended)
- `"sk-ant-..."` - Direct Anthropic API key

**Model Options:**
- `claude-3-5-sonnet-20241022` - Latest Sonnet (recommended)
- `claude-3-haiku-20240307` - Faster, cheaper option
- `claude-3-opus-20240229` - Most capable, slowest

### Repository Configuration

```yaml
repositories:
  - name: "org/repo"
    enabled: true
    events: ["issues", "pull_request", "pull_request_review"]
    settings:
      apply_labels: true
      post_analysis_comments: true
      auto_close_invalid: false
      custom_labels:
        - "ai-analyzed"
        - "needs-triage"
```

**Event Types:**
- `issues` - Issue created, edited, closed
- `pull_request` - PR created, updated, merged
- `pull_request_review` - Review requested, submitted
- `workflow_run` - GitHub Actions workflow completed

**Repository Settings:**
- `apply_labels`: Auto-apply AI-suggested labels
- `post_analysis_comments`: Post AI analysis as comments
- `auto_close_invalid`: Auto-close issues deemed invalid
- `custom_labels`: Additional labels to create/use

### Prompt Configuration

```yaml
prompts:
  base_dir: "prompts"
  templates:
    issues:
      # Single-step prompts
      opened: "issues/analyze.j2"
      closed: "issues/closed.j2"
      
      # Chained prompts
      analyze: "issues/analyze.md"
      respond: "issues/respond.md"
      
    pull_request:
      opened: "pull_requests/analyze.j2"
      new_pr: "pull_requests/new.md"
      pr_updated: "pull_requests/updated.md"
```

**Template Types:**
- **Single-step**: One prompt processes the entire event
- **Chained**: Multiple prompts with context sharing

**Template Variables:**
- `{{ issue }}` - Issue data
- `{{ pull_request }}` - PR data  
- `{{ repository }}` - Repository info
- `{{ sender }}` - User who triggered event

### Feature Flags

```yaml
features:
  signature_validation: true    # Validate webhook signatures
  async_processing: false       # Use async processing
  auto_labeling: true          # Apply AI-suggested labels
  auto_commenting: true        # Post AI comments
  save_analyses: true          # Save analysis files
```

**Development Flags:**
```yaml
development:
  debug: true                  # Enable debug logging
  skip_signature_validation: true  # Skip webhook validation
  mock_claude: true           # Use mock AI responses
  mock_github: true           # Use mock GitHub API
```

### Cron Analysis Configuration

```yaml
cron_analysis:
  enabled: true
  min_age_minutes: 30          # Only process issues older than 30 minutes
  max_issues_per_repo: 10      # Process max 10 issues per repo per run
  delay_between_issues: 2      # Wait 2 seconds between processing issues
  analyzed_label: "clide-analyzed"  # Label marking processed issues
  log_level: "INFO"            # Log level for cron jobs
```

**Safety Settings:**
- `min_age_minutes`: Prevents processing issues still being handled by webhooks
- `max_issues_per_repo`: Prevents runaway processing
- `delay_between_issues`: Rate limiting for API calls

## Environment-Specific Configuration

### Development Environment

```yaml
# config/development.yaml
server:
  port: 8001
  
development:
  debug: true
  skip_signature_validation: true
  mock_claude: true
  
logging:
  level: "DEBUG"
  
cron_analysis:
  enabled: false  # Disable cron jobs in development
```

### Production Environment

```yaml
# config/production.yaml
server:
  host: "127.0.0.1"  # Only local connections
  
features:
  signature_validation: true
  
logging:
  level: "INFO"
  file: "/var/log/hls/webhook.log"
  
development:
  debug: false
  mock_claude: false
  mock_github: false
```

### Testing Environment

```yaml
# config/testing.yaml
development:
  mock_claude: true
  mock_github: true
  
repositories:
  - name: "test-org/test-repo"
    enabled: true
    events: ["issues"]
    
cron_analysis:
  enabled: false
```

## Configuration Loading

### Order of Precedence

1. **Environment Variables** (highest priority)
2. **YAML Configuration File**
3. **Default Values** (lowest priority)

### Loading Custom Configuration

```bash
# Specify custom config file
export CONFIG_FILE=/path/to/config.yaml
python -m hls.src.hls_handler.main

# Or use command line argument
python scripts/analyze_missed_issues.py --config /path/to/config.yaml
```

### Environment Variable Overrides

```bash
# Override any setting with environment variables
export GITHUB_TOKEN=ghp_new_token
export LOG_LEVEL=DEBUG
export WEBHOOK_PORT=9001
```

## Validation

### Configuration Validation

```bash
# Test configuration loading
python3 -c "
from hls.src.hsl_handler.config import load_settings
config = load_settings('config/settings.yaml')
print('Configuration loaded successfully')
print(f'Repositories: {[r.name for r in config.repositories]}')
"
```

### GitHub Token Validation

```bash
# Test GitHub token
gh auth status

# Or with curl
curl -H "Authorization: token $GITHUB_TOKEN" https://api.github.com/user
```

### Webhook Secret Validation

```bash
# Generate new webhook secret
openssl rand -hex 32

# Test webhook signature validation
python test_webhook_signature.py
```

## Security Best Practices

### File Permissions

```bash
# Secure configuration files
chmod 600 config/settings.yaml
chmod 600 .env

# Secure scripts
chmod 755 scripts/*.sh
chmod 755 webhook_dispatch.py
```

### Environment Variables

```bash
# Use environment variables for secrets
export GITHUB_TOKEN="$(cat /secure/path/github_token)"
export GITHUB_WEBHOOK_SECRET="$(cat /secure/path/webhook_secret)"
```

### Webhook Security

```yaml
features:
  signature_validation: true  # Always enable in production

github:
  webhook_secret: "${GITHUB_WEBHOOK_SECRET}"  # Use environment variable
```

## Troubleshooting

### Common Configuration Issues

1. **Invalid YAML Syntax**
   ```bash
   python3 -c "import yaml; yaml.safe_load(open('config/settings.yaml'))"
   ```

2. **Missing Environment Variables**
   ```bash
   python3 -c "import os; print('GITHUB_TOKEN' in os.environ)"
   ```

3. **Invalid GitHub Token**
   ```bash
   curl -H "Authorization: token $GITHUB_TOKEN" https://api.github.com/rate_limit
   ```

4. **Webhook Secret Mismatch**
   - Verify secret matches in GitHub webhook settings
   - Check GITHUB_WEBHOOK_SECRET environment variable

### Configuration Debugging

```bash
# Enable debug mode
export LOG_LEVEL=DEBUG
export DEBUG=true

# Test individual components
python3 -c "from hls.src.hsl_handler.clients import GitHubClient; print('GitHub client OK')"
python3 -c "from hls.src.hsl_handler.clients import ClaudeClient; print('Claude client OK')"
```

## Migration Guide

### Upgrading Configuration

When upgrading to new versions:

1. **Backup current configuration**
   ```bash
   cp config/settings.yaml config/settings.yaml.backup
   ```

2. **Compare with new template**
   ```bash
   diff config/settings.yaml config/settings.example.yaml
   ```

3. **Add new required fields**
   ```bash
   # Check for new configuration options in changelog
   ```

4. **Test new configuration**
   ```bash
   python3 scripts/analyze_missed_issues.py --dry-run
   ```

## Related Documentation

- [Chained Prompts Guide](CHAINED_PROMPTS.md)
- [Cron Jobs Documentation](CRON_JOBS.md)
- [Main README](../README.md)
- [Deployment Guide](DEPLOYMENT.md)