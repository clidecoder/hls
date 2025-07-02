# Auto-Accept Repository Invitations

This document describes the automatic repository collaboration invitation acceptance feature.

## Overview

The auto-accept invitations feature automatically processes GitHub repository collaboration invitations based on configurable criteria. It uses a cron-based polling approach to check for pending invitations and accept/decline them according to your specified rules.

## How It Works

1. **Polling**: Script runs periodically (via cron) to check for pending invitations
2. **Evaluation**: Each invitation is evaluated against configured criteria
3. **Action**: Invitations are automatically accepted, declined, or skipped
4. **Post-Acceptance Setup**: When accepted, automatically:
   - Clones the repository locally
   - Updates webhook handler configuration
   - Registers webhook in the new repository
   - Restarts the webhook service
5. **Logging**: All actions are logged for monitoring and debugging

## Configuration

### Basic Configuration

Add the following to your `config/settings.yaml`:

```yaml
auto_accept_invitations:
  enabled: true
  check_interval_minutes: 10
  log_level: "INFO"
  criteria:
    repository_patterns: ["*"]  # Accept all repositories by default
  
  # Post-acceptance actions
  post_acceptance:
    clone_repository: true
    clone_base_dir: "/home/clide"
    update_config: true
    register_webhook: true
    webhook_url: "https://clidecoder.com/hooks/github-webhook"
    webhook_events: ["issues", "pull_request", "pull_request_review"]
```

### Advanced Configuration

```yaml
auto_accept_invitations:
  enabled: true
  check_interval_minutes: 10
  log_level: "INFO"
  criteria:
    # Repository patterns to accept (glob patterns)
    repository_patterns: 
      - "my-org/*"        # Accept any repo in my-org
      - "*/project-*"     # Accept any repo starting with project-
      - "specific-repo"   # Accept specific repository
    
    # Only accept invitations from these organizations
    from_organizations:
      - "trusted-company"
      - "partner-org"
    
    # Only accept invitations from these specific users
    from_users:
      - "trusted-user"
      - "automation-bot"
    
    # Exclude repositories matching these patterns
    exclude_patterns:
      - "*/private-*"     # Exclude private repositories
      - "test-*"          # Exclude test repositories
      - "experimental/*"  # Exclude experimental repos
```

## Installation and Setup

### 1. Install Dependencies

The feature is included with the standard HLS webhook handler installation:

```bash
# If not already done
pip install -r requirements.txt
```

### 2. Configure GitHub Token

Ensure your GitHub token has the necessary permissions:

```bash
# In .env file
GITHUB_TOKEN=your_github_personal_access_token
```

**Required token scopes:**
- `repo` - To accept repository invitations
- `user` - To read user invitation data

### 3. Set Up Cron Job

Add to your crontab to run every 10 minutes:

```bash
crontab -e

# Add this line:
*/10 * * * * /home/clide/hls/scripts/cron_auto_accept_invitations.sh
```

### 4. Test the Setup

Test with a dry run first:

```bash
cd /home/clide/hls
python scripts/auto_accept_invitations.py --dry-run
```

## Usage

### Manual Execution

#### Auto-Accept Invitations Script
```bash
# Dry run (shows what would happen)
python scripts/auto_accept_invitations.py --dry-run

# Process invitations
python scripts/auto_accept_invitations.py

# Custom configuration file
python scripts/auto_accept_invitations.py --config /path/to/settings.yaml

# Custom log level
python scripts/auto_accept_invitations.py --log-level DEBUG
```

#### Repository Setup Script
For manual repository onboarding:
```bash
# Set up a specific repository
python scripts/setup_new_repository.py owner/repo-name

# Dry run to see what would happen
python scripts/setup_new_repository.py owner/repo-name --dry-run

# Use custom configuration
python scripts/setup_new_repository.py owner/repo-name --config path/to/settings.yaml
```

### Cron Execution

The cron wrapper script handles:
- Environment setup
- Lock file management (prevents concurrent runs)
- Error handling and logging
- Virtual environment activation

## Decision Logic

For each invitation, the system evaluates:

1. **Exclude Patterns**: If repository matches any exclude pattern → **DECLINE**
2. **Repository Patterns**: Must match at least one repository pattern
3. **Organization Filter**: If specified, inviter must be from allowed organization
4. **User Filter**: If specified, inviter must be in allowed users list

**Final Decision:**
- All criteria match → **ACCEPT**
- Any criteria fails → **SKIP** (no action)
- Matches exclude pattern → **DECLINE**

## Monitoring and Logging

### Log Files

- **Main Log**: `logs/auto_accept_invitations.log`
- **Cron Log**: `logs/cron_auto_accept_invitations.log`
- **Results**: `logs/invitation_results_<timestamp>.json`

### Log Levels

- **ERROR**: Critical failures, API errors
- **WARNING**: Non-critical issues, missing configurations
- **INFO**: Normal operations, decisions made
- **DEBUG**: Detailed processing information

### Monitoring Commands

```bash
# View recent activity
tail -f logs/auto_accept_invitations.log

# Check cron execution
tail -f logs/cron_auto_accept_invitations.log

# View recent results
ls -la logs/invitation_results_*.json | tail -5
```

## Security Considerations

### Token Security

- Store GitHub token in `.env` file (not in repository)
- Use tokens with minimal required permissions
- Rotate tokens regularly

### Access Control

- Review invitation criteria regularly
- Monitor acceptance activity via logs
- Consider setting up organization/user allowlists

### Audit Trail

- All actions are logged with details
- Results saved to JSON files for analysis
- Failed operations logged with error details

## Troubleshooting

### Common Issues

1. **No Invitations Processed**
   - Check if feature is enabled in configuration
   - Verify GitHub token has correct permissions
   - Check if criteria are too restrictive

2. **API Rate Limiting**
   - GitHub API has rate limits (5000 requests/hour)
   - Script respects rate limits and logs warnings
   - Consider reducing check frequency if needed

3. **Permission Errors**
   - Ensure GitHub token has `repo` and `user` scopes
   - Check if token is valid and not expired
   - Verify repository access permissions

### Debug Mode

Run with debug logging for detailed information:

```bash
python scripts/auto_accept_invitations.py --log-level DEBUG --dry-run
```

### Manual Verification

Check pending invitations manually:

```bash
# Using GitHub CLI (if installed)
gh api user/repository_invitations

# Or check via GitHub web interface
# https://github.com/settings/repositories
```

## Configuration Examples

### Accept All Invitations
```yaml
auto_accept_invitations:
  enabled: true
  check_interval_minutes: 10
  criteria:
    repository_patterns: ["*"]
```

### Organization-Only
```yaml
auto_accept_invitations:
  enabled: true
  check_interval_minutes: 15
  criteria:
    repository_patterns: ["*"]
    from_organizations: ["my-company", "trusted-partner"]
```

### Selective Acceptance
```yaml
auto_accept_invitations:
  enabled: true
  check_interval_minutes: 10
  criteria:
    repository_patterns: 
      - "company/*"
      - "*/public-*"
    from_organizations: ["trusted-org"]
    exclude_patterns: 
      - "*/test-*"
      - "experimental/*"
```

### Bot-Only
```yaml
auto_accept_invitations:
  enabled: true
  check_interval_minutes: 5
  criteria:
    repository_patterns: ["*"]
    from_users: ["github-actions[bot]", "dependabot[bot]"]
```

## Advanced Usage

### Custom Filtering

You can extend the `InvitationHandler` class to implement custom filtering logic:

```python
# In handlers.py
def _evaluate_invitation(self, invitation: Dict[str, Any]) -> str:
    # Add custom logic here
    repo_name = invitation["repository"]["full_name"]
    
    # Example: Only accept during business hours
    import datetime
    now = datetime.datetime.now()
    if now.hour < 9 or now.hour > 17:
        return "outside business hours"
    
    # Call parent method for standard criteria
    return super()._evaluate_invitation(invitation)
```

### Integration with Other Systems

The invitation processor can be integrated with:
- Slack notifications for accepted invitations
- Database logging for audit purposes
- Custom approval workflows

## Performance Considerations

### API Usage

- Each run makes ~2-3 GitHub API calls
- Rate limit: 5000 requests/hour per token
- Running every 10 minutes ≈ 144 calls/day (well within limits)

### Resource Usage

- Script runs for <10 seconds typically
- Minimal memory usage (~50MB)
- Log files grow slowly (rotate if needed)

### Optimization

- Adjust check interval based on invitation frequency
- Use exclude patterns to reduce processing
- Monitor logs for performance issues

## Complete Automation Workflow

When an invitation is accepted, the following automated sequence occurs:

1. **Invitation Acceptance** - Repository invitation is accepted via GitHub API
2. **Repository Cloning** - Repository is cloned to `{clone_base_dir}/{repo_name}`
3. **Configuration Update** - `config/settings.yaml` is automatically updated with:
   ```yaml
   - name: "owner/repo-name"
     enabled: true
     local_path: "/home/clide/repo-name"
     events: ["issues", "pull_request", "pull_request_review"]
     labels:
       auto_apply: true
     comments:
       auto_post: true
   ```
4. **Webhook Registration** - Webhook is registered in the new repository with:
   - URL: `https://clidecoder.com/hooks/github-webhook`
   - Events: Issues, Pull Requests, Reviews
   - Secret: From `GITHUB_WEBHOOK_SECRET`
5. **Service Restart** - `github-webhook` systemd service is restarted to load new configuration
6. **Immediate Availability** - Repository is immediately ready to receive webhooks and be processed

### Manual Repository Setup

You can also manually set up repositories without going through the invitation process:

```bash
# Set up any repository you have access to
python scripts/setup_new_repository.py owner/repo-name

# This performs the same steps 2-6 from the automation workflow
```

## File Structure After Setup

After accepting an invitation for `owner/repo-name`, the following structure is created:

```
/home/clide/
├── hls/                                    # Main webhook handler
│   ├── config/settings.yaml               # Updated with new repo config
│   └── logs/
│       ├── auto_accept_invitations.log     # Invitation processing logs
│       ├── repository_setup_*.json        # Setup results
│       └── invitation_results_*.json      # Invitation results
└── repo-name/                             # Cloned repository
    ├── .git/
    ├── CLAUDE.md                          # Project-specific instructions (if exists)
    └── ...                                # Repository contents
```

This feature provides automated, configurable, and secure handling of repository collaboration invitations while maintaining full audit trails and monitoring capabilities.