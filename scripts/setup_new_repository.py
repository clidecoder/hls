#!/home/clide/hls/venv/bin/python
"""
New Repository Setup Script

This script handles the complete onboarding of a new repository:
1. Clones the repository locally
2. Updates the webhook handler configuration
3. Registers the webhook in the repository
4. Restarts the webhook service

Usage: python setup_new_repository.py <repo_full_name> [--dry-run]
"""

import asyncio
import argparse
import json
import logging
import os
import subprocess
import sys
import tempfile
import yaml
from pathlib import Path
from typing import Dict, Any, Optional

# Add the project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from hls.src.hsl_handler.config import Settings
from hls.src.hsl_handler.clients import GitHubClient
from hls.src.hsl_handler.logging_config import setup_logging


class RepositorySetup:
    """Handle new repository setup and onboarding."""
    
    def __init__(self, settings: Settings, github_client: GitHubClient, 
                 dry_run: bool = False):
        self.settings = settings
        self.github_client = github_client
        self.dry_run = dry_run
        self.logger = logging.getLogger(__name__)
        
    async def setup_repository(self, repo_full_name: str) -> Dict[str, Any]:
        """Complete setup process for a new repository."""
        
        self.logger.info(f"Starting repository setup for: {repo_full_name}")
        
        result = {
            "repository": repo_full_name,
            "dry_run": self.dry_run,
            "steps": {},
            "success": False
        }
        
        try:
            # Step 1: Get repository information
            repo_info = await self.github_client.get_repository_info(repo_full_name)
            if not repo_info:
                raise Exception("Could not retrieve repository information")
            
            result["repo_info"] = repo_info
            self.logger.info(f"Retrieved repository info: {repo_info['description'] or 'No description'}")
            
            # Step 2: Clone repository
            clone_result = await self._clone_repository(repo_info)
            result["steps"]["clone"] = clone_result
            
            # Step 3: Update configuration
            config_result = await self._update_configuration(repo_info)
            result["steps"]["config_update"] = config_result
            
            # Step 4: Register webhook
            webhook_result = await self._register_webhook(repo_full_name)
            result["steps"]["webhook"] = webhook_result
            
            # Step 5: Restart service (if not dry run)
            restart_result = await self._restart_service()
            result["steps"]["service_restart"] = restart_result
            
            # Check if all steps succeeded
            all_success = all(
                step.get("success", False) 
                for step in result["steps"].values()
            )
            
            result["success"] = all_success
            
            if all_success:
                self.logger.info(f"Repository setup completed successfully: {repo_full_name}")
            else:
                self.logger.warning(f"Repository setup completed with some failures: {repo_full_name}")
            
        except Exception as e:
            self.logger.error(f"Repository setup failed: {e}", exc_info=True)
            result["error"] = str(e)
        
        return result
    
    async def _clone_repository(self, repo_info: Dict[str, Any]) -> Dict[str, Any]:
        """Clone the repository to the local directory."""
        
        if not self.settings.auto_accept_invitations.post_acceptance.clone_repository:
            return {"success": True, "skipped": True, "reason": "cloning disabled"}
        
        clone_base = self.settings.auto_accept_invitations.post_acceptance.clone_base_dir
        repo_name = repo_info["name"]
        clone_path = Path(clone_base) / repo_name
        
        self.logger.info(f"Cloning repository to: {clone_path}")
        
        if self.dry_run:
            return {
                "success": True,
                "dry_run": True,
                "clone_path": str(clone_path),
                "clone_url": repo_info["clone_url"]
            }
        
        try:
            # Check if directory already exists
            if clone_path.exists():
                self.logger.warning(f"Directory already exists: {clone_path}")
                return {
                    "success": True,
                    "already_exists": True,
                    "clone_path": str(clone_path)
                }
            
            # Clone the repository
            cmd = ["git", "clone", repo_info["clone_url"], str(clone_path)]
            
            self.logger.info(f"Running: {' '.join(cmd)}")
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )
            
            if result.returncode == 0:
                self.logger.info(f"Successfully cloned repository to: {clone_path}")
                return {
                    "success": True,
                    "clone_path": str(clone_path),
                    "output": result.stdout
                }
            else:
                self.logger.error(f"Git clone failed: {result.stderr}")
                return {
                    "success": False,
                    "error": result.stderr,
                    "command": ' '.join(cmd)
                }
            
        except subprocess.TimeoutExpired:
            self.logger.error("Git clone timed out")
            return {"success": False, "error": "Clone operation timed out"}
        except Exception as e:
            self.logger.error(f"Clone failed: {e}")
            return {"success": False, "error": str(e)}
    
    async def _update_configuration(self, repo_info: Dict[str, Any]) -> Dict[str, Any]:
        """Update the webhook handler configuration to include the new repository."""
        
        if not self.settings.auto_accept_invitations.post_acceptance.update_config:
            return {"success": True, "skipped": True, "reason": "config update disabled"}
        
        config_path = project_root / "config" / "settings.yaml"
        clone_base = self.settings.auto_accept_invitations.post_acceptance.clone_base_dir
        local_path = Path(clone_base) / repo_info["name"]
        
        self.logger.info(f"Updating configuration: {config_path}")
        
        if self.dry_run:
            return {
                "success": True,
                "dry_run": True,
                "config_path": str(config_path),
                "new_repo_config": {
                    "name": repo_info["full_name"],
                    "enabled": True,
                    "local_path": str(local_path),
                    "events": self.settings.auto_accept_invitations.post_acceptance.webhook_events
                }
            }
        
        try:
            # Read current configuration
            with open(config_path, 'r') as f:
                config_data = yaml.safe_load(f)
            
            # Check if repository already exists in configuration
            repositories = config_data.get("repositories", [])
            repo_exists = any(
                repo.get("name") == repo_info["full_name"] 
                for repo in repositories
            )
            
            if repo_exists:
                self.logger.info(f"Repository already in configuration: {repo_info['full_name']}")
                return {
                    "success": True,
                    "already_exists": True,
                    "repository": repo_info["full_name"]
                }
            
            # Add new repository configuration
            new_repo = {
                "name": repo_info["full_name"],
                "enabled": True,
                "local_path": str(local_path),
                "events": self.settings.auto_accept_invitations.post_acceptance.webhook_events,
                "labels": {
                    "auto_apply": True
                },
                "comments": {
                    "auto_post": True
                }
            }
            
            repositories.append(new_repo)
            config_data["repositories"] = repositories
            
            # Create backup of original configuration
            backup_path = config_path.with_suffix('.yaml.backup')
            with open(backup_path, 'w') as f:
                yaml.dump(config_data, f, default_flow_style=False, indent=2)
            
            # Write updated configuration
            with open(config_path, 'w') as f:
                yaml.dump(config_data, f, default_flow_style=False, indent=2)
            
            self.logger.info(f"Updated configuration with new repository: {repo_info['full_name']}")
            
            return {
                "success": True,
                "repository": repo_info["full_name"],
                "local_path": str(local_path),
                "backup_created": str(backup_path)
            }
            
        except Exception as e:
            self.logger.error(f"Configuration update failed: {e}")
            return {"success": False, "error": str(e)}
    
    async def _register_webhook(self, repo_full_name: str) -> Dict[str, Any]:
        """Register webhook in the new repository."""
        
        if not self.settings.auto_accept_invitations.post_acceptance.register_webhook:
            return {"success": True, "skipped": True, "reason": "webhook registration disabled"}
        
        webhook_url = self.settings.auto_accept_invitations.post_acceptance.webhook_url
        events = self.settings.auto_accept_invitations.post_acceptance.webhook_events
        secret = self.settings.github.webhook_secret
        
        self.logger.info(f"Registering webhook for: {repo_full_name}")
        
        if self.dry_run:
            return {
                "success": True,
                "dry_run": True,
                "webhook_url": webhook_url,
                "events": events
            }
        
        try:
            success = await self.github_client.create_repository_webhook(
                repo_full_name, webhook_url, events, secret
            )
            
            if success:
                return {
                    "success": True,
                    "webhook_url": webhook_url,
                    "events": events
                }
            else:
                return {
                    "success": False,
                    "error": "Webhook creation failed (check logs for details)"
                }
            
        except Exception as e:
            self.logger.error(f"Webhook registration failed: {e}")
            return {"success": False, "error": str(e)}
    
    async def _restart_service(self) -> Dict[str, Any]:
        """Restart the webhook service to pick up configuration changes."""
        
        if self.dry_run:
            return {
                "success": True,
                "dry_run": True,
                "action": "would restart github-webhook service"
            }
        
        try:
            # Restart the systemd service
            cmd = ["sudo", "systemctl", "restart", "github-webhook"]
            
            self.logger.info("Restarting github-webhook service")
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                self.logger.info("Successfully restarted github-webhook service")
                return {
                    "success": True,
                    "service": "github-webhook",
                    "action": "restarted"
                }
            else:
                self.logger.error(f"Service restart failed: {result.stderr}")
                return {
                    "success": False,
                    "error": result.stderr,
                    "command": ' '.join(cmd)
                }
            
        except subprocess.TimeoutExpired:
            self.logger.error("Service restart timed out")
            return {"success": False, "error": "Service restart timed out"}
        except Exception as e:
            self.logger.error(f"Service restart failed: {e}")
            return {"success": False, "error": str(e)}


async def main():
    """Main function to set up a new repository."""
    
    parser = argparse.ArgumentParser(description='Set up a new repository')
    parser.add_argument('repository', help='Repository full name (owner/repo)')
    parser.add_argument('--dry-run', action='store_true',
                       help='Show what would be done without making changes')
    parser.add_argument('--config', default='config/settings.yaml',
                       help='Path to configuration file')
    
    args = parser.parse_args()
    
    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger(__name__)
    
    logger.info(f"Setting up repository: {args.repository}")
    logger.info(f"Dry run: {args.dry_run}")
    
    try:
        # Load settings
        config_path = project_root / args.config
        if not config_path.exists():
            logger.error(f"Configuration file not found: {config_path}")
            sys.exit(1)
        
        settings = Settings.from_yaml(str(config_path))
        
        # Initialize GitHub client
        github_client = GitHubClient(settings.github)
        
        # Initialize setup handler
        setup = RepositorySetup(settings, github_client, args.dry_run)
        
        # Run setup
        result = await setup.setup_repository(args.repository)
        
        # Print results
        print("\n" + "="*50)
        print("REPOSITORY SETUP RESULTS")
        print("="*50)
        print(f"Repository: {result['repository']}")
        print(f"Success: {result['success']}")
        print(f"Dry Run: {result['dry_run']}")
        
        if result.get("error"):
            print(f"Error: {result['error']}")
        
        print("\nStep Results:")
        for step_name, step_result in result.get("steps", {}).items():
            status = "✓" if step_result.get("success") else "✗"
            skipped = " (skipped)" if step_result.get("skipped") else ""
            dry_run = " (dry run)" if step_result.get("dry_run") else ""
            print(f"  {status} {step_name.replace('_', ' ').title()}{skipped}{dry_run}")
            
            if step_result.get("error"):
                print(f"    Error: {step_result['error']}")
        
        # Save detailed results
        if not args.dry_run:
            timestamp = int(asyncio.get_event_loop().time())
            results_file = project_root / "logs" / f"repository_setup_{timestamp}.json"
            
            os.makedirs(project_root / "logs", exist_ok=True)
            with open(results_file, 'w') as f:
                json.dump(result, f, indent=2)
            
            logger.info(f"Detailed results saved to: {results_file}")
        
        sys.exit(0 if result["success"] else 1)
        
    except Exception as e:
        logger.error(f"Setup failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())