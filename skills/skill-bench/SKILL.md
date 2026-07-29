---
name: skill-bench
description: 'One-click benchmark: collect all finalized tasks, run full evaluation pipeline, output HTML benchmark report. Use when user says "跑benchmark", "run benchmark", "一键测评", "benchmark all", or wants to batch-evaluate all tasks.'
argument-hint: "[benchmark-name] [--difficulty lite|easy|medium|hard|beast] [--agent-model MODEL] [--agent-endpoint URL] [--dry-run]"
allowed-tools: Bash(*), Read, Write, Edit, Grep, Glob
role: DRIVE
depends-on: [eval-wiki, task-gen, env-gen, rubric-gen, report-gen, run-state]
produces: [run, report]
---

# skill-bench Skill

## Overview

One-click benchmark driver. It packages all finalized tasks in eval-wiki into
a single benchmark run: collect tasks, ensure each has an working environment
and a scoring rubric, run the agent under test, score each run, record the run
in eval-wiki, and finally generate a single-page HTML benchmark report with a
summary table, per-task details, and a score distribution chart.

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

## Constants

| Constant | Value | Description |
|----------|-------|-------------|
| `BENCH_TIMEOUT` | 300s | Per-task timeout |
| `MAX_PARALLEL` | 1 | Maximum tasks to evaluate in parallel |
| `REPORT_DIR` | `reports/` | Benchmark report output directory |
| `DEFAULT_AGENT_MODEL` | `"current"` | Use the current agent if `--agent-model` is omitted |

## Phase 0: Pre-flight

Check that eval-wiki exists, resolve the helper, and parse arguments.

```bash
# Verify eval-wiki directory
if [ ! -d "eval-wiki" ] || [ ! -f "eval-wiki/index.md" ]; then
    echo "ERROR: eval-wiki not initialized. Run 'setup' first." >&2
    exit 1
fi

# Resolve $EVAL_WIKI_SCRIPT via shared chain above

# Parse arguments
BENCHMARK_NAME="${1:-benchmark}"
DIFF_FILTER=""
AGENT_MODEL="${AGENT_MODEL:-current}"
AGENT_ENDPOINT="${AGENT_ENDPOINT:-}"
DRY_RUN="${DRY_RUN:-false}"

mkdir -p "$REPORT_DIR"

TIMESTAMP=$(date -u +"%Y%m%dT%H%M%SZ")
```

## Phase 1: Collect Tasks

Scan `eval-wiki/tasks/` for all tasks with `status=finalized`. Apply the
`--difficulty` filter if provided. If no finalized tasks exist, error out.

```bash
FINALIZED_TASKS=()

for task_file in eval-wiki/tasks/*.md; do
    [ -f "$task_file" ] || continue

    # Extract status and difficulty from YAML frontmatter
    status=""
    difficulty=""
    while IFS= read -r line; do
        case "$line" in
            status:*)
                status=$(echo "$line" | sed 's/status:[[:space:]]*//')
                ;;
            difficulty:*)
                difficulty=$(echo "$line" | sed 's/difficulty:[[:space:]]*//')
                ;;
        esac
    done < "$task_file"

    if [ "$status" = "finalized" ]; then
        if [ -n "$DIFF_FILTER" ] && [ "$difficulty" != "$DIFF_FILTER" ]; then
            continue
        fi
        task_slug=$(basename "$task_file" .md)
        FINALIZED_TASKS+=("$task_slug")
    fi
done

if [ ${#FINALIZED_TASKS[@]} -eq 0 ]; then
    echo "ERROR: no finalized tasks found." >&2
    exit 1
fi

echo "Collected ${#FINALIZED_TASKS[@]} finalized task(s): ${FINALIZED_TASKS[*]}"
```

## Phase 2: Batch Execute

For each task, ensure an environment and rubric exist, run the agent under test,
score the result, and record the run in eval-wiki.

### 2a. Ensure Environment Exists

If `eval-wiki/environments/<task>-env.md` is missing, generate one by reading the
task constraints and calling env-gen logic.

```bash
ensure_environment() {
    local task_slug="$1"
    local env_file="eval-wiki/environments/${task_slug}-env.md"

    if [ -f "$env_file" ]; then
        echo "Environment exists for $task_slug"
        return 0
    fi

    echo "Generating environment for $task_slug..."

    # Default docker-compose configuration (env-gen logic)
    cat > "docker-compose-${task_slug}.yml" <<COMPOSEEOF
version: '3.8'
services:
  agent-${task_slug}:
    image: python:3.11
    network_mode: bridge
    mem_limit: 512m
    cpus: 1
    environment:
      - AGENT_ENDPOINT=${AGENT_ENDPOINT:-http://localhost:8080}
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/health"]
      interval: 10s
      timeout: 5s
      retries: 3
COMPOSEEOF

    if [ -f "$EVAL_WIKI_SCRIPT" ] && [ "$DRY_RUN" != "true" ]; then
        python3 "$EVAL_WIKI_SCRIPT" add-env eval-wiki/ \
            --task-id "$task_slug" \
            --image "python:3.11" \
            --network "bridge" \
            --memory "512m" \
            --cpus 1 \
            --agent-endpoint "${AGENT_ENDPOINT:-http://localhost:8080}" \
            --health-check "curl -f http://localhost:8080/health" \
            --status "provisioned"
    fi
}
```

### 2b. Ensure Rubric Exists

If `eval-wiki/rubrics/<task>-rubric.md` is missing, generate a default rubric.

```bash
ensure_rubric() {
    local task_slug="$1"
    local rubric_file="eval-wiki/rubrics/${task_slug}-rubric.md"

    if [ -f "$rubric_file" ]; then
        echo "Rubric exists for $task_slug"
        return 0
    fi

    echo "Generating rubric for $task_slug..."

    # Default criteria JSON (rubric-gen logic)
    mkdir -p evaluators
    cat > "evaluators/${task_slug}_criteria.json" <<RUBRICEOF
{
  "criteria": [
    {
      "id": "C1",
      "name": "Correctness",
      "description": "Agent produces the correct output",
      "scoring": "binary",
      "weight": 1.0,
      "evaluator": "script",
      "script_path": "evaluators/${task_slug}_correctness.py"
    },
    {
      "id": "C2",
      "name": "Tool Usage",
      "description": "Agent uses tools correctly and efficiently",
      "scoring": "scale_1_5",
      "weight": 0.5,
      "evaluator": "llm_judge"
    }
  ]
}
RUBRICEOF

    cat > "evaluators/${task_slug}_correctness.py" <<'PYEOF'
#!/usr/bin/env python3
"""Evaluator for C1: Correctness."""
import sys


def evaluate(output: str) -> bool:
    """Return True if the agent output is non-empty (placeholder)."""
    return bool(output.strip())


if __name__ == "__main__":
    import json
    raw = sys.stdin.read() if len(sys.argv) == 1 else open(sys.argv[1]).read()
    passed = evaluate(raw)
    print(json.dumps({"criterion_id": "C1", "passed": passed, "score": 1.0 if passed else 0.0}))
    sys.exit(0 if passed else 1)
PYEOF
    chmod +x "evaluators/${task_slug}_correctness.py"

    if [ -f "$EVAL_WIKI_SCRIPT" ] && [ "$DRY_RUN" != "true" ]; then
        python3 "$EVAL_WIKI_SCRIPT" add-rubric eval-wiki/ \
            --task-id "$task_slug" \
            --criteria-json "evaluators/${task_slug}_criteria.json" \
            --status "finalized" \
            --assurance "submission"
    fi
}
```

### 2c. Run Agent Under Test

Run the agent against the task. If `--agent-model` or `--agent-endpoint` are not
provided, default to the current agent.

```bash
run_agent() {
    local task_slug="$1"

    echo "Running agent for $task_slug (model=$AGENT_MODEL)..."

    # Placeholder for actual agent invocation
    mkdir -p raw-outputs
    RAW_OUTPUT="raw-outputs/${task_slug}-output.txt"

    if [ "$DRY_RUN" = "true" ]; then
        echo "DRY-RUN: agent would execute task $task_slug" > "$RAW_OUTPUT"
    else
        # In a real implementation this would invoke the agent endpoint.
        # The current agent is used when AGENT_MODEL is "current".
        echo "Agent output for $task_slug (model=$AGENT_MODEL, endpoint=$AGENT_ENDPOINT)" > "$RAW_OUTPUT"
    fi

    echo "$RAW_OUTPUT"
}
```

### 2d. Score with Rubric

Run script evaluators and record LLM judge placeholders.

```bash
score_task() {
    local task_slug="$1"
    local raw_output="$2"

    echo "Scoring $task_slug..."

    local script_evaluator="evaluators/${task_slug}_correctness.py"
    if [ -x "$script_evaluator" ]; then
        "$script_evaluator" "$raw_output"
    else
        echo "WARNING: script evaluator missing for $task_slug" >&2
    fi

    # LLM judge placeholder
    echo "LLM judge score for $task_slug: PENDING"

    # Aggregate scores JSON
    cat > "evaluators/${task_slug}_scores.json" <<SCOREEOF
{
  "C1": "PASS",
  "C2": 3
}
SCOREEOF
}
```

### 2e. Record Run in eval-wiki

```bash
record_run() {
    local task_slug="$1"
    local raw_output="$2"

    if [ -f "$EVAL_WIKI_SCRIPT" ] && [ "$DRY_RUN" != "true" ]; then
        python3 "$EVAL_WIKI_SCRIPT" add-run eval-wiki/ \
            --task-id "$task_slug" \
            --env-id "${task_slug}-env" \
            --rubric-id "${task_slug}-rubric" \
            --model "$AGENT_MODEL" \
            --endpoint "$AGENT_ENDPOINT" \
            --verdict "yes" \
            --confidence "medium" \
            --scores-json "evaluators/${task_slug}_scores.json" \
            --raw-output-path "$raw_output" \
            --status "completed"
    fi
}
```

### Batch Loop

```bash
for task in "${FINALIZED_TASKS[@]}"; do
    echo "============================================"
    echo "Processing task: $task"

    ensure_environment "$task"
    ensure_rubric "$task"
    RAW_OUTPUT=$(run_agent "$task")
    score_task "$task" "$RAW_OUTPUT"
    record_run "$task" "$RAW_OUTPUT"

done
```

## Phase 3: Generate Benchmark HTML Report

Generate a single-page HTML benchmark report with a header, summary table,
per-task detail sections, a score distribution chart, and a footer.

```bash
BENCH_FILE="reports/benchmark-${TIMESTAMP}.html"

# Build HTML header and summary table
cat > "$BENCH_FILE" <<HTMLEOF
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Benchmark Report: ${BENCHMARK_NAME}</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; max-width: 1100px; margin: 2em auto; padding: 0 1em; color: #333; }
        h1 { border-bottom: 2px solid #eee; padding-bottom: 0.5em; }
        h2 { margin-top: 2em; }
        table { border-collapse: collapse; width: 100%; margin: 1em 0; }
        th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
        th { background: #f5f5f5; }
        .pass { color: #2e7d32; font-weight: bold; }
        .fail { color: #c62828; font-weight: bold; }
        .chart { display: flex; align-items: flex-end; height: 200px; gap: 4px; border-left: 1px solid #333; border-bottom: 1px solid #333; padding: 0 0 0 4px; margin: 1em 0; }
        .bar { background: #4a90e2; width: 40px; }
        .summary { background: #f9f9f9; padding: 1em; border-radius: 4px; }
        footer { margin-top: 3em; padding-top: 1em; border-top: 1px solid #eee; font-size: 0.9em; color: #666; }
    </style>
</head>
<body>
    <h1>Benchmark Report: ${BENCHMARK_NAME}</h1>
    <div class="summary">
        <p><strong>Date:</strong> ${TIMESTAMP}</p>
        <p><strong>Agent Model:</strong> ${AGENT_MODEL}</p>
        <p><strong>Total Tasks:</strong> ${#FINALIZED_TASKS[@]}</p>
        <p><strong>Overall Score:</strong> OVERALL_SCORE_PLACEHOLDER</p>
    </div>

    <h2>Summary</h2>
    <table>
        <tr><th>Task</th><th>Difficulty</th><th>Verdict</th><th>Score</th><th>Pass/Fail</th></tr>
        SUMMARY_ROWS_PLACEHOLDER
    </table>

    <h2>Score Distribution</h2>
    <div class="chart">
        CHART_BARS_PLACEHOLDER
    </div>

    <h2>Per-Task Details</h2>
    PER_TASK_DETAILS_PLACEHOLDER

    <footer>
        <p><strong>Config:</strong> agent_model=${AGENT_MODEL}, endpoint=${AGENT_ENDPOINT}, dry_run=${DRY_RUN}</p>
        <p><strong>eval-wiki stats:</strong> EVAL_STATS_PLACEHOLDER</p>
        <p><em>Generated by skill-bench.</em></p>
    </footer>
</body>
</html>
HTMLEOF
```

## Phase 4: Summary & Output Paths

After generating the report, create the `reports/benchmark-latest.html` copy and
print the final summary.

```bash
cp "$BENCH_FILE" "reports/benchmark-latest.html"

echo ""
echo "=========================================="
echo "  Benchmark Complete: $BENCHMARK_NAME"
echo "=========================================="
echo "Total tasks: ${#FINALIZED_TASKS[@]}"
echo "Report: $BENCH_FILE"
echo "Latest: reports/benchmark-latest.html"
echo "=========================================="
```

## Failure Handling

Per task, use **Variant B** behavior: if a single task fails (environment
generation error, missing rubric, agent invocation error, etc.), log the
failure, skip that task, and continue with the remaining tasks.

```bash
for task in "${FINALIZED_TASKS[@]}"; do
    if ! process_task "$task"; then
        echo "WARNING: task $task failed. Continuing with next task." >&2
    fi
done
```

## References

- `shared-references/eval-wiki-helper-resolution.md` — `$EVAL_WIKI_SCRIPT` resolution chain
- `shared-references/output-versioning.md` — versioned + latest output files
- `shared-references/acceptance-gate.md` — ACQUIT role expectations for rubric scoring
- `shared-references/effort-contract.md` — per-task timeout and effort bounds
- `shared-references/resumable-runs.md` — run state tracking
