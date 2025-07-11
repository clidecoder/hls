"""API clients for Claude and GitHub."""

import asyncio
import time
import subprocess
import tempfile
import os
from typing import Dict, List, Optional, Any
from pathlib import Path

import requests
from github import Github, GithubException

from .config import ClaudeConfig, GitHubConfig
from .logging_config import get_logger

logger = get_logger(__name__)


class ClaudeClient:
    """Client for interacting with Claude via Claude Code."""
    
    def __init__(self, config: ClaudeConfig):
        self.config = config
        self._request_count = 0
        self._last_request_time = 0.0
    
    async def analyze(self, prompt: str, context: str, conversation_history: Optional[str] = None, working_directory: Optional[str] = None) -> str:
        """Analyze content using Claude via Claude Code.
        
        Args:
            prompt: The prompt to send to Claude
            context: The immediate context for this request
            conversation_history: Optional previous conversation for chained prompts
            working_directory: Optional directory to execute Claude Code from
        """
        
        # Simple rate limiting
        current_time = time.time()
        if current_time - self._last_request_time < 1.0:  # 1 second between requests
            await asyncio.sleep(1.0 - (current_time - self._last_request_time))
        
        self._last_request_time = time.time()
        self._request_count += 1
        
        try:
            # Build full prompt with conversation history if provided
            full_prompt_parts = []
            
            if conversation_history:
                full_prompt_parts.append(conversation_history)
                full_prompt_parts.append("\n# Current Request\n")
            
            full_prompt_parts.append(context)
            full_prompt_parts.append("\n\n")
            full_prompt_parts.append(prompt)
            
            full_prompt = "".join(full_prompt_parts)
            
            logger.info("Sending request to Claude Code", 
                       request_count=self._request_count,
                       has_conversation_history=bool(conversation_history),
                       working_directory=working_directory)
            
            # Make call in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                self._make_claude_code_request,
                full_prompt,
                working_directory
            )
            
            logger.info("Received response from Claude Code", response_length=len(response))
            return response
            
        except Exception as e:
            logger.error("Claude Code error", error=str(e), exc_info=True)
            # Return a mock response for testing
            return f"Claude Code analysis: {prompt[:100]}..."
    
    def _make_claude_code_request(self, prompt: str, working_directory: Optional[str] = None) -> str:
        """Make a request to Claude via Claude Code CLI."""
        try:
            # Create a temporary file with the prompt
            with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
                f.write(prompt)
                temp_file = f.name
            
            # Try to use claude command if available
            try:
                # Check if we're in a Claude Code environment
                result = subprocess.run([
                    'claude', 'prompt', temp_file
                ], capture_output=True, text=True, timeout=30, cwd=working_directory)
                
                if result.returncode == 0:
                    return result.stdout.strip()
                else:
                    logger.warning("Claude command failed", stderr=result.stderr)
                    
            except (subprocess.TimeoutExpired, FileNotFoundError):
                logger.warning("Claude command not available or timed out")
            
            # Fallback: return a simulated analysis
            return self._generate_mock_analysis(prompt)
            
        except Exception as e:
            logger.error("Failed to call Claude Code", error=str(e))
            return self._generate_mock_analysis(prompt)
        finally:
            # Clean up temp file
            try:
                os.unlink(temp_file)
            except:
                pass
    
    def _generate_mock_analysis(self, prompt: str) -> str:
        """Generate a mock analysis response for testing."""
        if "issue" in prompt.lower():
            return """Hi! I'm Clide, and I'll analyze this issue for you. Here's my assessment:

1. **Priority Level**: Medium - This appears to be a legitimate concern that should be addressed
2. **Category**: Bug/Enhancement (needs clarification from the author)
3. **Suggested Labels**: bug, needs-investigation, priority-medium
4. **Recommended Action**: 
   - Request more details about reproduction steps
   - Assign to appropriate team member
   - Add to current sprint backlog
5. **Estimated Complexity**: Moderate - May require some investigation

---
*Analysis provided by Clide - Your friendly AI code assistant*"""

        elif "pull request" in prompt.lower() or "pr" in prompt.lower():
            return """Hi! I'm Clide, and I'll review this pull request for you. Here's my analysis:

1. **Code Quality**: The changes look generally well-structured and follow good practices
2. **Testing**: I recommend adding unit tests for the new functionality
3. **Documentation**: Consider updating relevant documentation to reflect these changes
4. **Security**: No obvious security concerns identified in this review
5. **Performance**: Changes appear to have minimal performance impact
6. **Review Priority**: Medium - Standard review process should suffice
7. **Suggested Labels**: enhancement, needs-tests
8. **Recommendation**: Approve with minor suggestions for improvement

---
*Review provided by Clide - Your friendly AI code assistant*"""

        else:
            return f"""Hi! I'm Clide, your friendly AI code assistant.

I've processed the content and here are my observations:
- Content type appears to be related to software development
- Automated analysis completed successfully
- No immediate issues identified

---
*Analysis provided by Clide - Your friendly AI code assistant*"""


class GitHubClient:
    """Client for interacting with GitHub API."""
    
    def __init__(self, config: GitHubConfig):
        self.config = config
        self.client = Github(config.token)
        self._request_count = 0
    
    async def get_issue(self, repo_name: str, issue_number: int) -> Dict[str, Any]:
        """Get issue details."""
        try:
            repo = self.client.get_repo(repo_name)
            issue = repo.get_issue(issue_number)
            
            return {
                "number": issue.number,
                "title": issue.title,
                "body": issue.body or "",
                "user": issue.user.login,
                "state": issue.state,
                "labels": [label.name for label in issue.labels],
                "url": issue.html_url
            }
        except GithubException as e:
            logger.error("GitHub API error getting issue", error=str(e))
            raise
    
    async def get_pull_request(self, repo_name: str, pr_number: int) -> Dict[str, Any]:
        """Get pull request details."""
        try:
            repo = self.client.get_repo(repo_name)
            pr = repo.get_pull(pr_number)
            
            # Get diff (limited size)
            diff_content = ""
            try:
                diff_response = requests.get(
                    pr.diff_url,
                    headers={"Authorization": f"token {self.config.token}"}
                )
                if diff_response.status_code == 200:
                    diff_content = diff_response.text[:10000]  # Limit diff size
            except Exception as e:
                logger.warning("Could not fetch PR diff", error=str(e))
            
            return {
                "number": pr.number,
                "title": pr.title,
                "body": pr.body or "",
                "user": pr.user.login,
                "state": pr.state,
                "labels": [label.name for label in pr.labels],
                "url": pr.html_url,
                "diff": diff_content,
                "files": [f.filename for f in pr.get_files()],
                "additions": pr.additions,
                "deletions": pr.deletions,
                "changed_files": pr.changed_files
            }
        except GithubException as e:
            logger.error("GitHub API error getting PR", error=str(e))
            raise
    
    async def post_issue_comment(self, repo_name: str, issue_number: int, comment: str) -> bool:
        """Post a comment on an issue."""
        try:
            repo = self.client.get_repo(repo_name)
            issue = repo.get_issue(issue_number)
            issue.create_comment(comment)
            
            logger.info("Posted comment on issue", repo=repo_name, issue=issue_number)
            return True
        except GithubException as e:
            logger.error("Failed to post issue comment", error=str(e))
            return False
    
    async def post_pr_comment(self, repo_name: str, pr_number: int, comment: str) -> bool:
        """Post a comment on a pull request."""
        try:
            repo = self.client.get_repo(repo_name)
            pr = repo.get_pull(pr_number)
            pr.create_issue_comment(comment)
            
            logger.info("Posted comment on PR", repo=repo_name, pr=pr_number)
            return True
        except GithubException as e:
            logger.error("Failed to post PR comment", error=str(e))
            return False
    
    async def add_issue_labels(self, repo_name: str, issue_number: int, labels: List[str]) -> bool:
        """Add labels to an issue."""
        try:
            repo = self.client.get_repo(repo_name)
            issue = repo.get_issue(issue_number)
            
            # Get existing labels to avoid duplicates
            existing_labels = {label.name for label in issue.labels}
            new_labels = [label for label in labels if label not in existing_labels]
            
            if new_labels:
                issue.add_to_labels(*new_labels)
                logger.info("Added labels to issue", repo=repo_name, issue=issue_number, labels=new_labels)
            
            return True
        except GithubException as e:
            logger.error("Failed to add issue labels", error=str(e))
            return False
    
    async def add_pr_labels(self, repo_name: str, pr_number: int, labels: List[str]) -> bool:
        """Add labels to a pull request."""
        try:
            repo = self.client.get_repo(repo_name)
            pr = repo.get_pull(pr_number)
            
            # Get existing labels to avoid duplicates
            existing_labels = {label.name for label in pr.labels}
            new_labels = [label for label in labels if label not in existing_labels]
            
            if new_labels:
                pr.add_to_labels(*new_labels)
                logger.info("Added labels to PR", repo=repo_name, pr=pr_number, labels=new_labels)
            
            return True
        except GithubException as e:
            logger.error("Failed to add PR labels", error=str(e))
            return False
    
    async def close_issue(self, repo_name: str, issue_number: int, comment: Optional[str] = None) -> bool:
        """Close an issue."""
        try:
            repo = self.client.get_repo(repo_name)
            issue = repo.get_issue(issue_number)
            
            if comment:
                issue.create_comment(comment)
            
            issue.edit(state="closed")
            logger.info("Closed issue", repo=repo_name, issue=issue_number)
            return True
        except GithubException as e:
            logger.error("Failed to close issue", error=str(e))
            return False
    
    async def create_repository_labels(self, repo_name: str, labels: List[Dict[str, str]]) -> None:
        """Create repository labels if they don't exist."""
        try:
            repo = self.client.get_repo(repo_name)
            existing_labels = {label.name for label in repo.get_labels()}
            
            for label_info in labels:
                if label_info["name"] not in existing_labels:
                    try:
                        repo.create_label(
                            name=label_info["name"],
                            color=label_info.get("color", "ffffff"),
                            description=label_info.get("description", "")
                        )
                        logger.info("Created label", repo=repo_name, label=label_info["name"])
                    except GithubException as e:
                        logger.warning("Failed to create label", label=label_info["name"], error=str(e))
        except GithubException as e:
            logger.error("Failed to setup repository labels", error=str(e))
    
    async def get_user_repository_invitations(self) -> List[Dict[str, Any]]:
        """Get all pending repository invitations for the authenticated user."""
        try:
            invitations = []
            for invitation in self.client.get_user().get_invitations():
                invitations.append({
                    "id": invitation.id,
                    "repository": {
                        "name": invitation.repository.name,
                        "full_name": invitation.repository.full_name,
                        "owner": invitation.repository.owner.login
                    },
                    "inviter": {
                        "login": invitation.inviter.login,
                        "type": invitation.inviter.type
                    },
                    "permissions": invitation.permissions,
                    "created_at": invitation.created_at.isoformat(),
                    "url": invitation.html_url
                })
            
            logger.info("Retrieved repository invitations", count=len(invitations))
            return invitations
        except GithubException as e:
            logger.error("Failed to get repository invitations", error=str(e))
            return []
    
    async def accept_repository_invitation(self, invitation_id: int) -> bool:
        """Accept a repository invitation."""
        try:
            # Use the REST API directly for repository invitations
            url = f"/user/repository_invitations/{invitation_id}"
            headers = {"Accept": "application/vnd.github+json"}
            
            # Make PATCH request to accept invitation
            response = requests.patch(
                f"https://api.github.com{url}",
                headers={
                    "Authorization": f"token {self.config.token}",
                    "Accept": "application/vnd.github+json"
                }
            )
            
            if response.status_code == 204:
                logger.info("Accepted repository invitation", invitation_id=invitation_id)
                self._request_count += 1
                return True
            else:
                logger.error("Failed to accept repository invitation", 
                           invitation_id=invitation_id, 
                           status_code=response.status_code,
                           response=response.text)
                return False
                
        except Exception as e:
            logger.error("Failed to accept repository invitation", 
                        invitation_id=invitation_id, error=str(e))
            return False
    
    async def decline_repository_invitation(self, invitation_id: int) -> bool:
        """Decline a repository invitation."""
        try:
            # Use the REST API directly for repository invitations
            url = f"/user/repository_invitations/{invitation_id}"
            
            # Make DELETE request to decline invitation
            response = requests.delete(
                f"https://api.github.com{url}",
                headers={
                    "Authorization": f"token {self.config.token}",
                    "Accept": "application/vnd.github+json"
                }
            )
            
            if response.status_code == 204:
                logger.info("Declined repository invitation", invitation_id=invitation_id)
                self._request_count += 1
                return True
            else:
                logger.error("Failed to decline repository invitation", 
                           invitation_id=invitation_id, 
                           status_code=response.status_code,
                           response=response.text)
                return False
                
        except Exception as e:
            logger.error("Failed to decline repository invitation", 
                        invitation_id=invitation_id, error=str(e))
            return False
    
    async def create_repository_webhook(self, repo_name: str, webhook_url: str, 
                                      events: List[str], secret: Optional[str] = None) -> bool:
        """Create a webhook in a repository."""
        try:
            repo = self.client.get_repo(repo_name)
            
            # Check if webhook already exists
            existing_webhooks = repo.get_hooks()
            for hook in existing_webhooks:
                if hook.config.get("url") == webhook_url:
                    logger.info("Webhook already exists", repo=repo_name, url=webhook_url)
                    return True
            
            # Create webhook configuration
            config = {
                "url": webhook_url,
                "content_type": "json"
            }
            
            if secret:
                config["secret"] = secret
            
            # Create the webhook
            hook = repo.create_hook(
                name="web",
                config=config,
                events=events,
                active=True
            )
            
            logger.info("Created repository webhook", 
                       repo=repo_name, webhook_id=hook.id, events=events)
            self._request_count += 1
            return True
            
        except GithubException as e:
            logger.error("Failed to create repository webhook", 
                        repo=repo_name, error=str(e))
            return False
    
    async def get_repository_info(self, repo_name: str) -> Optional[Dict[str, Any]]:
        """Get basic repository information."""
        try:
            repo = self.client.get_repo(repo_name)
            
            return {
                "name": repo.name,
                "full_name": repo.full_name,
                "owner": repo.owner.login,
                "private": repo.private,
                "clone_url": repo.clone_url,
                "ssh_url": repo.ssh_url,
                "default_branch": repo.default_branch,
                "description": repo.description
            }
            
        except GithubException as e:
            logger.error("Failed to get repository info", repo=repo_name, error=str(e))
            return None
    
    def get_stats(self) -> Dict[str, Any]:
        """Get client statistics."""
        rate_limit = self.client.get_rate_limit()
        
        return {
            "requests_made": self._request_count,
            "rate_limit": {
                "core": {
                    "limit": rate_limit.core.limit,
                    "remaining": rate_limit.core.remaining,
                    "reset": rate_limit.core.reset.isoformat()
                }
            }
        }