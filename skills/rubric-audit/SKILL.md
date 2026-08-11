---
name: rubric-audit
description: 'ACQUIT audit for the rubric-gen stage. Reads rubric-gen worker output (criteria + evaluator scripts) and verifies (a) rubric was honestly generated, (b) evaluators are real and usable (actually run --help and against sample output), (c) criteria cover the task. Cross-model required. Use after rubric-gen runs, or when user says "审计rubric", "audit rubric", "检查评分".'
argument-hint: "[task-id] [--strict]"
allowed-tools: Bash(*), Read, Write, Edit, Grep, Glob
role: ACQUIT
depends-on: [eval-wiki, rubric-gen]
produces: [audit-verdict]
audits: [rubric-gen]
cross-model-required: true
audits-stage: 3
---

# rubric-audit Skill

## Overview

ACQUIT audit skill for **Stage 3 (rubric-gen)**. After the role redesign
(issue #5), **rubric-gen is a DRIVE worker** that generates criteria and
evaluator scripts. The ACQUIT responsibility for *verifying rubric
correctness* now lives here, in this dedicated audit skill. This skill
never generates rubrics itself — it only audits them.

Per issue #5, each pipeline stage must have a companion ACQUIT audit that:

1. **Reads the worker's output** — criteria JSON + evaluator scripts.
2. **Checks three things**:
   - a. **Completeness** — did rubric-gen honestly do the work (criteria
     count 3–5, each criterion has id/name/description/scoring/weight,
     evaluator field set)?
   - b. **Usability** — are the evaluators real and usable (actually run
     each script's `--help` and against a sample output; criteria.json
     parses; not just claimed)?
   - c. **Coverage** — do the criteria cover the task's scenario_type and
     expected behavior (cross-model judge)?

This is an **ACQUIT** role — the auditor must be a *different model family*
than the one that ran rubric-gen, per `acceptance-gate.md`.

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

## Phases

### Phase 0: Resolve Scope

```bash
TASK_ID="${1:-}"
if [ -z "$TASK_ID" ]; then
    echo "ERROR: task-id is required (which rubric to audit)" >&2
    exit 1
fi
RUBRIC_FILE="eval-wiki/rubrics/${TASK_ID}-rubric.md"
CRITERIA_JSON="evaluators/criteria.json"
```

### Phase 1: Read Worker Output

```bash
[ -f "$RUBRIC_FILE" ] && cat "$RUBRIC_FILE"
[ -f "$CRITERIA_JSON" ] && cat "$CRITERIA_JSON"
ls -1 evaluators/*.py 2>/dev/null
if [ -f "$EVAL_WIKI_SCRIPT" ]; then
    python3 "$EVAL_WIKI_SCRIPT" query eval-wiki/ "rubric:${TASK_ID}-rubric"
fi
```

### Phase 2: Audit Checklist

#### 2a. Completeness — did rubric-gen honestly do the work?

```bash
COMPLETENESS_FAIL=0
[ -f "$CRITERIA_JSON" ] || { echo "FAIL (completeness): criteria.json missing"; COMPLETENESS_FAIL=1; }
python3 -c "
import json
with open('$CRITERIA_JSON') as f:
    d = json.load(f)
crit = d.get('criteria', [])
assert 3 <= len(crit) <= 5, f'expected 3-5 criteria, got {len(crit)}'
for c in crit:
    for k in ['id','name','description','scoring','weight','evaluator']:
        assert c.get(k), f'criterion {c.get(\"id\")} missing {k}'
    assert c['scoring'] in ('binary','scale_1_5','percentage'), c['scoring']
    assert c['evaluator'] in ('script','llm_judge'), c['evaluator']
" || { echo "FAIL (completeness): criteria malformed"; COMPLETENESS_FAIL=1; }
```

#### 2b. Usability — are evaluators real and usable? (actually run & verify)

This is the core "actually run" check from issue requirement b. Every
script evaluator is executed; `--help` must exit 0 and the script must
produce a pass/fail verdict on a sample output.

```bash
USABILITY_FAIL=0
for script in evaluators/*.py; do
    [ -f "$script" ] || continue
    # --help must exit 0 (rubric-gen contract)
    if ! python3 "$script" --help > /dev/null 2>&1; then
        echo "FAIL (usability): $script --help failed"; USABILITY_FAIL=1
    fi
    # Must produce a deterministic pass/fail on a sample input
    echo "sample agent output" | python3 "$script" > /dev/null 2>&1 || {
        echo "FAIL (usability): $script did not evaluate sample output"; USABILITY_FAIL=1; }
done
```

#### 2c. Coverage — do criteria cover the task?

```bash
COVERAGE_FAIL=0
if [ -f "$EVAL_WIKI_SCRIPT" ]; then
    TASK_DATA=$(python3 "$EVAL_WIKI_SCRIPT" query eval-wiki/ "$TASK_ID")
    # Cross-model judge: do the criteria cover the task's scenario_type
    # and expected_behavior? (e.g., multi-turn task needs state_persistence
    # criterion). Record PASS/FAIL/INCONCLUSIVE.
    :
fi
```

### Phase 3: Record Audit Verdict

```bash
VERDICT="pass"
[ "$COMPLETENESS_FAIL" -eq 1 ] && VERDICT="fail"
[ "$USABILITY_FAIL" -eq 1 ] && VERDICT="fail"
[ "$COVERAGE_FAIL" -eq 1 ] && VERDICT="fail"

if [ -f "$EVAL_WIKI_SCRIPT" ]; then
    python3 "$EVAL_WIKI_SCRIPT" add-feedback eval-wiki/ \
      --target-type rubric \
      --target-id "${TASK_ID}-rubric" \
      --from auditor \
      --issue-type rubric_error \
      --description "rubric-audit verdict: $VERDICT" \
      --action "audit" \
      --status "$VERDICT"
fi
echo "rubric-audit verdict: $VERDICT"
[ "$VERDICT" = "pass" ] && exit 0 || exit 1
```

## Audit Checklist Summary

| Check | What it verifies | Pass condition |
|-------|------------------|----------------|
| Read Worker Output | rubric + criteria + scripts | files readable |
| Completeness | 3-5 criteria, all fields present | 0 failures |
| Usability | every evaluator `--help` + runs | 0 failures |
| Coverage | criteria cover task scenario | 0 failures |

## Cross-Model Requirement

This auditor MUST run on a different model family than rubric-gen, per
`acceptance-gate.md` Hard Invariant #1. This is the key change from the
old design, where rubric-gen was *itself* the ACQUIT role — that conflated
the worker with its auditor.

## Output

- `eval-wiki/feedback/rubric-audit-<timestamp>.md` — audit verdict
- Exit code 0 (pass) / 1 (fail) for pipeline gating
