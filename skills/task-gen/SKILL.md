---
name: task-gen
description: 'Generate eval tasks for Agent verification. DRIVE role. Use when user says "生成测试", "generate task", "创建task", or wants to expand eval coverage.'
argument-hint: "[difficulty: lite|easy|medium|hard|beast] [cost: 0.1-unlimited] [count: N]"
allowed-tools: Bash(*), Read, Write, Edit, Grep, Glob
role: DRIVE
depends-on: [eval-wiki]
produces: [task]
activates-env-gen: true
activates-rubric-gen: true
---

# task-gen Skill

## Overview

Generates eval tasks based on query_pack.md context. This is a DRIVE role
skill — it can be performed by the same model that runs the evaluation.

## Helper Resolution

Resolve `$EVAL_WIKI_SCRIPT` via the shared chain (Variant B — warn + skip):

```bash
cd "$(git rev-parse --show-toplevel 2>/dev/null || pwd)" || exit 1
EVAL_REPO="${EVAL_REPO:-$(awk -F'\t' '$1=="repo_root"{print $2; exit}' .eval/installed-skills.txt 2>/dev/null)}"
EVAL_WIKI_SCRIPT=".eval/dist/tools/eval-wiki.py"
[ -f "$EVAL_WIKI_SCRIPT" ] || EVAL_WIKI_SCRIPT="dist/tools/eval-wiki.py"
[ -f "$EVAL_WIKI_SCRIPT" ] || { [ -n "${EVAL_REPO:-}" ] && EVAL_WIKI_SCRIPT="$EVAL_REPO/dist/tools/eval-wiki.py"; }

if [ ! -f "$EVAL_WIKI_SCRIPT" ]; then
    echo "WARNING: eval-wiki.py not found. Skipping eval-wiki write." >&2
fi
```

## Phases

### Phase 0: Load query_pack.md

If `eval-wiki/` exists, read the query pack for context:

```bash
if [ -f "eval-wiki/query_pack.md" ]; then
    echo "Loading query_pack.md for context..."
    cat eval-wiki/query_pack.md
fi
```

### Phase 1: Generate Tasks

Generate tasks based on difficulty level. Each level has specific
characteristics:

| Difficulty | Turns | Tools | Error Injection | Adversarial | Context |
|------------|-------|-------|-----------------|-------------|---------|
| lite | 1 | 1 | No | No | Short |
| easy | 1 | 2+ | No | No | Short |
| medium | 2-5 | Chain | No | No | Medium |
| hard | 2-5 | Chain | Yes | Yes | Medium |
| beast | 5+ | Multi | Yes | Yes | Long |

Templates are used to generate the task specification. Each task includes:
- Title
- Scenario type (single-turn, multi-turn, tool-chain, error-recovery)
- Difficulty
- Cost
- Max turns
- Allowed tools
- Expected behavior
- Agent constraints (if applicable)

### Phase 2: Write Tasks to eval-wiki

For each generated task, call `eval-wiki.py` to persist it:

```bash
if [ -f "$EVAL_WIKI_SCRIPT" ]; then
    python3 "$EVAL_WIKI_SCRIPT" add-task eval-wiki/ \
      --title "$TITLE" \
      --difficulty "$DIFFICULTY" \
      --scenario-type "$SCENARIO_TYPE" \
      --max-turns "$MAX_TURNS" \
      --allowed-tools "$TOOLS" \
      --expected-behavior "$BEHAVIOR" \
      --cost "$COST"
fi
```

### Phase 3: Rebuild query_pack

After writing tasks, rebuild the query pack:

```bash
if [ -f "$EVAL_WIKI_SCRIPT" ]; then
    python3 "$EVAL_WIKI_SCRIPT" rebuild-query-pack eval-wiki/
fi
```

## Output

Task files are written to `eval-wiki/tasks/`. Each task is a Markdown file
with YAML frontmatter containing the task specification.