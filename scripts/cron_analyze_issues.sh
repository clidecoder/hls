#!/bin/bash
"""
Cron wrapper script for analyzing missed issues.

This script is designed to be run by cron. It:
1. Sets up the proper environment
2. Runs the Python script
3. Handles logging and error reporting
4. Ensures only one instance runs at a time
"""

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
PYTHON_SCRIPT="$SCRIPT_DIR/analyze_missed_issues.py"
VENV_PATH="$PROJECT_DIR/venv"
LOG_DIR="$PROJECT_DIR/logs"
LOCK_FILE="/tmp/hls-analyze-issues.lock"
CONFIG_FILE="$PROJECT_DIR/config/settings.yaml"

# Ensure log directory exists
mkdir -p "$LOG_DIR"

# Logging function
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> "$LOG_DIR/cron-analyze.log"
}

# Error handling
handle_error() {
    log "ERROR: $1"
    exit 1
}

# Cleanup function
cleanup() {
    if [ -f "$LOCK_FILE" ]; then
        rm -f "$LOCK_FILE"
    fi
}

# Trap cleanup on exit
trap cleanup EXIT

# Check if script is already running
if [ -f "$LOCK_FILE" ]; then
    PID=$(cat "$LOCK_FILE")
    if kill -0 "$PID" 2>/dev/null; then
        log "Script already running with PID $PID, exiting"
        exit 0
    else
        log "Stale lock file found, removing"
        rm -f "$LOCK_FILE"
    fi
fi

# Create lock file
echo $$ > "$LOCK_FILE"

log "Starting missed issue analysis"

# Change to project directory
cd "$PROJECT_DIR" || handle_error "Could not change to project directory: $PROJECT_DIR"

# Activate virtual environment if it exists
if [ -d "$VENV_PATH" ]; then
    source "$VENV_PATH/bin/activate" || handle_error "Could not activate virtual environment"
    log "Activated virtual environment: $VENV_PATH"
else
    log "WARNING: No virtual environment found at $VENV_PATH"
fi

# Check if Python script exists
if [ ! -f "$PYTHON_SCRIPT" ]; then
    handle_error "Python script not found: $PYTHON_SCRIPT"
fi

# Check if config file exists
if [ ! -f "$CONFIG_FILE" ]; then
    handle_error "Configuration file not found: $CONFIG_FILE"
fi

# Set environment variables
export PYTHONPATH="$PROJECT_DIR:$PYTHONPATH"

# Run the Python script
log "Executing Python script with config: $CONFIG_FILE"
python3 "$PYTHON_SCRIPT" --config "$CONFIG_FILE" --log-level INFO 2>&1 | while IFS= read -r line; do
    log "$line"
done

EXIT_CODE=${PIPESTATUS[0]}

if [ $EXIT_CODE -eq 0 ]; then
    log "Missed issue analysis completed successfully"
else
    log "ERROR: Missed issue analysis failed with exit code $EXIT_CODE"
fi

# Clean up
cleanup

exit $EXIT_CODE