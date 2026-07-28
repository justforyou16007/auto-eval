# Review Tracing

_Adapted from ARIS patterns for the eval-wiki context._

## Trace Storage

All review operations must save their traces to `.eval/traces/` for audit
and debugging purposes.

## Trace Format

Each trace file is a JSONL file with one entry per review step:

```json
{"timestamp": "2026-07-28T14:12:00Z", "run_id": "run-001", "phase": "rubric-gen", "action": "review_start", "reviewer": "gpt-4"}
{"timestamp": "2026-07-28T14:12:05Z", "run_id": "run-001", "phase": "rubric-gen", "action": "criteria_check", "criterion": "C1", "result": "PASS"}
{"timestamp": "2026-07-28T14:12:10Z", "run_id": "run-001", "phase": "rubric-gen", "action": "review_complete", "verdict": "accept"}
```

## Trace Contents

Each trace entry should include:

1. **Timestamp**: UTC timestamp of the review action
2. **Run ID**: The run being reviewed
3. **Phase**: The pipeline phase being reviewed
4. **Action**: The review action (review_start, criteria_check, review_complete, etc.)
5. **Reviewer**: The model family performing the review
6. **Result**: The result of the review action
7. **Evidence**: Any supporting evidence paths

## Implementation

```bash
# Save review trace
TRACE_DIR=".eval/traces/${RUN_ID}"
mkdir -p "$TRACE_DIR"

# Write trace entry
echo "{\"timestamp\": \"$(date -u +"%Y-%m-%dT%H:%M:%SZ")\", \"run_id\": \"$RUN_ID\", \"phase\": \"$PHASE\", \"action\": \"review_start\", \"reviewer\": \"$REVIEWER_MODEL\"}" \
    >> "$TRACE_DIR/${PHASE}.jsonl"

# ... perform review ...

echo "{\"timestamp\": \"$(date -u +"%Y-%m-%dT%H:%M:%SZ")\", \"run_id\": \"$RUN_ID\", \"phase\": \"$PHASE\", \"action\": \"review_complete\", \"verdict\": \"$VERDICT\"}" \
    >> "$TRACE_DIR/${PHASE}.jsonl"
```

## Cross-Reference

- `run-state.py` — State machine for tracking phases
- `evidence-check.py` — Evidence verification checks trace files
- `experiment-integrity.md` — Prevention of fake results