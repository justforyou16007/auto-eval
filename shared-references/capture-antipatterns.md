# Capture Antipatterns

_Adapted from ARIS patterns for the eval-wiki context._

## Noise Patterns

Runtime noise must be filtered from captured output before it is persisted
as valid tasks, rubrics, or feedback. The `capture-filter.py` tool detects
these patterns.

## Pattern Categories

### 1. Env-Failure

Indicates the environment cannot run the evaluation:

| Pattern | Example |
|---------|---------|
| `no module named` | "No module named 'requests'" |
| `importerror` | "ImportError: cannot import name" |
| `modulenotfounderror` | "ModuleNotFoundError: No module named" |
| `pip install` | "pip install pandas" |

These outputs are environment configuration failures, not valid task results.

### 2. Transient-Error

Indicates a temporary infrastructure issue:

| Pattern | Example |
|---------|---------|
| `timeout` | "Timeout waiting for response" |
| `connection refused` | "Connection refused: connect" |
| `rate limit` | "Rate limit exceeded" |
| `503` | "HTTP 503 Service Unavailable" |
| `502` | "HTTP 502 Bad Gateway" |

These outputs are infrastructure issues, not valid evaluation results.

### 3. Negative-Tool-Claim

Indicates the agent is refusing or unable to perform the task:

| Pattern | Example |
|---------|---------|
| `can't do` | "I can't do that" |
| `unable to` | "Unable to complete the task" |
| `i cannot` | "I cannot perform this action" |
| `not possible to` | "It is not possible to" |

These outputs indicate the agent is not in a valid evaluation state.

## Strict Mode

With `--strict`, additional patterns are checked:

- Empty output (all whitespace)
- Output containing only error messages
- Output that is a repetition of the prompt

## Implementation

```bash
# Filter captured output
python3 capture-filter.py agent-output.txt --strict
if [ $? -eq 1 ]; then
    echo "WARNING: Captured output contains noise patterns"
    # Do not persist as valid task/rubric/feedback
fi
```

## Cross-Reference

- `capture-filter.py` — The noise filtering tool
- `evidence-check.py` — Evidence verification
- `injection-hygiene.md` — Prompt injection defense