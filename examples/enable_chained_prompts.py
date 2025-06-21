#!/usr/bin/env python3
"""Example of how to enable chained prompts in the webhook handler."""

import sys
import os

# Add the parent directory to the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from hls.src.hsl_handler.handlers import HANDLERS
from hls.src.hsl_handler.chained_issue_handler import ChainedIssueHandler


def enable_chained_handlers():
    """Enable chained handlers for better multi-step analysis."""
    
    # Replace the standard IssueHandler with ChainedIssueHandler
    HANDLERS["issues"] = ChainedIssueHandler
    
    print("Chained handlers enabled!")
    print(f"Current handlers: {list(HANDLERS.keys())}")
    print(f"Issue handler type: {HANDLERS['issues'].__name__}")


def show_chain_usage():
    """Show how chained prompts work."""
    
    print("\nChained Prompt Workflow:")
    print("1. First prompt analyzes the issue to understand it")
    print("2. Extracts structured data (labels, priority, etc.)")
    print("3. Second prompt uses the analysis to generate a response")
    print("4. Both steps maintain conversation context")
    print("\nBenefits:")
    print("- Better analysis by breaking down complex tasks")
    print("- More consistent responses")
    print("- Ability to extract and use structured data between steps")
    print("- Maintains context throughout the conversation")


def show_configuration():
    """Show how to configure chained prompts."""
    
    print("\nConfiguration Steps:")
    print("1. Create prompt templates in prompts/issues/:")
    print("   - analyze.md (first step)")
    print("   - respond.md (second step)")
    print("2. Update handlers.py to use ChainedIssueHandler")
    print("3. Optionally update settings.yaml with new prompt mappings")
    
    print("\nPrompt Template Structure:")
    print("- Use Jinja2 templating for dynamic content")
    print("- Access previous step data via context variables")
    print("- Each step can extract and pass data to the next")


if __name__ == "__main__":
    print("=== Chained Prompts Example ===\n")
    
    # Show current state
    print("Before enabling:")
    print(f"Issue handler type: {HANDLERS.get('issues', 'Not found').__name__}")
    
    # Enable chained handlers
    enable_chained_handlers()
    
    # Show usage
    show_chain_usage()
    
    # Show configuration
    show_configuration()
    
    print("\n=== Done ===")