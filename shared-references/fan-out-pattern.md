# Fan-Out Pattern

_Adapted from ARIS patterns for the eval-wiki context._

## Parallel Dispatch + Degrade

The eval-wiki pipeline may dispatch multiple parallel tasks. The fan-out
pattern defines how to manage parallel execution and handle partial failures.

## Fan-Out Strategy

When generating multiple tasks, environments, or rubrics, the pipeline may
dispatch them in parallel:

```bash
# Fan-out: dispatch all tasks in parallel
for TASK_ID in "${TASK_IDS[@]}"; do
    python3 eval-wiki.py add-task eval-wiki/ \
        --title "$TITLE_$TASK_ID" \
        --difficulty "$DIFFICULTY" \
        --scenario-type "$SCENARIO_TYPE" &
done

# Wait for all to complete
wait
```

## Degrade Strategy

When a parallel dispatch fails for some items, the pipeline should degrade
gracefully:

1. **Complete successes**: Items that completed successfully are recorded
2. **Partial failures**: Items that failed are recorded with status "failed"
3. **Continue**: The pipeline continues with the successful items
4. **Report**: The failure is reported but does not block the pipeline

## Implementation

```bash
# Fan-out with degrade
FAILED=0
for ITEM in "${ITEMS[@]}"; do
    (
        # Attempt the operation
        if ! python3 eval-wiki.py add-task eval-wiki/ --title "$ITEM" ...; then
            echo "FAILED: $ITEM"
            exit 1
        fi
    ) &
done

# Wait and collect results
for job in $(jobs -p); do
    wait "$job" || ((FAILED++))
done

if [ "$FAILED" -gt 0 ]; then
    echo "WARNING: $FAILED items failed (continuing with successful items)"
fi
```

## Cross-Reference

- `run-state.py` — State machine for tracking parallel phases
- `resumable-runs.md` — Crash recovery
- `output-manifest.md` — Tracking parallel outputs