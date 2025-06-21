#!/usr/bin/env python3
"""
Cron job script to analyze issues that may have been missed by webhooks.

This script runs periodically to find issues that:
1. Are older than a specified age (default: 30 minutes)
2. Don't have the 'clide-analyzed' label
3. Are still open
4. Are in configured repositories

It then processes them using the same webhook handler logic.
"""

import os
import sys
import asyncio
import argparse
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Optional
from pathlib import Path

# Add the project root to the path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from hls.src.hsl_handler.config import load_settings
from hls.src.hsl_handler.clients import GitHubClient
from hls.src.hsl_handler.webhook_processor import WebhookProcessor
from hls.src.hsl_handler.logging_config import get_logger, setup_logging

logger = get_logger(__name__)


class MissedIssueAnalyzer:
    """Analyzes issues that may have been missed by webhooks."""
    
    def __init__(self, settings_path: Optional[str] = None):
        """Initialize the analyzer with configuration."""
        self.settings = load_settings(settings_path)
        self.github_client = GitHubClient(self.settings.github)
        self.webhook_processor = WebhookProcessor(self.settings)
        
        # Configure analysis parameters from settings
        cron_config = self.settings.cron_analysis
        self.min_age_minutes = cron_config.min_age_minutes
        self.analyzed_label = cron_config.analyzed_label
        self.max_issues_per_repo = cron_config.max_issues_per_repo
        self.delay_between_issues = cron_config.delay_between_issues
        
    async def find_unanalyzed_issues(
        self, 
        repo_name: str, 
        min_age_minutes: int = 30
    ) -> List[Dict[str, Any]]:
        """Find issues in a repository that haven't been analyzed."""
        
        try:
            repo = self.github_client.client.get_repo(repo_name)
            cutoff_time = datetime.now(timezone.utc) - timedelta(minutes=min_age_minutes)
            
            # Get open issues
            issues = repo.get_issues(state='open', sort='created', direction='desc')
            
            unanalyzed_issues = []
            count = 0
            
            for issue in issues:
                # Stop if we've checked enough recent issues
                if count >= self.max_issues_per_repo:
                    break
                    
                # Skip if issue is too recent
                if issue.created_at > cutoff_time:
                    continue
                
                # Skip pull requests (they have different handling)
                if issue.pull_request:
                    continue
                
                # Check if already analyzed
                label_names = [label.name for label in issue.labels]
                if self.analyzed_label in label_names:
                    continue
                
                # Convert to our format
                issue_data = {
                    "number": issue.number,
                    "title": issue.title,
                    "body": issue.body or "",
                    "created_at": issue.created_at.isoformat(),
                    "updated_at": issue.updated_at.isoformat(),
                    "user": {
                        "login": issue.user.login
                    },
                    "labels": [{"name": label.name} for label in issue.labels],
                    "state": issue.state,
                    "html_url": issue.html_url
                }
                
                unanalyzed_issues.append(issue_data)
                count += 1
                
                logger.info(
                    "Found unanalyzed issue",
                    repo=repo_name,
                    issue=issue.number,
                    title=issue.title,
                    age_hours=round((datetime.now(timezone.utc) - issue.created_at).total_seconds() / 3600, 1)
                )
            
            return unanalyzed_issues
            
        except Exception as e:
            logger.error(f"Error finding unanalyzed issues in {repo_name}: {str(e)}", exc_info=True)
            return []
    
    async def process_missed_issue(self, repo_name: str, issue_data: Dict[str, Any]) -> bool:
        """Process a single missed issue using the webhook processor."""
        
        try:
            # Create a mock webhook payload
            payload = {
                "action": "opened",
                "issue": issue_data,
                "repository": {
                    "full_name": repo_name,
                    "name": repo_name.split('/')[-1],
                    "owner": {
                        "login": repo_name.split('/')[0]
                    }
                },
                "sender": issue_data["user"]
            }
            
            # Generate a unique delivery ID for tracking
            delivery_id = f"cron-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{issue_data['number']}"
            
            logger.info(
                "Processing missed issue",
                repo=repo_name,
                issue=issue_data["number"],
                delivery_id=delivery_id
            )
            
            # Process using the existing webhook processor
            result = await self.webhook_processor.process_webhook(
                event_type="issues",
                payload=payload,
                delivery_id=delivery_id,
                request_id=f"cron-{delivery_id}"
            )
            
            if result.get("status") == "success":
                logger.info(
                    "Successfully processed missed issue",
                    repo=repo_name,
                    issue=issue_data["number"],
                    result=result
                )
                return True
            else:
                logger.warning(
                    "Failed to process missed issue",
                    repo=repo_name,
                    issue=issue_data["number"],
                    result=result
                )
                return False
                
        except Exception as e:
            logger.error(
                f"Error processing missed issue {issue_data['number']} in {repo_name}: {str(e)}",
                exc_info=True
            )
            return False
    
    async def analyze_all_repositories(self, min_age_minutes: int = 30) -> Dict[str, Any]:
        """Analyze all configured repositories for missed issues."""
        
        results = {
            "total_repos": 0,
            "total_found": 0,
            "total_processed": 0,
            "total_successful": 0,
            "repositories": {}
        }
        
        for repo_config in self.settings.repositories:
            if not repo_config.enabled:
                continue
                
            if "issues" not in repo_config.events:
                continue
            
            repo_name = repo_config.name
            results["total_repos"] += 1
            
            logger.info(f"Checking repository: {repo_name}")
            
            # Find unanalyzed issues
            unanalyzed_issues = await self.find_unanalyzed_issues(repo_name, min_age_minutes)
            
            repo_results = {
                "found": len(unanalyzed_issues),
                "processed": 0,
                "successful": 0,
                "errors": []
            }
            
            results["total_found"] += len(unanalyzed_issues)
            
            # Process each issue
            for issue_data in unanalyzed_issues:
                repo_results["processed"] += 1
                results["total_processed"] += 1
                
                success = await self.process_missed_issue(repo_name, issue_data)
                if success:
                    repo_results["successful"] += 1
                    results["total_successful"] += 1
                else:
                    repo_results["errors"].append(issue_data["number"])
                
                # Small delay between issues to avoid rate limiting
                await asyncio.sleep(self.delay_between_issues)
            
            results["repositories"][repo_name] = repo_results
            
            logger.info(
                "Repository analysis complete",
                repo=repo_name,
                found=repo_results["found"],
                successful=repo_results["successful"],
                errors=len(repo_results["errors"])
            )
        
        return results
    
    async def run(self, min_age_minutes: int = 30, dry_run: bool = False) -> None:
        """Main entry point for the analyzer."""
        
        start_time = datetime.now()
        logger.info(
            "Starting missed issue analysis",
            min_age_minutes=min_age_minutes,
            dry_run=dry_run
        )
        
        if dry_run:
            logger.info("DRY RUN MODE - No issues will be processed")
        
        try:
            if dry_run:
                # In dry run, just find issues but don't process them
                total_found = 0
                for repo_config in self.settings.repositories:
                    if repo_config.enabled and "issues" in repo_config.events:
                        issues = await self.find_unanalyzed_issues(repo_config.name, min_age_minutes)
                        total_found += len(issues)
                
                logger.info(f"DRY RUN: Found {total_found} unanalyzed issues")
                
            else:
                # Actually process the issues
                results = await self.analyze_all_repositories(min_age_minutes)
                
                # Log summary
                duration = datetime.now() - start_time
                logger.info(
                    "Missed issue analysis completed",
                    duration_seconds=duration.total_seconds(),
                    **results
                )
                
                # Log per-repository results
                for repo_name, repo_results in results["repositories"].items():
                    if repo_results["found"] > 0:
                        logger.info(
                            "Repository summary",
                            repo=repo_name,
                            found=repo_results["found"],
                            successful=repo_results["successful"],
                            errors=repo_results["errors"]
                        )
        
        except Exception as e:
            logger.error(f"Error in missed issue analysis: {str(e)}", exc_info=True)
            raise


async def main():
    """Main function for command-line usage."""
    
    parser = argparse.ArgumentParser(description="Analyze issues missed by webhooks")
    parser.add_argument(
        "--min-age", 
        type=int, 
        default=30,
        help="Minimum age in minutes for issues to be considered (default: 30)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only find issues, don't process them"
    )
    parser.add_argument(
        "--config",
        type=str,
        help="Path to configuration file"
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Logging level"
    )
    
    args = parser.parse_args()
    
    # Setup logging - create a simple config for the cron job
    from hls.src.hsl_handler.config import LoggingConfig
    log_config = LoggingConfig(level=args.log_level, file="logs/cron-analyze.log")
    setup_logging(log_config)
    
    # Create and run analyzer
    analyzer = MissedIssueAnalyzer(args.config)
    await analyzer.run(args.min_age, args.dry_run)


if __name__ == "__main__":
    asyncio.run(main())