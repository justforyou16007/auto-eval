---
name: scorecard-evaluator
description: 'ACQUIT sub-agent for benchmark quality scorecard evaluation across six dimensions from BetterBench (arxiv 2411.12990). Reads raw benchmark data and judges each dimension 0-5 with evidence-backed justifications. Cross-model required. Dispatched by benchmark-compare; never generates artifacts itself.'
argument-hint: "[--benchmark <path>] [--baseline <path>] [--candidate <name>]"
allowed-tools: Bash(*), Read, Write, Edit, Grep, Glob
role: ACQUIT
depends-on: [eval-wiki, benchmark-compare]
produces: [scorecard-verdict]
audits: [benchmark-compare]
cross-model-required: true
---

# scorecard-evaluator Skill

## Overview

**ACQUIT sub-agent** dispatched by the `benchmark-compare` orchestrator. It
evaluates benchmark quality across **six dimensions** defined in the paper
"BetterBench: Assessing AI Benchmarks" (**arxiv 2411.12990**). The BetterBench
paper defines 46 best practices across a benchmark lifecycle and organises
them into four lifecycle stages (J.1 Benchmark Design, J.2 Benchmark
Implementation, J.3 Benchmark Documentation, J.4 Benchmark Maintenance).

This sub-agent **never generates** benchmark artifacts. It only **reads raw
benchmark data** and judges each dimension on a **0–5 scale** with
**evidence-backed justifications**. Because it is an ACQUIT role, it MUST run
on a **different model family** than the one that produced/curated the
benchmark, per `acceptance-gate.md` and `reviewer-independence.md`.

### Reviewer Independence (critical)

Per `reviewer-independence.md`, this ACQUIT sub-agent receives only **raw
benchmark data** — task files, scenario definitions, rubric criteria, run
results, and score data. It must **never** receive the DRIVE worker's
self-assessment, commentary, or explanation of its own work. The sub-agent
judges the artifact, not the agent's claims about the artifact.

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

## The Six Dimensions (BetterBench, arxiv 2411.12990)

Each dimension maps to a lifecycle stage (J.1–J.4) and the specific
best-practice items the BetterBench paper defines for that stage. The
sub-agent must judge the dimension using these criteria — it must **not**
invent its own. Quote paper language is used to anchor each check.

| # | Dimension | Lifecycle Stage | What the sub-agent judges |
|---|-----------|-----------------|--------------------------|
| 1 | Properties | J.1 Benchmark Design | Are benchmark properties clearly defined? Purpose, scope, target capabilities, domain boundaries. Does the benchmark document normative assumptions and discuss limitations? |
| 2 | Grounding Levels | J.1 Benchmark Design | How deeply is the benchmark grounded in real-world tasks? Are tasks derived from actual use cases or synthetic? Does the benchmark specify the grounding rationale? |
| 3 | Metric Assumptions | J.2 Benchmark Implementation | Are evaluation metrics well-defined? Are scoring functions documented with threshold rationale? Does the benchmark use appropriate statistical methods? |
| 4 | Validation Evidence | J.2 Benchmark Implementation | Has the benchmark been validated? Are there held-out validation results? Are results reproducible with provided scripts/environments? Is there evidence the benchmark measures what it claims? |
| 5 | Gaming Risks | J.3 Benchmark Documentation | Can the benchmark be gamed? Are there documented mitigation strategies against overfitting, data leakage, or prompt engineering exploits? Does the scoring prevent shortcut solutions? |
| 6 | Known Failure Cases | J.4 Benchmark Maintenance | Are failure modes documented? Is there a feedback channel? Does the benchmark clearly state retirement status if unmaintained? Are edge cases and limitations disclosed? |

> **Key paper principle.** The BetterBench paper (arxiv 2411.12990) defines
> assessment criteria across lifecycle stages: **Design** then
> **Implementation** then **Documentation** then **Maintenance**. Each
> dimension's instructions below reference which lifecycle stage(s) the
> dimension belongs to and the specific best-practice items defined in that
> section. The paper states developers should *"document normative
> assumptions about benchmark properties and discuss the limitations of
> their benchmark."*

### Dimension 1 — Properties (J.1 Benchmark Design)

Judge whether the benchmark's **properties** are clearly defined:

- **Purpose** — is there a clear statement of what the benchmark measures?
- **Scope** — are the target capabilities and domain boundaries explicit?
- **Normative assumptions** — does the benchmark document its normative
  assumptions about benchmark properties? The paper states developers should
  *"document normative assumptions about benchmark properties and discuss the
  limitations of their benchmark."*
- **Limitations** — are the limitations of the benchmark discussed?

Score 0–5: 5 = all properties clearly defined with normative assumptions and
limitations; 0 = no properties documented.

### Dimension 2 — Grounding Levels (J.1 Benchmark Design)

Judge how deeply the benchmark is **grounded in real-world tasks**:

- Are tasks derived from **actual use cases** or are they **synthetic**?
- Does the benchmark specify the **grounding rationale** (why these tasks
  represent the target capability)?
- Are the grounding levels consistent across the benchmark?

Score 0–5: 5 = all tasks grounded in real-world use cases with rationale; 0 =
purely synthetic with no grounding rationale.

### Dimension 3 — Metric Assumptions (J.2 Benchmark Implementation)

Judge whether **evaluation metrics** are well-defined:

- Are scoring functions **documented** with threshold rationale?
- Does the benchmark use **appropriate statistical methods**?
- Are metric assumptions (e.g., what a "pass" means) explicit?

Score 0–5: 5 = metrics fully documented with rationale and statistical
methods; 0 = no metric documentation.

### Dimension 4 — Validation Evidence (J.2 Benchmark Implementation)

Judge whether the benchmark has been **validated**:

- Are there **held-out validation results**?
- Are results **reproducible** with provided scripts/environments?
- Is there **evidence the benchmark measures what it claims**?

Score 0–5: 5 = held-out validation + reproducible scripts + construct evidence;
0 = no validation evidence.

### Dimension 5 — Gaming Risks (J.3 Benchmark Documentation)

Judge whether the benchmark can be **gamed**:

- Are there documented **mitigation strategies** against overfitting, data
  leakage, or prompt engineering exploits?
- Does the **scoring prevent shortcut solutions**?
- Are gaming risks acknowledged and addressed in documentation?

Score 0–5: 5 = gaming risks documented with mitigation strategies and
shortcut-resistant scoring; 0 = no gaming-risk analysis.

### Dimension 6 — Known Failure Cases (J.4 Benchmark Maintenance)

Judge whether **failure modes** are documented:

- Are **failure modes** documented?
- Is there a **feedback channel** for reporting issues?
- Does the benchmark clearly state **retirement status** if unmaintained?
- Are **edge cases and limitations disclosed**?

Score 0–5: 5 = failure cases documented + feedback channel + maintenance status
clear; 0 = no failure/maintenance documentation.

## Phases

### Phase 0: Receive Dispatch + Raw Data

The `benchmark-compare` orchestrator dispatches this sub-agent with the path(s)
to the benchmark(s) under evaluation. Receive **raw benchmark data** only:

```bash
BENCHMARK_PATH="${1:-}"
BASELINE_PATH="${BASELINE:-}"
CANDIDATE="${CANDIDATE:-}"

# Read raw benchmark data: task files, scenario definitions, rubric criteria,
# run results, and score data. NEVER read the DRIVE worker's self-assessment.
RAW_FILES=()
if [ -n "$BENCHMARK_PATH" ] && [ -d "$BENCHMARK_PATH" ]; then
    RAW_FILES+=("$BENCHMARK_PATH")
fi
if [ -n "$BASELINE_PATH" ] && [ -d "$BASELINE_PATH" ]; then
    RAW_FILES+=("$BASELINE_PATH")
fi
```

### Phase 1: Read Raw Benchmark Data

Read the raw benchmark artifacts directly — never the orchestrator's
commentary.

```bash
# Read task/scenario/rubric/run files from each benchmark under evaluation
for raw_dir in "${RAW_FILES[@]}"; do
    find "$raw_dir" -type f \( -name '*.md' -o -name '*.json' -o -name '*.yaml' \) -print \
        | head -200
done
```

### Phase 2: Judge Each Dimension (0–5, evidence-backed)

For each of the six dimensions, the cross-model reviewer applies the
BetterBench criteria above, cites the specific best-practice item and lifecycle
stage, and records a 0–5 score with an evidence-backed justification quoting
the raw benchmark data.

```bash
# Dimension scores are recorded by the cross-model LLM judge after reading
# the raw benchmark data. Each score MUST cite the lifecycle stage (J.1-J.4)
# and the specific best-practice item it maps to.
declare -A DIM_SCORE
declare -A DIM_EVIDENCE

# Dimension 1: Properties (J.1)
# Dimension 2: Grounding Levels (J.1)
# Dimension 3: Metric Assumptions (J.2)
# Dimension 4: Validation Evidence (J.2)
# Dimension 5: Gaming Risks (J.3)
# Dimension 6: Known Failure Cases (J.4)
```

### Phase 3: Record Scorecard Verdict

Aggregate the six dimension scores and record the verdict in eval-wiki so the
orchestrator can aggregate it.

```bash
TOTAL=0
for dim in Properties "Grounding Levels" "Metric Assumptions" \
           "Validation Evidence" "Gaming Risks" "Known Failure Cases"; do
    TOTAL=$((TOTAL + ${DIM_SCORE[$dim]:-0}))
done
# Max = 30 (6 dimensions * 5)
SCORECARD_SCORE=$(awk "BEGIN { printf \"%.2f\", ($TOTAL / 30.0) * 100 }")

if [ -f "$EVAL_WIKI_SCRIPT" ]; then
    python3 "$EVAL_WIKI_SCRIPT" add-feedback eval-wiki/ \
        --target-type benchmark \
        --target-id "${CANDIDATE:-benchmark}" \
        --from "scorecard-evaluator" \
        --issue-type "scorecard" \
        --description "BetterBench scorecard: $SCORECARD_SCORE/100 (6 dims)" \
        --action "audit" \
        --status "$( [ "$SCORECARD_SCORE" -ge 60 ] && echo pass || echo fail )"
fi
echo "scorecard-evaluator verdict: $SCORECARD_SCORE/100"
```

## Cross-Model Requirement

This ACQUIT sub-agent MUST run on a **different model family** than the one
that produced the benchmark, per `acceptance-gate.md` Hard Invariant #1. The
reviewer-independence principle (`reviewer-independence.md`) requires that the
sub-agent receive only raw benchmark data, never the producer's
self-assessment. Record the verifying model family in the feedback record.

## Failure Handling (Degrade)

If this sub-agent cannot complete (missing raw data, reviewer unavailable),
it records its verdict as **N/A** and exits non-zero so the orchestrator can
degrade gracefully and continue with the other sub-agent, per
`fan-out-pattern.md`.

## Output

- `eval-wiki/feedback/scorecard-evaluator-<timestamp>.md` — six dimension
  scores (0–5 each) with evidence-backed justifications and lifecycle-stage
  references (arxiv 2411.12990).
- Exit code 0 (verdict recorded) / non-zero (degrade — N/A).

## References

- `shared-references/acceptance-gate.md` — ACQUIT role, cross-model invariant
- `shared-references/reviewer-independence.md` — raw-data-only rule
- `shared-references/fan-out-pattern.md` — parallel dispatch + degrade
- Paper: "BetterBench: Assessing AI Benchmarks" (arxiv 2411.12990)
