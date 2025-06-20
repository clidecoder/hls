# HLS Integration with Existing Webhook System

## Current Setup Analysis

You already have a **production-ready webhook infrastructure**:

```
GitHub → nginx (clidecoder.com) → Go webhook (port 9000) → handler script → logs
```

**Existing Components:**
- ✅ **Go webhook** (v2.8.0) with HMAC validation  
- ✅ **Nginx routing** with SSL and proper headers
- ✅ **Handler script** that parses and logs events
- ✅ **JSON configuration** for webhook rules

## Integration Strategy: Hook Line Sinker

Instead of replacing your working system, **enhance it** with Claude intelligence:

### Architecture: Existing + HLS
```
GitHub → nginx → Go webhook → Enhanced handler → SQLite Queue → HLS Workers → Claude → GitHub
                                      ↓
                              (Keep existing logging)
```

## Phase 1: Add HLS Queue Integration (1 week)

### Step 1: Create HLS Queue Script
Create `/home/clide/hls/bin/queue-hls-event`:

```bash
#!/bin/bash
# HLS Event Queue Script
# Called from existing webhook handler to queue events for Claude processing

set -e

REPO_NAME="$1"
EVENT_TYPE="$2"
ACTION="$3"
PAYLOAD="$4"
DELIVERY_ID="${GITHUB_DELIVERY:-$(date +%s)-$$}"

# Only process events that HLS handles
case "$EVENT_TYPE" in
    "issues"|"pull_request"|"pull_request_review"|"workflow_run")
        # Extract signature from environment or generate one
        SIGNATURE="${X_HUB_SIGNATURE_256:-sha256=existing-system}"
        
        # Queue for HLS processing
        cd /home/clide/hls
        python3 -c "
import asyncio
import json
import sys
import os
sys.path.insert(0, 'hls/src')
from hls_handler.database import WebhookDatabase

async def queue_webhook():
    db = WebhookDatabase('/home/clide/hls/data/webhooks.db')
    payload = json.loads('$PAYLOAD')
    success = await db.queue_webhook(
        delivery_id='$DELIVERY_ID',
        event_type='$EVENT_TYPE',
        repository='$REPO_NAME',
        action='$ACTION',
        payload=payload,
        signature='$SIGNATURE'
    )
    if success:
        print('HLS: Event queued for Claude processing')
    else:
        print('HLS: Event already processed (duplicate)')

try:
    asyncio.run(queue_webhook())
except Exception as e:
    print(f'HLS: Queue error: {e}')
"
        ;;
    *)
        echo "HLS: Event type '$EVENT_TYPE' not handled by Claude system"
        ;;
esac
```

### Step 2: Enhance Existing Handler
Modify `/home/clide/promptforge/webhook-config/handle-github-event.sh` to add HLS integration:

```bash
# Add after line 90 (before the exit):

# === NEW: HLS Integration ===
# Queue supported events for Claude processing
echo ""
echo "=== HLS Claude Processing ==="
if [[ "$EVENT_TYPE" =~ ^(issues|pull_request|pull_request_review|workflow_run)$ ]]; then
    log_event "Queuing for HLS Claude processing..."
    
    # Set environment variables for HLS script
    export GITHUB_DELIVERY="${GITHUB_DELIVERY:-$(date +%s)-$$}"
    export X_HUB_SIGNATURE_256="${X_HUB_SIGNATURE_256:-sha256=existing-system}"
    
    # Queue for HLS processing (async)
    /home/clide/hls/bin/queue-hls-event "$REPO_NAME" "$EVENT_TYPE" "$ACTION" "$PAYLOAD" &
    HLS_PID=$!
    
    log_event "HLS processing queued (PID: $HLS_PID)"
else
    log_event "Event type '$EVENT_TYPE' not supported by HLS Claude system"
fi
echo "=========================="

log_event "Event processing completed"
exit 0
```

### Step 3: Setup SQLite Database
```bash
# Create HLS data directory
mkdir -p /home/clide/hls/data
mkdir -p /home/clide/hls/bin

# Create SQLite database
cd /home/clide/hls
sqlite3 data/webhooks.db < schema.sql
```

Create `/home/clide/hls/schema.sql`:
```sql
-- Main webhook queue for HLS processing
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

-- Processing results with Claude integration
CREATE TABLE claude_analyses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    webhook_id INTEGER NOT NULL,
    event_type TEXT NOT NULL,
    repository TEXT NOT NULL,
    claude_prompt TEXT,
    claude_response TEXT,
    claude_tokens_used INTEGER,
    claude_cost_usd REAL,
    github_actions_json TEXT,
    processing_time_ms INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (webhook_id) REFERENCES webhook_events(id)
);

-- Daily statistics
CREATE TABLE daily_stats (
    date TEXT PRIMARY KEY,
    total_webhooks INTEGER DEFAULT 0,
    claude_analyses INTEGER DEFAULT 0,
    github_actions INTEGER DEFAULT 0,
    total_cost_usd REAL DEFAULT 0.0
);
```

### Step 4: Make Scripts Executable
```bash
chmod +x /home/clide/hls/bin/queue-hls-event
```

## Phase 2: Deploy HLS Workers (1 week)

### Step 1: Configure HLS
Create `/home/clide/hls/config/settings.yaml`:
```yaml
server:
  host: "127.0.0.1"
  port: 8001  # Different from existing system
  webhook_path: "/hls-api"

github:
  token: "${GITHUB_TOKEN}"
  webhook_secret: "existing-system-integration"

claude:
  api_key: "${ANTHROPIC_API_KEY}"
  model: "claude-3-5-sonnet-20241022"
  max_tokens: 4000

repositories:
  - name: "your-repo-here"
    enabled: true
    events: ["issues", "pull_request", "pull_request_review", "workflow_run"]
    labels:
      auto_apply: true
    comments:
      auto_post: true

features:
  signature_validation: false  # We trust the existing system
  async_processing: true
  auto_labeling: true

database:
  path: "/home/clide/hls/data/webhooks.db"

logging:
  level: "INFO"
  file: "/home/clide/hls/logs/hls.log"
```

### Step 2: Start HLS Workers
```bash
# Create systemd service for HLS workers
sudo tee /etc/systemd/system/hls-worker@.service << EOF
[Unit]
Description=HLS Claude Worker %i
After=network.target

[Service]
Type=simple
User=clide
WorkingDirectory=/home/clide/hls
Environment=PATH=/home/clide/hls/venv/bin
ExecStart=/home/clide/hls/venv/bin/python -m hls.src.hls_handler.worker --worker-id=%i
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Start workers
sudo systemctl daemon-reload
sudo systemctl enable hls-worker@{1,2}
sudo systemctl start hls-worker@{1,2}
```

### Step 3: Add HLS Management API
```bash
# Create systemd service for HLS API
sudo tee /etc/systemd/system/hls-api.service << EOF
[Unit]
Description=HLS Management API
After=network.target

[Service]
Type=simple
User=clide
WorkingDirectory=/home/clide/hls
Environment=PATH=/home/clide/hls/venv/bin
ExecStart=/home/clide/hls/venv/bin/python -m hls.src.hls_handler.main
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl enable hls-api
sudo systemctl start hls-api
```

### Step 4: Update Nginx for HLS API
Add to `/etc/nginx/sites-enabled/clidecoder.com`:

```nginx
# Add after existing /hooks location
location /hls {
    proxy_pass http://localhost:8001;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    
    # For HLS management interface
    proxy_read_timeout 60s;
}
```

## Phase 3: Monitoring and Optimization (1 week)

### Step 1: Create Monitoring Script
Create `/home/clide/hls/bin/monitor-hls`:
```bash
#!/bin/bash
# Monitor HLS queue and processing

# Check queue status
STATS=$(curl -s http://localhost:8001/stats 2>/dev/null || echo '{"error":"API unavailable"}')

echo "=== HLS Status $(date) ==="
echo "$STATS" | python3 -c "
import json, sys
try:
    data = json.load(sys.stdin)
    if 'error' in data:
        print(f'❌ HLS API Error: {data[\"error\"]}')
    else:
        print(f'✅ Queue Status: {data.get(\"total_pending\", 0)} pending')
        print(f'📊 Success Rate: {data.get(\"success_rate\", 0):.1%}')
        print(f'⏱️  Avg Processing: {data.get(\"average_processing_time\", 0):.1f}s')
except:
    print('❌ Failed to parse HLS stats')
"

# Check worker status
echo ""
echo "=== Worker Status ==="
systemctl is-active hls-worker@1 hls-worker@2 hls-api | while read status; do
    if [ "$status" = "active" ]; then
        echo "✅ Worker active"
    else
        echo "❌ Worker inactive: $status"
    fi
done

echo "======================"
```

### Step 2: Add to Crontab
```bash
# Monitor every 15 minutes
*/15 * * * * /home/clide/hls/bin/monitor-hls >> /home/clide/hls/logs/monitor.log 2>&1
```

## Benefits of This Integration

### ✅ **Zero Disruption**
- Keep existing webhook system working perfectly
- Add Claude intelligence as enhancement
- Gradual rollout with easy rollback

### ✅ **Best of Both Worlds**
- **Existing system**: Proven reliability, fast logging, all events
- **HLS system**: Claude intelligence, automatic labeling, smart responses

### ✅ **Operational Excellence**
- **Dual logging**: Events logged in both systems
- **Selective processing**: Only relevant events go to Claude
- **Cost control**: Claude only processes what matters

### ✅ **Easy Management**
- **Existing monitoring**: Keep current webhook monitoring
- **HLS monitoring**: New endpoints for Claude-specific metrics
- **Independent scaling**: Scale workers based on Claude processing needs

## Testing the Integration

### Test Event Flow
```bash
# 1. Trigger a test webhook (issues event)
curl -X POST https://clidecoder.com/hooks/github-webhook \
  -H "Content-Type: application/json" \
  -H "X-GitHub-Event: issues" \
  -H "X-GitHub-Delivery: test-integration" \
  -d '{"action":"opened","issue":{"title":"Test HLS Integration"}}'

# 2. Check existing system logs
tail -f /home/clide/promptforge/webhook-config/logs/github-events-$(date +%Y%m%d).log

# 3. Check HLS queue
curl https://clidecoder.com/hls/stats

# 4. Check HLS processing logs
tail -f /home/clide/hls/logs/hls.log
```

## Migration Timeline

### Week 1: Foundation
- ✅ Install SQLite database
- ✅ Create queue integration script  
- ✅ Enhance existing handler
- ✅ Test with sample events

### Week 2: Workers
- ✅ Deploy HLS worker processes
- ✅ Configure repository settings
- ✅ Start Claude processing
- ✅ Monitor and tune

### Week 3: Production
- ✅ Full monitoring setup
- ✅ Error handling and alerting  
- ✅ Performance optimization
- ✅ Documentation and training

This approach gives you **production-ready Claude integration** while keeping your **proven webhook infrastructure** intact. It's the perfect "Hook Line Sinker" - catching all events, connecting them reliably, and processing the important ones deeply with AI! 🎣