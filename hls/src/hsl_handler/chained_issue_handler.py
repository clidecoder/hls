"""Chained prompt implementation for issue handling."""

import re
from typing import Dict, List, Any, Optional
from pathlib import Path

from .chained_handlers import ChainedPromptHandler, ChainStep, ChainResult, ChainType
from .logging_config import get_logger

logger = get_logger(__name__)


class ChainedIssueHandler(ChainedPromptHandler):
    """Issue handler using chained prompts for better analysis."""
    
    event_type = "issues"
    
    def get_chain_type(self) -> ChainType:
        """Issues use sequential chain type."""
        return ChainType.SEQUENTIAL
    
    def get_chain_steps(self, payload: Dict[str, Any], action: str) -> List[ChainStep]:
        """Define the chain steps for issue analysis."""
        
        if action != "opened":
            return []
        
        # Define a two-step chain:
        # 1. First analyze the issue to understand it
        # 2. Then generate a response based on the analysis
        return [
            ChainStep(
                name="initial_analysis",
                prompt_key="issues.analyze",
                extract_func="extract_analysis_data",
                save_response=True
            ),
            ChainStep(
                name="generate_response", 
                prompt_key="issues.respond",
                save_response=True
            )
        ]
    
    def extract_analysis_data(self, response: str) -> Dict[str, Any]:
        """Extract structured data from the initial analysis."""
        
        data = {
            "labels": [],
            "priority": "medium",
            "category": "unknown",
            "needs_more_info": False,
            "is_duplicate": False,
            "should_close": False
        }
        
        # Extract labels
        label_patterns = {
            r'\bbug\b': 'bug',
            r'\benhancement\b': 'enhancement',
            r'\bquestion\b': 'question',
            r'\bdocumentation\b': 'documentation',
            r'\bmaintenance\b': 'maintenance'
        }
        
        response_lower = response.lower()
        for pattern, label in label_patterns.items():
            if re.search(pattern, response_lower):
                data["labels"].append(label)
        
        # Extract priority
        if re.search(r'high.priority|critical|urgent', response_lower):
            data["priority"] = "high"
        elif re.search(r'low.priority|minor|trivial', response_lower):
            data["priority"] = "low"
        
        # Extract category
        if "bug" in response_lower:
            data["category"] = "bug"
        elif "feature" in response_lower or "enhancement" in response_lower:
            data["category"] = "feature"
        elif "question" in response_lower:
            data["category"] = "question"
        elif "documentation" in response_lower:
            data["category"] = "documentation"
        
        # Check for special conditions
        if re.search(r'need.more.information|need.more.details|unclear', response_lower):
            data["needs_more_info"] = True
        
        if re.search(r'duplicate|already.reported|existing.issue', response_lower):
            data["is_duplicate"] = True
            
        if "RECOMMENDATION: CLOSE ISSUE" in response:
            data["should_close"] = True
        
        # Add priority-based labels
        data["labels"].append(f"priority-{data['priority']}")
        
        return data
    
    def format_final_response(self, results: List[ChainResult]) -> str:
        """Combine the analysis and response into final output."""
        
        if len(results) < 2:
            return super().format_final_response(results)
        
        # Get the response from the second step
        response_result = results[-1]
        
        # Get extracted data from first step
        analysis_data = results[0].extracted_data or {}
        
        # Add metadata to response
        metadata_parts = []
        
        if analysis_data.get("labels"):
            metadata_parts.append(f"**Suggested Labels**: {', '.join(analysis_data['labels'])}")
        
        metadata_parts.append(f"**Priority**: {analysis_data.get('priority', 'medium').title()}")
        metadata_parts.append(f"**Category**: {analysis_data.get('category', 'unknown').title()}")
        
        if analysis_data.get("needs_more_info"):
            metadata_parts.append("**Status**: Needs more information")
        
        if analysis_data.get("is_duplicate"):
            metadata_parts.append("**Status**: Possible duplicate")
        
        # Combine everything
        final_parts = [
            response_result.response,
            "\n---\n",
            "### Issue Metadata",
            "\n".join(metadata_parts)
        ]
        
        return "\n".join(final_parts)
    
    async def save_chain_results(
        self, 
        payload: Dict[str, Any], 
        results: List[ChainResult], 
        final_response: str
    ) -> None:
        """Save the chain analysis results."""
        
        issue = payload.get("issue", {})
        issue_number = issue.get("number")
        
        # Save individual step results
        output_dir = self.outputs_dir / self.settings.outputs.directories.get("issues", "issues")
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Save combined analysis
        analysis_file = output_dir / f"issue_{issue_number}_chained_analysis.md"
        with open(analysis_file, 'w', encoding='utf-8') as f:
            f.write(f"# Chained Analysis for Issue #{issue_number}\n\n")
            
            for i, result in enumerate(results, 1):
                f.write(f"## Step {i}: {result.step_name}\n\n")
                f.write(result.response)
                
                if result.extracted_data:
                    f.write("\n\n### Extracted Data\n")
                    for key, value in result.extracted_data.items():
                        f.write(f"- **{key}**: {value}\n")
                
                f.write("\n\n---\n\n")
            
            f.write("## Final Response\n\n")
            f.write(final_response)
        
        logger.info(f"Saved chained analysis to {analysis_file}")
    
    async def post_process(
        self, 
        payload: Dict[str, Any], 
        results: List[ChainResult], 
        final_response: str
    ) -> Dict[str, Any]:
        """Post-process the results by adding labels and posting comment."""
        
        issue = payload.get("issue", {})
        issue_number = issue.get("number")
        repository = payload.get("repository", {})
        repo_name = repository.get("full_name")
        
        # Get analysis data
        analysis_data = {}
        if results and results[0].extracted_data:
            analysis_data = results[0].extracted_data
        
        # Check if already analyzed
        labels = [label["name"] for label in issue.get("labels", [])]
        if "clide-analyzed" in labels:
            logger.info("Issue already analyzed", issue=issue_number)
            return {"status": "skipped", "reason": "already analyzed"}
        
        repo_config = self.settings.get_repository_config(repo_name)
        
        # Apply labels
        labels_applied = []
        if repo_config and repo_config.settings.get("apply_labels", True):
            suggested_labels = analysis_data.get("labels", [])
            if suggested_labels:
                await self.github_client.add_issue_labels(repo_name, issue_number, suggested_labels)
                labels_applied = suggested_labels
        
        # Post comment
        if repo_config and repo_config.settings.get("post_analysis_comments", True):
            comment = final_response
            
            await self.github_client.post_issue_comment(repo_name, issue_number, comment)
        
        # Check if should close
        if (repo_config and 
            repo_config.settings.get("auto_close_invalid", False) and 
            analysis_data.get("should_close", False)):
            
            close_comment = """This issue has been automatically closed as it appears to be off-topic or not related to bugs, features, or codebase improvements.

If you believe this was closed in error, please feel free to provide additional context about how this relates to the project."""
            
            await self.github_client.close_issue(repo_name, issue_number, close_comment)
        
        # Mark as analyzed
        await self.github_client.add_issue_labels(repo_name, issue_number, ["clide-analyzed"])
        
        logger.info("Issue chained analysis completed", issue=issue_number)
        
        return {
            "status": "success",
            "issue_number": issue_number,
            "chain_steps": len(results),
            "labels_applied": labels_applied,
            "analysis_data": analysis_data
        }