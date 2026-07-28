# Output Composition

_Adapted from ARIS patterns for the eval-wiki context._

## Multi-Artifact Folding

Stage skills may produce multiple output artifacts. These artifacts are folded
into a single run record in eval-wiki.

## Composition Rules

1. **Primary artifact**: The main output of the stage (e.g., task file, rubric
   file, run record). This is the artifact referenced by `node_id`.

2. **Secondary artifacts**: Supporting files generated during the stage (e.g.,
   evaluator scripts, docker-compose files, HTML reports). These are referenced
   by `provenance` paths in the run record.

3. **Evidence artifacts**: Raw output files that serve as evidence (e.g.,
   stdout, stderr, trace.jsonl). These are validated by `evidence-check.py`.

## Folding Process

```bash
# After stage completion, collect all artifacts
ARTIFACTS=(
    "eval-wiki/tasks/${SLUG}.md"
    "evaluators/${SLUG}.py"
    "docker-compose-${SLUG}.yml"
    "reports/report-${TIMESTAMP}.html"
)

# Register primary artifact in run state
python3 run-state.py set-status "$RUN_ID" "$PHASE" "done" \
    --artifact "eval-wiki/runs/${RUN_SLUG}.md"

# Register provenance paths
python3 eval-wiki.py add-run eval-wiki/ \
    --task-id "$TASK_ID" \
    --provenance "$(IFS=,; echo "${ARTIFACTS[*]}")"
```

## Cross-Reference

- `output-manifest.md` — Artifact index
- `output-versioning.md` — Timestamped output patterns
- `evidence-check.py` — Evidence verification