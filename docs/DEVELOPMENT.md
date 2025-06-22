# Development Guide

This guide covers development setup, testing, and contribution guidelines for the HLS webhook handler.

## Development Setup

### Prerequisites

- Python 3.8+
- Git
- GitHub CLI (`gh`) - optional but recommended
- Claude Code CLI - for AI integration testing

### Initial Setup

```bash
# Clone the repository
git clone https://github.com/clidecoder/hls.git
cd hls

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt  # Development dependencies

# Install pre-commit hooks
pre-commit install

# Copy development configuration
cp config/settings.example.yaml config/settings.yaml
cp .env.example .env
```

### Environment Configuration

Edit `.env` for development:

```bash
# GitHub (use a test repository)
GITHUB_TOKEN=ghp_your_development_token
GITHUB_WEBHOOK_SECRET=development_secret_123

# Claude (use mock mode for development)
ANTHROPIC_API_KEY=claude-code

# Development flags
DEBUG=true
LOG_LEVEL=DEBUG
MOCK_CLAUDE=true
SKIP_SIGNATURE_VALIDATION=true
```

Edit `config/settings.yaml`:

```yaml
development:
  debug: true
  skip_signature_validation: true
  mock_claude: true
  mock_github: false

repositories:
  - name: "your-username/test-repo"
    enabled: true
    events: ["issues", "pull_request"]

cron_analysis:
  enabled: false  # Disable in development
```

## Project Structure

```
hls/
├── hls/src/hsl_handler/           # Core application code
│   ├── main.py                    # FastAPI application entry point
│   ├── webhook_processor.py       # Main webhook processing logic
│   ├── handlers.py                # Event-specific handlers
│   ├── chained_handlers.py        # Chained prompt base classes
│   ├── chained_issue_handler.py   # Chained issue handler implementation
│   ├── clients.py                 # API clients (Claude, GitHub)
│   ├── config.py                  # Configuration management
│   ├── prompts.py                 # Template management
│   └── logging_config.py          # Logging configuration
├── scripts/                       # Utility scripts
│   ├── analyze_missed_issues.py   # Cron job for missed issues
│   └── cron_analyze_issues.sh     # Cron wrapper script
├── prompts/                       # Jinja2 templates
│   ├── issues/                    # Issue analysis prompts
│   │   ├── analyze.md             # Chained: Step 1
│   │   └── respond.md             # Chained: Step 2
│   └── pull_requests/             # PR analysis prompts
├── config/                        # Configuration files
├── docs/                          # Documentation
├── examples/                      # Example scripts
├── tests/                         # Test suite
└── outputs/                       # Generated analysis files
```

## Running the Application

### Development Mode

```bash
# Start FastAPI development server
uvicorn hls.src.hsl_handler.main:app --reload --host 0.0.0.0 --port 8000

# Or use the Python module
python -m hls.src.hsl_handler.main
```

### Webhook Service (for testing)

```bash
# Install webhook service
go install github.com/adnanh/webhook@latest

# Run webhook service
webhook -hooks hooks.json -port 9000 -verbose
```

### Testing Webhooks Locally

```bash
# Use ngrok for local webhook testing
ngrok http 9000

# Update GitHub webhook URL to: https://your-ngrok-id.ngrok.io/hooks
```

## Testing

### Unit Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=hls.src.hsl_handler

# Run specific test file
pytest tests/test_handlers.py

# Run with verbose output
pytest -v
```

### Integration Tests

```bash
# Test webhook signature validation
python test_webhook_signature.py

# Test Claude response parsing
python test_clide_response.py

# Test chained prompts
python examples/enable_chained_prompts.py

# Test cron job functionality
python scripts/analyze_missed_issues.py --dry-run
```

### Manual Testing

#### Test Issue Analysis

```bash
# Create test payload
cat > test_payload.json << 'EOF'
{
  "action": "opened",
  "issue": {
    "number": 1,
    "title": "Test Issue",
    "body": "This is a test issue for development",
    "user": {"login": "test-user"},
    "labels": [],
    "state": "open",
    "html_url": "https://github.com/test/repo/issues/1"
  },
  "repository": {
    "full_name": "test/repo",
    "name": "repo"
  },
  "sender": {"login": "test-user"}
}
EOF

# Test webhook processing
export GITHUB_EVENT=issues
export GITHUB_DELIVERY=test-123
./webhook_dispatch.py "$(cat test_payload.json)"
```

#### Test API Endpoints

```bash
# Health check
curl http://localhost:8000/health

# Statistics
curl http://localhost:8000/stats

# Send webhook (if running FastAPI)
curl -X POST http://localhost:8000/webhook \
  -H "Content-Type: application/json" \
  -H "X-GitHub-Event: issues" \
  -d @test_payload.json
```

## Development Workflows

### Adding New Event Types

1. **Create Handler**:
   ```python
   # hls/src/hsl_handler/handlers.py
   class NewEventHandler(BaseHandler):
       async def handle(self, payload, action):
           # Implementation
           pass
   ```

2. **Register Handler**:
   ```python
   # hls/src/hsl_handler/handlers.py
   HANDLERS = {
       "new_event": NewEventHandler,
       # ... existing handlers
   }
   ```

3. **Create Prompts**:
   ```bash
   mkdir prompts/new_event
   # Create prompt templates
   ```

4. **Update Configuration**:
   ```yaml
   # config/settings.yaml
   prompts:
     templates:
       new_event:
         default: "new_event/analyze.j2"
   ```

5. **Add Tests**:
   ```python
   # tests/test_new_event.py
   def test_new_event_handler():
       # Test implementation
   ```

### Adding Chained Prompts

1. **Create Chained Handler**:
   ```python
   # hls/src/hsl_handler/chained_new_handler.py
   class ChainedNewHandler(ChainedPromptHandler):
       def get_chain_steps(self, payload, action):
           return [
               ChainStep(name="analyze", prompt_key="new.analyze"),
               ChainStep(name="respond", prompt_key="new.respond")
           ]
   ```

2. **Create Prompt Templates**:
   ```bash
   # prompts/new/analyze.md
   # prompts/new/respond.md
   ```

3. **Enable Handler**:
   ```python
   # hls/src/hsl_handler/handlers.py
   HANDLERS["new_event"] = ChainedNewHandler
   ```

### Creating Custom Prompts

#### Single-Step Prompt Template

```jinja2
{# prompts/issues/custom.j2 #}
# Custom Issue Analysis

Analyze this issue from {{ repository.name }}:

**Title**: {{ issue.title }}
**Author**: {{ issue.user.login }}
**Created**: {{ issue.created_at }}

## Description
{{ issue.body }}

## Analysis Required
1. Determine issue category
2. Assess priority level
3. Suggest appropriate labels
4. Recommend next actions

Provide a structured response with clear recommendations.
```

#### Chained Prompt Templates

```markdown
<!-- prompts/issues/step1_analyze.md -->
# Issue Analysis - Step 1

Analyze this GitHub issue to understand its nature:

**Repository**: {{ repository.full_name }}
**Issue #**: {{ issue.number }}
**Title**: {{ issue.title }}
**Author**: {{ issue.user.login }}

## Issue Content
{{ issue.body }}

Determine:
1. **Type**: bug/feature/question/documentation
2. **Priority**: high/medium/low  
3. **Complexity**: easy/moderate/complex
4. **Component**: frontend/backend/database/other

Focus only on analysis, not response generation.
```

```markdown
<!-- prompts/issues/step2_respond.md -->
# Issue Response - Step 2

Based on the previous analysis, generate an appropriate response.

## Analysis Summary
{% if step1_data %}
- **Type**: {{ step1_data.type }}
- **Priority**: {{ step1_data.priority }}
- **Complexity**: {{ step1_data.complexity }}
{% endif %}

Generate a welcoming response that:
1. Thanks the contributor
2. Acknowledges the issue based on its type
3. Provides relevant guidance
4. Sets appropriate expectations

Be friendly and professional.
```

## Code Style

### Python Code Style

```python
# Use Black formatter
black hls/ scripts/ tests/

# Use isort for imports  
isort hls/ scripts/ tests/

# Use flake8 for linting
flake8 hls/ scripts/ tests/

# Use mypy for type checking
mypy hls/src/hsl_handler/
```

### Configuration

```python
# pyproject.toml
[tool.black]
line-length = 100
target-version = ['py38']

[tool.isort]
profile = "black"
line_length = 100

[tool.mypy]
python_version = "3.8"
warn_return_any = true
warn_unused_configs = true
```

### Pre-commit Hooks

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/psf/black
    rev: 22.3.0
    hooks:
      - id: black
  
  - repo: https://github.com/pycqa/isort
    rev: 5.10.1
    hooks:
      - id: isort
  
  - repo: https://github.com/pycqa/flake8
    rev: 4.0.1
    hooks:
      - id: flake8
```

## Debugging

### Debug Configuration

```yaml
# config/settings.yaml
development:
  debug: true
  mock_claude: true
  mock_github: false

logging:
  level: "DEBUG"
  format: "text"  # Easier to read during development
```

### Debug Environment Variables

```bash
export DEBUG=true
export LOG_LEVEL=DEBUG
export PYTHONPATH=/path/to/hls:$PYTHONPATH
```

### Common Debug Commands

```bash
# Debug webhook processing
python3 -c "
from hls.src.hsl_handler.config import load_settings
from hls.src.hsl_handler.webhook_processor import WebhookProcessor
import asyncio
import json

config = load_settings()
processor = WebhookProcessor(config)

# Test payload
payload = {'action': 'opened', 'issue': {'number': 1, 'title': 'Test'}}
result = asyncio.run(processor.process_webhook('issues', payload, 'test-123'))
print(result)
"

# Debug configuration loading
python3 -c "
from hls.src.hsl_handler.config import load_settings
config = load_settings()
print(f'Repos: {[r.name for r in config.repositories]}')
print(f'Features: {config.features}')
"

# Debug prompt loading
python3 -c "
from hls.src.hsl_handler.config import load_settings
from hls.src.hsl_handler.prompts import PromptLoader
config = load_settings()
loader = PromptLoader(config.prompts)
prompts = loader.list_available_prompts()
print(prompts)
"
```

### Debugging Chained Prompts

```python
# Debug chain execution
from hls.src.hsl_handler.chained_issue_handler import ChainedIssueHandler
from hls.src.hsl_handler.config import load_settings

config = load_settings()
handler = ChainedIssueHandler(config, None, None, None)

# Test chain steps
payload = {"action": "opened", "issue": {"title": "Test"}}
steps = handler.get_chain_steps(payload, "opened")
print(f"Chain steps: {[step.name for step in steps]}")
```

## Performance Testing

### Load Testing

```bash
# Install artillery for load testing
npm install -g artillery

# Create load test config
cat > artillery.yml << 'EOF'
config:
  target: 'http://localhost:8000'
  phases:
    - duration: 60
      arrivalRate: 10
scenarios:
  - name: "Health checks"
    flow:
      - get:
          url: "/health"
EOF

# Run load test
artillery run artillery.yml
```

### Memory Profiling

```bash
# Install memory profiler
pip install memory-profiler

# Profile memory usage
python -m memory_profiler scripts/analyze_missed_issues.py --dry-run
```

### Performance Monitoring

```python
# Add timing decorators
import time
import functools

def timing(func):
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        start = time.time()
        result = await func(*args, **kwargs)
        duration = time.time() - start
        print(f"{func.__name__} took {duration:.2f}s")
        return result
    return wrapper

# Use in handlers
@timing
async def handle(self, payload, action):
    # Handler implementation
```

## Contributing

### Pull Request Process

1. **Fork and Clone**
   ```bash
   git clone https://github.com/your-username/hls.git
   cd hls
   git remote add upstream https://github.com/clidecoder/hls.git
   ```

2. **Create Feature Branch**
   ```bash
   git checkout -b feature/your-feature-name
   ```

3. **Development**
   ```bash
   # Make changes
   # Add tests
   # Update documentation
   ```

4. **Test Changes**
   ```bash
   pytest
   python scripts/analyze_missed_issues.py --dry-run
   pre-commit run --all-files
   ```

5. **Commit and Push**
   ```bash
   git add .
   git commit -m "feat: add your feature description"
   git push origin feature/your-feature-name
   ```

6. **Create Pull Request**
   ```bash
   gh pr create --title "Add your feature" --body "Description of changes"
   ```

### Commit Message Format

```
type(scope): description

[optional body]

[optional footer]
```

**Types:**
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes
- `refactor`: Code refactoring
- `test`: Test additions or changes
- `chore`: Maintenance tasks

**Examples:**
```
feat(handlers): add support for workflow_run events
fix(cron): handle rate limiting in missed issue analysis
docs(readme): update installation instructions
test(handlers): add unit tests for issue handler
```

### Code Review Guidelines

**For Authors:**
- Include clear description of changes
- Add tests for new functionality
- Update documentation
- Ensure CI passes

**For Reviewers:**
- Check for security issues
- Verify test coverage
- Review error handling
- Test functionality locally

## Troubleshooting Development Issues

### Common Issues

1. **Module Import Errors**
   ```bash
   export PYTHONPATH=/path/to/hls:$PYTHONPATH
   python3 -c "import hls.src.hsl_handler.main"
   ```

2. **Virtual Environment Issues**
   ```bash
   deactivate
   rm -rf venv
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

3. **Configuration Errors**
   ```bash
   python3 -c "
   from hls.src.hsl_handler.config import load_settings
   try:
       config = load_settings()
       print('Config loaded successfully')
   except Exception as e:
       print(f'Config error: {e}')
   "
   ```

4. **GitHub API Issues**
   ```bash
   # Test token
   curl -H "Authorization: token $GITHUB_TOKEN" https://api.github.com/rate_limit
   
   # Check scopes
   curl -I -H "Authorization: token $GITHUB_TOKEN" https://api.github.com/user
   ```

### Getting Help

- Check [existing issues](https://github.com/clidecoder/hls/issues)
- Review [documentation](../README.md)
- Ask questions in discussions
- Join development Slack/Discord (if available)

## Related Documentation

- [Main README](../README.md)
- [Configuration Reference](CONFIGURATION.md)
- [Chained Prompts Guide](CHAINED_PROMPTS.md)
- [Cron Jobs Documentation](CRON_JOBS.md)
- [Deployment Guide](DEPLOYMENT.md)