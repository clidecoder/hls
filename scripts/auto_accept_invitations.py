#!/home/clide/hls/venv/bin/python
"""
Auto-Accept Repository Invitations Script

This script automatically processes repository collaboration invitations
based on configured criteria. It can be run manually or via cron job.

Usage: python auto_accept_invitations.py [--dry-run] [--config CONFIG_PATH]
"""

import asyncio
import argparse
import json
import logging
import sys
import time
from pathlib import Path
from typing import Dict, Any

# Add the project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from hls.src.hsl_handler.config import Settings
from hls.src.hsl_handler.clients import GitHubClient
from hls.src.hsl_handler.handlers import InvitationHandler
from hls.src.hsl_handler.logging_config import setup_logging


def setup_script_logging(log_level: str = "INFO") -> logging.Logger:
    """Set up logging for the script."""
    
    # Create logs directory if it doesn't exist
    logs_dir = project_root / "logs"
    logs_dir.mkdir(exist_ok=True)
    
    # Configure logging
    log_file = logs_dir / "auto_accept_invitations.log"
    
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )
    
    return logging.getLogger(__name__)


async def main():
    """Main function to process repository invitations."""
    
    parser = argparse.ArgumentParser(description='Auto-accept repository invitations')
    parser.add_argument('--dry-run', action='store_true', 
                       help='Show what would be done without making changes')
    parser.add_argument('--config', default='config/settings.yaml',
                       help='Path to configuration file')
    parser.add_argument('--log-level', default=None,
                       help='Override log level (DEBUG, INFO, WARNING, ERROR)')
    
    args = parser.parse_args()
    
    # Load settings
    try:
        config_path = project_root / args.config
        if not config_path.exists():
            print(f"Configuration file not found: {config_path}")
            sys.exit(1)
            
        settings = Settings.from_yaml(str(config_path))
        
        # Override log level if specified
        log_level = args.log_level or settings.auto_accept_invitations.log_level
        
    except Exception as e:
        print(f"Failed to load configuration: {e}")
        sys.exit(1)
    
    # Set up logging
    logger = setup_script_logging(log_level)
    
    logger.info("Starting auto-accept invitations script")
    logger.info(f"Configuration: {args.config}")
    logger.info(f"Dry run: {args.dry_run}")
    
    # Check if feature is enabled
    if not settings.auto_accept_invitations.enabled:
        logger.info("Auto-accept invitations is disabled in configuration")
        return
    
    try:
        # Initialize GitHub client
        github_client = GitHubClient(settings.github)
        
        # Initialize invitation handler
        invitation_handler = InvitationHandler(settings, github_client)
        
        if args.dry_run:
            logger.info("DRY RUN MODE: No actual changes will be made")
            
            # Get invitations without processing
            invitations = await github_client.get_user_repository_invitations()
            
            if not invitations:
                logger.info("No pending invitations found")
                return
            
            logger.info(f"Found {len(invitations)} pending invitation(s)")
            
            for invitation in invitations:
                decision = invitation_handler._evaluate_invitation(invitation)
                repo_name = invitation["repository"]["full_name"]
                inviter = invitation["inviter"]["login"]
                
                logger.info(f"Would {decision} invitation from {inviter} for {repo_name}")
        
        else:
            # Process invitations for real
            result = await invitation_handler.process_invitations()
            
            logger.info("Invitation processing completed")
            logger.info(f"Status: {result['status']}")
            logger.info(f"Total processed: {result.get('processed', 0)}")
            logger.info(f"Accepted: {result.get('accepted', 0)}")
            logger.info(f"Declined: {result.get('declined', 0)}")
            
            # Log details of each processed invitation
            for invitation in result.get('invitations', []):
                logger.info(f"Invitation {invitation['id']} for {invitation['repository']}: "
                           f"{invitation['action']} ({invitation['reason']})")
            
            # Save results to file for monitoring/debugging
            timestamp = int(time.time())
            results_file = project_root / "logs" / f"invitation_results_{timestamp}.json"
            
            with open(results_file, 'w') as f:
                json.dump(result, f, indent=2)
            
            logger.info(f"Results saved to: {results_file}")
    
    except Exception as e:
        logger.error(f"Script execution failed: {e}", exc_info=True)
        sys.exit(1)
    
    logger.info("Auto-accept invitations script completed")


if __name__ == "__main__":
    asyncio.run(main())