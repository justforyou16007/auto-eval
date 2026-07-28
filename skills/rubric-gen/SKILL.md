---
name: rubric-gen
description: 'Generate scoring rubrics for eval tasks. ACQUIT role — must use cross-model. Use when user says "生成rubric", "generate rubric", "评分标准", or wants to create scoring criteria.'
argument-hint: "[task-id] [assurance: draft|submission]"
allowed-tools: Bash(*), Read, Write, Edit, Grep, Glob
role: ACQUIT
depends-on: [eval-wiki, task]
produces: [rubric]
cross-model-required: true
---

# rubric-gen Skill

## Overview

Generates rubric criteria and evaluator scripts based on a task. This is an
**ACQUIT** role skill — rubric generation defines "what is correct", which
is a quality verdict on the task. Per the acceptance gate, this must be
cross-model.

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
- **evaluator**: `script` (DRIVE, mechanical) or `llm_judge` (ACQUIT, cross-model)

**Script evaluators** are DRIVE — mechanical checks that can be self-judged.
**LLM judge evaluators** are ACQUIT — must be cross-model per acceptance-gate.md.

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

### Phase 5: Verify

Check that all evaluator scripts exist and are valid Python:

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

If verification fails, the rubric status stays "draft" and is not finalized.

## Output

- `eval-wiki/rubrics/<task-id>-rubric.md` — Rubric metadata
- `evaluators/<criterion_slug>.py` — Evaluator scripts
- `evaluators/criteria.json` — Criteria definitions for eval-wiki ingestion