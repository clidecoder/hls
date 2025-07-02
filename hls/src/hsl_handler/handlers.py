"""Event-specific handlers for different GitHub webhook events."""

import re
import json
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
from pathlib import Path

from .clients import ClaudeClient, GitHubClient
from .prompts import PromptLoader, create_prompt_context
from .config import Settings
from .logging_config import get_logger

logger = get_logger(__name__)


class BaseHandler(ABC):
    """Base class for webhook event handlers."""
    
    def __init__(self, settings: Settings, claude_client: ClaudeClient, github_client: GitHubClient, prompt_loader: PromptLoader):
        self.settings = settings
        self.claude_client = claude_client
        self.github_client = github_client
        self.prompt_loader = prompt_loader
        self.outputs_dir = Path(settings.outputs.base_dir)
        self.outputs_dir.mkdir(parents=True, exist_ok=True)
    
    @abstractmethod
    async def handle(self, payload: Dict[str, Any], action: str) -> Dict[str, Any]:
        """Handle the webhook event."""
        pass
    
    def get_repository_working_directory(self, payload: Dict[str, Any]) -> Optional[str]:
        """Get the local working directory for the repository from the payload."""
        repository = payload.get("repository", {})
        repo_name = repository.get("full_name")
        if not repo_name:
            return None
            
        repo_config = self.settings.get_repository_config(repo_name)
        if repo_config:
            return repo_config.local_path
        return None
    
    def extract_labels_from_analysis(self, analysis: str) -> List[str]:
        """Extract suggested labels from Claude's analysis."""
        labels = []
        
        # Define label patterns
        label_patterns = {
            r'\bbug\b': 'bug',
            r'\benhancement\b': 'enhancement',
            r'\bquestion\b': 'question',
            r'\bdocumentation\b': 'documentation',
            r'\bmaintenance\b': 'maintenance',
            r'\bhigh.priority\b|\bpriority.high\b': 'priority-high',
            r'\bmedium.priority\b|\bpriority.medium\b': 'priority-medium',
            r'\blow.priority\b|\bpriority.low\b': 'priority-low',
            r'\beasy\b|\bdifficulty.easy\b': 'difficulty-easy',
            r'\bmoderate\b|\bdifficulty.moderate\b': 'difficulty-moderate',
            r'\bcomplex\b|\bdifficulty.complex\b': 'difficulty-complex',
            r'\bfrontend\b|\bcomponent.frontend\b': 'component-frontend',
            r'\bbackend\b|\bcomponent.backend\b': 'component-backend',
            r'\bdatabase\b|\bcomponent.database\b': 'component-database'
        }
        
        analysis_lower = analysis.lower()
        for pattern, label in label_patterns.items():
            if re.search(pattern, analysis_lower):
                labels.append(label)
        
        return list(set(labels))  # Remove duplicates
    
    def should_close_issue(self, analysis: str) -> bool:
        """Check if Claude recommends closing the issue."""
        return "RECOMMENDATION: CLOSE ISSUE" in analysis


class IssueHandler(BaseHandler):
    """Handler for GitHub issue events."""
    
    async def handle(self, payload: Dict[str, Any], action: str) -> Dict[str, Any]:
        """Handle issue events."""
        
        if action != "opened":
            return {"status": "ignored", "reason": f"action '{action}' not handled"}
        
        issue = payload.get("issue", {})
        issue_number = issue.get("number")
        repository = payload.get("repository", {})
        repo_name = repository.get("full_name")
        
        logger.info("Processing issue", repo=repo_name, issue=issue_number, action=action)
        
        try:
            # Check if already analyzed
            labels = [label["name"] for label in issue.get("labels", [])]
            if "clide-analyzed" in labels:
                logger.info("Issue already analyzed", issue=issue_number)
                return {"status": "skipped", "reason": "already analyzed"}
            
            # Load and render prompt
            context = create_prompt_context("issues", payload)
            prompt = self.prompt_loader.render_prompt("issues", action, context)
            
            if not prompt:
                logger.error("No prompt found for issue", action=action)
                return {"status": "error", "reason": "no prompt template"}
            
            # Create context for Claude
            issue_context = f"""# GitHub Issue Analysis Request

## Issue Details
- **Repository**: {repo_name}
- **Issue Number**: #{issue_number}
- **Title**: {issue.get('title', '')}
- **URL**: {issue.get('html_url', '')}
- **Author**: {issue.get('user', {}).get('login', '')}

## Issue Description
{issue.get('body', '')}
"""
            
            # Get repository working directory
            working_directory = self.get_repository_working_directory(payload)
            
            # Analyze with Claude
            analysis = await self.claude_client.analyze(prompt, issue_context, working_directory=working_directory)
            
            # Save analysis
            output_dir = self.outputs_dir / self.settings.outputs.directories["issues"]
            output_dir.mkdir(parents=True, exist_ok=True)
            
            analysis_file = output_dir / f"issue_{issue_number}_analysis.md"
            with open(analysis_file, 'w', encoding='utf-8') as f:
                f.write(analysis)
            
            # Extract labels and post comment
            repo_config = self.settings.get_repository_config(repo_name)
            if repo_config and repo_config.settings.get("apply_labels", True):
                suggested_labels = self.extract_labels_from_analysis(analysis)
                if suggested_labels:
                    await self.github_client.add_issue_labels(repo_name, issue_number, suggested_labels)
            
            # Post analysis comment
            if repo_config and repo_config.settings.get("post_analysis_comments", True):
                comment = f"""## 🤖 Automated Issue Analysis

Hi! I've automatically analyzed this issue using Claude Code. Here's my assessment:

---

{analysis}

---

*This analysis was generated automatically by the PromptForge webhook system. The suggestions above are AI-generated and should be reviewed by a human maintainer.*

*Issue analyzed at: {context.get('timestamp', 'unknown')}*"""
                
                await self.github_client.post_issue_comment(repo_name, issue_number, comment)
            
            # Check if should close
            if (repo_config and 
                repo_config.settings.get("auto_close_invalid", False) and 
                self.should_close_issue(analysis)):
                
                close_comment = """## Issue Closed by Automated Analysis

This issue has been automatically closed based on the analysis above.

If you believe this was closed in error, please feel free to provide additional context and request that a maintainer review the decision.

Thank you for your interest in the project!"""
                
                await self.github_client.close_issue(repo_name, issue_number, close_comment)
            
            # Mark as analyzed
            await self.github_client.add_issue_labels(repo_name, issue_number, ["clide-analyzed"])
            
            logger.info("Issue analysis completed", issue=issue_number)
            
            return {
                "status": "success",
                "issue_number": issue_number,
                "analysis_file": str(analysis_file),
                "labels_applied": suggested_labels if repo_config and repo_config.settings.get("apply_labels") else []
            }
            
        except Exception as e:
            logger.error("Error processing issue", issue=issue_number, error=str(e), exc_info=True)
            return {"status": "error", "error": str(e)}


class PullRequestHandler(BaseHandler):
    """Handler for GitHub pull request events."""
    
    async def handle(self, payload: Dict[str, Any], action: str) -> Dict[str, Any]:
        """Handle pull request events."""
        
        if action not in ["opened", "synchronize"]:
            return {"status": "ignored", "reason": f"action '{action}' not handled"}
        
        pr = payload.get("pull_request", {})
        pr_number = pr.get("number")
        repository = payload.get("repository", {})
        repo_name = repository.get("full_name")
        
        logger.info("Processing PR", repo=repo_name, pr=pr_number, action=action)
        
        try:
            # Get full PR details including diff
            pr_details = await self.github_client.get_pull_request(repo_name, pr_number)
            
            # Load and render prompt
            context = create_prompt_context("pull_request", payload)
            context.update(pr_details)  # Add detailed PR info
            
            prompt_action = "new_pr" if action == "opened" else "pr_updated"
            prompt = self.prompt_loader.render_prompt("pull_request", prompt_action, context)
            
            if not prompt:
                logger.error("No prompt found for PR", action=action)
                return {"status": "error", "reason": "no prompt template"}
            
            # Create context for Claude
            pr_context = f"""# GitHub Pull Request Analysis Request

## PR Details
- **Repository**: {repo_name}
- **PR Number**: #{pr_number}
- **Title**: {pr.get('title', '')}
- **URL**: {pr.get('html_url', '')}
- **Author**: {pr.get('user', {}).get('login', '')}
- **State**: {pr.get('state', '')}
- **Draft**: {pr.get('draft', False)}

## PR Description
{pr.get('body', '')}

## Files Changed
{', '.join(pr_details.get('files', []))}

## Statistics
- **Additions**: {pr_details.get('additions', 0)}
- **Deletions**: {pr_details.get('deletions', 0)}
- **Changed Files**: {pr_details.get('changed_files', 0)}

## Code Diff (truncated)
```diff
{pr_details.get('diff', '')[:5000]}...
```
"""
            
            # Get repository working directory
            working_directory = self.get_repository_working_directory(payload)
            
            # Analyze with Claude
            analysis = await self.claude_client.analyze(prompt, pr_context, working_directory=working_directory)
            
            # Save analysis
            output_dir = self.outputs_dir / self.settings.outputs.directories["pull_requests"]
            output_dir.mkdir(parents=True, exist_ok=True)
            
            analysis_file = output_dir / f"pr_{pr_number}_analysis.md"
            with open(analysis_file, 'w', encoding='utf-8') as f:
                f.write(analysis)
            
            # Post analysis comment
            repo_config = self.settings.get_repository_config(repo_name)
            if repo_config and repo_config.settings.get("post_analysis_comments", True):
                comment = analysis
                
                await self.github_client.post_pr_comment(repo_name, pr_number, comment)
            
            # Apply PR labels if configured
            if repo_config and repo_config.settings.get("apply_labels", True):
                # Extract PR-specific labels (size, type, etc.)
                pr_labels = self._extract_pr_labels(analysis, pr_details)
                if pr_labels:
                    await self.github_client.add_pr_labels(repo_name, pr_number, pr_labels)
            
            logger.info("PR analysis completed", pr=pr_number)
            
            return {
                "status": "success",
                "pr_number": pr_number,
                "analysis_file": str(analysis_file),
                "action": action
            }
            
        except Exception as e:
            logger.error("Error processing PR", pr=pr_number, error=str(e), exc_info=True)
            return {"status": "error", "error": str(e)}
    
    def _extract_pr_labels(self, analysis: str, pr_details: Dict[str, Any]) -> List[str]:
        """Extract PR-specific labels."""
        labels = []
        
        # Size labels based on changes
        total_changes = pr_details.get('additions', 0) + pr_details.get('deletions', 0)
        if total_changes < 50:
            labels.append('size/small')
        elif total_changes < 200:
            labels.append('size/medium')
        else:
            labels.append('size/large')
        
        # Type labels from analysis
        analysis_lower = analysis.lower()
        if 'bug' in analysis_lower or 'fix' in analysis_lower:
            labels.append('type/bug-fix')
        elif 'feature' in analysis_lower or 'enhancement' in analysis_lower:
            labels.append('type/feature')
        elif 'refactor' in analysis_lower:
            labels.append('type/refactor')
        elif 'documentation' in analysis_lower or 'docs' in analysis_lower:
            labels.append('type/docs')
        
        return labels


class ReviewHandler(BaseHandler):
    """Handler for GitHub pull request review events."""
    
    async def handle(self, payload: Dict[str, Any], action: str) -> Dict[str, Any]:
        """Handle review request events."""
        
        pr = payload.get("pull_request", {})
        pr_number = pr.get("number")
        repository = payload.get("repository", {})
        repo_name = repository.get("full_name")
        
        # Handle review requests
        if "requested_reviewer" in payload:
            reviewer = payload.get("requested_reviewer", {}).get("login", "")
            requester = payload.get("sender", {}).get("login", "")
            
            logger.info("Processing review request", repo=repo_name, pr=pr_number, reviewer=reviewer)
            
            try:
                # Get full PR details
                pr_details = await self.github_client.get_pull_request(repo_name, pr_number)
                
                # Load and render prompt
                context = create_prompt_context("pull_request_review", payload)
                context.update(pr_details)
                context.update({
                    "reviewer": reviewer,
                    "requester": requester
                })
                
                prompt = self.prompt_loader.render_prompt("pull_request_review", "requested", context)
                
                if not prompt:
                    logger.error("No prompt found for review request")
                    return {"status": "error", "reason": "no prompt template"}
                
                # Create context for Claude
                review_context = f"""# GitHub Pull Request Review Request

## Review Request Details
- **Repository**: {repo_name}
- **PR Number**: #{pr_number}
- **PR Title**: {pr.get('title', '')}
- **PR Author**: {pr.get('user', {}).get('login', '')}
- **Reviewer Requested**: {reviewer}
- **Requested By**: {requester}

## PR Description
{pr.get('body', '')}

## Files to Review
{', '.join(pr_details.get('files', []))}

## Code Changes
```diff
{pr_details.get('diff', '')[:8000]}...
```
"""
                
                # Get repository working directory
                working_directory = self.get_repository_working_directory(payload)
                
                # Analyze with Claude
                analysis = await self.claude_client.analyze(prompt, review_context, working_directory=working_directory)
                
                # Save analysis
                output_dir = self.outputs_dir / self.settings.outputs.directories["reviews"]
                output_dir.mkdir(parents=True, exist_ok=True)
                
                import time
                timestamp = int(time.time())
                analysis_file = output_dir / f"pr_{pr_number}_review_{timestamp}.md"
                with open(analysis_file, 'w', encoding='utf-8') as f:
                    f.write(analysis)
                
                # Post review comment
                repo_config = self.settings.get_repository_config(repo_name)
                if repo_config and repo_config.settings.get("post_analysis_comments", True):
                    comment = f"""## 👁️ Automated Code Review

A review was requested from **{reviewer}**. Here's an automated analysis to help with the review:

---

{analysis}

---

*This review was generated automatically by the PromptForge webhook system. The suggestions above are AI-generated and should supplement, not replace, human code review.*

*Review analysis completed at: {context.get('timestamp', 'unknown')}*"""
                    
                    await self.github_client.post_pr_comment(repo_name, pr_number, comment)
                
                logger.info("Review analysis completed", pr=pr_number, reviewer=reviewer)
                
                return {
                    "status": "success",
                    "pr_number": pr_number,
                    "reviewer": reviewer,
                    "analysis_file": str(analysis_file)
                }
                
            except Exception as e:
                logger.error("Error processing review request", pr=pr_number, error=str(e), exc_info=True)
                return {"status": "error", "error": str(e)}
        
        return {"status": "ignored", "reason": "not a review request"}


class WorkflowHandler(BaseHandler):
    """Handler for GitHub workflow events."""
    
    async def handle(self, payload: Dict[str, Any], action: str) -> Dict[str, Any]:
        """Handle workflow events."""
        
        if action != "completed":
            return {"status": "ignored", "reason": f"action '{action}' not handled"}
        
        workflow_run = payload.get("workflow_run", {})
        conclusion = workflow_run.get("conclusion")
        
        if conclusion != "failure":
            return {"status": "ignored", "reason": f"conclusion '{conclusion}' not handled"}
        
        workflow_name = workflow_run.get("name", "")
        workflow_id = workflow_run.get("id")
        repository = payload.get("repository", {})
        repo_name = repository.get("full_name")
        
        logger.info("Processing failed workflow", repo=repo_name, workflow=workflow_name, run_id=workflow_id)
        
        try:
            # Load and render prompt
            context = create_prompt_context("workflow_run", payload)
            prompt = self.prompt_loader.render_prompt("workflow_run", "completed", context)
            
            if not prompt:
                logger.error("No prompt found for workflow failure")
                return {"status": "error", "reason": "no prompt template"}
            
            # Create context for Claude
            workflow_context = f"""# GitHub Workflow Failure Analysis

## Workflow Details
- **Repository**: {repo_name}
- **Workflow**: {workflow_name}
- **Run ID**: {workflow_id}
- **Conclusion**: {conclusion}
- **Commit**: {workflow_run.get('head_sha', '')}
- **Branch**: {workflow_run.get('head_branch', '')}

## Workflow URL
{workflow_run.get('html_url', '')}

## Commit Message
{workflow_run.get('head_commit', {}).get('message', '')}
"""
            
            # Get repository working directory
            working_directory = self.get_repository_working_directory(payload)
            
            # Analyze with Claude
            analysis = await self.claude_client.analyze(prompt, workflow_context, working_directory=working_directory)
            
            # Save analysis
            output_dir = self.outputs_dir / self.settings.outputs.directories["workflows"]
            output_dir.mkdir(parents=True, exist_ok=True)
            
            analysis_file = output_dir / f"workflow_{workflow_id}_analysis.md"
            with open(analysis_file, 'w', encoding='utf-8') as f:
                f.write(analysis)
            
            logger.info("Workflow failure analysis completed", workflow=workflow_name, run_id=workflow_id)
            
            return {
                "status": "success",
                "workflow_name": workflow_name,
                "run_id": workflow_id,
                "analysis_file": str(analysis_file)
            }
            
        except Exception as e:
            logger.error("Error processing workflow failure", workflow=workflow_name, error=str(e), exc_info=True)
            return {"status": "error", "error": str(e)}


# Handler registry
class GenericHandler(BaseHandler):
    """Generic handler for any GitHub webhook event not specifically implemented."""
    
    async def handle(self, payload: Dict[str, Any], action: str) -> Dict[str, Any]:
        """Handle generic webhook events."""
        
        event_type = payload.get("event_type", "unknown")
        repository = payload.get("repository", {})
        repo_name = repository.get("full_name", "unknown")
        sender = payload.get("sender", {})
        sender_login = sender.get("login", "unknown")
        
        logger.info("Processing generic event", event_type=event_type, repo=repo_name, action=action, sender=sender_login)
        
        try:
            # Load and render generic prompt
            context = create_prompt_context("generic", payload)
            context["event_type"] = event_type
            context["action"] = action
            
            prompt = self.prompt_loader.render_prompt("generic", "default", context)
            
            if not prompt:
                # Use a basic default prompt if no template exists
                prompt = """Analyze this GitHub webhook event and provide insights about what happened and any recommended actions.

Focus on:
1. What triggered this event
2. What changes or actions occurred
3. Any potential impact or follow-up needed
4. Suggestions for automation or process improvements"""
            
            # Create context for Claude
            event_context = f"""# GitHub Webhook Event Analysis

## Event Details
- **Event Type**: {event_type}
- **Repository**: {repo_name}
- **Action**: {action}
- **Sender**: {sender_login}
- **Timestamp**: {context.get('timestamp', 'unknown')}

## Event Payload
```json
{json.dumps(payload, indent=2)[:3000]}...
```
"""
            
            # Get repository working directory
            working_directory = self.get_repository_working_directory(payload)
            
            # Analyze with Claude
            analysis = await self.claude_client.analyze(prompt, event_context, working_directory=working_directory)
            
            # Save analysis
            output_dir = self.outputs_dir / "generic_events"
            output_dir.mkdir(parents=True, exist_ok=True)
            
            import time
            timestamp = int(time.time())
            analysis_file = output_dir / f"{event_type}_{action}_{timestamp}_analysis.md"
            with open(analysis_file, 'w', encoding='utf-8') as f:
                f.write(analysis)
            
            logger.info("Generic event analysis completed", event_type=event_type, action=action)
            
            return {
                "status": "success",
                "event_type": event_type,
                "action": action,
                "analysis_file": str(analysis_file)
            }
            
        except Exception as e:
            logger.error("Error processing generic event", event_type=event_type, error=str(e), exc_info=True)
            return {"status": "error", "error": str(e)}


class PushHandler(BaseHandler):
    """Handler for GitHub push events."""
    
    async def handle(self, payload: Dict[str, Any], action: str) -> Dict[str, Any]:
        """Handle push events."""
        
        repository = payload.get("repository", {})
        repo_name = repository.get("full_name")
        ref = payload.get("ref", "")
        pusher = payload.get("pusher", {})
        
        logger.info("Processing push event", repo=repo_name, ref=ref, pusher=pusher.get("name"))
        
        try:
            # Get commit information
            commits = payload.get("commits", [])
            if not commits:
                return {"status": "ignored", "reason": "no commits"}
            
            # Load and render prompt
            context = create_prompt_context("push", payload)
            prompt = self.prompt_loader.render_prompt("push", "commits", context)
            
            if not prompt:
                logger.error("No prompt found for push event")
                return {"status": "error", "reason": "no prompt template"}
            
            # Create context for Claude
            push_context = f"""# GitHub Push Event Analysis

## Push Details
- **Repository**: {repo_name}
- **Branch/Tag**: {ref}
- **Pusher**: {pusher.get('name', 'unknown')}
- **Commits**: {len(commits)}

## Commits
"""
            for commit in commits[:10]:  # Limit to first 10 commits
                push_context += f"""
### {commit.get('id', '')[:7]}
- **Author**: {commit.get('author', {}).get('name', '')}
- **Message**: {commit.get('message', '')}
- **Added**: {len(commit.get('added', []))} files
- **Modified**: {len(commit.get('modified', []))} files
- **Removed**: {len(commit.get('removed', []))} files
"""
            
            # Get repository working directory
            working_directory = self.get_repository_working_directory(payload)
            
            # Analyze with Claude
            analysis = await self.claude_client.analyze(prompt, push_context, working_directory=working_directory)
            
            # Save analysis
            output_dir = self.outputs_dir / self.settings.outputs.directories.get("pushes", "pushes")
            output_dir.mkdir(parents=True, exist_ok=True)
            
            import time
            timestamp = int(time.time())
            analysis_file = output_dir / f"push_{timestamp}_analysis.md"
            with open(analysis_file, 'w', encoding='utf-8') as f:
                f.write(analysis)
            
            logger.info("Push analysis completed", repo=repo_name)
            
            return {
                "status": "success",
                "repository": repo_name,
                "ref": ref,
                "commits": len(commits),
                "analysis_file": str(analysis_file)
            }
            
        except Exception as e:
            logger.error("Error processing push", repo=repo_name, error=str(e), exc_info=True)
            return {"status": "error", "error": str(e)}


class ReleaseHandler(BaseHandler):
    """Handler for GitHub release events."""
    
    async def handle(self, payload: Dict[str, Any], action: str) -> Dict[str, Any]:
        """Handle release events."""
        
        if action not in ["published", "created", "edited"]:
            return {"status": "ignored", "reason": f"action '{action}' not handled"}
        
        release = payload.get("release", {})
        repository = payload.get("repository", {})
        repo_name = repository.get("full_name")
        
        logger.info("Processing release event", repo=repo_name, action=action, tag=release.get("tag_name"))
        
        try:
            # Load and render prompt
            context = create_prompt_context("release", payload)
            prompt = self.prompt_loader.render_prompt("release", action, context)
            
            if not prompt:
                logger.error("No prompt found for release event", action=action)
                return {"status": "error", "reason": "no prompt template"}
            
            # Create context for Claude
            release_context = f"""# GitHub Release Event Analysis

## Release Details
- **Repository**: {repo_name}
- **Action**: {action}
- **Tag**: {release.get('tag_name', '')}
- **Name**: {release.get('name', '')}
- **Author**: {release.get('author', {}).get('login', '')}
- **Prerelease**: {release.get('prerelease', False)}
- **Draft**: {release.get('draft', False)}

## Release Description
{release.get('body', '')}

## Assets
"""
            for asset in release.get('assets', []):
                release_context += f"- {asset.get('name', '')} ({asset.get('size', 0)} bytes)\n"
            
            # Get repository working directory
            working_directory = self.get_repository_working_directory(payload)
            
            # Analyze with Claude
            analysis = await self.claude_client.analyze(prompt, release_context, working_directory=working_directory)
            
            # Save analysis
            output_dir = self.outputs_dir / self.settings.outputs.directories.get("releases", "releases")
            output_dir.mkdir(parents=True, exist_ok=True)
            
            analysis_file = output_dir / f"release_{release.get('tag_name', 'unknown')}_analysis.md"
            with open(analysis_file, 'w', encoding='utf-8') as f:
                f.write(analysis)
            
            logger.info("Release analysis completed", tag=release.get("tag_name"))
            
            return {
                "status": "success",
                "repository": repo_name,
                "tag": release.get("tag_name"),
                "analysis_file": str(analysis_file)
            }
            
        except Exception as e:
            logger.error("Error processing release", repo=repo_name, error=str(e), exc_info=True)
            return {"status": "error", "error": str(e)}


class ForkHandler(BaseHandler):
    """Handler for GitHub fork events."""
    
    async def handle(self, payload: Dict[str, Any], action: str) -> Dict[str, Any]:
        """Handle fork events."""
        
        forkee = payload.get("forkee", {})
        repository = payload.get("repository", {})
        repo_name = repository.get("full_name")
        
        logger.info("Processing fork event", repo=repo_name, fork=forkee.get("full_name"))
        
        try:
            # Load and render prompt
            context = create_prompt_context("fork", payload)
            prompt = self.prompt_loader.render_prompt("fork", "created", context)
            
            if not prompt:
                logger.warning("No prompt for fork event, using generic handler")
                return await GenericHandler(self.settings, self.claude_client, self.github_client, self.prompt_loader).handle(payload, action)
            
            # Create context for Claude
            fork_context = f"""# GitHub Fork Event Analysis

## Fork Details
- **Original Repository**: {repo_name}
- **Fork**: {forkee.get('full_name', '')}
- **Owner**: {forkee.get('owner', {}).get('login', '')}
- **Private**: {forkee.get('private', False)}

## Repository Stats
- **Stars**: {repository.get('stargazers_count', 0)}
- **Forks**: {repository.get('forks_count', 0)}
- **Open Issues**: {repository.get('open_issues_count', 0)}
"""
            
            # Get repository working directory
            working_directory = self.get_repository_working_directory(payload)
            
            # Analyze with Claude
            analysis = await self.claude_client.analyze(prompt, fork_context, working_directory=working_directory)
            
            # Save analysis
            output_dir = self.outputs_dir / self.settings.outputs.directories.get("forks", "forks")
            output_dir.mkdir(parents=True, exist_ok=True)
            
            import time
            timestamp = int(time.time())
            analysis_file = output_dir / f"fork_{timestamp}_analysis.md"
            with open(analysis_file, 'w', encoding='utf-8') as f:
                f.write(analysis)
            
            logger.info("Fork analysis completed", fork=forkee.get("full_name"))
            
            return {
                "status": "success",
                "repository": repo_name,
                "fork": forkee.get("full_name"),
                "analysis_file": str(analysis_file)
            }
            
        except Exception as e:
            logger.error("Error processing fork", repo=repo_name, error=str(e), exc_info=True)
            return {"status": "error", "error": str(e)}


class StarHandler(BaseHandler):
    """Handler for GitHub star events."""
    
    async def handle(self, payload: Dict[str, Any], action: str) -> Dict[str, Any]:
        """Handle star events."""
        
        if action not in ["created", "deleted"]:
            return {"status": "ignored", "reason": f"action '{action}' not handled"}
        
        repository = payload.get("repository", {})
        repo_name = repository.get("full_name")
        sender = payload.get("sender", {})
        
        logger.info("Processing star event", repo=repo_name, action=action, user=sender.get("login"))
        
        # For star events, we might just track them without detailed analysis
        try:
            output_dir = self.outputs_dir / self.settings.outputs.directories.get("stars", "stars")
            output_dir.mkdir(parents=True, exist_ok=True)
            
            # Log star event
            import time
            timestamp = int(time.time())
            star_file = output_dir / f"stars_{timestamp}.json"
            
            star_data = {
                "repository": repo_name,
                "action": action,
                "user": sender.get("login"),
                "timestamp": timestamp,
                "total_stars": repository.get("stargazers_count", 0)
            }
            
            import json
            with open(star_file, 'w') as f:
                json.dump(star_data, f, indent=2)
            
            logger.info("Star event recorded", action=action, user=sender.get("login"))
            
            return {
                "status": "success",
                "action": action,
                "user": sender.get("login"),
                "total_stars": repository.get("stargazers_count", 0)
            }
            
        except Exception as e:
            logger.error("Error processing star event", repo=repo_name, error=str(e), exc_info=True)
            return {"status": "error", "error": str(e)}


class CommitCommentHandler(BaseHandler):
    """Handler for GitHub commit comment events."""
    
    async def handle(self, payload: Dict[str, Any], action: str) -> Dict[str, Any]:
        """Handle commit comment events."""
        
        if action != "created":
            return {"status": "ignored", "reason": f"action '{action}' not handled"}
        
        comment = payload.get("comment", {})
        repository = payload.get("repository", {})
        repo_name = repository.get("full_name")
        
        logger.info("Processing commit comment", repo=repo_name, commit=comment.get("commit_id"))
        
        try:
            # Create context for analysis
            comment_context = f"""# GitHub Commit Comment Analysis

## Comment Details
- **Repository**: {repo_name}
- **Commit**: {comment.get('commit_id', '')[:7]}
- **Author**: {comment.get('user', {}).get('login', '')}
- **Path**: {comment.get('path', 'general comment')}
- **Line**: {comment.get('line', 'N/A')}

## Comment
{comment.get('body', '')}
"""
            
            # Use generic handler for now
            return await GenericHandler(self.settings, self.claude_client, self.github_client, self.prompt_loader).handle(payload, action)
            
        except Exception as e:
            logger.error("Error processing commit comment", repo=repo_name, error=str(e), exc_info=True)
            return {"status": "error", "error": str(e)}


class ProjectHandler(BaseHandler):
    """Handler for GitHub project events."""
    
    async def handle(self, payload: Dict[str, Any], action: str) -> Dict[str, Any]:
        """Handle project events."""
        
        project = payload.get("project", {})
        repository = payload.get("repository", {})
        repo_name = repository.get("full_name")
        
        logger.info("Processing project event", repo=repo_name, action=action, project=project.get("name"))
        
        try:
            # Create context for analysis
            project_context = f"""# GitHub Project Event Analysis

## Project Details
- **Repository**: {repo_name}
- **Action**: {action}
- **Project**: {project.get('name', '')}
- **Number**: {project.get('number', '')}
- **State**: {project.get('state', '')}
- **Creator**: {project.get('creator', {}).get('login', '')}

## Project Description
{project.get('body', '')}
"""
            
            # Use generic handler
            return await GenericHandler(self.settings, self.claude_client, self.github_client, self.prompt_loader).handle(payload, action)
            
        except Exception as e:
            logger.error("Error processing project event", repo=repo_name, error=str(e), exc_info=True)
            return {"status": "error", "error": str(e)}


class MilestoneHandler(BaseHandler):
    """Handler for GitHub milestone events."""
    
    async def handle(self, payload: Dict[str, Any], action: str) -> Dict[str, Any]:
        """Handle milestone events."""
        
        milestone = payload.get("milestone", {})
        repository = payload.get("repository", {})
        repo_name = repository.get("full_name")
        
        logger.info("Processing milestone event", repo=repo_name, action=action, milestone=milestone.get("title"))
        
        try:
            # Create context for analysis
            milestone_context = f"""# GitHub Milestone Event Analysis

## Milestone Details
- **Repository**: {repo_name}
- **Action**: {action}
- **Title**: {milestone.get('title', '')}
- **Number**: {milestone.get('number', '')}
- **State**: {milestone.get('state', '')}
- **Due Date**: {milestone.get('due_on', 'Not set')}

## Progress
- **Open Issues**: {milestone.get('open_issues', 0)}
- **Closed Issues**: {milestone.get('closed_issues', 0)}

## Description
{milestone.get('description', '')}
"""
            
            # Use generic handler
            return await GenericHandler(self.settings, self.claude_client, self.github_client, self.prompt_loader).handle(payload, action)
            
        except Exception as e:
            logger.error("Error processing milestone event", repo=repo_name, error=str(e), exc_info=True)
            return {"status": "error", "error": str(e)}


class DeploymentHandler(BaseHandler):
    """Handler for GitHub deployment events."""
    
    async def handle(self, payload: Dict[str, Any], action: str) -> Dict[str, Any]:
        """Handle deployment events."""
        
        deployment = payload.get("deployment", {})
        repository = payload.get("repository", {})
        repo_name = repository.get("full_name")
        
        logger.info("Processing deployment event", repo=repo_name, environment=deployment.get("environment"))
        
        try:
            # Load and render prompt
            context = create_prompt_context("deployment", payload)
            prompt = self.prompt_loader.render_prompt("deployment", "created", context)
            
            if not prompt:
                logger.warning("No prompt for deployment event, using generic handler")
                return await GenericHandler(self.settings, self.claude_client, self.github_client, self.prompt_loader).handle(payload, action)
            
            # Create context for Claude
            deployment_context = f"""# GitHub Deployment Event Analysis

## Deployment Details
- **Repository**: {repo_name}
- **Environment**: {deployment.get('environment', '')}
- **Ref**: {deployment.get('ref', '')}
- **SHA**: {deployment.get('sha', '')[:7]}
- **Creator**: {deployment.get('creator', {}).get('login', '')}
- **Task**: {deployment.get('task', 'deploy')}

## Deployment Description
{deployment.get('description', '')}

## Payload
```json
{json.dumps(deployment.get('payload', {}), indent=2)[:1000]}...
```
"""
            
            # Get repository working directory
            working_directory = self.get_repository_working_directory(payload)
            
            # Analyze with Claude
            analysis = await self.claude_client.analyze(prompt, deployment_context, working_directory=working_directory)
            
            # Save analysis
            output_dir = self.outputs_dir / self.settings.outputs.directories.get("deployments", "deployments")
            output_dir.mkdir(parents=True, exist_ok=True)
            
            import time
            timestamp = int(time.time())
            analysis_file = output_dir / f"deployment_{timestamp}_analysis.md"
            with open(analysis_file, 'w', encoding='utf-8') as f:
                f.write(analysis)
            
            logger.info("Deployment analysis completed", environment=deployment.get("environment"))
            
            return {
                "status": "success",
                "repository": repo_name,
                "environment": deployment.get("environment"),
                "analysis_file": str(analysis_file)
            }
            
        except Exception as e:
            logger.error("Error processing deployment", repo=repo_name, error=str(e), exc_info=True)
            return {"status": "error", "error": str(e)}


class WatchHandler(BaseHandler):
    """Handler for GitHub watch events."""
    
    async def handle(self, payload: Dict[str, Any], action: str) -> Dict[str, Any]:
        """Handle watch events."""
        
        repository = payload.get("repository", {})
        repo_name = repository.get("full_name")
        sender = payload.get("sender", {})
        
        logger.info("Processing watch event", repo=repo_name, action=action, user=sender.get("login"))
        
        # Similar to star events, just track them
        try:
            output_dir = self.outputs_dir / self.settings.outputs.directories.get("watches", "watches")
            output_dir.mkdir(parents=True, exist_ok=True)
            
            import time
            timestamp = int(time.time())
            watch_file = output_dir / f"watch_{timestamp}.json"
            
            watch_data = {
                "repository": repo_name,
                "action": action,
                "user": sender.get("login"),
                "timestamp": timestamp,
                "total_watchers": repository.get("watchers_count", 0)
            }
            
            with open(watch_file, 'w') as f:
                json.dump(watch_data, f, indent=2)
            
            logger.info("Watch event recorded", action=action, user=sender.get("login"))
            
            return {
                "status": "success",
                "action": action,
                "user": sender.get("login"),
                "total_watchers": repository.get("watchers_count", 0)
            }
            
        except Exception as e:
            logger.error("Error processing watch event", repo=repo_name, error=str(e), exc_info=True)
            return {"status": "error", "error": str(e)}


class TeamHandler(BaseHandler):
    """Handler for GitHub team events."""
    
    async def handle(self, payload: Dict[str, Any], action: str) -> Dict[str, Any]:
        """Handle team events."""
        
        team = payload.get("team", {})
        organization = payload.get("organization", {})
        
        logger.info("Processing team event", team=team.get("name"), org=organization.get("login"), action=action)
        
        # Use generic handler for team events
        return await GenericHandler(self.settings, self.claude_client, self.github_client, self.prompt_loader).handle(payload, action)


class MemberHandler(BaseHandler):
    """Handler for GitHub member events."""
    
    async def handle(self, payload: Dict[str, Any], action: str) -> Dict[str, Any]:
        """Handle member events."""
        
        member = payload.get("member", {})
        repository = payload.get("repository", {})
        repo_name = repository.get("full_name")
        
        logger.info("Processing member event", repo=repo_name, member=member.get("login"), action=action)
        
        try:
            # Create context for analysis
            member_context = f"""# GitHub Member Event Analysis

## Member Details
- **Repository**: {repo_name}
- **Action**: {action}
- **Member**: {member.get('login', '')}
- **Member Type**: {member.get('type', '')}

## Repository Access
This event indicates that a member's access to the repository has changed.
"""
            
            # Use generic handler
            return await GenericHandler(self.settings, self.claude_client, self.github_client, self.prompt_loader).handle(payload, action)
            
        except Exception as e:
            logger.error("Error processing member event", repo=repo_name, error=str(e), exc_info=True)
            return {"status": "error", "error": str(e)}


class InvitationHandler:
    """Handler for repository collaboration invitations."""
    
    def __init__(self, settings: Settings, github_client: GitHubClient):
        self.settings = settings
        self.github_client = github_client
        self.config = settings.auto_accept_invitations
    
    async def process_invitations(self) -> Dict[str, Any]:
        """Process all pending invitations based on configured criteria."""
        if not self.config.enabled:
            logger.info("Auto-accept invitations is disabled")
            return {"status": "disabled", "processed": 0}
        
        logger.info("Starting invitation processing")
        
        # Get all pending invitations
        invitations = await self.github_client.get_user_repository_invitations()
        
        if not invitations:
            logger.info("No pending invitations found")
            return {"status": "success", "processed": 0, "invitations": []}
        
        processed_invitations = []
        accepted_count = 0
        declined_count = 0
        
        for invitation in invitations:
            try:
                decision = self._evaluate_invitation(invitation)
                
                if decision == "accept":
                    success = await self.github_client.accept_repository_invitation(invitation["id"])
                    if success:
                        accepted_count += 1
                        repo_full_name = invitation["repository"]["full_name"]
                        
                        # Perform post-acceptance setup
                        setup_result = await self._setup_new_repository(repo_full_name)
                        
                        processed_invitations.append({
                            "id": invitation["id"],
                            "repository": repo_full_name,
                            "action": "accepted",
                            "reason": "matched criteria",
                            "setup_result": setup_result
                        })
                    else:
                        processed_invitations.append({
                            "id": invitation["id"],
                            "repository": invitation["repository"]["full_name"],
                            "action": "failed",
                            "reason": "api error"
                        })
                elif decision == "decline":
                    success = await self.github_client.decline_repository_invitation(invitation["id"])
                    if success:
                        declined_count += 1
                        processed_invitations.append({
                            "id": invitation["id"],
                            "repository": invitation["repository"]["full_name"],
                            "action": "declined",
                            "reason": "excluded by criteria"
                        })
                else:
                    processed_invitations.append({
                        "id": invitation["id"],
                        "repository": invitation["repository"]["full_name"],
                        "action": "skipped",
                        "reason": decision
                    })
                
            except Exception as e:
                logger.error("Error processing invitation", 
                           invitation_id=invitation["id"], error=str(e))
                processed_invitations.append({
                    "id": invitation["id"],
                    "repository": invitation["repository"]["full_name"],
                    "action": "error",
                    "reason": str(e)
                })
        
        logger.info("Invitation processing completed", 
                   accepted=accepted_count, declined=declined_count, 
                   total=len(invitations))
        
        return {
            "status": "success",
            "processed": len(processed_invitations),
            "accepted": accepted_count,
            "declined": declined_count,
            "invitations": processed_invitations
        }
    
    def _evaluate_invitation(self, invitation: Dict[str, Any]) -> str:
        """Evaluate whether to accept, decline, or skip an invitation."""
        repo_name = invitation["repository"]["full_name"]
        repo_owner = invitation["repository"]["owner"]
        inviter_login = invitation["inviter"]["login"]
        inviter_type = invitation["inviter"]["type"]
        
        criteria = self.config.criteria
        
        # Check exclude patterns first
        if criteria.exclude_patterns:
            for pattern in criteria.exclude_patterns:
                if self._matches_pattern(repo_name, pattern):
                    logger.info("Invitation excluded by pattern", 
                               repo=repo_name, pattern=pattern)
                    return "decline"
        
        # Check repository patterns
        repo_matches = False
        if criteria.repository_patterns:
            for pattern in criteria.repository_patterns:
                if self._matches_pattern(repo_name, pattern):
                    repo_matches = True
                    break
        
        # Check organization restrictions
        org_matches = True
        if criteria.from_organizations:
            org_matches = repo_owner in criteria.from_organizations
        
        # Check user restrictions
        user_matches = True
        if criteria.from_users:
            user_matches = inviter_login in criteria.from_users
        
        # Decision logic
        if repo_matches and org_matches and user_matches:
            logger.info("Invitation accepted by criteria", 
                       repo=repo_name, inviter=inviter_login)
            return "accept"
        else:
            logger.info("Invitation does not match criteria", 
                       repo=repo_name, inviter=inviter_login,
                       repo_matches=repo_matches, org_matches=org_matches, 
                       user_matches=user_matches)
            return "no match"
    
    def _matches_pattern(self, text: str, pattern: str) -> bool:
        """Check if text matches a glob-style pattern."""
        import fnmatch
        return fnmatch.fnmatch(text, pattern)
    
    async def _setup_new_repository(self, repo_full_name: str) -> Dict[str, Any]:
        """Set up a newly accepted repository (clone, configure, webhook)."""
        try:
            import subprocess
            import asyncio
            from pathlib import Path
            
            # Get the path to the setup script
            project_root = Path(__file__).parent.parent.parent.parent
            setup_script = project_root / "scripts" / "setup_new_repository.py"
            
            if not setup_script.exists():
                logger.error("Setup script not found", script_path=str(setup_script))
                return {"success": False, "error": "Setup script not found"}
            
            logger.info("Running repository setup", repository=repo_full_name)
            
            # Run the setup script
            cmd = [str(setup_script), repo_full_name]
            
            # Run in background to avoid blocking
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(project_root)
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0:
                logger.info("Repository setup completed successfully", 
                           repository=repo_full_name)
                return {
                    "success": True,
                    "repository": repo_full_name,
                    "output": stdout.decode() if stdout else ""
                }
            else:
                logger.error("Repository setup failed", 
                           repository=repo_full_name, 
                           error=stderr.decode() if stderr else "Unknown error")
                return {
                    "success": False,
                    "repository": repo_full_name,
                    "error": stderr.decode() if stderr else "Setup script failed"
                }
                
        except Exception as e:
            logger.error("Failed to run repository setup", 
                        repository=repo_full_name, error=str(e))
            return {
                "success": False,
                "repository": repo_full_name,
                "error": str(e)
            }


# Handler registry with all supported GitHub webhook events
HANDLERS = {
    # Core events
    "issues": IssueHandler,
    "pull_request": PullRequestHandler,
    "pull_request_review": ReviewHandler,
    "workflow_run": WorkflowHandler,
    
    # Code events
    "push": PushHandler,
    "commit_comment": CommitCommentHandler,
    
    # Release and deployment events
    "release": ReleaseHandler,
    "deployment": DeploymentHandler,
    
    # Repository events
    "fork": ForkHandler,
    "star": StarHandler,
    "watch": WatchHandler,
    
    # Collaboration events
    "member": MemberHandler,
    "team": TeamHandler,
    
    # Project management events
    "project": ProjectHandler,
    "milestone": MilestoneHandler,
    
    # Generic fallback for any event not explicitly handled
    "generic": GenericHandler,
}

# Optional: Import chained handlers if you want to use them
try:
    from .chained_issue_handler import ChainedIssueHandler
    # To use chained handlers, update the HANDLERS dict:
    HANDLERS["issues"] = ChainedIssueHandler
except ImportError:
    pass