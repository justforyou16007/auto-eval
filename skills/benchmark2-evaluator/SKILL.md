---
name: benchmark2-evaluator
description: 'ACQUIT sub-agent for quantitative benchmark evaluation using three metrics from Benchmark2 (arxiv 2601.03986): Cross-Benchmark Ranking Consistency (CBRC, Kendall tau), Discriminability Score (DS), and Capability Alignment Deviation (CAD, model family hierarchy). Cross-model required. Dispatched by benchmark-compare; never generates artifacts itself.'
argument-hint: "[--benchmark <path>] [--baseline <path>] [--candidate <name>]"
allowed-tools: Bash(*), Read, Write, Edit, Grep, Glob
role: ACQUIT
depends-on: [eval-wiki, benchmark-compare]
produces: [metric-verdict]
audits: [benchmark-compare]
cross-model-required: true
---

# benchmark2-evaluator Skill

## Overview

**ACQUIT sub-agent** dispatched by the `benchmark-compare` orchestrator. It
evaluates benchmark quality using three **quantitative metrics** defined in the
paper "Benchmark2: Systematic Evaluation of LLM Benchmarks"
(**arxiv 2601.03986**). Each metric has a **formal definition** and
**interpretation thresholds** taken literally from the paper — the sub-agent
must apply these definitions, **not invent its own**.

This sub-agent **never generates** benchmark artifacts. It only reads **raw
benchmark data** (run results, score data, model rankings) and computes/judges
the three metrics. Because it is an ACQUIT role, it MUST run on a **different
model family** than the one that produced the benchmark, per
`acceptance-gate.md` and `reviewer-independence.md`.

### Reviewer Independence (critical)

Per `reviewer-independence.md`, this ACQUIT sub-agent receives only **raw
benchmark data** — task files, scenario definitions, run results, and score
data. It must **never** receive the DRIVE worker's self-assessment, commentary,
or explanation of its own work.

## Helper Resolution

Resolve `$EVAL_WIKI_SCRIPT` via the shared chain (Variant B — warn + skip):

```bash
cd "$(git rev-parse --show-toplevel 2>/dev/null || pwd)" || exit 1
EVAL_REPO="${EVAL_REPO:-$(awk -F'\t' '$1=="repo_root"{print $2; exit}' .eval/installed-skills.txt 2>/dev/null)}"
EVAL_WIKI_SCRIPT=".eval/dist/tools/eval-wiki.py"
[ -f "$EVAL_WIKI_SCRIPT" ] || EVAL_WIKI_SCRIPT="dist/tools/eval-wiki.py"
[ -f "$EVAL_WIKI_SCRIPT" ] || { [ -n "${EVAL_REPO:-}" ] && EVAL_WIKI_SCRIPT="$EVAL_REPO/dist/tools/eval-wiki.py"; }
if [ ! -f "$EVAL_WIKI_SCRIPT" ]; then
    echo "WARNING: eval-wiki.py not found. Skipping eval-wiki read." >&2
fi
```

## The Three Metrics (Benchmark2, arxiv 2601.03986)

The sub-agent must apply the following **literal paper definitions**. Do not
invent alternative definitions.

| # | Metric | Paper Definition (literal) | Interpretation Thresholds (from paper) |
|---|--------|----------------------------|---------------------------------------|
| 1 | Cross-Benchmark Ranking Consistency (CBRC) | CBRC(B_i) = (1/(n-1)) * sum_{j≠i} tau(r_i, r_j) — average Kendall's tau correlation between the rankings induced by benchmark B_i and every other benchmark B_j in the same domain | >0.7 = high consistency; 0.4–0.7 = moderate; <0.4 = low (paper section 3.1) |
| 2 | Discriminability Score (DS) | DS(B_i) = (sigma_i / s_bar_i) * sqrt( sum_{j<k} 1[\|s_ij - s_ik\| > epsilon] / (m(m-1)/2) ) — normalized score spread multiplied by the proportion of model pairs with practically significant score differences | Higher = better at differentiating between models (paper section 3.2). The paper states "DS alone maximizes discriminability" |
| 3 | Capability Alignment Deviation (CAD) | Identifies problematic instances where stronger models fail but weaker models succeed within the same model family. Uses model family hierarchy for comparison | Lower deviation = better alignment. The paper states "CAD alone provides good stability" and identifies "problematic instances" (paper section 3.3) |

> **Key paper principle.** The CAD metric specifically uses a **Model Family
> Hierarchy** (paper section 3.3) — models are grouped into families (e.g.,
> GPT-4 family, Claude family, Llama family). CAD finds cases where a
> larger/stronger model in a family fails on an item that a smaller/weaker
> model in the same family passes. This reveals benchmark items that do **not**
> reflect true capability ordering. The sub-agent must describe this
> hierarchy-based comparison logic explicitly, per the paper's Definition and
> Interpretation.

### Metric 1 — Cross-Benchmark Ranking Consistency (CBRC) (paper section 3.1)

**Definition (literal):**

```
CBRC(B_i) = (1/(n-1)) * sum_{j≠i} tau(r_i, r_j)
```

where `tau(r_i, r_j)` is the **Kendall's tau** rank correlation between the
ranking of models induced by benchmark `B_i` and the ranking induced by
benchmark `B_j`, averaged over all other benchmarks `B_j` in the same domain
(`n` = number of benchmarks in the domain).

**Interpretation thresholds (from paper section 3.1):**

- **>0.7** = high consistency
- **0.4–0.7** = moderate consistency
- **<0.4** = low consistency

The sub-agent computes (or estimates from available run data) the Kendall's
tau between the benchmark under evaluation and each other benchmark in the
same domain, averages them, and classifies the result using the thresholds
above.

### Metric 2 — Discriminability Score (DS) (paper section 3.2)

**Definition (literal):**

```
DS(B_i) = (sigma_i / s_bar_i) * sqrt( sum_{j<k} 1[|s_ij - s_ik| > epsilon] / (m(m-1)/2) )
```

where:

- `sigma_i` = standard deviation of scores on benchmark `B_i`
- `s_bar_i` = mean score on benchmark `B_i`
- `s_ij`, `s_ik` = scores of model `j` and model `k` on benchmark `B_i`
- `1[|s_ij - s_ik| > epsilon]` = indicator that the score difference exceeds a
  practically significant threshold `epsilon`
- `m` = number of models
- the inner sum is over all model pairs `j < k`

This is the **normalized score spread** (`sigma_i / s_bar_i`) multiplied by the
**proportion of model pairs with practically significant score differences**.

**Interpretation (from paper section 3.2):** Higher DS = the benchmark is
better at differentiating between models. The paper states *"DS alone
maximizes discriminability."* The sub-agent reports the computed DS and judges
whether the benchmark discriminates well between models.

### Metric 3 — Capability Alignment Deviation (CAD) (paper section 3.3)

**Definition (literal):** CAD identifies **problematic instances** where
stronger models fail but weaker models succeed within the same **model family**.
It uses a **Model Family Hierarchy** for comparison.

**Model Family Hierarchy (paper section 3.3):** Models are grouped into
families (e.g., GPT-4 family, Claude family, Llama family). Within each family,
there is a known capability ordering (larger/stronger > smaller/weaker). CAD
finds cases where a larger/stronger model in a family **fails** on an item that
a smaller/weaker model in the same family **passes**. Such items do **not**
reflect true capability ordering and are flagged as problematic.

**Interpretation (from paper section 3.3):** Lower deviation = better
alignment (fewer problematic instances). The paper states *"CAD alone provides
good stability."* The sub-agent must:

1. Group models into families using the model family hierarchy.
2. Within each family, compare stronger-vs-weaker model performance per item.
3. Count items where the stronger model fails but the weaker model passes
   (problematic instances).
4. Report the deviation and flag the problematic instances.

## Phases

### Phase 0: Receive Dispatch + Raw Data

The `benchmark-compare` orchestrator dispatches this sub-agent with the
path(s) to the benchmark(s) under evaluation. Receive **raw benchmark data**
only:

```bash
BENCHMARK_PATH="${1:-}"
BASELINE_PATH="${BASELINE:-}"
CANDIDATE="${CANDIDATE:-}"

# Read raw benchmark data: run results, score data, model rankings.
# NEVER read the DRIVE worker's self-assessment.
RAW_FILES=()
if [ -n "$BENCHMARK_PATH" ] && [ -d "$BENCHMARK_PATH" ]; then
    RAW_FILES+=("$BENCHMARK_PATH")
fi
if [ -n "$BASELINE_PATH" ] && [ -d "$BASELINE_PATH" ]; then
    RAW_FILES+=("$BASELINE_PATH")
fi
```

### Phase 1: Read Raw Benchmark Data

Read the raw run results and score data directly.

```bash
for raw_dir in "${RAW_FILES[@]}"; do
    find "$raw_dir" -type f \( -name '*.json' -o -name '*.csv' \
        -o -name '*.md' -o -name '*.yaml' \) -print | head -200
done
```

### Phase 2: Compute / Judge the Three Metrics

For each metric, the cross-model reviewer applies the **literal paper
definition** above and records the value plus an interpretation using the
paper's thresholds.

```bash
# Metric 1: CBRC — average Kendall's tau against other same-domain benchmarks
#   thresholds: >0.7 high, 0.4-0.7 moderate, <0.4 low
# Metric 2: DS  — (sigma_i / s_bar_i) * sqrt( proportion of significant pairs )
#   interpretation: higher = better discriminability
# Metric 3: CAD — model family hierarchy comparison, count problematic instances
#   interpretation: lower deviation = better alignment
```

### Phase 3: Record Metric Verdict

Aggregate the three metric interpretations and record the verdict in eval-wiki
so the orchestrator can aggregate it.

```bash
if [ -f "$EVAL_WIKI_SCRIPT" ]; then
    python3 "$EVAL_WIKI_SCRIPT" add-feedback eval-wiki/ \
        --target-type benchmark \
        --target-id "${CANDIDATE:-benchmark}" \
        --from "benchmark2-evaluator" \
        --issue-type "quantitative-metrics" \
        --description "Benchmark2 metrics: CBRC=$CBRC DS=$DS CAD=$CAD" \
        --action "audit" \
        --status "$METRIC_STATUS"
fi
echo "benchmark2-evaluator verdict: CBRC=$CBRC DS=$DS CAD=$CAD"
```

## Cross-Model Requirement

This ACQUIT sub-agent MUST run on a **different model family** than the one
that produced the benchmark, per `acceptance-gate.md` Hard Invariant #1. The
reviewer-independence principle (`reviewer-independence.md`) requires that the
sub-agent receive only raw benchmark data, never the producer's
self-assessment. Record the verifying model family in the feedback record.

## Failure Handling (Degrade)

If this sub-agent cannot complete (insufficient run data for a metric,
reviewer unavailable), it records that metric as **N/A** and exits non-zero so
the orchestrator can degrade gracefully and continue with the other sub-agent,
per `fan-out-pattern.md`.

## Output

- `eval-wiki/feedback/benchmark2-evaluator-<timestamp>.md` — the three
  metric values (CBRC, DS, CAD) with paper-definition citations
  (arxiv 2601.03986) and interpretation thresholds.
- Exit code 0 (verdict recorded) / non-zero (degrade — N/A).

## References

- `shared-references/acceptance-gate.md` — ACQUIT role, cross-model invariant
- `shared-references/reviewer-independence.md` — raw-data-only rule
- `shared-references/fan-out-pattern.md` — parallel dispatch + degrade
- Paper: "Benchmark2: Systematic Evaluation of LLM Benchmarks"
  (arxiv 2601.03986)
