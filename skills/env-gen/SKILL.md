---
name: env-gen
description: Generate Docker environment for a task and provision the container
argument-hint: [task-id] [image: python:3.11]
allowed-tools: Bash(*), Read, Write, Edit
---

# env-gen

Generates a Docker environment for a task. Reads task constraints from
eval-wiki, creates docker config, provisions real container, runs health check.

## Workflow

1. Read task constraints from eval-wiki (max_turns, allowed_tools, scenario_type)
2. Generate docker-compose.yml and environment markdown
3. Write environment to eval-wiki via `eval-wiki.py add-env`
4. If not --dry-run: start Docker container, poll health check, log result