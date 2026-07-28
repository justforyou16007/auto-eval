# Assurance Contract

_Adapted from ARIS patterns for the eval-wiki context._

## Draft vs Submission

Artifacts in the eval-wiki pipeline have two assurance levels:

| Level | Label | Description | Audit Strictness |
|-------|-------|-------------|------------------|
| Draft | `draft` | Work in progress, may be incomplete | No audit required |
| Submission | `submission` | Ready for evaluation, auditable | Full audit required |

## Lifecycle

1. **Draft**: Initial creation. The artifact is being developed and may change.
   - No audit required
   - May be overwritten by `--update` flag
   - Used during development iteration

2. **Submission**: Finalized artifact. The artifact is ready for evaluation.
   - Full audit required before acceptance
   - Must pass `evidence-check.py` for run artifacts
   - Must pass `provenance.py check` for provenance links
   - May be reviewed by `capture-filter.py` for noise patterns

## Audit Strictness

| Artifact Type | Draft Audits | Submission Audits |
|---------------|-------------|-------------------|
| Task | None | YAML schema validation |
| Environment | None | Docker compose validation |
| Rubric | None | Criteria completeness check |
| Run | None | Evidence must exist (non-empty) |
| Feedback | None | Target must exist in wiki |
| Report | None | All provenance links must resolve |

## Implementation

In eval-wiki, assurance is stored in rubric frontmatter:

```yaml
assurance: "draft"
```

Run artifacts are verified by `evidence-check.py` and `provenance.py`.

## Cross-Reference

- `acceptance-gate.md` — DRIVE vs ACQUIT roles
- `evidence-check.py` — Evidence verification
- `provenance.py` — Provenance link validation
- `capture-filter.py` — Noise pattern filtering