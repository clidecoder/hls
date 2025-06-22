"""Prompt loading and template system."""

import os
from pathlib import Path
from typing import Dict, Optional, Any
from jinja2 import Environment, FileSystemLoader, Template

from .config import PromptsConfig
from .logging_config import get_logger

logger = get_logger(__name__)


class PromptLoader:
    """Loads and processes prompt templates."""
    
    def __init__(self, config: PromptsConfig):
        self.config = config
        self.base_dir = Path(config.base_dir)
        
        # Setup Jinja2 environment for templating
        self.jinja_env = Environment(
            loader=FileSystemLoader(str(self.base_dir)),
            trim_blocks=True,
            lstrip_blocks=True
        )
        
        # Cache for loaded prompts
        self._prompt_cache: Dict[str, str] = {}
    
    def get_prompt_path(self, event_type: str, action: str) -> Optional[str]:
        """Get the prompt file path for an event type and action."""
        templates = self.config.templates.get(event_type, {})
        
        # Try specific action first, then default
        prompt_file = templates.get(action) or templates.get("default")
        
        if not prompt_file:
            logger.warning("No prompt template found", event_type=event_type, action=action)
            return None
        
        return prompt_file
    
    def load_prompt(self, event_type: str, action: str, use_cache: bool = True) -> Optional[str]:
        """Load a prompt template for the given event type and action."""
        
        # Get prompt file path
        prompt_file = self.get_prompt_path(event_type, action)
        if not prompt_file:
            return None
        
        # Check cache first
        cache_key = f"{event_type}:{action}"
        if use_cache and cache_key in self._prompt_cache:
            return self._prompt_cache[cache_key]
        
        # Load from file
        full_path = self.base_dir / prompt_file
        
        if not full_path.exists():
            logger.error("Prompt file not found", path=str(full_path))
            return None
        
        try:
            with open(full_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Cache the content
            if use_cache:
                self._prompt_cache[cache_key] = content
            
            logger.info("Loaded prompt template", event_type=event_type, action=action, file=prompt_file)
            return content
            
        except Exception as e:
            logger.error("Failed to load prompt file", path=str(full_path), error=str(e))
            return None
    
    def render_prompt(self, event_type: str, action: str, context: Dict[str, Any]) -> Optional[str]:
        """Load and render a prompt template with context variables."""
        
        prompt_template = self.load_prompt(event_type, action)
        if not prompt_template:
            return None
        
        try:
            # Render with Jinja2
            template = Template(prompt_template)
            rendered = template.render(**context)
            
            logger.info("Rendered prompt template", event_type=event_type, action=action)
            return rendered
            
        except Exception as e:
            logger.error("Failed to render prompt template", error=str(e), exc_info=True)
            return prompt_template  # Return unrendered template as fallback
    
    def clear_cache(self) -> None:
        """Clear the prompt cache."""
        self._prompt_cache.clear()
        logger.info("Prompt cache cleared")
    
    def list_available_prompts(self) -> Dict[str, Dict[str, str]]:
        """List all available prompt templates."""
        available = {}
        
        for event_type, templates in self.config.templates.items():
            available[event_type] = {}
            for action, template_file in templates.items():
                full_path = self.base_dir / template_file
                available[event_type][action] = {
                    "file": template_file,
                    "exists": full_path.exists(),
                    "path": str(full_path)
                }
        
        return available


def create_prompt_context(event_type: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Create context variables for prompt rendering."""
    
    context = {
        "event_type": event_type,
        "payload": payload,
        "repository": payload.get("repository", {}),
        "sender": payload.get("sender", {})
    }
    
    if event_type == "issues":
        context["issue"] = payload.get("issue", {})
    
    elif event_type == "pull_request":
        context["pull_request"] = payload.get("pull_request", {})
    
    elif event_type == "pull_request_review":
        context["review"] = payload.get("review", {})
        context["pull_request"] = payload.get("pull_request", {})
    
    elif event_type == "workflow_run":
        context["workflow_run"] = payload.get("workflow_run", {})
    
    return context