---
name: feedback-align
description: 'Record and apply user feedback to align eval tasks, rubrics, environments, and reports. DRIVE+ACQUIT role. Use when user says "反馈", "feedback", "调整", or wants to revise eval artifacts based on user input.'
argument-hint: "[target-type] [target-id] [action]"
allowed-tools: Bash(*), Read, Write, Edit, Grep, Glob
role: DRIVE_ACQUIT
depends-on: [eval-wiki]
produces: [feedback]
---

# feedback-align Skill

## Overview

Records feedback, classifies the issue type, generates a proposed change,
applies the change, and verifies it. This skill has both DRIVE and ACQUIT
aspects:
- **DRIVE part**: Feedback analysis and change proposal (can be same model)
- **ACQUIT part**: Change verification (must be cross-model per acceptance-gate.md)

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

### Phase 1: Record Feedback

Record the user feedback in eval-wiki:

```bash
TARGET_TYPE="${1:-}"
TARGET_ID="${2:-}"
ACTION="${3:-}"

if [ -f "$EVAL_WIKI_SCRIPT" ]; then
    python3 "$EVAL_WIKI_SCRIPT" add-feedback eval-wiki/ \
      --target-type "$TARGET_TYPE" \
      --target-id "$TARGET_ID" \
      --from user \
      --issue-type "$ISSUE_TYPE" \
      --description "$DESCRIPTION" \
      --action "$ACTION"
fi
```

### Phase 2: Analyze Feedback (DRIVE)

Classify the feedback into one of these issue types:

| Issue Type | Description | Example |
|------------|-------------|---------|
| `misalignment` | Task doesn't match user intent | "The task should test search, not math" |
| `missing_case` | Edge case not covered | "What if the tool returns an error?" |
| `rubric_error` | Rubric criteria are wrong | "The pass threshold is too low" |
| `env_error` | Environment configuration is wrong | "The image doesn't have curl" |
| `difficulty_mismatch` | Difficulty level is wrong | "This is too hard for a lite task" |

Generate a proposed change with:
- Field to change
- Current value (from_value)
- New value (to_value)

Update the feedback record with the proposed change:

```bash
if [ -f "$EVAL_WIKI_SCRIPT" ]; then
    python3 "$EVAL_WIKI_SCRIPT" add-feedback eval-wiki/ \
      --target-type "$TARGET_TYPE" \
      --target-id "$TARGET_ID" \
      --from user \
      --issue-type "$ISSUE_TYPE" \
      --description "$DESCRIPTION" \
      --action "$ACTION" \
      --field "$FIELD" \
      --from-value "$FROM_VALUE" \
      --to-value "$TO_VALUE" \
      --status "analyzed"
fi
```

### Phase 3: Apply Change (DRIVE)

Modify the target entity in eval-wiki:

```bash
if [ -f "$EVAL_WIKI_SCRIPT" ]; then
    case "$TARGET_TYPE" in
        task)
            python3 "$EVAL_WIKI_SCRIPT" add-task eval-wiki/ \
              --title "$TITLE" \
              --difficulty "$DIFFICULTY" \
              --scenario-type "$SCENARIO_TYPE" \
              --max-turns "$MAX_TURNS" \
              --allowed-tools "$TOOLS" \
              --expected-behavior "$BEHAVIOR" \
              --update
            ;;
        rubric)
            python3 "$EVAL_WIKI_SCRIPT" add-rubric eval-wiki/ \
              --task-id "$TASK_ID" \
              --criteria-json "$CRITERIA_JSON" \
              --update
            ;;
        env)
            python3 "$EVAL_WIKI_SCRIPT" add-env eval-wiki/ \
              --task-id "$TASK_ID" \
              --image "$IMAGE" \
              --network "$NETWORK" \
              --memory "$MEMORY" \
              --cpus "$CPUS" \
              --agent-endpoint "$ENDPOINT" \
              --update
            ;;
    esac
fi
```

Set the feedback status to "applied":

```bash
if [ -f "$EVAL_WIKI_SCRIPT" ]; then
    python3 "$EVAL_WIKI_SCRIPT" add-feedback eval-wiki/ \
      --target-type "$TARGET_TYPE" \
      --target-id "$TARGET_ID" \
      --from user \
      --issue-type "$ISSUE_TYPE" \
      --description "$DESCRIPTION" \
      --action "$ACTION" \
      --status "applied"
fi
```

### Phase 4: Verify Change (ACQUIT)

Re-run the affected task to confirm the change resolved the issue.
**Cross-model verification**: The verifying agent must be a different model
family (per acceptance-gate.md).

```bash
# Run the task with the updated configuration
# The verifying agent must be from a different model family

if [ "$VERIFIED" = "true" ]; then
    python3 "$EVAL_WIKI_SCRIPT" add-feedback eval-wiki/ \
      --target-type "$TARGET_TYPE" \
      --target-id "$TARGET_ID" \
      --from user \
      --issue-type "$ISSUE_TYPE" \
      --description "$DESCRIPTION" \
      --action "$ACTION" \
      --status "verified" \
      --field "$FIELD" \
      --from-value "$FROM_VALUE" \
      --to-value "$TO_VALUE"
else
    python3 "$EVAL_WIKI_SCRIPT" add-feedback eval-wiki/ \
      --target-type "$TARGET_TYPE" \
      --target-id "$TARGET_ID" \
      --from user \
      --issue-type "$ISSUE_TYPE" \
      --description "$DESCRIPTION" \
      --action "$ACTION" \
      --status "open" \
      --field "$FIELD" \
      --from-value "$FROM_VALUE" \
      --to-value "$TO_VALUE"
fi
```

### Phase 5: Rebuild query_pack

```bash
if [ -f "$EVAL_WIKI_SCRIPT" ] && [ "$VERIFIED" = "true" ]; then
    python3 "$EVAL_WIKI_SCRIPT" rebuild-query-pack eval-wiki/
fi
```

## Output

- `eval-wiki/feedback/<slug>.md` — Feedback record with status
- Modified entities (task, rubric, env, or report) in eval-wiki