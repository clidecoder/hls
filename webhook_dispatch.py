#!/home/clide/hls/venv/bin/python
"""
GitHub Webhook Dispatch Script

This script is executed by the webhook service (adnanh/webhook) when GitHub sends a webhook.
It processes the webhook payload and can either:
1. Call the existing FastAPI service for processing
2. Process the webhook directly using the existing modules

Usage: Called by webhook service with GitHub headers as arguments and JSON payload via stdin
"""

import sys
import json
import os
import hmac
import hashlib
import asyncio
import logging
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Import existing modules
from hls.src.hsl_handler.config import Settings
from hls.src.hsl_handler.webhook_processor import WebhookProcessor
from hls.src.hsl_handler.clients import ClaudeClient, GitHubClient
from hls.src.hsl_handler.prompts import PromptLoader
from hls.src.hsl_handler.logging_config import setup_logging, RequestIDProcessor
import uuid

def verify_signature(payload_body: bytes, signature: str, secret: str) -> bool:
    """Verify GitHub webhook signature"""
    if not signature.startswith('sha256='):
        return False
    
    expected_signature = hmac.new(
        secret.encode('utf-8'),
        payload_body,
        hashlib.sha256
    ).hexdigest()
    
    return hmac.compare_digest(f'sha256={expected_signature}', signature)

def setup_environment():
    """Setup environment and logging"""
    # Load settings from YAML file (will use container path if available)
    from hls.src.hsl_handler.config import load_settings
    settings = load_settings()
    
    # Setup logging
    setup_logging(settings.logging)
    logger = logging.getLogger(__name__)
    
    # Generate request ID for tracking
    request_id = str(uuid.uuid4())
    request_id_processor = RequestIDProcessor()
    request_id_processor.set_request_id(request_id)
    
    return logger, request_id, settings

async def process_webhook_directly(payload: dict, event_type: str, delivery_id: str, request_id: str) -> dict:
    """Process webhook using existing modules directly"""
    try:
        # Load settings from YAML (will use container path if available)
        from hls.src.hsl_handler.config import load_settings
        settings = load_settings()
        
        # Initialize processor with settings
        processor = WebhookProcessor(settings)
        
        # Process the webhook  
        try:
            result = await processor.process_webhook(event_type, payload, delivery_id, request_id)
        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            print(f"Detailed error: {error_details}", file=sys.stderr)
            raise e
        
        return {
            "status": "processed",
            "request_id": request_id,
            "result": result
        }
        
    except Exception as e:
        return {
            "status": "error",
            "request_id": request_id,
            "error": str(e)
        }

def main():
    """Main dispatch function"""
    logger, request_id, settings = setup_environment()
    
    try:
        # Get GitHub headers from environment (set by webhook service)
        event_type = os.environ.get('GITHUB_EVENT')
        delivery_id = os.environ.get('GITHUB_DELIVERY')
        signature = os.environ.get('GITHUB_SIGNATURE')
        
        logger.info(f"Processing webhook: event={event_type}, delivery={delivery_id}")
        
        # Read JSON payload from command line argument
        if len(sys.argv) > 1:
            payload_body = sys.argv[1].encode('utf-8')
            payload = json.loads(sys.argv[1])
        else:
            # Fallback to stdin for testing
            payload_body = sys.stdin.buffer.read()
            payload = json.loads(payload_body.decode('utf-8'))
        
        # Use settings from environment setup
        
        # Verify signature if enabled
        logger.info(f"Signature validation enabled: {settings.features.signature_validation}")
        if settings.features.signature_validation:
            if not signature:
                logger.error("No signature provided but validation is enabled")
                print(json.dumps({"status": "error", "error": "Missing signature"}))
                sys.exit(1)
                
            if not verify_signature(payload_body, signature, settings.github.webhook_secret):
                logger.error("Invalid webhook signature")
                print(json.dumps({"status": "error", "error": "Invalid signature"}))
                sys.exit(1)
        else:
            logger.info("Signature validation disabled, skipping verification")
        
        # Check if repository is configured
        repo_name = payload.get('repository', {}).get('full_name')
        if not repo_name or not settings.get_repository_config(repo_name):
            logger.info(f"Repository {repo_name} not configured, ignoring")
            print(json.dumps({"status": "ignored", "reason": "repository not configured"}))
            return
        
        # Check if event type is enabled
        if not settings.is_event_enabled(repo_name, event_type):
            logger.info(f"Event {event_type} not enabled for {repo_name}, ignoring") 
            print(json.dumps({"status": "ignored", "reason": f"event {event_type} not enabled"}))
            return
        
        # Process webhook directly using existing modules
        result = asyncio.run(process_webhook_directly(payload, event_type, delivery_id, request_id))
        
        # Output result as JSON
        print(json.dumps(result))
        
        # Log result
        if result["status"] == "processed":
            logger.info(f"Webhook processed successfully: {result.get('result', {}).get('status')}")
        else:
            logger.error(f"Webhook processing failed: {result.get('error')}")
            
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON payload: {e}")
        print(json.dumps({"status": "error", "error": "Invalid JSON payload"}))
        sys.exit(1)
        
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        print(json.dumps({"status": "error", "error": str(e)}))
        sys.exit(1)

if __name__ == "__main__":
    main()