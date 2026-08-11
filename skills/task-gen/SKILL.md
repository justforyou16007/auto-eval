---
name: task-gen
description: 'Generate eval tasks for Agent verification. DRIVE role. Uses AWM-style two-stage generation: scenario generation first, then task generation from scenarios. Use when user says "生成测试", "generate task", "创建task", or wants to expand eval coverage.'
argument-hint: "[difficulty: lite|easy|medium|hard|beast] [cost: 0.1-unlimited] [count: N]"
allowed-tools: Bash(*), Read, Write, Edit, Grep, Glob
role: DRIVE
depends-on: [eval-wiki]
produces: [scenario, task]
activates-env-gen: true
activates-rubric-gen: true
---

# task-gen Skill

## Overview

Generates eval tasks using AWM (Agent World Model) two-stage generation:

1. **Phase 1 — Scenario Generation**: Generate diverse scenario descriptions
   from query_pack.md context. Each scenario is a rich description of a testing
   context (seed for task generation).

2. **Phase 2 — Task Generation**: For each scenario, generate M concrete tasks
   (default M=3). Each task references its parent scenario via `scenario_id`.

This replaces the previous single-stage template-based generation with a richer,
more structured approach inspired by AWM (arxiv 2602.10090).

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

### Phase 0: Load Context

Read query_pack.md for existing scenarios, gaps, failed tasks, and coverage
context. Also read EVAL_CONFIG.md for project direction.

```bash
# Load query pack for context
if [ -f "eval-wiki/query_pack.md" ]; then
    echo "Loading query_pack.md for context..."
    cat eval-wiki/query_pack.md
fi

# Load EVAL_CONFIG.md for project direction
if [ -f "eval-wiki/EVAL_CONFIG.md" ]; then
    echo "Loading EVAL_CONFIG.md for project direction..."
    cat eval-wiki/EVAL_CONFIG.md
fi
```

### Phase 1: Scenario Generation (NEW — AWM-style)

Generate N diverse scenario descriptions (configurable, default N=3). Each
scenario is a rich description of a testing context:

- **Name** (e.g., "E-commerce Inventory Management")
- **Description** — what the Agent needs to do in this scenario
- **Scenario type** — single-turn, multi-turn, tool-chain, error-recovery
- **Difficulty level** — lite, easy, medium, hard, beast
- **Required capabilities** — what Agent abilities this tests
  (e.g., tool-use, multi-step-reasoning, error-recovery)
- **Environment hints** — what kind of components this scenario needs
  (e.g., "Needs e-commerce backend API, product database, order management system")

Scenarios are written to eval-wiki using the `add-scenario` command:

```bash
if [ -f "$EVAL_WIKI_SCRIPT" ]; then
    python3 "$EVAL_WIKI_SCRIPT" add-scenario eval-wiki/ \
      --name "$SCENARIO_NAME" \
      --description "$SCENARIO_DESCRIPTION" \
      --scenario-type "$SCENARIO_TYPE" \
      --difficulty "$DIFFICULTY" \
      --capabilities "$CAPABILITIES" \
      --env-hints "$ENVIRONMENT_HINTS"
fi
```

Scenarios serve as "seeds" — Phase 2 reads them and produces concrete tasks.

### Phase 2: Task Generation (rewritten)

Read generated scenarios from eval-wiki. For each scenario, generate M concrete
tasks (default M=3). **Each task MUST carry concrete content derived from its
parent scenario — do not leave the body sections as `_TODO` stubs.** The
`add-task` command renders the supplied `--goal`, `--input-spec`,
`--expected-behavior`, `--preconditions`, and `--constraints` into the
corresponding body sections (测试目标 / 输入规格 / 预期输出 / 前置条件 /
边界条件). When any of these is omitted the section falls back to a `_TODO`
stub, so supply all of them from the scenario description.

Each task includes:
- Title
- Difficulty
- Cost
- Scenario type
- Max turns
- Allowed tools
- Expected behavior
- Test goal (`--goal`)
- Input spec (`--input-spec`)
- Preconditions (`--preconditions`)
- Boundary constraints (`--constraints`)
- Coverage gaps
- **scenario_id** — reference to parent scenario

```bash
# List existing scenarios
if [ -f "$EVAL_WIKI_SCRIPT" ]; then
    python3 "$EVAL_WIKI_SCRIPT" query eval-wiki/ "scenario:"
fi
```

For each scenario, generate tasks and write them — filling every body section
from the scenario context so the task file is an effective spec, not a TODO stub:

```bash
if [ -f "$EVAL_WIKI_SCRIPT" ]; then
    python3 "$EVAL_WIKI_SCRIPT" add-task eval-wiki/ \
      --title "$TITLE" \
      --difficulty "$DIFFICULTY" \
      --scenario-type "$SCENARIO_TYPE" \
      --max-turns "$MAX_TURNS" \
      --allowed-tools "$TOOLS" \
      --expected-behavior "$BEHAVIOR" \
      --goal "$GOAL" \
      --input-spec "$INPUT_SPEC" \
      --preconditions "$PRECONDITIONS" \
      --constraints "$CONSTRAINTS" \
      --cost "$COST" \
      --scenario-id "$SCENARIO_ID"
fi
```


### Phase 3: Post-write

After writing tasks, rebuild the index and query pack, then activate downstream
skills (env-gen, rubric-gen):

```bash
if [ -f "$EVAL_WIKI_SCRIPT" ]; then
    python3 "$EVAL_WIKI_SCRIPT" rebuild-index eval-wiki/
    python3 "$EVAL_WIKI_SCRIPT" rebuild-query-pack eval-wiki/
    echo "Rebuild complete. Downstream skills (env-gen, rubric-gen) can now proceed."
fi
```

## Scenario Generation Guidelines

When generating scenarios, ensure diversity across:

| Dimension | Options |
|-----------|---------|
| Scenario type | single-turn, multi-turn, tool-chain, error-recovery |
| Difficulty | lite, easy, medium, hard, beast |
| Domain | e-commerce, search, file-system, API, data-processing, etc. |
| Capabilities | tool-use, multi-step-reasoning, error-recovery, planning, code-gen, data-analysis |

Each scenario should focus on a specific testing context and avoid overlap
with existing scenarios. Check existing scenarios in query_pack.md before
generating new ones.

## Task Generation Guidelines

For each scenario, generate M diverse tasks:

| Task Dimension | Options |
|----------------|---------|
| Agent interaction | direct query, tool invocation, multi-step workflow |
| Error handling | graceful degradation, retry logic, error reporting |
| Data complexity | simple CRUD, complex queries, pagination, filtering |
| State management | stateless, session-based, persistent state |

Each task within a scenario should test different aspects of the scenario's
requirements. Avoid generating duplicate or near-identical tasks.

## Output

- Scenario files in `eval-wiki/scenarios/` — each with YAML frontmatter
- Task files in `eval-wiki/tasks/` — each with `scenario_id` field
- `eval-wiki/query_pack.md` — rebuilt with new scenarios and tasks
- `eval-wiki/index.md` — rebuilt index