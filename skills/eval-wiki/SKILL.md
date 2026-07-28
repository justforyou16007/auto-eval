---
name: eval-wiki
description: 'Persistent eval knowledge base for Agent verification. Accumulates tasks, environments, rubrics, runs, and feedback across the eval lifecycle. Use when user says "eval wiki", "add task", "query tasks", "查知识库", or wants to build/query a persistent eval knowledge base.'
argument-hint: '[subcommand: init|add-task|add-env|add-rubric|add-run|add-feedback|add-edge|rebuild-index|rebuild-query-pack|query|log|stats]'
allowed-tools: Bash(*), Read, Write, Edit, Grep, Glob
role: TOOL
---

# eval-wiki Skill

## Overview

A persistent per-project knowledge base for Agent verification. The eval-wiki
accumulates structured data across the eval lifecycle: tasks, environments,
rubrics, runs, and feedback. All data is stored as flat Markdown files with
YAML frontmatter in a git-tracked directory.

## Entity Types

| Entity | Directory | Description |
|--------|-----------|-------------|
| **Task** | `tasks/` | Evaluation task specification (title, difficulty, scenario type, tools, expected behavior) |
| **Environment** | `environments/` | Docker container configuration (image, network, resource limits, health check) |
| **Rubric** | `rubrics/` | Scoring criteria and evaluator scripts (criteria, weights, evaluator type) |
| **Run** | `runs/` | Agent execution result (model, verdict, scores, confidence, evidence) |
| **Feedback** | `feedback/` | User or auto-audit feedback (issue type, target, proposed change, status) |

## Edge Types

| Edge Type | Direction | Purpose |
|-----------|-----------|---------|
| `depends_on` | Task → Task | Task dependency |
| `tested_by` | Task → Run | Run tests a task |
| `scored_by` | Run → Rubric | Run is scored by a rubric |
| `supports` | Run → Feedback | Run supports a feedback |
| `invalidates` | Run → Task | Run invalidates a task |
| `covers_gap` | Task → Task | Task covers a gap |
| `addresses` | Feedback → Task/Rubric/Env | Feedback addresses an entity |
| `supersedes` | Task → Task | Task supersedes another |
| `extends` | Task → Task | Task extends another |

## Directory Structure

```
eval-wiki/
├── tasks/            # Task files (*.md)
├── environments/     # Environment files (*.md)
├── rubrics/          # Rubric files (*.md)
├── runs/             # Run files (*.md)
├── feedback/         # Feedback files (*.md)
├── index.md          # Entity index (auto-generated)
├── query_pack.md     # Compressed context for generation (auto-generated)
├── gap_map.md        # Coverage gap analysis (auto-generated)
└── eval.db           # SQLite query cache (auto-generated)
```

## Helper Resolution Chain

Since eval-wiki IS the wiki tool itself, the helper resolution uses
**Variant A (hard-fail)** — the script must be found.

```bash
# Resolve $EVAL_WIKI_SCRIPT — the canonical path to eval-wiki.py
# Variant A: hard-fail (this IS the eval-wiki skill)

cd "$(git rev-parse --show-toplevel 2>/dev/null || pwd)" || exit 1

# 1. Check for installed copy in .eval
EVAL_REPO="${EVAL_REPO:-$(awk -F'\t' '$1=="repo_root"{print $2; exit}' .eval/installed-skills.txt 2>/dev/null)}"
EVAL_WIKI_SCRIPT=".eval/dist/tools/eval-wiki.py"

# 2. Fall back to canonical dist path
[ -f "$EVAL_WIKI_SCRIPT" ] || EVAL_WIKI_SCRIPT="dist/tools/eval-wiki.py"

# 3. Fall back to EVAL_REPO
[ -f "$EVAL_WIKI_SCRIPT" ] || { [ -n "${EVAL_REPO:-}" ] && EVAL_WIKI_SCRIPT="$EVAL_REPO/dist/tools/eval-wiki.py"; }

# 4. Hard fail — this IS the eval-wiki skill
if [ ! -f "$EVAL_WIKI_SCRIPT" ]; then
    echo "ERROR: eval-wiki.py not found. Run 'tools/install_eval_wiki.sh' first." >&2
    exit 1
fi
```

## Subcommand Reference

### `init`
Initialize a new eval-wiki directory.

```bash
python3 "$EVAL_WIKI_SCRIPT" init <wiki-root>
```

### `add-task`
Add a task entity.

```bash
python3 "$EVAL_WIKI_SCRIPT" add-task <wiki-root> \
  --title "<title>" \
  --difficulty <lite|easy|medium|hard|beast> \
  --scenario-type <single-turn|multi-turn|tool-chain|error-recovery> \
  --max-turns <N> \
  --allowed-tools "<tool1,tool2>" \
  --expected-behavior "<description>" \
  [--cost <float>] \
  [--status <status>] \
  [--update]
```

### `add-env`
Add an environment entity.

```bash
python3 "$EVAL_WIKI_SCRIPT" add-env <wiki-root> \
  --task-id <slug> \
  --image <docker-image> \
  --network <network> \
  --memory <memory> \
  --cpus <cpus> \
  --agent-endpoint <endpoint> \
  [--health-check <command>] \
  [--status <status>] \
  [--update]
```

### `add-rubric`
Add a rubric entity.

```bash
python3 "$EVAL_WIKI_SCRIPT" add-rubric <wiki-root> \
  --task-id <slug> \
  --criteria-json <path> \
  [--status <status>] \
  [--update]
```

### `add-run`
Add a run entity.

```bash
python3 "$EVAL_WIKI_SCRIPT" add-run <wiki-root> \
  --task-id <slug> \
  --env-id <slug> \
  --rubric-id <slug> \
  --model <model-name> \
  --verdict <yes|no|inconclusive> \
  --confidence <high|medium|low> \
  --scores-json <path> \
  [--evidence <path>] \
  [--status <status>]
```

### `add-feedback`
Add a feedback entity.

```bash
python3 "$EVAL_WIKI_SCRIPT" add-feedback <wiki-root> \
  --target-type <task|rubric|env|run> \
  --target-id <slug> \
  --from <user|auto-audit> \
  --issue-type <misalignment|missing_case|rubric_error|env_error|difficulty_mismatch> \
  --description "<text>" \
  --action <revise_task|revise_rubric|revise_env|revise_report> \
  [--field <field-name>] \
  [--from-value <value>] \
  [--to-value <value>] \
  [--status <status>]
```

### `add-edge`
Add an edge between two entities.

```bash
python3 "$EVAL_WIKI_SCRIPT" add-edge <wiki-root> \
  --from <node-id> \
  --to <node-id> \
  --type <edge-type>
```

### `rebuild-index`
Rebuild the entity index.

```bash
python3 "$EVAL_WIKI_SCRIPT" rebuild-index <wiki-root>
```

### `rebuild-query-pack`
Rebuild the query pack (compressed context for generation).

```bash
python3 "$EVAL_WIKI_SCRIPT" rebuild-query-pack <wiki-root>
```

### `query`
Query entities by ID or criteria.

```bash
python3 "$EVAL_WIKI_SCRIPT" query <wiki-root> [entity-id]
```

### `log`
Show the eval-wiki log.

```bash
python3 "$EVAL_WIKI_SCRIPT" log <wiki-root> [--lines N]
```

### `stats`
Show statistics for the eval-wiki.

```bash
python3 "$EVAL_WIKI_SCRIPT" stats <wiki-root>
```

## Entity Schemas

### Task

```yaml
---
type: task
node_id: "task:<slug>"
title: "<title>"
difficulty: "<lite|easy|medium|hard|beast>"
scenario_type: "<single-turn|multi-turn|tool-chain|error-recovery>"
max_turns: <N>
allowed_tools: ["<tool1>", "<tool2>"]
expected_behavior: "<description>"
cost: <float>
status: "<draft|finalized|retired>"
created_at: "<ISO-8601>"
---
```

### Environment

```yaml
---
type: environment
node_id: "env:<slug>"
task_id: "<task-slug>"
image: "<docker-image>"
network: "<network>"
memory: "<memory>"
cpus: <cpus>
agent_endpoint: "<endpoint>"
health_check: "<command>"
status: "<draft|provisioned|destroyed>"
created_at: "<ISO-8601>"
---
```

### Rubric

```yaml
---
type: rubric
node_id: "rubric:<slug>"
task_id: "<task-slug>"
criteria:
  - id: "<C1>"
    name: "<name>"
    description: "<description>"
    scoring: "<binary|scale>"
    weight: <float>
    evaluator: "<script|llm_judge>"
    script_path: "<path>"
status: "<draft|finalized>"
created_at: "<ISO-8601>"
---
```

### Run

```yaml
---
type: run
node_id: "run:<slug>"
task_id: "<task-slug>"
env_id: "<env-slug>"
rubric_id: "<rubric-slug>"
model: "<model-name>"
verdict: "<yes|no|inconclusive>"
confidence: "<high|medium|low>"
scores:
  "<C1>": "<PASS|FAIL|score>"
  "<C2>": "<PASS|FAIL|score>"
evidence: "<path-or-uri>"
status: "<completed|failed|timed_out>"
executed_at: "<ISO-8601>"
---
```

### Feedback

```yaml
---
type: feedback
node_id: "fb:<slug>"
target_type: "<task|rubric|env|run>"
target_id: "<node-id>"
from: "<user|auto-audit>"
issue_type: "<misalignment|missing_case|rubric_error|env_error|difficulty_mismatch>"
description: "<text>"
action: "<revise_task|revise_rubric|revise_env|revise_report>"
proposed_change:
  field: "<field-name>"
  from_value: "<value>"
  to_value: "<value>"
status: "<open|applied|verified|rejected>"
created_at: "<ISO-8601>"
---
```