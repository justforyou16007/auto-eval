# Output Versioning

Adapted from ARIS `output-versioning.md`.

## Principle

All generated artifacts (reports, evaluator scripts, docker-compose files)
must be versioned with a timestamp and have a fixed-name "latest" copy.

## Format

### Timestamped File

```
<artifact>-<YYYYMMDDTHHMMSSZ>.<ext>
```

Example: `report-20260728T141200Z.html`

### Latest Copy (Fixed Name)

```
<artifact>-latest.<ext>
```

Example: `report-latest.html`

## Implementation

Skills that produce artifacts must write both versions:

```bash
# Generate timestamp
TIMESTAMP=$(date -u +"%Y%m%dT%H%M%SZ")

# Write versioned copy
cp "$output" "reports/report-${TIMESTAMP}.html"

# Write latest copy
cp "$output" "reports/report-latest.html"
```

## Supported Artifacts

| Skill | Artifact | Pattern |
|-------|----------|---------|
| `report-gen` | HTML report | `reports/report-<timestamp>.html` + `reports/report-latest.html` |
| `env-gen` | Docker compose | `docker-compose-<slug>.yml` (single file, no versioning needed) |
| `rubric-gen` | Evaluator scripts | `evaluators/<criterion_slug>.py` (single file, no versioning needed) |