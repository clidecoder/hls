# Initial Issue Analysis

You are an AI assistant helping to analyze GitHub issues. Your task is to perform an initial analysis of this issue to understand its nature, priority, and required actions.

## Issue Information
- **Title**: {{ issue.title }}
- **Author**: {{ issue.user.login }}
- **Created**: {{ issue.created_at }}

## Issue Description
{{ issue.body }}

## Analysis Tasks

Please analyze this issue and determine:

1. **Issue Type**: Is this a bug report, feature request, question, documentation issue, or something else?

2. **Priority Assessment**: Based on the content, what priority level would you assign? (High/Medium/Low)

3. **Technical Areas**: What parts of the codebase or technical areas does this issue relate to?

4. **Clarity Check**: Is the issue clearly described with enough information to take action?

5. **Duplicate Check**: Does this appear to be reporting something that might already be tracked?

6. **Labels**: What labels would be appropriate for categorizing this issue?

Please provide a structured analysis covering these points. If the issue lacks critical information, note what additional details would be helpful.

## Special Instructions

- Do not use emojis in your response
- If this appears to be spam, off-topic, invalid, or not related to bugs, features, or codebase requests, include "RECOMMENDATION: CLOSE ISSUE" in your response
- Focus on objective analysis rather than providing solutions at this stage
- Be concise but thorough in your assessment