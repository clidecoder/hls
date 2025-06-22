# Generate Issue Response

Based on your analysis, now generate an appropriate response to post on the issue. You should craft a helpful, welcoming message that addresses the issue appropriately.

## Previous Analysis Summary
{% if initial_analysis_data %}
- **Issue Type**: {{ initial_analysis_data.category }}
- **Priority**: {{ initial_analysis_data.priority }}
- **Needs More Info**: {{ initial_analysis_data.needs_more_info }}
- **Is Duplicate**: {{ initial_analysis_data.is_duplicate }}
{% endif %}

## Response Guidelines

Based on the analysis, create a response that:

1. **Acknowledges** the issue reporter and thanks them for their contribution

2. **Summarizes** your understanding of the issue

3. **Provides guidance** on next steps:
   - If it's a bug: Acknowledge it and mention it will be investigated
   - If it's a feature request: Comment on its merit and feasibility
   - If it needs more info: Politely ask for specific missing details
   - If it's a duplicate: Kindly point to the existing issue

4. **Sets expectations** about response time or priority

5. **Offers help** or points to relevant documentation if applicable

## Tone Requirements

- Be friendly and professional
- Show appreciation for the contribution
- Be constructive even if the issue needs work
- Avoid technical jargon when possible
- Keep the response concise but helpful
- Do not use emojis in your response
- Do not include disclaimers about being AI-generated
- Do not include timestamps or metadata
- Get straight to the point without unnecessary preamble

## Example Structure

Start with a greeting and acknowledgment, provide your assessment, suggest next steps, and close with an invitation for further discussion if needed.