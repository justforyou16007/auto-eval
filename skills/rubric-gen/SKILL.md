---
name: rubric-gen
description: 'Generate scoring rubrics for eval tasks. DRIVE role — generates criteria + evaluator scripts; verification is delegated to the rubric-audit ACQUIT skill. Use when user says "生成rubric", "generate rubric", "评分标准", or wants to create scoring criteria.'
argument-hint: "[task-id] [assurance: draft|submission]"
allowed-tools: Bash(*), Read, Write, Edit, Grep, Glob
role: DRIVE
depends-on: [eval-wiki, task]
produces: [rubric]
audited-by: [rubric-audit]
---

# rubric-gen Skill

## Overview

Generates rubric criteria and evaluator scripts based on a task. After the
role redesign (issue #5), this is a **DRIVE** worker skill — it
*constructs* rubrics and evaluator scripts. The ACQUIT responsibility for
*verifying* rubric correctness is delegated to the dedicated **`rubric-audit`**
skill (cross-model), not performed by rubric-gen itself.

> **Why the change.** Previously rubric-gen was tagged `ACQUIT` and expected
> to cross-model-verify its own output. That conflated the worker with its
> auditor and violated the DRIVE/ACQUIT separation. Now rubric-gen is a pure
> DRIVE worker; `rubric-audit` (a different model family) audits it.

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

### Phase 1: Read Task File

Parse the task's expected_behavior, scenario_type, and difficulty:

```bash
TASK_ID="${1:-}"
if [ -z "$TASK_ID" ]; then
    echo "ERROR: task-id is required" >&2
    exit 1
fi

if [ -f "$EVAL_WIKI_SCRIPT" ]; then
    TASK_DATA=$(python3 "$EVAL_WIKI_SCRIPT" query eval-wiki/ "$TASK_ID")
    echo "Task data: $TASK_DATA"
fi
```

### Phase 2: Generate Criteria

Generate 3–5 criteria based on the scenario_type:

| Scenario Type | Criteria | Evaluator Type |
|--------------|----------|----------------|
| single-turn | C1: tool_correctness, C2: output_format, C3: no_hallucination | C1-C3: script |
| multi-turn | C1-C3 + C4: error_recovery, C5: state_persistence | C1-C3: script, C4-C5: llm_judge |
| tool-chain | C1-C3 + C4: tool_chaining, C5: state_persistence | C1-C3: script, C4-C5: llm_judge |
| error-recovery | C1-C3 + C5: graceful_degradation | C1-C3: script, C5: llm_judge |

Each criterion includes:
- **id**: C1, C2, C3, C4, C5
- **name**: Human-readable name
- **description**: What is being evaluated
- **scoring**: `binary` (pass/fail) or `scale` (1-5)
- **weight**: Relative importance (0.0-1.0)
- **evaluator**: `script` (mechanical, deterministic) or `llm_judge` (semantic)

**Note on roles.** rubric-gen is a DRIVE worker — it *generates* both script
and llm_judge evaluators. Whether an evaluator is mechanical or semantic
does not change rubric-gen's own role: it is always DRIVE. The ACQUIT
verification of the generated rubric (correctness, coverage, that scripts
actually run) is the job of the **`rubric-audit`** skill, run cross-model
per `acceptance-gate.md`.

### Phase 3: Generate Evaluator Scripts

For each script evaluator, generate a Python skeleton:

```python
#!/usr/bin/env python3
"""
Evaluator for <criterion_name>.

Reads agent output from stdin (or a file path as argument).
Returns exit code 0 (pass) or 1 (fail).
"""
import sys


def evaluate(output: str) -> bool:
    """Evaluate the agent output. Return True if pass, False if fail."""
    # TODO: Implement evaluation logic
    return True


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as f:
            output = f.read()
    else:
        output = sys.stdin.read()

    if evaluate(output):
        sys.exit(0)
    else:
        sys.exit(1)
```

Each script must:
- Be self-contained (no external dependencies beyond stdlib)
- Read agent output from stdin or a file path argument
- Return exit 0 (pass) or 1 (fail)
- Have a `--help` flag that returns 0

### Phase 4: Write Rubric to eval-wiki

```bash
if [ -f "$EVAL_WIKI_SCRIPT" ]; then
    python3 "$EVAL_WIKI_SCRIPT" add-rubric eval-wiki/ \
      --task-id "$TASK_ID" \
      --criteria-json evaluators/criteria.json
fi
```

### Phase 5: Verify (self-check only — DRIVE)

This is a **DRIVE self-check**, NOT an ACQUIT verdict. rubric-gen verifies
only that the evaluator scripts it generated are syntactically valid Python
and respond to `--help`. This does NOT constitute quality verification —
that is the job of the `rubric-audit` ACQUIT skill (cross-model).

```bash
VERIFY_FAILED=0
for script in evaluators/*.py; do
    if [ ! -f "$script" ]; then
        echo "ERROR: Missing script: $script"
        VERIFY_FAILED=1
    elif ! python3 "$script" --help > /dev/null 2>&1; then
        echo "ERROR: Script failed --help: $script"
        VERIFY_FAILED=1
    fi
done

if [ "$VERIFY_FAILED" -eq 1 ]; then
    echo "Rubric status stays 'draft', not finalizing."
    exit 1
fi
```

If self-check fails, the rubric status stays "draft" and is not finalized.
After self-check passes, invoke the **`rubric-audit`** skill (different
model family) to perform the true ACQUIT audit (completeness, usability,
coverage) per `acceptance-gate.md`.

## Output

- `eval-wiki/rubrics/<task-id>-rubric.md` — Rubric metadata
- `evaluators/<criterion_slug>.py` — Evaluator scripts
- `evaluators/criteria.json` — Criteria definitions for eval-wiki ingestion