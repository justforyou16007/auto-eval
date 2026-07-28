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

End-to-end Agent verification pipeline driver. Takes a user query or evaluation
goal and drives the full pipeline through all stages: task generation, environment
generation, rubric generation, (Agent execution — stub), report generation, and
optional feedback alignment.

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

## Helper Resolution Chain

Resolve `$EVAL_WIKI_SCRIPT` via the shared chain (Variant A — hard-fail):

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

# Resolve $EVAL_WIKI_SCRIPT via shared chain above

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

### Phase 1 — Task Generation (task-gen)

Resolve difficulty/cost from argument overrides or EVAL_CONFIG.md defaults, then
generate tasks for unaddressed gaps.

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

# Generate tasks (stub — actual task-gen logic would read query_pack.md)
for i in $(seq 1 "$COUNT"); do
    TITLE="Evaluation Task $i - $(date +%Y%m%d)"
    python3 "$EVAL_WIKI_SCRIPT" add-task eval-wiki/ \
        --title "$TITLE" \
        --difficulty "$DIFFICULTY" \
        --scenario-type "single-turn" \
        --max-turns 1 \
        --allowed-tools "search" \
        --expected-behavior "Agent performs the task correctly" \
        --cost "$COST"
done

# Rebuild query pack
python3 "$EVAL_WIKI_SCRIPT" rebuild-query-pack eval-wiki/

# Update run-state
RUN_ID="run-$(date -u +'%Y%m%dT%H%M%SZ')"
python3 src/tools/run-state.py init-run "$RUN_ID"
python3 src/tools/run-state.py set-status "$RUN_ID" task-gen done

echo "- Tasks generated: $COUNT" >> "$LOG_FILE"
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

### Phase 2 — Environment Generation (env-gen)

Generate Docker environments for each finalized task.

```bash
echo "## Phase 2: Environment Generation" >> "$LOG_FILE"

# List tasks from eval-wiki
TASKS=$(python3 "$EVAL_WIKI_SCRIPT" query eval-wiki/ 2>/dev/null | grep "^task:" | sed 's/^task://')

for TASK_ID in $TASKS; do
    python3 "$EVAL_WIKI_SCRIPT" add-env eval-wiki/ \
        --task-id "$TASK_ID" \
        --image "${DOCKER_IMAGE:-python:3.11}" \
        --network "bridge" \
        --memory "${MEMORY:-512m}" \
        --cpus "${CPU:-1}" \
        --agent-endpoint "http://agent:8080" \
        --health-check "curl -f http://localhost:8080/health"
done

# Generate docker-compose.yml configuration (stub)
cat > docker-compose.yml << 'COMPOSEEOF'
version: '3.8'
services:
  agent:
    image: agent-under-test:latest
    networks:
      - eval-net
    mem_limit: 512m
    cpus: 1
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/health"]
      interval: 10s
      timeout: 5s
      retries: 3
networks:
  eval-net:
    driver: bridge
COMPOSEEOF

# Update run-state
python3 src/tools/run-state.py set-status "$RUN_ID" env-gen done

echo "- Environments generated for tasks: $TASKS" >> "$LOG_FILE"

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

### Phase 3 — Rubric Generation (rubric-gen)

Generate rubric criteria and evaluator scripts for each task.

```bash
echo "## Phase 3: Rubric Generation" >> "$LOG_FILE"

mkdir -p evaluators

TASKS=$(python3 "$EVAL_WIKI_SCRIPT" query eval-wiki/ 2>/dev/null | grep "^task:" | sed 's/^task://')

for TASK_ID in $TASKS; do
    # Read task's expected_behavior and scenario_type from eval-wiki
    TASK_FILE="eval-wiki/tasks/${TASK_ID}.md"
    EXPECTED_BEHAVIOR=""
    SCENARIO_TYPE=""
    if [ -f "$TASK_FILE" ]; then
        EXPECTED_BEHAVIOR=$(grep 'expected_behavior' "$TASK_FILE" | sed 's/.*: *"//;s/"//')
        SCENARIO_TYPE=$(grep 'scenario_type' "$TASK_FILE" | sed 's/.*: *"//;s/"//')
    fi

    # Generate criteria JSON
    python3 -c "
import json
criteria = {
    'criteria': [
        {
            'id': 'C1',
            'name': 'Correctness',
            'description': 'Agent produces the correct output',
            'scoring': 'binary',
            'weight': 1.0,
            'evaluator': 'script',
            'script_path': 'evaluators/${TASK_ID}_correctness.py'
        },
        {
            'id': 'C2',
            'name': 'Tool Usage',
            'description': 'Agent uses tools correctly and efficiently',
            'scoring': 'scale',
            'weight': 0.5,
            'evaluator': 'llm_judge',
            'script_path': ''
        }
    ]
}
with open('evaluators/criteria.json', 'w') as f:
    json.dump(criteria, f, indent=2)
"

    # Create evaluator script skeleton
    cat > "evaluators/${TASK_ID}_correctness.py" << 'EVALEOF'
#!/usr/bin/env python3
"""Evaluator script for C1: Correctness."""
import sys

def evaluate(agent_output: str, expected: str) -> dict:
    """Evaluate correctness of agent output."""
    passed = agent_output.strip() == expected.strip()
    return {
        "criterion_id": "C1",
        "passed": passed,
        "score": 1.0 if passed else 0.0,
        "evidence": f"Expected: {expected}, Got: {agent_output}"
    }

if __name__ == "__main__":
    # Stub: read from stdin or args
    result = evaluate("", "")
    print(json.dumps(result))
EVALEOF
    chmod +x "evaluators/${TASK_ID}_correctness.py"

    # Add rubric to eval-wiki
    python3 "$EVAL_WIKI_SCRIPT" add-rubric eval-wiki/ \
        --task-id "$TASK_ID" \
        --criteria-json evaluators/criteria.json
done

# Update run-state
python3 src/tools/run-state.py set-status "$RUN_ID" rubric-gen done

echo "- Rubrics generated for tasks: $TASKS" >> "$LOG_FILE"

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

### Phase 4 — Report Generation (report-gen)

Read all tasks, runs, rubrics, and feedback from eval-wiki and generate a
single HTML report with overview stats and per-task sections.

```bash
echo "## Phase 4: Report Generation" >> "$LOG_FILE"

mkdir -p reports

# Gather data from eval-wiki
TASKS=$(python3 "$EVAL_WIKI_SCRIPT" query eval-wiki/ 2>/dev/null)
RUNS=$(python3 "$EVAL_WIKI_SCRIPT" query eval-wiki/ 2>/dev/null || true)
RUBRICS=$(python3 "$EVAL_WIKI_SCRIPT" query eval-wiki/ 2>/dev/null || true)
FEEDBACK=$(python3 "$EVAL_WIKI_SCRIPT" query eval-wiki/ 2>/dev/null || true)

# Generate HTML report
TIMESTAMP=$(date -u +"%Y%m%dT%H%M%SZ")
cat > "$REPORT_FILE" << 'HTMLEOF'
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Pipeline Evaluation Report</title>
    <style>
        body { font-family: -apple-system, sans-serif; max-width: 960px; margin: 2em auto; padding: 0 1em; }
        h1 { color: #333; border-bottom: 2px solid #eee; padding-bottom: 0.5em; }
        h2 { color: #555; margin-top: 2em; }
        table { border-collapse: collapse; width: 100%; margin: 1em 0; }
        th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
        th { background: #f5f5f5; }
        .pass { color: #2e7d32; }
        .fail { color: #c62828; }
        .summary { background: #f9f9f9; padding: 1em; border-radius: 4px; }
    </style>
</head>
<body>
    <h1>Pipeline Evaluation Report</h1>
    <div class="summary">
        <p><strong>Generated:</strong> TIMESTAMP_PLACEHOLDER</p>
        <p><strong>Run ID:</strong> RUN_ID_PLACEHOLDER</p>
    </div>
    <h2>Overview</h2>
    <table>
        <tr><th>Metric</th><th>Value</th></tr>
        <tr><td>Tasks Generated</td><td>TASK_COUNT_PLACEHOLDER</td></tr>
        <tr><td>Environments Created</td><td>ENV_COUNT_PLACEHOLDER</td></tr>
        <tr><td>Rubrics Created</td><td>RUBRIC_COUNT_PLACEHOLDER</td></tr>
        <tr><td>Runs Completed</td><td>RUN_COUNT_PLACEHOLDER</td></tr>
    </table>
    <h2>Tasks</h2>
    <p>See eval-wiki/tasks/ for full task specifications.</p>
    <p><em>Report generated by auto-eval-pipeline skill.</em></p>
</body>
</html>
HTMLEOF

# Replace placeholders
sed -i "s/TIMESTAMP_PLACEHOLDER/$TIMESTAMP/g" "$REPORT_FILE"
sed -i "s/RUN_ID_PLACEHOLDER/$RUN_ID/g" "$REPORT_FILE"
TASK_COUNT=$(echo "$TASKS" | grep -c "^task:" 2>/dev/null || echo "0")
sed -i "s/TASK_COUNT_PLACEHOLDER/$TASK_COUNT/g" "$REPORT_FILE"
sed -i "s/ENV_COUNT_PLACEHOLDER/0/g" "$REPORT_FILE"
sed -i "s/RUBRIC_COUNT_PLACEHOLDER/0/g" "$REPORT_FILE"
sed -i "s/RUN_COUNT_PLACEHOLDER/0/g" "$REPORT_FILE"

# Write versioned copy (per output-versioning.md)
cp "$REPORT_FILE" "reports/pipeline-report-${TIMESTAMP}.html"
cp "$REPORT_FILE" "reports/pipeline-report-latest.html"

# Update run-state
python3 src/tools/run-state.py set-status "$RUN_ID" report-gen done

echo "- Report generated: $REPORT_FILE" >> "$LOG_FILE"
echo "- Versioned: reports/pipeline-report-${TIMESTAMP}.html" >> "$LOG_FILE"
echo "- Latest: reports/pipeline-report-latest.html" >> "$LOG_FILE"

# Save state
python3 -c "
import json
state = json.load(open('$STATE_FILE'))
state['last_completed_phase'] = 4
state['report_path'] = '$REPORT_FILE'
state['report_timestamp'] = '$TIMESTAMP'
with open('$STATE_FILE', 'w') as f:
    json.dump(state, f)
"

# Human checkpoint
if [ "$HUMAN_CHECKPOINT" = "true" ]; then
    AskUserQuestion "Phase 4 complete. Proceed to summary? (Y/n)" "Y"
fi
```

### Phase 5 — Summary & Feedback Loop

Print pipeline summary and optionally collect feedback.

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

# Mark pipeline as complete
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

# Optional feedback collection
if [ "$HUMAN_CHECKPOINT" = "true" ]; then
    AskUserQuestion "Would you like to provide feedback on this run? (Y/n)" "n"
    if [ "$ANSWER" = "Y" ] || [ "$ANSWER" = "y" ]; then
        AskUserQuestion "Describe your feedback:" ""
        python3 "$EVAL_WIKI_SCRIPT" add-feedback eval-wiki/ \
            --target-type "run" \
            --target-id "$RUN_ID" \
            --from "user" \
            --issue-type "misalignment" \
            --description "$ANSWER" \
            --action "revise_report"
        echo "- Feedback recorded" >> "$LOG_FILE"
    fi
fi

echo ""
echo "Next steps:"
echo "  - Review the report at $REPORT_FILE"
echo "  - Run /feedback-align for iterative improvement"
echo "  - Run /auto-eval-pipeline again with different parameters"
echo "=========================================="
```

## Key Design Patterns

- **Uses `run-state.py`** for phase orchestration (`init-run`, `set-status` per phase).
- **Accepts `— difficulty:` and `— cost:` parameters**, passed through to task-gen.
- **Resumable** via `.eval/pipeline/state.json` — detects and resumes from last incomplete phase.
- **Each phase logs** to `LOG_FILE` (`.eval/pipeline/log.md`).
- **`HUMAN_CHECKPOINT` flag** for interactive mode with user confirmation at each stage.
- **`$EVAL_WIKI_SCRIPT` resolution chain** (Variant A — hard-fail).
- **References `shared-references/`** contracts for output versioning, effort/cost, etc.
- **All phases are DRIVE role** — the pipeline orchestrator drives execution directly.
- **Output versioning**: Report files are written with timestamped copies plus a `-latest` symlink, per `shared-references/output-versioning.md`.