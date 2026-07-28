---
name: feedback-align
description: Process user feedback to align task/rubric/env/report with user expectations
argument-hint: [target-type: task|rubric|env|run] [target-id] [feedback-text]
allowed-tools: Bash(*), Read, Write, Edit
---

# feedback-align

Processes user feedback to align task/rubric/env/report with user expectations.
Analyzes feedback type, proposes changes, applies verified changes.

## Workflow

1. Record feedback via `eval-wiki.py add-feedback`
2. If --apply: modify the target entity file directly (update specified field)
3. Mark feedback status as "applied" if changes were applied
4. Print summary of what was recorded and/or applied