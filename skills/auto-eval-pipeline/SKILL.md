---
name: auto-eval-pipeline
description: 'End-to-end Agent verification pipeline driver. Takes a user query or evaluation goal and drives the full pipeline: task-gen → env-gen → rubric-gen → (Agent runs) → report-gen. Optionally iterates with feedback-align. Uses eval-wiki as the canonical record and run-state for orchestration. Use when user says "开始验证", "run evaluation", "启动验证", "eval pipeline", "run pipeline", or wants to execute the full Agent verification workflow.'
argument-hint: "[goal] [— difficulty: lite|easy|medium|hard|beast] [— cost: 0.1-unlimited] [— count: N]"
allowed-tools: Bash(*), Read, Write, Edit, Grep, Glob, WebSearch, WebFetch, AskUserQuestion
role: DRIVE
depends-on: [eval-wiki, task-gen, env-gen, rubric-gen, report-gen, feedback-align, run-state]
produces: [task, environment, rubric, run, report, feedback]
---

# auto-eval-pipeline Skill

## Overview

End-to-end Agent verification pipeline **orchestrator**. It takes a user query
or evaluation goal and drives the full pipeline through all stages by
**delegating each stage to its dedicated sub-skill**:

- **task-gen** — scenario + task generation
- **env-gen** — environment generation
- **rubric-gen** — rubric + evaluator generation
- **report-gen** — report generation
- **feedback-align** — feedback loop (optional)

This skill is an **orchestrator only**. It does **not** reimplement the logic of
its sub-skills inline. Each phase loads the corresponding sub-skill's `SKILL.md`,
passes it the resolved arguments, and lets that skill produce its artifacts.
The pipeline itself is responsible only for: pre-flight checks, argument
parsing, delegating to each sub-skill, `run-state.py` phase tracking, state
persistence/resume, logging, and human checkpoints.

Uses `eval-wiki` as the canonical record and `run-state.py` for phase orchestration.

## Constants

| Constant | Value | Description |
|----------|-------|-------------|
| `STATE_DIR` | `.eval/pipeline/` | Pipeline state directory |
| `STATE_FILE` | `.eval/pipeline/state.json` | Pipeline state file |
| `LOG_FILE` | `.eval/pipeline/log.md` | Pipeline execution log |
| `REPORT_FILE` | `reports/pipeline-report.html` | Generated HTML report |
| `MAX_TASKS` | 5 | Default number of tasks to generate |
| `HUMAN_CHECKPOINT` | false | Pause after each stage for user confirmation |
| `DEBUG` | false | Enable verbose debug output |

## Helper Resolution Chains

### Resolve `$EVAL_WIKI_SCRIPT` (Variant A — hard-fail)

The pipeline needs `eval-wiki.py` for pre-flight checks and run-state tracking.

```bash
cd "$(git rev-parse --show-toplevel 2>/dev/null || pwd)" || exit 1

# 1. Check for installed copy in .eval
EVAL_REPO="${EVAL_REPO:-$(awk -F'\t' '$1=="repo_root"{print $2; exit}' .eval/installed-skills.txt 2>/dev/null)}"
EVAL_WIKI_SCRIPT=".eval/dist/tools/eval-wiki.py"

# 2. Fall back to canonical dist path
[ -f "$EVAL_WIKI_SCRIPT" ] || EVAL_WIKI_SCRIPT="dist/tools/eval-wiki.py"

# 3. Fall back to EVAL_REPO
[ -f "$EVAL_WIKI_SCRIPT" ] || { [ -n "${EVAL_REPO:-}" ] && EVAL_WIKI_SCRIPT="$EVAL_REPO/dist/tools/eval-wiki.py"; }

# 4. Hard fail — pipeline cannot proceed without eval-wiki
if [ ! -f "$EVAL_WIKI_SCRIPT" ]; then
    echo "ERROR: eval-wiki.py not found. Run 'tools/install_eval_wiki.sh' first." >&2
    exit 1
fi
```

### Resolve `$SKILLS_DIR` (for sub-skill delegation)

The pipeline drives its sub-skills by loading each sub-skill's `SKILL.md` and
executing it with the resolved arguments. Resolve the skills directory the same
way `setup` does:

```bash
# Check for skills installed via ARIS-style install (.claude/skills/)
SKILLS_DIR=".claude/skills"
if [ ! -d "$SKILLS_DIR" ]; then
    # Fall back to the auto-eval repo's skills/ directory
    AUTOEVAL_REPO="${AUTOEVAL_REPO:-$EVAL_REPO}"
    if [ -z "$AUTOEVAL_REPO" ]; then
        CANDIDATE="$(pwd)"
        while [ "$CANDIDATE" != "/" ]; do
            [ -d "$CANDIDATE/skills" ] && { AUTOEVAL_REPO="$CANDIDATE"; break; }
            CANDIDATE="$(dirname "$CANDIDATE")"
        done
    fi
    [ -n "$AUTOEVAL_REPO" ] && SKILLS_DIR="$AUTOEVAL_REPO/skills"
fi

# Helper: verify a sub-skill exists before delegating to it.
require_subskill() {
    SUBSKILL="$1"
    if [ ! -f "$SKILLS_DIR/$SUBSKILL/SKILL.md" ]; then
        echo "ERROR: sub-skill '$SUBSKILL' not found at $SKILLS_DIR/$SUBSKILL/SKILL.md" >&2
        echo "Run 'tools/install_eval_wiki.sh' first, or set AUTOEVAL_REPO." >&2
        exit 1
    fi
}
```

> **Delegation contract.** To delegate to a sub-skill, the pipeline:
> 1. Calls `require_subskill <name>` to confirm the skill is present.
> 2. Loads and follows `skills/<name>/SKILL.md`, passing the resolved
>    arguments (per that skill's `argument-hint`).
> 3. After the sub-skill returns, verifies the expected artifact exists and
>    records the phase in `run-state.py`.
>
> The pipeline never inlines the sub-skill's generation/assembly/writing logic.

## Phases

### Phase 0 — Pre-flight Check

Check that eval-wiki exists and load state for resume detection.

```bash
mkdir -p "$STATE_DIR"

# Check that eval-wiki exists
if [ ! -f "eval-wiki/index.md" ]; then
    echo "ERROR: eval-wiki not initialized. Run 'setup' first." >&2
    exit 1
fi

# Resolve $EVAL_WIKI_SCRIPT and $SKILLS_DIR via the chains above

# Load existing state for resume detection
if [ -f "$STATE_FILE" ]; then
    echo "Resuming previous pipeline run..."
    cat "$STATE_FILE"
fi

# Parse $ARGUMENTS for overrides
# difficulty, cost, count can be passed as -- key:value pairs
ARG_DIFFICULTY=""
ARG_COST=""
ARG_COUNT=""

# Read EVAL_CONFIG.md for project context
if [ -f "EVAL_CONFIG.md" ]; then
    echo "Loading project configuration from EVAL_CONFIG.md..."
    head -30 EVAL_CONFIG.md
fi
```

### Phase 1 — Task Generation (delegate to task-gen)

Resolve difficulty/cost from argument overrides or `EVAL_CONFIG.md` defaults,
then **delegate task generation to the `task-gen` skill**. The pipeline does not
generate tasks itself; it hands off to `task-gen` (which performs AWM-style
scenario generation → task generation) and only tracks the result.

```bash
DIFFICULTY="${ARG_DIFFICULTY:-$(grep -i 'default difficulty' EVAL_CONFIG.md 2>/dev/null | head -1 | sed 's/.*: *//' | sed 's/ *$//')}"
COST="${ARG_COST:-$(grep -i 'cost budget' EVAL_CONFIG.md 2>/dev/null | head -1 | sed 's/.*: *//' | sed 's/ *$//')}"
COUNT="${ARG_COUNT:-$MAX_TASKS}"

# Set defaults if not resolved
DIFFICULTY="${DIFFICULTY:-medium}"
COST="${COST:-1.0}"

echo "## Phase 1: Task Generation" >> "$LOG_FILE"
echo "- Difficulty: $DIFFICULTY" >> "$LOG_FILE"
echo "- Cost: $COST" >> "$LOG_FILE"
echo "- Count: $COUNT" >> "$LOG_FILE"

# --- Delegate to the task-gen sub-skill ---
require_subskill task-gen
# Invoke task-gen with the resolved difficulty/cost/count, following
# skills/task-gen/SKILL.md (argument-hint: [difficulty] [cost] [count]).
# task-gen performs scenario generation → task generation and writes
# scenarios/tasks to eval-wiki and rebuilds the query pack.
echo "Delegating task generation to the task-gen skill..."
Read "$SKILLS_DIR/task-gen/SKILL.md"
# Pass arguments to task-gen: "$DIFFICULTY" "$COST" "$COUNT"

# Update run-state
RUN_ID="run-$(date -u +'%Y%m%dT%H%M%SZ')"
python3 src/tools/run-state.py init-run "$RUN_ID"
python3 src/tools/run-state.py set-status "$RUN_ID" task-gen done

# Verify task-gen produced tasks (the sub-skill owns the generation logic)
TASK_COUNT=$(ls eval-wiki/tasks/*.md 2>/dev/null | wc -l)
echo "- Tasks generated: $TASK_COUNT" >> "$LOG_FILE"
echo "- Run ID: $RUN_ID" >> "$LOG_FILE"

# Save state
python3 -c "
import json
state = {'run_id': '$RUN_ID', 'last_completed_phase': 1, 'difficulty': '$DIFFICULTY', 'cost': '$COST', 'count': $COUNT}
with open('$STATE_FILE', 'w') as f:
    json.dump(state, f)
"

# Human checkpoint
if [ "$HUMAN_CHECKPOINT" = "true" ]; then
    AskUserQuestion "Phase 1 complete. Proceed to environment generation? (Y/n)" "Y"
fi
```

### Phase 2 — Environment Generation (delegate to env-gen)

Generate Docker environments for each finalized task by **delegating to the
`env-gen` skill**. The pipeline does not assemble `docker-compose.yml` itself;
`env-gen` performs component search → assemble → fine-tune → provision and
records the environment in eval-wiki.

```bash
echo "## Phase 2: Environment Generation" >> "$LOG_FILE"

# List tasks from eval-wiki (produced by task-gen in Phase 1)
TASKS=$(python3 "$EVAL_WIKI_SCRIPT" query eval-wiki/ 2>/dev/null | grep "^task:" | sed 's/^task://')

# --- Delegate to the env-gen sub-skill, once per task ---
require_subskill env-gen
# Invoke env-gen for each task, following skills/env-gen/SKILL.md
# (argument-hint: [task-id] [dry-run]). env-gen queries the component
# manager, assembles/fine-tunes components, provisions containers, and
# writes the environment record to eval-wiki.
for TASK_ID in $TASKS; do
    echo "Delegating environment generation to the env-gen skill for $TASK_ID..."
    Read "$SKILLS_DIR/env-gen/SKILL.md"
    # Pass arguments to env-gen: "$TASK_ID"
done

# Update run-state
python3 src/tools/run-state.py set-status "$RUN_ID" env-gen done

ENV_COUNT=$(ls eval-wiki/environments/*.md 2>/dev/null | wc -l)
echo "- Environments generated: $ENV_COUNT (for tasks: $TASKS)" >> "$LOG_FILE"

# Save state
python3 -c "
import json
state = json.load(open('$STATE_FILE'))
state['last_completed_phase'] = 2
with open('$STATE_FILE', 'w') as f:
    json.dump(state, f)
"

# Human checkpoint
if [ "$HUMAN_CHECKPOINT" = "true" ]; then
    AskUserQuestion "Phase 2 complete. Proceed to rubric generation? (Y/n)" "Y"
fi
```

### Phase 3 — Rubric Generation (delegate to rubric-gen)

Generate rubric criteria and evaluator scripts for each task by **delegating to
the `rubric-gen` skill**. The pipeline does not build criteria JSON or evaluator
scripts itself; `rubric-gen` generates scenario-type-based criteria, evaluator
script skeletons, writes the rubric to eval-wiki, and verifies the scripts.

```bash
echo "## Phase 3: Rubric Generation" >> "$LOG_FILE"

mkdir -p evaluators

TASKS=$(python3 "$EVAL_WIKI_SCRIPT" query eval-wiki/ 2>/dev/null | grep "^task:" | sed 's/^task://')

# --- Delegate to the rubric-gen sub-skill, once per task ---
require_subskill rubric-gen
# Invoke rubric-gen for each task, following skills/rubric-gen/SKILL.md
# (argument-hint: [task-id] [assurance: draft|submission]). rubric-gen
# generates criteria, evaluator scripts, writes the rubric to eval-wiki,
# and verifies the scripts. It is an ACQUIT skill — cross-model per
# acceptance-gate.md.
for TASK_ID in $TASKS; do
    echo "Delegating rubric generation to the rubric-gen skill for $TASK_ID..."
    Read "$SKILLS_DIR/rubric-gen/SKILL.md"
    # Pass arguments to rubric-gen: "$TASK_ID"
done

# Update run-state
python3 src/tools/run-state.py set-status "$RUN_ID" rubric-gen done

RUBRIC_COUNT=$(ls eval-wiki/rubrics/*.md 2>/dev/null | wc -l)
echo "- Rubrics generated: $RUBRIC_COUNT (for tasks: $TASKS)" >> "$LOG_FILE"

# Save state
python3 -c "
import json
state = json.load(open('$STATE_FILE'))
state['last_completed_phase'] = 3
with open('$STATE_FILE', 'w') as f:
    json.dump(state, f)
"

# Human checkpoint
if [ "$HUMAN_CHECKPOINT" = "true" ]; then
    AskUserQuestion "Phase 3 complete. Proceed to report generation? (Y/n)" "Y"
fi
```

### Phase 4 — Report Generation (delegate to report-gen)

Read all tasks, runs, rubrics, and feedback from eval-wiki and generate a
single HTML report by **delegating to the `report-gen` skill**. The pipeline
does not author the HTML itself; `report-gen` collects eval-wiki data and
produces the versioned report.

```bash
echo "## Phase 4: Report Generation" >> "$LOG_FILE"

mkdir -p reports

# --- Delegate to the report-gen sub-skill ---
require_subskill report-gen
# Invoke report-gen, following skills/report-gen/SKILL.md
# (argument-hint: [wiki-root] [output-path]). report-gen collects all
# runs/rubrics/tasks from eval-wiki and writes the versioned HTML report
# (report-<timestamp>.html + report-latest.html).
echo "Delegating report generation to the report-gen skill..."
Read "$SKILLS_DIR/report-gen/SKILL.md"
# Pass arguments to report-gen: "eval-wiki" "reports"

# Update run-state
python3 src/tools/run-state.py set-status "$RUN_ID" report-gen done

# The report-gen skill owns the report path/structure; pin the expected path
# for state and the summary, but do not author the HTML here.
echo "- Report generated: $REPORT_FILE" >> "$LOG_FILE"

# Save state
python3 -c "
import json
state = json.load(open('$STATE_FILE'))
state['last_completed_phase'] = 4
state['report_path'] = '$REPORT_FILE'
with open('$STATE_FILE', 'w') as f:
    json.dump(state, f)
"

# Human checkpoint
if [ "$HUMAN_CHECKPOINT" = "true" ]; then
    AskUserQuestion "Phase 4 complete. Proceed to summary? (Y/n)" "Y"
fi
```

### Phase 5 — Summary & Feedback Loop (delegate to feedback-align)

Print the pipeline summary and, when feedback is requested, **delegate to the
`feedback-align` skill**. The pipeline does not record or apply feedback itself;
`feedback-align` records feedback, proposes/applies changes, and verifies them
cross-model.

```bash
echo "## Phase 5: Summary" >> "$LOG_FILE"

echo "=========================================="
echo "  Pipeline Run Complete"
echo "=========================================="
echo ""
echo "Run ID: $RUN_ID"
echo ""

# Gather counts
TASK_COUNT=$(ls eval-wiki/tasks/*.md 2>/dev/null | wc -l)
ENV_COUNT=$(ls eval-wiki/environments/*.md 2>/dev/null | wc -l)
RUBRIC_COUNT=$(ls eval-wiki/rubrics/*.md 2>/dev/null | wc -l)
RUN_COUNT=$(ls eval-wiki/runs/*.md 2>/dev/null | wc -l)

echo "Pipeline Summary:"
echo "  - Tasks created:       $TASK_COUNT"
echo "  - Environments:        $ENV_COUNT"
echo "  - Rubrics created:     $RUBRIC_COUNT"
echo "  - Runs completed:      $RUN_COUNT"
echo ""
echo "Report: $REPORT_FILE"
echo ""

echo "- Tasks: $TASK_COUNT" >> "$LOG_FILE"
echo "- Environments: $ENV_COUNT" >> "$LOG_FILE"
echo "- Rubrics: $RUBRIC_COUNT" >> "$LOG_FILE"
echo "- Runs: $RUN_COUNT" >> "$LOG_FILE"

# --- Optional: delegate feedback to the feedback-align sub-skill ---
require_subskill feedback-align

# Optional feedback collection
if [ "$HUMAN_CHECKPOINT" = "true" ]; then
    AskUserQuestion "Would you like to provide feedback on this run? (Y/n)" "n"
    if [ "$ANSWER" = "Y" ] || [ "$ANSWER" = "y" ]; then
        AskUserQuestion "Describe your feedback:" ""
        # Invoke feedback-align, following skills/feedback-align/SKILL.md
        # (argument-hint: [target-type] [target-id] [action]). feedback-align
        # records the feedback, analyzes/applies the change, and verifies it
        # cross-model.
        echo "Delegating feedback to the feedback-align skill..."
        Read "$SKILLS_DIR/feedback-align/SKILL.md"
        # Pass arguments to feedback-align: "run" "$RUN_ID" "revise_report"
        echo "- Feedback recorded (via feedback-align)" >> "$LOG_FILE"
    fi
fi

# Mark pipeline as complete (after the feedback-align sub-skill has run)
python3 src/tools/run-state.py set-status "$RUN_ID" feedback-align done

# Save final state
python3 -c "
import json
state = json.load(open('$STATE_FILE'))
state['last_completed_phase'] = 5
state['status'] = 'complete'
with open('$STATE_FILE', 'w') as f:
    json.dump(state, f)
"

echo ""
echo "Next steps:"
echo "  - Review the report at $REPORT_FILE"
echo "  - Run /feedback-align for iterative improvement"
echo "  - Run /auto-eval-pipeline again with different parameters"
echo "=========================================="
```

## Key Design Patterns

- **Delegates each stage to its sub-skill** (`task-gen`, `env-gen`,
  `rubric-gen`, `report-gen`, `feedback-align`) — the pipeline never inlines a
  sub-skill's generation/assembly/writing logic. Each sub-skill owns its
  artifacts; the pipeline only orchestrates, tracks, and verifies.
- **Uses `run-state.py`** for phase orchestration (`init-run`, `set-status` per phase).
- **Accepts `— difficulty:` and `— cost:` parameters**, passed through to task-gen.
- **Resumable** via `.eval/pipeline/state.json` — detects and resumes from last incomplete phase.
- **Each phase logs** to `LOG_FILE` (`.eval/pipeline/log.md`).
- **`HUMAN_CHECKPOINT` flag** for interactive mode with user confirmation at each stage.
- **`$EVAL_WIKI_SCRIPT` resolution chain** (Variant A — hard-fail).
- **`$SKILLS_DIR` resolution chain** for sub-skill discovery (same as `setup`).
- **References `shared-references/`** contracts for output versioning, effort/cost, etc.
- **All phases are DRIVE role** — the pipeline orchestrator drives execution directly.
- **Output versioning**: Report files are written with timestamped copies plus a `-latest` symlink, per `shared-references/output-versioning.md` (handled by report-gen).
