# Evidence Precheck

_Adapted from ARIS patterns for the eval-wiki context._

## Principle

Before referencing evidence files, verify they exist and are non-empty.
This prevents broken links and empty references in run records.

## Precheck Steps

Before any stage skill writes provenance paths to a run record:

1. **Check existence**: Each referenced file must exist on disk
2. **Check non-empty**: Each referenced file must be > 0 bytes
3. **Check readability**: Each referenced file must be readable by the
   current user
4. **Check format**: JSON files must be valid JSON; markdown files must
   have valid YAML frontmatter

## Implementation

```bash
# Precheck evidence before writing run record
EVIDENCE_DIR=".eval/evidence/${RUN_ID}"

# Check trace.jsonl
if [ ! -f "$EVIDENCE_DIR/trace.jsonl" ]; then
    echo "ERROR: trace.jsonl not found" >&2
    exit 1
fi
if [ ! -s "$EVIDENCE_DIR/trace.jsonl" ]; then
    echo "ERROR: trace.jsonl is empty" >&2
    exit 1
fi

# Check output.txt
if [ ! -f "$EVIDENCE_DIR/output.txt" ]; then
    echo "ERROR: output.txt not found" >&2
    exit 1
fi
if [ ! -s "$EVIDENCE_DIR/output.txt" ]; then
    echo "ERROR: output.txt is empty" >&2
    exit 1
fi
```

## Tool

The `evidence-check.py` tool automates this precheck:

```bash
python3 evidence-check.py .eval/evidence/${RUN_ID}/
```

Returns `{"valid": true}` if all evidence files exist and are non-empty.

## Cross-Reference

- `evidence-check.py` — Evidence verification tool
- `provenance.py` — Provenance link validation
- `output-manifest.md` — Artifact tracking
- `assurance-contract.md` — Submission audit requirements