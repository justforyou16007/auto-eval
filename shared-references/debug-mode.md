# Debug Mode

_Adapted from ARIS patterns for the eval-wiki context._

## Debug Halt Protocol

When a stage skill encounters an unexpected condition, it may enter debug
mode. Debug mode pauses execution and allows manual inspection.

## Entering Debug Mode

Debug mode is triggered by:

1. `--debug` flag passed to the stage skill
2. Evidence check failure (`evidence-check.py` returns invalid)
3. Provenance validation failure (`provenance.py` returns broken links)
4. Capture filter finding noise patterns (`capture-filter.py` returns findings)
5. Convergence detection failure (`iteration-log.py` returns diverging)

## Debug Mode Behavior

When in debug mode, the stage skill:

1. **Pauses** execution at the current phase
2. **Writes** a debug snapshot to `.eval/debug/<run_id>/`
3. **Prints** diagnostic information to stderr
4. **Waits** for manual intervention or a resume signal

## Debug Snapshot Contents

The debug snapshot includes:

```bash
.eval/debug/<run_id>/
├── state.json          # Current run state
├── phase-<phase>.json  # Current phase data
├── evidence/           # Evidence files (if available)
│   ├── trace.jsonl
│   └── output.txt
├── diagnostic.txt     # Diagnostic information
└── resume.sh          # Resume script (when ready)
```

## Resume Protocol

To resume from debug mode:

```bash
# Inspect the debug snapshot
cat .eval/debug/<run_id>/diagnostic.txt

# Fix the issue (if needed)
# ...

# Resume execution
python3 run-state.py set-status <run_id> <phase> running
# Re-run the stage skill
```

## Cross-Reference

- `run-state.py` — State machine for tracking phases
- `evidence-check.py` — Evidence verification
- `capture-filter.py` — Noise filtering
- `provenance.py` — Provenance validation
- `iteration-log.py` — Convergence tracking
- `resumable-runs.md` — Crash recovery