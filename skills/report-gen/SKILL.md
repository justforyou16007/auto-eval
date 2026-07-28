---
name: report-gen
description: 'Generate HTML verification report from eval-wiki data. DRIVE role. Use when user says "生成报告", "generate report", "验证报告", or wants to see verification results.'
argument-hint: "[wiki-root] [output-path]"
allowed-tools: Bash(*), Read, Write, Edit, Grep, Glob
role: DRIVE
depends-on: [eval-wiki, run]
produces: [report]
---

# report-gen Skill

## Overview

Reads all runs, rubrics, and tasks from eval-wiki and generates a
single-page HTML verification report. This is a DRIVE role skill — report
generation is mechanical/constructive.

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

### Phase 1: Collect Data

Collect all data from eval-wiki:

```bash
WIKI_ROOT="${1:-eval-wiki}"

# Get overview stats
if [ -f "$EVAL_WIKI_SCRIPT" ]; then
    STATS=$(python3 "$EVAL_WIKI_SCRIPT" stats "$WIKI_ROOT")
    echo "Wiki stats: $STATS"
fi

# Read all run files
for run_file in "$WIKI_ROOT"/runs/*.md; do
    [ -f "$run_file" ] && cat "$run_file"
done

# Read all rubric files
for rubric_file in "$WIKI_ROOT"/rubrics/*.md; do
    [ -f "$rubric_file" ] && cat "$rubric_file"
done

# Read all task files
for task_file in "$WIKI_ROOT"/tasks/*.md; do
    [ -f "$task_file" ] && cat "$task_file"
done
```

### Phase 2: Generate HTML Structure

Generate a single-page HTML report with the following structure:

- **Sidebar navigation**: Links to each task section via anchor
- **Overview section**: Stat cards
  - Total Tasks
  - Total Runs
  - Pass Rate (percentage)
  - Coverage (tasks with runs / total tasks)
- **Per-task section**: For each task:
  - Task title and metadata
  - Run results table (model, verdict, confidence, scores)
  - Rubric criteria with scores
  - Evidence links to raw output
- **Color coding**: 
  - Green (`#4caf50`) = PASS
  - Red (`#f44336`) = FAIL
  - Yellow (`#ff9800`) = inconclusive
- **Provenance**: Each score links to the raw output/evidence

### Phase 3: Write Report

Write the report to disk with versioning per `output-versioning.md`:

```bash
TIMESTAMP=$(date -u +"%Y%m%dT%H%M%SZ")
OUTPUT_DIR="${2:-reports}"
mkdir -p "$OUTPUT_DIR"

# Write versioned copy
cp "$REPORT_HTML" "$OUTPUT_DIR/report-${TIMESTAMP}.html"

# Write latest copy
cp "$REPORT_HTML" "$OUTPUT_DIR/report-latest.html"

echo "Report written to:"
echo "  $OUTPUT_DIR/report-${TIMESTAMP}.html"
echo "  $OUTPUT_DIR/report-latest.html"
```

## Output

- `reports/report-<timestamp>.html` — Versioned report
- `reports/report-latest.html` — Latest copy (fixed name)