# Migration Guide: FastAPI-only to Go Webhook + SQLite Architecture

## Overview

This guide provides a step-by-step migration from the current FastAPI-only architecture to the improved Go webhook + SQLite design. The migration is designed to be incremental with minimal downtime.

## Pre-Migration Checklist

### Prerequisites
- [ ] Go webhook tool confirmed installed (`which webhook`)
- [ ] SQLite3 available (`which sqlite3`)
- [ ] Current system backed up
- [ ] Test environment available
- [ ] Maintenance window scheduled

### Environment Preparation
```bash
# Create necessary directories
sudo mkdir -p /opt/hsl/{bin,data,config,logs}
sudo chown -R hsl:hsl /opt/hsl

# Install additional Python dependencies
pip install sqlite3  # Usually included in Python
pip install watchdog  # For file monitoring
```

## Migration Phases

### Phase 1: Add SQLite Foundation (Week 1)

#### Step 1.1: Create Database Schema
```bash
# Create the SQLite database
cd /opt/hsl
sqlite3 data/webhooks.db < schema.sql
```

Create `schema.sql`:
```sql
-- Main webhook queue
CREATE TABLE webhook_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    delivery_id TEXT UNIQUE NOT NULL,
    event_type TEXT NOT NULL,
    repository TEXT NOT NULL,
    action TEXT,
    payload_json TEXT NOT NULL,
    signature TEXT NOT NULL,
    status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'processing', 'completed', 'failed', 'retry')),
    retry_count INTEGER DEFAULT 0,
    priority INTEGER DEFAULT 5,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    scheduled_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    error_message TEXT
);

CREATE INDEX idx_webhook_status ON webhook_events(status);
CREATE INDEX idx_webhook_scheduled ON webhook_events(scheduled_at);
CREATE INDEX idx_webhook_repository ON webhook_events(repository);

-- Processing results
CREATE TABLE processing_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    webhook_id INTEGER NOT NULL,
    claude_prompt TEXT,
    claude_response TEXT,
    claude_tokens_used INTEGER,
    claude_cost_usd REAL,
    github_actions_json TEXT,
    processing_time_ms INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (webhook_id) REFERENCES webhook_events(id)
);

-- Configuration cache
CREATE TABLE repository_configs (
    repository TEXT PRIMARY KEY,
    config_json TEXT NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Daily statistics
CREATE TABLE daily_stats (
    date TEXT PRIMARY KEY,
    total_webhooks INTEGER DEFAULT 0,
    successful_processing INTEGER DEFAULT 0,
    failed_processing INTEGER DEFAULT 0,
    claude_api_calls INTEGER DEFAULT 0,
    claude_cost_usd REAL DEFAULT 0.0,
    avg_processing_time_ms REAL DEFAULT 0.0
);
```

#### Step 1.2: Create Database Helper Module
Create `hls/src/hls_handler/database.py`:
```python
import sqlite3
import json
import asyncio
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from contextlib import asynccontextmanager

class WebhookDatabase:
    def __init__(self, db_path: str = "/opt/hsl/data/webhooks.db"):
        self.db_path = db_path
        
    @asynccontextmanager
    async def get_connection(self):
        """Async context manager for database connections."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()
    
    async def queue_webhook(
        self, 
        delivery_id: str,
        event_type: str,
        repository: str,
        action: str,
        payload: Dict[str, Any],
        signature: str,
        priority: int = 5
    ) -> bool:
        """Queue a webhook for processing."""
        async with self.get_connection() as conn:
            try:
                conn.execute("""
                    INSERT OR IGNORE INTO webhook_events 
                    (delivery_id, event_type, repository, action, payload_json, signature, priority)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (delivery_id, event_type, repository, action, json.dumps(payload), signature, priority))
                conn.commit()
                return conn.changes > 0
            except sqlite3.Error as e:
                print(f"Database error: {e}")
                return False
    
    async def get_next_webhook(self, worker_id: str = None) -> Optional[Dict]:
        """Get the next webhook to process."""
        async with self.get_connection() as conn:
            # Get next pending webhook
            cursor = conn.execute("""
                SELECT * FROM webhook_events 
                WHERE status = 'pending' AND scheduled_at <= ?
                ORDER BY priority ASC, created_at ASC 
                LIMIT 1
            """, (datetime.now(),))
            
            row = cursor.fetchone()
            if not row:
                return None
            
            # Mark as processing
            conn.execute("""
                UPDATE webhook_events 
                SET status = 'processing', started_at = ?
                WHERE id = ?
            """, (datetime.now(), row['id']))
            conn.commit()
            
            return dict(row)
    
    async def complete_webhook(self, webhook_id: int, result: Dict[str, Any]):
        """Mark webhook as completed and save results."""
        async with self.get_connection() as conn:
            # Update webhook status
            conn.execute("""
                UPDATE webhook_events 
                SET status = 'completed', completed_at = ?
                WHERE id = ?
            """, (datetime.now(), webhook_id))
            
            # Save processing results
            conn.execute("""
                INSERT INTO processing_results 
                (webhook_id, claude_prompt, claude_response, claude_tokens_used, 
                 claude_cost_usd, github_actions_json, processing_time_ms)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                webhook_id,
                result.get('claude_prompt'),
                result.get('claude_response'),
                result.get('claude_tokens_used'),
                result.get('claude_cost_usd'),
                json.dumps(result.get('github_actions', [])),
                result.get('processing_time_ms')
            ))
            
            conn.commit()
    
    async def fail_webhook(self, webhook_id: int, error_message: str, retry: bool = True):
        """Mark webhook as failed and optionally schedule retry."""
        async with self.get_connection() as conn:
            cursor = conn.execute(
                "SELECT retry_count FROM webhook_events WHERE id = ?", 
                (webhook_id,)
            )
            row = cursor.fetchone()
            if not row:
                return
            
            retry_count = row['retry_count']
            max_retries = 3
            
            if retry and retry_count < max_retries:
                # Schedule retry with exponential backoff
                delay_minutes = 2 ** retry_count  # 2, 4, 8 minutes
                scheduled_at = datetime.now() + timedelta(minutes=delay_minutes)
                
                conn.execute("""
                    UPDATE webhook_events 
                    SET status = 'retry', retry_count = retry_count + 1,
                        scheduled_at = ?, error_message = ?
                    WHERE id = ?
                """, (scheduled_at, error_message, webhook_id))
            else:
                # Mark as permanently failed
                conn.execute("""
                    UPDATE webhook_events 
                    SET status = 'failed', error_message = ?
                    WHERE id = ?
                """, (error_message, webhook_id))
            
            conn.commit()
    
    async def get_queue_stats(self) -> Dict[str, Any]:
        """Get current queue statistics."""
        async with self.get_connection() as conn:
            cursor = conn.execute("""
                SELECT 
                    status,
                    COUNT(*) as count
                FROM webhook_events 
                GROUP BY status
            """)
            
            status_counts = {row['status']: row['count'] for row in cursor.fetchall()}
            
            cursor = conn.execute("""
                SELECT COUNT(*) as overdue 
                FROM webhook_events 
                WHERE status = 'pending' AND scheduled_at < ?
            """, (datetime.now() - timedelta(minutes=5),))
            
            overdue_count = cursor.fetchone()['overdue']
            
            return {
                'queue_status': status_counts,
                'overdue_webhooks': overdue_count,
                'total_pending': status_counts.get('pending', 0)
            }
```

#### Step 1.3: Modify FastAPI to Use SQLite Queue
Update `main.py` to queue webhooks instead of processing them directly:

```python
# Add to imports
from .database import WebhookDatabase

# Initialize database
webhook_db = WebhookDatabase()

# Modify webhook handler
@app.post(settings.server.webhook_path)
async def handle_webhook(request: Request, background_tasks: BackgroundTasks):
    # ... existing validation code ...
    
    # Queue webhook instead of processing
    queued = await webhook_db.queue_webhook(
        delivery_id=delivery_id,
        event_type=event_type,
        repository=repo_name,
        action=payload.get("action", ""),
        payload=payload,
        signature=signature
    )
    
    if queued:
        logger.info("Webhook queued successfully", 
                   event_type=event_type, 
                   repository=repo_name,
                   delivery_id=delivery_id)
        
        return JSONResponse({
            "status": "queued",
            "delivery_id": delivery_id,
            "event_type": event_type,
            "repository": repo_name
        })
    else:
        logger.warning("Webhook already processed (duplicate)", 
                      delivery_id=delivery_id)
        return JSONResponse({"status": "duplicate", "delivery_id": delivery_id})

# Add queue management endpoints
@app.get("/queue/stats")
async def get_queue_stats():
    """Get queue statistics."""
    return await webhook_db.get_queue_stats()

@app.post("/queue/retry/{webhook_id}")
async def retry_webhook(webhook_id: int):
    """Manually retry a failed webhook."""
    # Implementation for manual retry
    pass
```

#### Step 1.4: Create Worker Process
Create `hls/src/hls_handler/worker.py`:
```python
#!/usr/bin/env python3
"""
HLS Webhook Worker Process
Processes webhooks from SQLite queue
"""

import asyncio
import argparse
import signal
import sys
import json
import time
from typing import Dict, Any

from .database import WebhookDatabase
from .webhook_processor import WebhookProcessor
from .config import Settings
from .logging_config import setup_logging, get_logger

class WebhookWorker:
    def __init__(self, worker_id: str, settings: Settings):
        self.worker_id = worker_id
        self.settings = settings
        self.database = WebhookDatabase()
        self.processor = WebhookProcessor(settings)
        self.running = False
        self.logger = get_logger(f"worker.{worker_id}")
        
    async def start(self):
        """Start the worker process."""
        self.running = True
        self.logger.info("Worker started", worker_id=self.worker_id)
        
        while self.running:
            try:
                webhook = await self.database.get_next_webhook(self.worker_id)
                
                if webhook:
                    await self.process_webhook(webhook)
                else:
                    # No work available, sleep briefly
                    await asyncio.sleep(5)
                    
            except Exception as e:
                self.logger.error("Worker error", error=str(e), exc_info=True)
                await asyncio.sleep(10)  # Back off on errors
    
    async def process_webhook(self, webhook: Dict[str, Any]):
        """Process a single webhook."""
        start_time = time.time()
        webhook_id = webhook['id']
        
        try:
            self.logger.info(
                "Processing webhook",
                webhook_id=webhook_id,
                event_type=webhook['event_type'],
                repository=webhook['repository'],
                delivery_id=webhook['delivery_id']
            )
            
            # Parse payload
            payload = json.loads(webhook['payload_json'])
            
            # Process using existing logic
            result = await self.processor.process_webhook(
                event_type=webhook['event_type'],
                payload=payload,
                delivery_id=webhook['delivery_id'],
                request_id=f"worker-{self.worker_id}-{webhook_id}"
            )
            
            # Calculate processing time
            processing_time_ms = int((time.time() - start_time) * 1000)
            
            # Add timing and cost info to result
            result.update({
                'processing_time_ms': processing_time_ms,
                'worker_id': self.worker_id
            })
            
            # Mark as completed
            await self.database.complete_webhook(webhook_id, result)
            
            self.logger.info(
                "Webhook processing completed",
                webhook_id=webhook_id,
                processing_time_ms=processing_time_ms,
                status=result.get('status')
            )
            
        except Exception as e:
            processing_time_ms = int((time.time() - start_time) * 1000)
            error_msg = f"Processing failed: {str(e)}"
            
            self.logger.error(
                "Webhook processing failed",
                webhook_id=webhook_id,
                error=error_msg,
                processing_time_ms=processing_time_ms,
                exc_info=True
            )
            
            # Mark as failed with retry
            await self.database.fail_webhook(webhook_id, error_msg, retry=True)
    
    def stop(self):
        """Stop the worker process."""
        self.logger.info("Worker stopping", worker_id=self.worker_id)
        self.running = False

async def main():
    parser = argparse.ArgumentParser(description='HLS Webhook Worker')
    parser.add_argument('--worker-id', default='1', help='Worker ID')
    parser.add_argument('--config', default='config/settings.yaml', help='Config file')
    args = parser.parse_args()
    
    # Load configuration
    settings = Settings.from_yaml(args.config)
    setup_logging(settings.logging)
    
    # Create worker
    worker = WebhookWorker(args.worker_id, settings)
    
    # Handle signals
    def signal_handler(signum, frame):
        worker.stop()
    
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    
    # Start worker
    try:
        await worker.start()
    except KeyboardInterrupt:
        pass
    finally:
        worker.stop()

if __name__ == "__main__":
    asyncio.run(main())
```

#### Step 1.5: Test SQLite Integration
```bash
# Start the modified FastAPI service
python -m hls.src.hls_handler.main

# In another terminal, start a worker
python -m hls.src.hls_handler.worker --worker-id=test-1

# Send a test webhook
curl -X POST http://localhost:8000/webhook \
  -H "Content-Type: application/json" \
  -H "X-GitHub-Event: issues" \
  -H "X-GitHub-Delivery: test-123" \
  -d '{"action":"opened","issue":{"title":"Test Issue"}}'

# Check queue stats
curl http://localhost:8000/queue/stats
```

### Phase 2: Add Go Webhook Receiver (Week 2)

#### Step 2.1: Create Queue Script
Create `/opt/hsl/bin/queue-webhook`:
```bash
#!/bin/bash
set -e

# HLS Webhook Queue Script
# Called by Go webhook to queue events

EVENT_TYPE="$1"
DELIVERY_ID="$2"
SIGNATURE="$3"
PAYLOAD="$4"

# Extract repository from payload
REPOSITORY=$(echo "$PAYLOAD" | python3 -c "
import json, sys
try:
    data = json.load(sys.stdin)
    repo = data.get('repository', {}).get('full_name', 'unknown')
    print(repo)
except:
    print('unknown')
")

# Extract action from payload
ACTION=$(echo "$PAYLOAD" | python3 -c "
import json, sys
try:
    data = json.load(sys.stdin)
    action = data.get('action', '')
    print(action)
except:
    print('')
")

# Queue webhook using Python script
cd /opt/hsl
python3 -c "
import asyncio
import json
import sys
from hls.src.hls_handler.database import WebhookDatabase

async def queue_webhook():
    db = WebhookDatabase()
    payload = json.loads('$PAYLOAD')
    success = await db.queue_webhook(
        delivery_id='$DELIVERY_ID',
        event_type='$EVENT_TYPE',
        repository='$REPOSITORY',
        action='$ACTION',
        payload=payload,
        signature='$SIGNATURE'
    )
    if success:
        print('Webhook queued successfully')
    else:
        print('Webhook already processed (duplicate)')

asyncio.run(queue_webhook())
"

echo "Event queued: $EVENT_TYPE from $REPOSITORY"
```

Make it executable:
```bash
chmod +x /opt/hsl/bin/queue-webhook
```

#### Step 2.2: Configure Go Webhook
Create `/etc/webhook.conf`:
```json
[
  {
    "id": "github-webhook",
    "execute-command": "/opt/hsl/bin/queue-webhook",
    "command-working-directory": "/opt/hsl",
    "response-message": "Webhook received and queued",
    "response-headers": [
      {
        "name": "Content-Type",
        "value": "application/json"
      }
    ],
    "include-command-output-in-response": true,
    "include-command-output-in-response-on-error": true,
    "pass-arguments-to-command": [
      {
        "source": "header",
        "name": "X-GitHub-Event"
      },
      {
        "source": "header",
        "name": "X-GitHub-Delivery"
      },
      {
        "source": "header",
        "name": "X-Hub-Signature-256"
      }
    ],
    "pass-entire-payload-as-argument": true,
    "trigger-rule": {
      "and": [
        {
          "match": {
            "type": "payload-hmac-sha256",
            "secret": "your-webhook-secret-here",
            "parameter": {
              "source": "header",
              "name": "X-Hub-Signature-256"
            }
          }
        },
        {
          "match": {
            "type": "value",
            "value": "application/json",
            "parameter": {
              "source": "header",
              "name": "Content-Type"
            }
          }
        }
      ]
    }
  }
]
```

#### Step 2.3: Start Go Webhook Service
```bash
# Test Go webhook
webhook -hooks /etc/webhook.conf -verbose -port 9000

# Create systemd service
sudo tee /etc/systemd/system/go-webhook.service << EOF
[Unit]
Description=Go Webhook Server
After=network.target

[Service]
Type=simple
User=hsl
ExecStart=/usr/bin/webhook -hooks /etc/webhook.conf -port 9000 -ip 127.0.0.1
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable go-webhook
sudo systemctl start go-webhook
```

#### Step 2.4: Update Nginx Configuration
```nginx
# Add to nginx config
upstream hsl_webhook {
    server 127.0.0.1:9000;
}

upstream hsl_api {
    server 127.0.0.1:8000;
}

server {
    # ... existing SSL config ...
    
    # Route webhooks to Go service
    location /hooks/github {
        proxy_pass http://hsl_webhook/hooks/github-webhook;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        
        # Fast timeout for webhook reception
        proxy_connect_timeout 5s;
        proxy_send_timeout 10s;
        proxy_read_timeout 10s;
        
        client_max_body_size 10M;
    }
    
    # Route API calls to Python service
    location /api/ {
        proxy_pass http://hsl_api/;
        # ... existing API config ...
    }
}
```

#### Step 2.5: Test Go Webhook Integration
```bash
# Update GitHub webhook URL to point to new endpoint
# Old: https://your-domain.com/webhook
# New: https://your-domain.com/hooks/github

# Test the new endpoint
curl -X POST https://your-domain.com/hooks/github \
  -H "Content-Type: application/json" \
  -H "X-GitHub-Event: issues" \
  -H "X-GitHub-Delivery: test-456" \
  -H "X-Hub-Signature-256: sha256=..." \
  -d '{"action":"opened","issue":{"title":"Test via Go"}}'

# Verify webhook was queued
curl https://your-domain.com/api/queue/stats
```

### Phase 3: Production Deployment (Week 3)

#### Step 3.1: Create Production Services
```bash
# Create worker service template
sudo tee /etc/systemd/system/hsl-worker@.service << EOF
[Unit]
Description=HLS Worker %i
After=network.target

[Service]
Type=simple
User=hsl
WorkingDirectory=/opt/hsl
Environment=PATH=/opt/hsl/venv/bin
ExecStart=/opt/hsl/venv/bin/python -m hls.src.hls_handler.worker --worker-id=%i
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

# Start multiple workers
sudo systemctl daemon-reload
sudo systemctl enable hsl-worker@{1,2,3}
sudo systemctl start hsl-worker@{1,2,3}
```

#### Step 3.2: Monitoring and Alerting
Create `/opt/hsl/bin/monitor-queue`:
```bash
#!/bin/bash
# Monitor queue health and alert on issues

STATS=$(curl -s http://localhost:8000/api/queue/stats)
PENDING=$(echo "$STATS" | python3 -c "
import json, sys
data = json.load(sys.stdin)
print(data.get('total_pending', 0))
")

OVERDUE=$(echo "$STATS" | python3 -c "
import json, sys
data = json.load(sys.stdin)
print(data.get('overdue_webhooks', 0))
")

# Alert if too many pending or overdue webhooks
if [ "$PENDING" -gt 100 ]; then
    echo "ALERT: High queue backlog ($PENDING pending webhooks)"
    # Send notification (email, Slack, etc.)
fi

if [ "$OVERDUE" -gt 10 ]; then
    echo "ALERT: Overdue webhooks detected ($OVERDUE overdue)"
    # Send notification
fi
```

Add to crontab:
```bash
# Monitor every 5 minutes
*/5 * * * * /opt/hsl/bin/monitor-queue
```

### Phase 4: Cleanup and Optimization (Week 4)

#### Step 4.1: Remove Old FastAPI Webhook Handler
- Remove webhook endpoint from FastAPI
- Keep only management API endpoints
- Update documentation

#### Step 4.2: Database Optimization
```sql
-- Add additional indexes for performance
CREATE INDEX idx_webhook_delivery_id ON webhook_events(delivery_id);
CREATE INDEX idx_webhook_repo_status ON webhook_events(repository, status);
CREATE INDEX idx_processing_webhook_id ON processing_results(webhook_id);

-- Add cleanup procedure for old records
DELETE FROM webhook_events 
WHERE completed_at < date('now', '-30 days') 
AND status = 'completed';
```

#### Step 4.3: Performance Tuning
- Tune SQLite settings for concurrent access
- Optimize worker polling intervals
- Add connection pooling if needed

## Rollback Plan

### Emergency Rollback to v1
1. Update nginx to route webhooks back to FastAPI
2. Stop Go webhook service
3. Start old FastAPI background task processing
4. Update GitHub webhook URL

### Partial Rollback (Keep SQLite)
1. Modify FastAPI to process webhooks directly while also queueing
2. Stop workers temporarily
3. Process backlog manually if needed

## Testing Strategy

### Unit Tests
```python
# Test database operations
async def test_webhook_queuing():
    db = WebhookDatabase(":memory:")
    success = await db.queue_webhook(
        "test-123", "issues", "owner/repo", "opened", {}, "sig"
    )
    assert success

    # Test deduplication
    duplicate = await db.queue_webhook(
        "test-123", "issues", "owner/repo", "opened", {}, "sig"
    )
    assert not duplicate
```

### Integration Tests
```bash
# Test complete flow
./test-webhook-flow.sh
```

### Load Testing
```bash
# Use artillery to test Go webhook performance
artillery quick --count 1000 --num 50 https://your-domain.com/hooks/github
```

## Success Metrics

### Performance Improvements
- [ ] Webhook response time < 10ms (vs 100-5000ms)
- [ ] Zero lost webhooks during restarts
- [ ] 100% deduplication effectiveness
- [ ] Worker horizontal scaling validated

### Reliability Improvements
- [ ] Automatic retry mechanism functional
- [ ] Queue monitoring and alerting working
- [ ] Database backup and recovery tested
- [ ] Graceful degradation under load

### Operational Improvements
- [ ] Easy worker scaling (add/remove workers)
- [ ] Clear queue visibility and management
- [ ] Cost tracking and budgeting
- [ ] Comprehensive monitoring dashboard

This migration guide provides a safe, incremental path to significantly improved reliability while maintaining all existing functionality.