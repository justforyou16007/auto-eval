---
name: rubric-gen
description: Generate scoring rubrics for a task
argument-hint: [task-id] [assurance: draft|submission]
allowed-tools: Bash(*), Read, Write, Edit
---

# rubric-gen

Generates scoring rubrics for a task. ACQUIT role — criteria designed for
cross-model evaluation. Generates both rubric metadata AND evaluator script
skeletons.

## Workflow

1. Read task file to get expected_behavior and scenario_type
2. Generate rubric criteria based on task type
3. For each script evaluator: generate a Python skeleton script
4. Write rubric to eval-wiki via `eval-wiki.py add-rubric`
5. Generate a criteria.json file for the add-rubric command