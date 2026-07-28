# Resumable Runs

_Adapted from ARIS patterns for the eval-wiki context._

## Crash Recovery Protocol

Run state files (`.eval/runs/<run_id>.json`) enable crash recovery for
long-running pipeline orchestrations.

## State File Format

```json
{
  "run_id": "run-20260728T141200Z",
  "created": "2026-07-28T14:12:00Z",
  "updated": "2026-07-28T14:15:00Z",
  "phases": {
    "task-gen": {"status": "done", "artifact": "eval-wiki/tasks/my-task.md", "accepted": true},
    "env-gen": {"status": "running", "artifact": null, "accepted": false},
    "rubric-gen": {"status": "pending", "artifact": null, "accepted": false},
    "agent-exec": {"status": "pending", "artifact": null, "accepted": false},
    "report-gen": {"status": "pending", "artifact": null, "accepted": false},
    "feedback-align": {"status": "pending", "artifact": null, "accepted": false}
  },
  "accepted_phases": {
    "task-gen": {
      "verdict_id": "v-001",
      "reviewer": "gpt-4",
      "accepted_at": "2026-07-28T14:13:00Z"
    }
  }
}
```

## Recovery Protocol

When a pipeline crashes and resumes:

1. **Scan** `.eval/runs/` for existing state files
2. **Check** each phase's status:
   - `done` or `skipped`: Skip phase (already completed)
   - `running`: Phase was in progress — check for artifacts, then either
     resume or restart
   - `pending`: Phase not started — execute normally
3. **Verify** artifacts exist for `done` phases using `evidence-check.py`
4. **Resume** from the first incomplete phase

## Implementation

```bash
# Resume from crash
RUN_ID="run-20260728T141200Z"
STATE=$(python3 run-state.py get-state "$RUN_ID")

# Check each phase
for PHASE in task-gen env-gen rubric-gen agent-exec report-gen feedback-align; do
    STATUS=$(echo "$STATE" | python3 -c "import sys,json; print(json.load(sys.stdin)['phases']['$PHASE']['status'])")
    case "$STATUS" in
        done|skipped) echo "Skipping $PHASE (already $STATUS)" ;;
        running) echo "Resuming $PHASE from crash..." ;;
        pending) echo "Starting $PHASE..." ;;
    esac
done
```

## Cross-Reference

- `run-state.py` — State machine tool
- `evidence-check.py` — Evidence verification
- `output-manifest.md` — Artifact tracking