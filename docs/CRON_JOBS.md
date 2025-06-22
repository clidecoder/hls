# Cron Jobs Documentation

This document describes the cron job system for analyzing missed issues in the HLS webhook handler.

## Overview

The cron job system provides a backup mechanism to catch and analyze GitHub issues that may have been missed by the webhook handler. This ensures comprehensive coverage of all issues.

## How It Works

### Main Components

1. **Main Script**: `scripts/analyze_missed_issues.py`
   - Python script that finds and processes unanalyzed issues
   - Uses the same chained prompt system as the webhook handler
   - Configurable via `config/settings.yaml`

2. **Wrapper Script**: `scripts/cron_analyze_issues.sh`
   - Bash wrapper designed for cron execution
   - Handles environment setup, logging, and error handling
   - Prevents concurrent executions with lock files

3. **Cron Configuration**: `config/crontab.txt`
   - Cron job definitions
   - Currently runs every hour at 15 minutes past the hour

### Process Flow

```
Cron Scheduler → Wrapper Script → Python Script → GitHub API → Claude Analysis → GitHub Actions
     ↓              ↓                ↓               ↓            ↓               ↓
  Every hour    Environment      Find Issues    Issue Data   AI Analysis    Comments/Labels
```

## Installation

### 1. Install Cron Job

```bash
crontab /home/clide/hls/config/crontab.txt
```

### 2. Verify Installation

```bash
crontab -l
```

### 3. Check Logs

```bash
tail -f /home/clide/hls/logs/cron-analyze.log
```

## Configuration

Edit `config/settings.yaml`:

```yaml
cron_analysis:
  enabled: true
  min_age_minutes: 30        # Only process issues older than 30 minutes
  max_issues_per_repo: 10    # Safety limit per repository
  delay_between_issues: 2    # Seconds to wait between processing issues
  analyzed_label: "clide-analyzed"  # Label to check for previous analysis
  log_level: "INFO"          # Logging level
```

## Manual Execution

### Dry Run (Test Mode)

```bash
cd /home/clide/hls
source venv/bin/activate
python3 scripts/analyze_missed_issues.py --dry-run
```

### Process Recent Issues

```bash
python3 scripts/analyze_missed_issues.py --min-age 30
```

### Process All Unanalyzed Issues

```bash
python3 scripts/analyze_missed_issues.py --min-age 0
```

### Custom Configuration

```bash
python3 scripts/analyze_missed_issues.py --config /path/to/config.yaml
```

## Monitoring

### Log Files

- **Cron Wrapper Logs**: `logs/cron-analyze.log`
- **Python Script Logs**: Included in cron-analyze.log
- **Main Webhook Logs**: `logs/webhook.log`

### Success Indicators

```bash
grep "Successfully processed missed issue" logs/cron-analyze.log
grep "Missed issue analysis completed" logs/cron-analyze.log
```

### Error Monitoring

```bash
grep "ERROR" logs/cron-analyze.log
grep "Failed to process missed issue" logs/cron-analyze.log
```

## Features

### Safety Mechanisms

1. **Lock File**: Prevents concurrent executions
2. **Rate Limiting**: Delays between API calls
3. **Issue Limits**: Maximum issues processed per run
4. **Age Filter**: Only processes issues older than specified age

### Smart Detection

- Checks for `clide-analyzed` label to avoid reprocessing
- Filters by repository configuration
- Skips pull requests (handled separately)
- Respects repository event settings

### Comprehensive Logging

- Structured logging with timestamps
- Process tracking and performance metrics
- Error reporting with stack traces
- Summary statistics

## Troubleshooting

### Common Issues

1. **Permission Errors**
   ```bash
   chmod +x /home/clide/hls/scripts/*.sh
   chmod +x /home/clide/hls/scripts/*.py
   ```

2. **Virtual Environment Issues**
   ```bash
   # Check if venv exists
   ls -la /home/clide/hls/venv/
   
   # Recreate if needed
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

3. **Configuration Errors**
   ```bash
   # Test configuration loading
   python3 -c "from hls.src.hsl_handler.config import load_settings; print(load_settings())"
   ```

4. **GitHub API Issues**
   ```bash
   # Check token
   gh auth status
   
   # Check rate limits
   gh api rate_limit
   ```

### Testing Lock File Behavior

```bash
# Manual lock test
touch /tmp/hls-analyze-issues.lock
/home/clide/hls/scripts/cron_analyze_issues.sh  # Should exit gracefully
rm /tmp/hls-analyze-issues.lock
```

### Debug Mode

```bash
python3 scripts/analyze_missed_issues.py --dry-run --log-level DEBUG
```

## Performance

### Typical Processing Times

- **Issue Analysis**: 30-60 seconds per issue (Claude response time)
- **GitHub API Calls**: 1-2 seconds per call
- **Total Runtime**: Depends on number of unanalyzed issues

### Optimization Tips

1. **Increase delays** if hitting rate limits
2. **Reduce max_issues_per_repo** for faster runs
3. **Increase min_age_minutes** to avoid duplicate processing

## Future Enhancements

- [ ] Email notifications for analysis summaries
- [ ] Slack/Discord integration for alerts
- [ ] Health check endpoint
- [ ] Metrics dashboard
- [ ] Retry logic for failed analyses
- [ ] Parallel processing for multiple repositories

## Related Documentation

- [Chained Prompts Guide](CHAINED_PROMPTS.md)
- [Main README](../README.md)
- [Configuration Guide](../config/README.md)