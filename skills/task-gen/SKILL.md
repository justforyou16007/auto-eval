---
name: task-gen
description: Generate eval tasks for Agent verification. Reads query_pack.md for context (existing tasks, gaps, failed tasks banlist), generates new tasks based on difficulty/cost parameters, and writes them to eval-wiki.
argument-hint: "[difficulty: lite|easy|medium|hard|beast] [cost: float]"
allowed-tools: Bash(*), Read, Write, Edit, Grep, Glob
---

# task-gen Skill

## Overview
This skill generates evaluation tasks for the Agent Verification Pipeline.
It is one of five stages (task-gen, env-gen, rubric-gen, report-gen, feedback-align).

## Workflow

1. **Read context** — Read `eval-wiki/query_pack.md` for compressed context:
   - Existing tasks grouped by scenario type
   - Coverage gaps from `gap_map.md`
   - Failed tasks banlist (tasks that previously failed verification)
   - Active feedback and coverage statistics

2. **Analyze gaps and coverage** — Identify which scenario types, difficulty levels, and behavioral areas are under-represented in the existing task set.

3. **Generate new tasks** — Generate 1–5 new tasks per invocation based on the `difficulty` and `cost` parameters. Each task is generated from predefined templates appropriate to the difficulty level:
   - **lite**: Simple single-turn tasks (greeting, factual QA)
   - **easy**: Single-turn tasks with tool use (search, calculator)
   - **medium**: Multi-turn tasks with tool chains (search+calc, tool error recovery)
   - **hard**: Multi-turn tasks with error injection and adversarial scenarios
   - **beast**: Long-context, multi-tool, error-injected, adversarial combined

4. **Deduplicate** — Query existing tasks via `eval-wiki.py query` to ensure no duplicate titles or overlapping scenarios.

5. **Write each task** — Use `python3 eval-wiki.py add-task ...` to persist each generated task.

6. **Log generation** — Append a summary log entry via `eval-wiki.py log`.

## Usage

```bash
python3 skills/task-gen/generate.py \
  --wiki-root /path/to/eval-wiki \
  --difficulty easy \
  --cost 0.5 \
  --count 3
```

## Parameters

| Parameter       | Type  | Default | Description                          |
|-----------------|-------|---------|--------------------------------------|
| `--wiki-root`   | path  | required | Path to eval-wiki directory          |
| `--difficulty`  | str   | easy    | lite, easy, medium, hard, beast      |
| `--cost`        | float | 0.5     | Cost budget for each task            |
| `--count`       | int   | 3       | Number of tasks to generate (1-5)    |
| `--scenario-type` | str | (all) | Optional filter on scenario type    |