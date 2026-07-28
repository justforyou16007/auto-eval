# Output Manifest

_Adapted from ARIS patterns for the eval-wiki context._

## Purpose

Each stage skill must produce a manifest of its output artifacts. The manifest
provides a human-readable and machine-readable index of everything produced.

## Manifest Contents

An output manifest contains:

1. **Run ID**: The unique run identifier
2. **Phase**: The stage phase that produced the artifacts
3. **Timestamp**: UTC timestamp of completion
4. **Artifacts**: List of all output files with paths and sizes
5. **Status**: Whether the stage completed successfully
6. **Provenance**: Links to evidence files

## 15+ Output Types

The eval-wiki pipeline produces at least 15 distinct artifact types:

| # | Artifact | Stage | Location |
|---|----------|-------|----------|
| 1 | Task file | task-gen | `eval-wiki/tasks/<slug>.md` |
| 2 | Environment file | env-gen | `eval-wiki/environments/<slug>.md` |
| 3 | Docker compose | env-gen | `docker-compose-<slug>.yml` |
| 4 | Rubric file | rubric-gen | `eval-wiki/rubrics/<slug>.md` |
| 5 | Criteria JSON | rubric-gen | `evaluators/criteria.json` |
| 6 | Evaluator scripts | rubric-gen | `evaluators/<criterion_slug>.py` |
| 7 | Run record | agent-exec | `eval-wiki/runs/<slug>.md` |
| 8 | Trace log | agent-exec | `trace.jsonl` |
| 9 | Output text | agent-exec | `output.txt` |
| 10 | Run state | run-state | `.eval/runs/<run_id>.json` |
| 11 | Feedback record | feedback-align | `eval-wiki/feedback/<slug>.md` |
| 12 | Verification report | report-gen | `reports/report-<timestamp>.html` |
| 13 | Latest report | report-gen | `reports/report-latest.html` |
| 14 | Query pack | eval-wiki | `eval-wiki/query_pack.md` |
| 15 | Wiki index | eval-wiki | `eval-wiki/index.md` |
| 16 | Edges | eval-wiki | `eval-wiki/graph/edges.jsonl` |
| 17 | Gap map | eval-wiki | `eval-wiki/gap_map.md` |

## Manifest Format

```json
{
  "run_id": "run-20260728T141200Z",
  "phase": "task-gen",
  "timestamp": "2026-07-28T14:12:00Z",
  "artifacts": [
    {"path": "eval-wiki/tasks/my-task.md", "size": 1024, "status": "created"},
    {"path": ".eval/runs/run-20260728T141200Z.json", "size": 512, "status": "created"}
  ],
  "status": "completed",
  "provenance": ["trace.jsonl", "output.txt"]
}
```

## Cross-Reference

- `output-composition.md` — Multi-artifact folding
- `output-versioning.md` — Timestamped output patterns
- `evidence-check.py` — Evidence verification