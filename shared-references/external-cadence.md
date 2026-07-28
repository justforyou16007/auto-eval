# External Cadence

_Adapted from ARIS patterns for the eval-wiki context._

## Heartbeat Files

Long-running evaluations may produce heartbeat files to indicate progress.
Heartbeat files allow the pipeline to distinguish between "waiting for
external service" and "wrapped in a semantic loop."

## Heartbeat Format

Heartbeat files are written to `.eval/heartbeats/`:

```json
{
  "timestamp": "2026-07-28T14:12:00Z",
  "run_id": "run-20260728T141200Z",
  "phase": "agent-exec",
  "status": "running",
  "message": "Waiting for external API response..."
}
```

## Distinguishing Scenarios

### "Wait for External"

The pipeline is waiting for an external service (Docker container, API,
database). Expected behavior:

- Heartbeat files are being written regularly
- The process is still running
- No semantic progress is being made (waiting for I/O)

### "Wrap Semantic Loop"

The pipeline is stuck in a semantic loop (repeatedly generating the same
output, retrying the same operation). Expected behavior:

- Heartbeat files may be written, but with the same message
- The process is consuming resources
- The output is repetitive or self-contradictory

## Detection

The `watchdog.py` tool monitors container health. Combined with heartbeat
files, it can distinguish between:

- **Healthy waiting**: Heartbeats updating, container running
- **Timeout**: Heartbeats stopped, container still running past timeout
- **Crash**: Container stopped, no heartbeats

## Implementation

```bash
# Write heartbeat
HEARTBEAT_DIR=".eval/heartbeats"
mkdir -p "$HEARTBEAT_DIR"
echo '{"timestamp": "'$(date -u +"%Y-%m-%dT%H:%M:%SZ")'", "run_id": "'$RUN_ID'", "phase": "agent-exec", "status": "running"}' \
    > "$HEARTBEAT_DIR/${RUN_ID}.json"

# Monitor with watchdog
python3 watchdog.py "$CONTAINER_NAME" --timeout 300
```

## Cross-Reference

- `watchdog.py` — Container monitoring
- `run-state.py` — State machine for run phases
- `resumable-runs.md` — Crash recovery