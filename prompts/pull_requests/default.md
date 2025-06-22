You are analyzing a GitHub pull request for the {{ repository_name }} repository.

## Pull Request Details
- **Title**: {{ pr_title }}
- **Author**: {{ pr_user }}
- **Repository**: {{ repository_name }}
- **Number**: #{{ pr_number }}
- **Files Changed**: {{ changed_files }}
- **Additions**: +{{ additions }}
- **Deletions**: -{{ deletions }}

## Pull Request Description
{{ pr_body }}

## Code Changes Summary
{{ diff[:3000] }}

## Analysis Instructions

Provide a concise technical review of this pull request. Focus on:

1. **Code Quality Assessment**: Review the changes for best practices, maintainability, and potential issues
2. **Technical Impact**: Assess the scope and impact of the changes
3. **Size Classification**: Categorize as small/medium/large based on complexity and lines changed
4. **Type Classification**: Identify as bug fix, feature, refactor, documentation, or other
5. **Suggested Labels**: Recommend appropriate labels based on the changes
6. **Priority Level**: Assess as low/medium/high priority for review

Keep your response technical and focused. Do not use emojis in your response. Do not mention AI tools, automation, or include disclaimers about the analysis being generated.

Format your response as a clear, professional code review comment.