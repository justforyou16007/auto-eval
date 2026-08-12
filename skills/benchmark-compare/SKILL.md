---
name: benchmark-compare
description: 'Benchmark quality evaluation orchestrator. Dispatches ACQUIT sub-agents for scorecard evaluation (arxiv 2411.12990) and quantitative metric evaluation (arxiv 2601.03986). Supports comparison mode (with baseline) and standalone evaluation (auto-search top-3 similar benchmarks).'
argument-hint: "[--baseline <path>] [--benchmark <path>] [--domain <capability-domain>]"
allowed-tools: Bash(*), Read, Write, Edit, Grep, Glob, WebSearch, WebFetch
role: DRIVE
depends-on: [eval-wiki, scorecard-evaluator, benchmark2-evaluator, benchmark-search]
produces: [benchmark-quality-report]
---

# benchmark-compare Skill

## Overview

**DRIVE orchestrator** for benchmark quality evaluation. Per issue #9, the
previous implementation used generic shell commands (`grep`, file-existence
checks, 3/5 neutral defaults) that could not distinguish between different
benchmarks. This skill is now a pure **sub-agent dispatcher**: it delegates
the actual evaluation to dedicated **ACQUIT sub-skills** that judge using
criteria strictly derived from the cited papers.

> **The orchestrator never judges directly.** It dispatches, collects,
> aggregates, and writes results. All scoring dimensions and quantitative
> metrics are owned by the ACQUIT sub-agents, not by this orchestrator.

### Architecture

```
benchmark-compare (DRIVE orchestrator — delegates, never judges directly)
  |
  +- Mode A: Comparison (--baseline <path>)
  |   +- Dispatch scorecard-evaluator (ACQUIT) for six-dimension scorecard
  |   |   comparing baseline vs new benchmark on each of 6 dimensions
  |   +- Dispatch benchmark2-evaluator (ACQUIT) for three quantitative metrics
  |   |   comparing baseline vs new benchmark rankings
  |   +- Aggregate results -> HTML report
  |
  +- Mode B: Standalone (no baseline)
      +- Phase 1: Dispatch benchmark-search (DRIVE) -> web search for publicly
      |   known benchmarks with similar capabilities/domain, select top-3
      +- Phase 2: For each top-3 benchmark, extract the subsets of
      |   tasks/envs/rubrics that overlap with the auto-eval benchmark's domain
      +- Phase 3: For each top-3 benchmark's similar subset, dispatch
      |   scorecard-evaluator + benchmark2-evaluator (ACQUIT) comparing the
      |   similar subset vs the auto-eval benchmark
      +- Aggregate (average across top-3) -> HTML report
```

## Helper Resolution

Resolve `$EVAL_WIKI_SCRIPT` via the shared chain (Variant A — hard fail):

```bash
cd "$(git rev-parse --show-toplevel 2>/dev/null || pwd)" || exit 1
EVAL_REPO="${EVAL_REPO:-$(awk -F'\t' '$1=="repo_root"{print $2; exit}' .eval/installed-skills.txt 2>/dev/null)}"
EVAL_WIKI_SCRIPT=".eval/dist/tools/eval-wiki.py"
[ -f "$EVAL_WIKI_SCRIPT" ] || EVAL_WIKI_SCRIPT="dist/tools/eval-wiki.py"
[ -f "$EVAL_WIKI_SCRIPT" ] || { [ -n "${EVAL_REPO:-}" ] && EVAL_WIKI_SCRIPT="$EVAL_REPO/dist/tools/eval-wiki.py"; }
if [ ! -f "$EVAL_WIKI_SCRIPT" ]; then
    echo "ERROR: eval-wiki.py not found. Run 'tools/install_eval_wiki.sh' first." >&2
    exit 1
fi
```

Resolve `$SKILLS_DIR` for sub-skill delegation:

```bash
SKILLS_DIR=".claude/skills"
[ -d "$SKILLS_DIR" ] || SKILLS_DIR="skills"
```

## Constants

| Constant | Value | Description |
|----------|-------|-------------|
| `REPORT_DIR` | `reports/` | Benchmark-quality report output directory |
| `TOP_N` | 3 | Number of similar benchmarks for standalone mode |

## Phase 1: Mode Detection

Detect whether a baseline is provided. If `--baseline <path>` is present,
select **Mode A (Comparison)**. Otherwise select **Mode B (Standalone)**.

```bash
BENCHMARK_PATH="${BENCHMARK:-}"
BASELINE_PATH="${BASELINE:-}"
DOMAIN="${DOMAIN:-}"

if [ -n "$BASELINE_PATH" ]; then
    MODE="A"   # Comparison mode (with baseline)
else
    MODE="B"   # Standalone mode (auto-search top-3)
fi
echo "benchmark-compare: Mode $MODE"
```

## Phase 2: Dispatch

### Mode A — Comparison (with --baseline)

In comparison mode, directly dispatch the two ACQUIT sub-agents to compare the
baseline benchmark vs the new benchmark. The orchestrator passes **raw
benchmark data** (task files, scenario definitions, rubric criteria, run
results, score data) to each sub-agent — never its own self-assessment.

#### 2a. Dispatch scorecard-evaluator (ACQUIT)

Dispatch the `scorecard-evaluator` sub-agent to evaluate the six BetterBench
dimensions (arxiv 2411.12990) across the baseline vs new benchmark.

```bash
# Dispatch scorecard-evaluator sub-agent with raw benchmark data.
# The sub-agent judges each of the 6 dimensions 0-5 with evidence-backed
# justifications (Properties, Grounding Levels, Metric Assumptions,
# Validation Evidence, Gaming Risks, Known Failure Cases).
# This is a cross-model ACQUIT evaluation — the orchestrator does NOT judge.
SCORECARD_VERDICT=$(dispatch sub-agent scorecard-evaluator \
    --benchmark "$BENCHMARK_PATH" \
    --baseline "$BASELINE_PATH" \
    --candidate "comparison" || echo "N/A")
```

#### 2b. Dispatch benchmark2-evaluator (ACQUIT)

Dispatch the `benchmark2-evaluator` sub-agent to evaluate the three
quantitative Benchmark2 metrics (arxiv 2601.03986) comparing baseline vs new
benchmark rankings.

```bash
# Dispatch benchmark2-evaluator sub-agent with raw run/score data.
# The sub-agent computes/judges CBRC (Kendall tau), DS, and CAD (model family
# hierarchy) using the literal paper definitions — the orchestrator does NOT
# compute metrics itself.
METRIC_VERDICT=$(dispatch sub-agent benchmark2-evaluator \
    --benchmark "$BENCHMARK_PATH" \
    --baseline "$BASELINE_PATH" \
    --candidate "comparison" || echo "N/A")
```

### Mode B — Standalone (no baseline)

In standalone mode, first dispatch `benchmark-search` to find top-3 similar
benchmarks, then for each candidate extract the overlapping subset and
dispatch the two ACQUIT evaluators.

#### 2c. Dispatch benchmark-search (DRIVE)

Dispatch the `benchmark-search` sub-agent to find publicly known benchmarks
with similar capabilities/domain, and return top-3.

```bash
# Dispatch benchmark-search sub-agent (DRIVE) — web search for similar
# benchmarks, return top-3 with metadata + similarity rationale.
dispatch sub-agent benchmark-search \
    --benchmark "$BENCHMARK_PATH" \
    --domain "$DOMAIN" \
    --top 3
```

#### 2d. Extract similar subsets

For each top-3 candidate, extract the subsets of tasks/envs/rubrics that
overlap with the auto-eval benchmark's domain. (Read the candidate's metadata
from `benchmark-search` output.)

```bash
# For each top-3 candidate, extract the overlapping subset of tasks/envs/
# rubrics that match the auto-eval benchmark's domain.
CANDIDATES=$(jq -r '.top_3[].name' \
    "${BENCHMARK_PATH}/candidates/top-3.json" 2>/dev/null)
```

#### 2e. Dispatch evaluators for each top-3 candidate

For each top-3 candidate's similar subset, dispatch both ACQUIT evaluators
comparing the similar subset vs the auto-eval benchmark.

```bash
for CANDIDATE in $CANDIDATES; do
    # Dispatch scorecard-evaluator for this candidate (ACQUIT, cross-model)
    dispatch sub-agent scorecard-evaluator \
        --benchmark "$BENCHMARK_PATH" \
        --candidate "$CANDIDATE" || echo "N/A: $CANDIDATE (scorecard)"
    # Dispatch benchmark2-evaluator for this candidate (ACQUIT, cross-model)
    dispatch sub-agent benchmark2-evaluator \
        --benchmark "$BENCHMARK_PATH" \
        --candidate "$CANDIDATE" || echo "N/A: $CANDIDATE (metrics)"
done
```

## Phase 3: Aggregate

Collect all sub-agent verdicts from both evaluators. For **Mode B**, compute
composite scores by averaging across the top-3 candidates. The orchestrator
performs only aggregation (averaging/collecting) — it does not define scoring
criteria.

```bash
# Collect sub-agent verdicts from eval-wiki feedback records.
# Mode A: aggregate the single scorecard + metric verdicts.
# Mode B: average the scorecard + metric verdicts across the top-3 candidates.
# Sub-agents that returned N/A are excluded from the average (graceful degrade).
COMPOSITE_SCORECARD=$(aggregate scorecard verdicts | average)
COMPOSITE_METRICS=$(aggregate metric verdicts | average)
```

### Generate HTML Report

Generate a single-page HTML benchmark-quality report aggregating all sub-agent
verdicts.

```bash
TIMESTAMP=$(date -u +"%Y%m%dT%H%M%SZ")
REPORT_FILE="reports/benchmark-quality-${TIMESTAMP}.html"
mkdir -p reports

# Build the HTML report from aggregated sub-agent verdicts.
# The report shows: mode (A/B), per-dimension scorecard scores (0-5) with
# evidence-backed justifications, the three Benchmark2 metrics (CBRC/DS/CAD)
# with interpretation thresholds, and per-candidate breakdown for Mode B.
cat > "$REPORT_FILE" <<HTMLEOF
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Benchmark Quality Report</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, sans-serif; max-width: 1100px; margin: 2em auto; padding: 0 1em; color: #333; }
        h1 { border-bottom: 2px solid #eee; padding-bottom: 0.5em; }
        table { border-collapse: collapse; width: 100%; margin: 1em 0; }
        th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
        th { background: #f5f5f5; }
        .summary { background: #f9f9f9; padding: 1em; border-radius: 4px; }
        .na { color: #999; font-style: italic; }
        footer { margin-top: 3em; padding-top: 1em; border-top: 1px solid #eee; font-size: 0.9em; color: #666; }
    </style>
</head>
<body>
    <h1>Benchmark Quality Report</h1>
    <div class="summary">
        <p><strong>Date:</strong> ${TIMESTAMP}</p>
        <p><strong>Mode:</strong> ${MODE} (${MODE_DESC})</p>
        <p><strong>Scorecard (BetterBench 2411.12990):</strong> ${COMPOSITE_SCORECARD}</p>
        <p><strong>Metrics (Benchmark2 2601.03986):</strong> ${COMPOSITE_METRICS}</p>
    </div>
    <h2>Scorecard Dimensions (ACQUIT: scorecard-evaluator)</h2>
    <table>
        <tr><th>Dimension</th><th>Stage</th><th>Score (0-5)</th><th>Evidence</th></tr>
        SCORECARD_ROWS_PLACEHOLDER
    </table>
    <h2>Quantitative Metrics (ACQUIT: benchmark2-evaluator)</h2>
    <table>
        <tr><th>Metric</th><th>Value</th><th>Interpretation</th></tr>
        METRIC_ROWS_PLACEHOLDER
    </table>
    <footer>
        <p><em>Generated by benchmark-compare orchestrator (delegates to ACQUIT sub-agents).</em></p>
    </footer>
</body>
</html>
HTMLEOF
cp "$REPORT_FILE" "reports/benchmark-quality-latest.html"
echo "Report: $REPORT_FILE"
```

## Phase 4: Write

Record results to eval-wiki. For each dimension/metric, add a feedback entity
with scores and evidence so the pipeline can gate on the benchmark quality.

```bash
# Record aggregated scorecard verdict (from scorecard-evaluator sub-agent)
python3 "$EVAL_WIKI_SCRIPT" add-feedback eval-wiki/ \
    --target-type benchmark \
    --target-id "${BENCHMARK_PATH}" \
    --from "benchmark-compare" \
    --issue-type "scorecard" \
    --description "composite scorecard: ${COMPOSITE_SCORECARD}" \
    --action "aggregate" \
    --status "recorded"

# Record aggregated metric verdict (from benchmark2-evaluator sub-agent)
python3 "$EVAL_WIKI_SCRIPT" add-feedback eval-wiki/ \
    --target-type benchmark \
    --target-id "${BENCHMARK_PATH}" \
    --from "benchmark-compare" \
    --issue-type "quantitative-metrics" \
    --description "composite metrics: ${COMPOSITE_METRICS}" \
    --action "aggregate" \
    --status "recorded"

echo "benchmark-compare: results recorded to eval-wiki"
```

## Fan-Out + Degrade

Per `fan-out-pattern.md`, the orchestrator dispatches sub-agents in parallel
with **graceful degradation**. If a single sub-agent or a single top-3
candidate fails, the orchestrator records that result as **N/A** and continues
with the remaining sub-agents/candidates. The aggregate phase excludes N/A
results from averages.

```bash
# If a sub-agent dispatch returns non-zero, record N/A and continue.
# The aggregate phase excludes N/A results from averages.
```

## No Inline Scoring

> **Critical design constraint.** This orchestrator does **not** perform
> evaluation directly. It contains **no grep-based scoring of tasks**, no
> file-existence-check scoring, and no hardcoded neutral 3/5 defaults. All
> scoring dimensions (the six BetterBench dimensions, arxiv 2411.12990) and
> all quantitative metrics (CBRC/DS/CAD, arxiv 2601.03986) are owned by the
> ACQUIT sub-agents (`scorecard-evaluator`, `benchmark2-evaluator`). The
> orchestrator only dispatches, collects, aggregates (averages), and writes
> results.

## References

- `shared-references/acceptance-gate.md` — DRIVE vs ACQUIT, cross-model
- `shared-references/reviewer-independence.md` — raw-data-only rule
- `shared-references/fan-out-pattern.md` — parallel dispatch + degrade
- `shared-references/skill-governance.md` — sub-agent dispatch pattern
- Papers: BetterBench (arxiv 2411.12990), Benchmark2 (arxiv 2601.03986)
