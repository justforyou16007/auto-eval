---
name: task-audit
description: 'ACQUIT audit for the task-gen stage. Reads task-gen worker output (scenarios + tasks) and verifies (a) the work was honestly completed, (b) the tasks are real and usable, and (c) tasks align with real-world scenarios. Cross-model required. Use after task-gen runs, or when user says "审计task", "audit tasks", "检查任务".'
argument-hint: "[scenario-id|task-id] [--strict]"
allowed-tools: Bash(*), Read, Write, Edit, Grep, Glob
role: ACQUIT
depends-on: [eval-wiki, task-gen]
produces: [audit-verdict]
audits: [task-gen]
cross-model-required: true
audits-stage: 1
---

# task-audit Skill

## Overview

ACQUIT audit skill for **Stage 1 (task-gen)**. The task-gen worker is a
DRIVE role that generates scenarios and tasks. This skill audits whether
task-gen *honestly completed* its work — it never generates tasks itself.

Per issue #5, each pipeline stage must have a companion ACQUIT audit that:

1. **Reads the worker's output** — scenarios + tasks written by task-gen.
2. **Checks three things**:
   - a. **Completeness** — did task-gen truthfully do the work (no `_TODO`
     stubs, real scenario/task bodies, correct scenario→task linkage)?
   - b. **Usability** — is the output real and usable (run the evaluator
     contracts task-gen claims: files exist, frontmatter valid, query pack
     rebuilt)?
   - c. **Alignment** — for task-generation, verify the tasks align with
     real-world scenarios (does each task plausibly test a capability a
     real Agent would face, derived from its parent scenario)?

This is an **ACQUIT** role — the auditor must be a *different model family*
than the one that ran task-gen, per `acceptance-gate.md`.

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

Determine what to audit — a specific scenario/task, or all task-gen output.

```bash
TARGET_SCENARIO="${1:-}"
STRICT="${STRICT:-false}"

# Default: audit all scenarios and tasks produced by task-gen
if [ -f "$EVAL_WIKI_SCRIPT" ]; then
    SCENARIOS=$(python3 "$EVAL_WIKI_SCRIPT" query eval-wiki/ "scenario:")
    TASKS=$(python3 "$EVAL_WIKI_SCRIPT" query eval-wiki/ "task:")
fi
```

### Phase 1: Read Worker Output

Read the scenarios and tasks that task-gen produced.

```bash
# Read every scenario file
for scenario_file in eval-wiki/scenarios/*.md; do
    [ -f "$scenario_file" ] || continue
    cat "$scenario_file"
done

# Read every task file
for task_file in eval-wiki/tasks/*.md; do
    [ -f "$task_file" ] || continue
    cat "$task_file"
done
```

### Phase 2: Audit Checklist

Run the three-part audit. **Record a PASS/FAIL/INCONCLUSIVE per check.**

#### 2a. Completeness — did task-gen honestly do the work?

- No task body section is a `_TODO` stub (`测试目标`, `输入规格`,
  `预期输出`, `前置条件`, `边界条件`).
- Each task has a `scenario_id` referencing a real scenario.
- Each scenario has a non-empty description and capabilities list.
- The number of tasks ≥ the configured count (default M=3 per scenario).

```bash
COMPLETENESS_FAIL=0
for task_file in eval-wiki/tasks/*.md; do
    [ -f "$task_file" ] || continue
    # _TODO stubs indicate task-gen did not actually fill the task
    if grep -q "_TODO" "$task_file"; then
        echo "FAIL (completeness): $task_file still contains _TODO stub"
        COMPLETENESS_FAIL=1
    fi
    # scenario_id must be present and resolvable
    SCENARIO_ID=$(grep -o 'scenario_id:[[:space:]]*[^[:space:]#]*' "$task_file" | head -1 | sed 's/scenario_id:[[:space:]]*//')
    if [ -z "$SCENARIO_ID" ]; then
        echo "FAIL (completeness): $task_file missing scenario_id"
        COMPLETENESS_FAIL=1
    fi
done
```

#### 2b. Usability — is the output real and usable? (actually run & verify)

- All task/scenario files exist on disk (not just claimed).
- Frontmatter parses and has required fields.
- `query_pack.md` and `index.md` were rebuilt by task-gen.

```bash
USABILITY_FAIL=0
[ -f "eval-wiki/query_pack.md" ] || { echo "FAIL (usability): query_pack.md missing"; USABILITY_FAIL=1; }
[ -f "eval-wiki/index.md" ] || { echo "FAIL (usability): index.md missing"; USABILITY_FAIL=1; }

# Validate frontmatter of every task
for task_file in eval-wiki/tasks/*.md; do
    [ -f "$task_file" ] || continue
    python3 -c "
import sys, yaml
with open('$task_file') as f:
    c = f.read()
assert c.startswith('---'), 'missing frontmatter'
end = c.find('---', 3)
fm = yaml.safe_load(c[3:end]) or {}
for k in ['title','difficulty','scenario_type']:
    assert fm.get(k), f'missing field {k}'
"
done
```

#### 2c. Alignment — do tasks align with real-world scenarios?

This check is **specific to task-generation** (issue requirement c). For
each task, the auditor judges whether the task plausibly tests a capability
a real Agent would face and is derived from its parent scenario — not a
fabricated or trivially-passing task.

```bash
ALIGNMENT_FAIL=0
for task_file in eval-wiki/tasks/*.md; do
    [ -f "$task_file" ] || continue
    # Read the task + its parent scenario and judge alignment cross-model.
    # The auditor (different model family) checks:
    #  - the task's expected_behavior is a realistic Agent task
    #  - the task derives from the scenario description, not a generic stub
    #  - the difficulty / tools / cost are consistent with the scenario
    # Record PASS/FAIL/INCONCLUSIVE.
    :
done
```

### Phase 3: Record Audit Verdict

Aggregate the three checks into a single verdict and record it as feedback
in eval-wiki so the pipeline can gate on it.

```bash
VERDICT="pass"
[ "$COMPLETENESS_FAIL" -eq 1 ] && VERDICT="fail"
[ "$USABILITY_FAIL" -eq 1 ] && VERDICT="fail"
[ "$ALIGNMENT_FAIL" -eq 1 ] && VERDICT="fail"

if [ -f "$EVAL_WIKI_SCRIPT" ]; then
    python3 "$EVAL_WIKI_SCRIPT" add-feedback eval-wiki/ \
      --target-type task \
      --target-id "task-gen" \
      --from auditor \
      --issue-type completeness \
      --description "task-audit verdict: $VERDICT" \
      --action "audit" \
      --status "$VERDICT"
fi
echo "task-audit verdict: $VERDICT"
[ "$VERDICT" = "pass" ] && exit 0 || exit 1
```

## Audit Checklist Summary

| Check | What it verifies | Pass condition |
|-------|------------------|----------------|
| Read Worker Output | scenarios + tasks exist | files readable |
| Completeness | no `_TODO` stubs, linkage correct | 0 failures |
| Usability | files real, frontmatter valid, index rebuilt | 0 failures |
| Alignment | tasks match real-world scenarios (issue c) | 0 failures |

## Cross-Model Requirement

This auditor MUST run on a different model family than task-gen, per
`acceptance-gate.md` Hard Invariant #1. Record the verifying model family
in the feedback record.

## Output

- `eval-wiki/feedback/task-audit-<timestamp>.md` — audit verdict + per-check results
- Exit code 0 (pass) / 1 (fail) for pipeline gating
