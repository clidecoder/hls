# HLS v2 Architecture - Go Webhook + SQLite Design

## Overview

This document outlines an improved architecture using the installed Go webhook library combined with SQLite for persistent queuing, addressing the core reliability issues identified in the current Python-only solution.

## Architecture Comparison

### Current Architecture (v1)
```
GitHub → nginx → FastAPI → Background Tasks → Claude → GitHub
```
**Issues**: Lost tasks on restart, no deduplication, single-instance bottleneck

### Proposed Architecture (v2)
```
GitHub → nginx → Go webhook → SQLite Queue → Python Workers → Claude → GitHub
```
**Benefits**: Persistent queue, fast webhook reception, horizontal scaling, reliable processing

## Component Breakdown

### 1. **Go Webhook Receiver** (`webhook` tool)
- **Purpose**: Ultra-fast webhook reception and queuing
- **Responsibilities**:
  - Validate GitHub webhook signatures
  - Queue events to SQLite database
  - Return immediate 200 OK to GitHub
  - Log webhook reception

### 2. **SQLite Database** (Persistent Queue)
- **Purpose**: Reliable event storage and deduplication
- **Tables**:
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
      status TEXT DEFAULT 'pending',
      retry_count INTEGER DEFAULT 0,
      priority INTEGER DEFAULT 5,
      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
      scheduled_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
      started_at TIMESTAMP,
      completed_at TIMESTAMP,
      error_message TEXT
  );
  
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
  
  -- Statistics and monitoring
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

### 3. **Python Worker Processes**
- **Purpose**: Process queued events using existing Python logic
- **Features**:
  - Poll SQLite for pending events
  - Use existing handlers, clients, and prompt system
  - Implement retry logic with exponential backoff
  - Update processing status and results

### 4. **Management Interface** (FastAPI)
- **Purpose**: Monitoring, configuration, and manual intervention
- **Endpoints**:
  - `GET /stats` - Processing statistics
  - `GET /queue` - Queue status and pending events
  - `POST /retry/{webhook_id}` - Manual retry
  - `GET /config/{repository}` - Repository configuration
  - `PUT /config/{repository}` - Update repository configuration

## Data Flow

### 1. Webhook Reception (Go)
```bash
# Go webhook receives request
curl -X POST https://your-domain.com/hooks/github \
  -H "X-GitHub-Event: issues" \
  -H "X-Hub-Signature-256: sha256=..." \
  -d '{"action":"opened","issue":{...}}'

# Go webhook executes queue script
/opt/hsl/bin/queue-webhook issues delivery-123 '{"action":"opened",...}'
```

### 2. Event Queuing (SQLite)
```python
# queue-webhook script
import sqlite3
import json
import sys

def queue_webhook(event_type, delivery_id, payload):
    conn = sqlite3.connect('/opt/hsl/data/webhooks.db')
    conn.execute("""
        INSERT OR IGNORE INTO webhook_events 
        (delivery_id, event_type, repository, action, payload_json, signature)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (delivery_id, event_type, repo, action, payload, signature))
    conn.commit()
```

### 3. Background Processing (Python Workers)
```python
# worker.py
async def process_queue():
    while True:
        # Get next pending webhook
        webhook = get_next_webhook()
        if not webhook:
            await asyncio.sleep(5)
            continue
            
        try:
            # Mark as processing
            update_webhook_status(webhook.id, 'processing')
            
            # Use existing processing logic
            result = await webhook_processor.process_webhook(
                webhook.event_type, 
                json.loads(webhook.payload_json),
                webhook.delivery_id
            )
            
            # Save results
            save_processing_result(webhook.id, result)
            update_webhook_status(webhook.id, 'completed')
            
        except Exception as e:
            handle_processing_error(webhook.id, e)
```

## Configuration Files

### Go Webhook Configuration (`/etc/webhook.conf`)
```json
[
  {
    "id": "github-webhook",
    "execute-command": "/opt/hsl/bin/queue-webhook",
    "command-working-directory": "/opt/hsl",
    "response-message": "Webhook queued successfully",
    "include-command-output-in-response": false,
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
            "secret": "your-webhook-secret",
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

### Systemd Service for Workers (`/etc/systemd/system/hsl-worker@.service`)
```ini
[Unit]
Description=HLS Worker %i
After=network.target

[Service]
Type=simple
User=hsl
WorkingDirectory=/opt/hsl
Environment=PATH=/opt/hsl/venv/bin
ExecStart=/opt/hsl/venv/bin/python -m hsl.worker --worker-id=%i
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

## Key Improvements Over Current Architecture

### 1. **Reliability**
- ✅ **Persistent queue** - No lost webhooks on restart
- ✅ **Deduplication** - SQLite UNIQUE constraints prevent duplicate processing
- ✅ **Retry mechanism** - Built-in exponential backoff with retry limits
- ✅ **Audit trail** - Complete processing history and error tracking

### 2. **Performance**
- ✅ **Fast webhook response** - Go returns 200 OK in microseconds
- ✅ **Asynchronous processing** - Workers process independently
- ✅ **Horizontal scaling** - Multiple worker processes
- ✅ **Resource isolation** - Webhook reception separate from processing

### 3. **Observability**
- ✅ **Queue visibility** - See pending, processing, failed events
- ✅ **Cost tracking** - Track Claude API usage and costs
- ✅ **Processing metrics** - Detailed timing and success rates
- ✅ **Error analysis** - Failed event analysis and debugging

### 4. **Operational Excellence**
- ✅ **Simple deployment** - Single SQLite file
- ✅ **Manual intervention** - Retry failed events, adjust priorities
- ✅ **Configuration management** - Runtime config updates
- ✅ **Resource management** - Worker scaling based on queue size

## Migration Path

### Phase 1: Add SQLite Layer (1-2 weeks)
1. Create SQLite schema and helper functions
2. Modify current FastAPI to queue to SQLite instead of background tasks
3. Add worker process that reads from SQLite
4. Test with existing functionality

### Phase 2: Add Go Webhook (1 week)
1. Configure Go webhook with queue script
2. Switch traffic from FastAPI to Go webhook
3. Remove webhook handling from FastAPI (keep management interface)
4. Performance testing and optimization

### Phase 3: Enhance and Scale (2-3 weeks)
1. Add multiple worker processes
2. Implement retry logic and error handling
3. Add monitoring and alerting
4. Cost tracking and budgeting features

## Deployment Architecture

### Production Setup
```
Internet → nginx → Go webhook (port 9000) → SQLite
                ↓
         Management API (port 8000) ← Worker 1 ← SQLite
                                   ← Worker 2 ← SQLite
                                   ← Worker N ← SQLite
```

### Nginx Configuration Update
```nginx
# Webhook traffic to Go
location /hooks/ {
    proxy_pass http://127.0.0.1:9000;
    proxy_read_timeout 10s;  # Go responds immediately
}

# Management API to Python
location /api/ {
    proxy_pass http://127.0.0.1:8000;
    proxy_read_timeout 60s;
}
```

## Benefits Summary

| Aspect | Current (v1) | Proposed (v2) | Improvement |
|--------|-------------|---------------|-------------|
| **Webhook Response** | ~100-5000ms | ~1-5ms | 100-1000x faster |
| **Reliability** | Lost on restart | Persistent | 100% reliable |
| **Deduplication** | None | SQLite UNIQUE | Built-in |
| **Retry Logic** | None | Exponential backoff | Full retry support |
| **Scaling** | Single instance | Multiple workers | Horizontal scaling |
| **Cost Tracking** | Basic stats | Full tracking | Complete visibility |
| **Observability** | Limited | Comprehensive | Full monitoring |

## Cost Analysis

### Development Cost
- **SQLite integration**: 3-5 days
- **Go webhook setup**: 1-2 days  
- **Worker refactoring**: 3-5 days
- **Testing & deployment**: 2-3 days
- **Total**: 2-3 weeks

### Operational Benefits
- **Reduced Claude API costs** through smart deduplication
- **Improved GitHub webhook reliability** (no retries/failures)
- **Lower infrastructure costs** (more efficient resource usage)
- **Reduced operational overhead** (self-healing with retries)

This architecture addresses all the major reliability concerns while leveraging existing tools and maintaining the current Python processing logic.