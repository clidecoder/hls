# Chained Prompts Guide

This guide explains how to use chained prompts in the HLS webhook handler to create more sophisticated AI-powered analysis workflows.

## Overview

Chained prompts allow you to break down complex analysis tasks into multiple steps, where each step:
- Has its own focused prompt
- Can extract structured data
- Passes context to subsequent steps
- Maintains conversation history

## Benefits

1. **Better Analysis**: Complex tasks are broken into manageable steps
2. **Context Preservation**: Each step builds on previous analysis
3. **Data Extraction**: Extract structured data between steps
4. **Flexibility**: Easy to add, remove, or modify steps

## How It Works

```
Step 1: Initial Analysis → Extract Data → Step 2: Generate Response → Final Output
         ↓                      ↓                    ↓
    Understand Issue      Labels, Priority    Contextual Response
```

## Implementation

### 1. Enable Chained Handlers

Edit `hls/src/hsl_handler/handlers.py`:

```python
from .chained_issue_handler import ChainedIssueHandler

# Replace standard handler with chained version
HANDLERS["issues"] = ChainedIssueHandler
```

### 2. Create Prompt Templates

Create separate prompt files for each step:

**prompts/issues/analyze.md** (Step 1):
```markdown
# Initial Issue Analysis

Analyze this issue and determine:
1. Issue Type (bug/feature/question)
2. Priority Level
3. Required Labels
4. Next Steps
```

**prompts/issues/respond.md** (Step 2):
```markdown
# Generate Issue Response

Based on your analysis:
- Priority: {{ initial_analysis_data.priority }}
- Type: {{ initial_analysis_data.category }}

Generate an appropriate response...
```

### 3. Define Chain Steps

In your handler, define the chain:

```python
def get_chain_steps(self, payload, action):
    return [
        ChainStep(
            name="initial_analysis",
            prompt_key="issues.analyze",
            extract_func="extract_analysis_data"
        ),
        ChainStep(
            name="generate_response",
            prompt_key="issues.respond"
        )
    ]
```

### 4. Extract Data Between Steps

Implement extraction functions:

```python
def extract_analysis_data(self, response):
    return {
        "labels": ["bug", "high-priority"],
        "priority": "high",
        "needs_more_info": False
    }
```

## Example Workflow

1. **Issue Created**: New issue webhook received
2. **Step 1 - Analysis**: 
   - Claude analyzes the issue
   - Extracts labels, priority, category
3. **Step 2 - Response**:
   - Uses analysis data
   - Generates contextual response
4. **Post-Processing**:
   - Applies extracted labels
   - Posts combined response

## Advanced Features

### Conditional Steps

```python
ChainStep(
    name="request_info",
    prompt_key="issues.request_info",
    condition_func="needs_more_info"
)
```

### Parallel Processing

```python
def get_chain_type(self):
    return ChainType.PARALLEL  # Run steps independently
```

### Custom Response Formatting

```python
def format_final_response(self, results):
    # Combine results from all steps
    return custom_format(results)
```

## Configuration

Update `config/settings.yaml`:

```yaml
prompts:
  templates:
    issues:
      analyze: "issues/analyze.md"
      respond: "issues/respond.md"
      request_info: "issues/request_info.md"
```

## Testing

Run the example script:

```bash
python examples/enable_chained_prompts.py
```

## Best Practices

1. **Keep Steps Focused**: Each step should have a single purpose
2. **Extract Key Data**: Pull out structured data for use in later steps
3. **Maintain Context**: Pass relevant context between steps
4. **Handle Errors**: Each step should handle potential failures
5. **Log Progress**: Use logging to track chain execution

## Troubleshooting

- **Step Not Found**: Check prompt_key matches configuration
- **Extraction Failed**: Verify extraction function exists
- **Context Missing**: Ensure data is passed between steps
- **Rate Limits**: Add delays between steps if needed

## Future Enhancements

- Branching logic based on conditions
- Retry logic for failed steps
- Caching of intermediate results
- Web UI for chain visualization