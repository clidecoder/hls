#!/bin/bash

# Cron Auto-Accept Invitations Wrapper Script
# This script wraps the auto-accept invitations Python script for reliable cron execution
# It handles environment setup, logging, and lock file management

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
LOCK_FILE="$PROJECT_DIR/logs/auto_accept_invitations.lock"
LOG_FILE="$PROJECT_DIR/logs/cron_auto_accept_invitations.log"
PYTHON_SCRIPT="$SCRIPT_DIR/auto_accept_invitations.py"

# Ensure logs directory exists
mkdir -p "$PROJECT_DIR/logs"

# Function to log messages with timestamp
log_message() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" >> "$LOG_FILE"
}

# Function to cleanup on exit
cleanup() {
    if [ -f "$LOCK_FILE" ]; then
        rm -f "$LOCK_FILE"
        log_message "Removed lock file"
    fi
}

# Set up cleanup trap
trap cleanup EXIT

# Start logging
log_message "========================================="
log_message "Starting auto-accept invitations cron job"
log_message "Project directory: $PROJECT_DIR"
log_message "Script: $PYTHON_SCRIPT"

# Check if another instance is running
if [ -f "$LOCK_FILE" ]; then
    LOCK_PID=$(cat "$LOCK_FILE" 2>/dev/null)
    if [ -n "$LOCK_PID" ] && kill -0 "$LOCK_PID" 2>/dev/null; then
        log_message "Another instance is already running (PID: $LOCK_PID). Exiting."
        exit 0
    else
        log_message "Stale lock file found. Removing and continuing."
        rm -f "$LOCK_FILE"
    fi
fi

# Create lock file
echo $$ > "$LOCK_FILE"
log_message "Created lock file with PID: $$"

# Change to project directory
cd "$PROJECT_DIR" || {
    log_message "ERROR: Could not change to project directory: $PROJECT_DIR"
    exit 1
}

# Check if virtual environment exists and activate it
if [ -d "venv" ]; then
    log_message "Activating virtual environment"
    source venv/bin/activate || {
        log_message "ERROR: Could not activate virtual environment"
        exit 1
    }
else
    log_message "WARNING: No virtual environment found at $PROJECT_DIR/venv"
fi

# Check if Python script exists
if [ ! -f "$PYTHON_SCRIPT" ]; then
    log_message "ERROR: Python script not found: $PYTHON_SCRIPT"
    exit 1
fi

# Check if configuration file exists
CONFIG_FILE="$PROJECT_DIR/config/settings.yaml"
if [ ! -f "$CONFIG_FILE" ]; then
    log_message "ERROR: Configuration file not found: $CONFIG_FILE"
    exit 1
fi

# Set environment variables if .env file exists
ENV_FILE="$PROJECT_DIR/.env"
if [ -f "$ENV_FILE" ]; then
    log_message "Loading environment variables from .env"
    set -a  # automatically export all variables
    source "$ENV_FILE"
    set +a
else
    log_message "WARNING: No .env file found. Make sure GITHUB_TOKEN is set."
fi

# Run the Python script
log_message "Executing auto-accept invitations script"

# Capture start time
START_TIME=$(date +%s)

# Run the script and capture output
if python3 "$PYTHON_SCRIPT" --config "$CONFIG_FILE" >> "$LOG_FILE" 2>&1; then
    # Calculate execution time
    END_TIME=$(date +%s)
    DURATION=$((END_TIME - START_TIME))
    
    log_message "Auto-accept invitations script completed successfully in ${DURATION} seconds"
    exit_code=0
else
    # Calculate execution time
    END_TIME=$(date +%s)
    DURATION=$((END_TIME - START_TIME))
    
    log_message "Auto-accept invitations script failed after ${DURATION} seconds"
    exit_code=1
fi

# Clean up lock file (done by trap)
log_message "Cron job completed with exit code: $exit_code"
log_message "========================================="

exit $exit_code