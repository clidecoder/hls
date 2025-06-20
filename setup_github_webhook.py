#!/usr/bin/env python3
"""
Setup GitHub webhook for HLS repository

This script creates or updates the webhook configuration in the GitHub repository.
"""

import os
import sys
import json
import requests
from urllib.parse import urljoin

# Load configuration
CONFIG_FILE = "config/settings.yaml"

def load_config():
    """Load configuration from settings.yaml"""
    import yaml
    with open(CONFIG_FILE, 'r') as f:
        config = yaml.safe_load(f)
    return config

def create_webhook(repo_name, webhook_url, secret, token):
    """Create or update webhook in GitHub repository"""
    
    # GitHub API endpoint
    api_url = f"https://api.github.com/repos/{repo_name}/hooks"
    
    # Webhook configuration
    webhook_config = {
        "name": "web",
        "active": True,
        "events": [
            "issues",
            "issue_comment",
            "pull_request",
            "pull_request_review",
            "pull_request_review_comment",
            "push",
            "release",
            "workflow_run"
        ],
        "config": {
            "url": webhook_url,
            "content_type": "json",
            "secret": secret,
            "insecure_ssl": "0"
        }
    }
    
    # Headers
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    # Check if webhook already exists
    response = requests.get(api_url, headers=headers)
    if response.status_code == 200:
        webhooks = response.json()
        for webhook in webhooks:
            if webhook.get("config", {}).get("url") == webhook_url:
                print(f"Webhook already exists with ID {webhook['id']}, updating...")
                # Update existing webhook
                update_url = f"{api_url}/{webhook['id']}"
                response = requests.patch(update_url, json=webhook_config, headers=headers)
                if response.status_code == 200:
                    print("✅ Webhook updated successfully!")
                    return response.json()
                else:
                    print(f"❌ Failed to update webhook: {response.status_code}")
                    print(response.text)
                    return None
    
    # Create new webhook
    print("Creating new webhook...")
    response = requests.post(api_url, json=webhook_config, headers=headers)
    
    if response.status_code == 201:
        print("✅ Webhook created successfully!")
        return response.json()
    else:
        print(f"❌ Failed to create webhook: {response.status_code}")
        print(response.text)
        return None

def main():
    """Main function"""
    
    # Load configuration
    config = load_config()
    
    # Get settings
    webhook_secret = config["github"]["webhook_secret"]
    github_token = config["github"]["token"]
    
    # Webhook URL
    webhook_url = "https://clidecoder.com/hooks/github-webhook"
    
    # Repository name (should be in config)
    if config.get("repositories"):
        repo_name = config["repositories"][0]["name"]
    else:
        print("❌ No repository configured in settings.yaml")
        sys.exit(1)
    
    print(f"Setting up webhook for repository: {repo_name}")
    print(f"Webhook URL: {webhook_url}")
    print(f"Secret: {webhook_secret[:8]}...")
    
    # Create webhook
    result = create_webhook(repo_name, webhook_url, webhook_secret, github_token)
    
    if result:
        print("\n📋 Webhook Details:")
        print(f"ID: {result['id']}")
        print(f"URL: {result['config']['url']}")
        print(f"Events: {', '.join(result['events'])}")
        print(f"Active: {result['active']}")
        print("\n✅ GitHub webhook setup complete!")
        print("\nNext steps:")
        print("1. Test the webhook using GitHub's 'Recent Deliveries' tab")
        print("2. Create an issue or pull request to trigger the webhook")
        print("3. Monitor logs at: logs/webhook.log")
    else:
        print("\n❌ Failed to setup webhook")
        sys.exit(1)

if __name__ == "__main__":
    main()