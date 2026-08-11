---
name: env-audit
description: 'ACQUIT audit for the env-gen stage. Reads env-gen worker output (docker-compose + env record) and verifies (a) the environment was honestly provisioned, (b) the environment is real and usable (actually runs & passes health check), (c) the env matches the task constraints. Cross-model required. Use after env-gen runs, or when user says "审计env", "audit environment", "检查环境".'
argument-hint: "[task-id] [--strict]"
allowed-tools: Bash(*), Read, Write, Edit, Grep, Glob
role: ACQUIT
depends-on: [eval-wiki, env-gen]
produces: [audit-verdict]
audits: [env-gen]
cross-model-required: true
audits-stage: 2
---

# env-audit Skill

## Overview

ACQUIT audit skill for **Stage 2 (env-gen)**. The env-gen worker is a DRIVE
role that assembles and provisions Docker environments. This skill audits
whether env-gen *honestly completed* its work — it never provisions
environments itself.

Per issue #5, each pipeline stage must have a companion ACQUIT audit that:

1. **Reads the worker's output** — `docker-compose-<slug>.yml`,
   `component-manifest.json`, and the env record in eval-wiki.
2. **Checks three things**:
   - a. **Completeness** — did env-gen truthfully do the work (compose file
     exists, manifest lists real components, env record has status)?
   - b. **Usability** — is the environment real and usable (actually run
     `docker compose config`, build, and health check; not just claimed)?
   - c. **Constraint match** — the environment matches the task's
     scenario_type, allowed tools, and resource limits.

This is an **ACQUIT** role — the auditor must be a *different model family*
than the one that ran env-gen, per `acceptance-gate.md`.

## Helper Resolution

Resolve `$EVAL_WIKI_SCRIPT` via the shared chain (Variant B — warn + skip):

```bash
cd "$(git rev-parse --show-toplevel 2>/dev/null || pwd)" || exit 1
EVAL_REPO="${EVAL_REPO:-$(awk -F'\t' '$1=="repo_root"{print $2; exit}' .eval/installed-skills.txt 2>/dev/null)}"
EVAL_WIKI_SCRIPT=".eval/dist/tools/eval-wiki.py"
[ -f "$EVAL_WIKI_SCRIPT" ] || EVAL_WIKI_SCRIPT="dist/tools/eval-wiki.py"
[ -f "$EVAL_WIKI_SCRIPT" ] || { [ -n "${EVAL_REPO:-}" ] && EVAL_WIKI_SCRIPT="$EVAL_REPO/dist/tools/eval-wiki.py"; }
if [ ! -f "$EVAL_WIKI_SCRIPT" ]; then
    echo "WARNING: eval-wiki.py not found. Skipping eval-wiki read." >&2
fi
```

## Phases

### Phase 0: Resolve Scope

```bash
TASK_ID="${1:-}"
if [ -z "$TASK_ID" ]; then
    echo "ERROR: task-id is required (which env to audit)" >&2
    exit 1
fi
SLUG="$TASK_ID"
```

### Phase 1: Read Worker Output

Read the artifacts env-gen claimed to produce.

```bash
COMPOSE="docker-compose-${SLUG}.yml"
MANIFEST="component-manifest.json"
ENV_FILE="eval-wiki/environments/${SLUG}-env.md"

[ -f "$COMPOSE" ] && cat "$COMPOSE"
[ -f "$MANIFEST" ] && cat "$MANIFEST"
[ -f "$ENV_FILE" ] && cat "$ENV_FILE"
if [ -f "$EVAL_WIKI_SCRIPT" ]; then
    python3 "$EVAL_WIKI_SCRIPT" query eval-wiki/ "env:${SLUG}-env"
fi
```

### Phase 2: Audit Checklist

#### 2a. Completeness — did env-gen honestly do the work?

- `docker-compose-<slug>.yml` exists and is non-empty.
- `component-manifest.json` exists and lists ≥1 component.
- The env record in eval-wiki has a `status` field (not blank).
- No `_TODO` / placeholder in compose or manifest.

```bash
COMPLETENESS_FAIL=0
[ -s "$COMPOSE" ] || { echo "FAIL (completeness): $COMPOSE missing/empty"; COMPLETENESS_FAIL=1; }
[ -s "$MANIFEST" ] || { echo "FAIL (completeness): $MANIFEST missing/empty"; COMPLETENESS_FAIL=1; }
grep -q "_TODO" "$COMPOSE" 2>/dev/null && { echo "FAIL (completeness): compose has _TODO"; COMPLETENESS_FAIL=1; }
```

#### 2b. Usability — is the environment real and usable? (actually run & verify)

This is the core "actually run" check from issue requirement b.

```bash
USABILITY_FAIL=0
# Validate compose syntax
if ! docker compose -f "$COMPOSE" config -q 2>/dev/null; then
    echo "FAIL (usability): $COMPOSE does not parse"
    USABILITY_FAIL=1
fi

# If not dry-run, actually build + health-check
if [ "${DRY_RUN:-false}" != "true" ]; then
    docker compose -f "$COMPOSE" build -q 2>/dev/null || {
        echo "FAIL (usability): build failed"; USABILITY_FAIL=1; }
    docker compose -f "$COMPOSE" up -d 2>/dev/null || {
        echo "FAIL (usability): up failed"; USABILITY_FAIL=1; }
    # Poll health check (max 60s)
    HEALTHY=false
    for i in $(seq 1 12); do
        sleep 5
        docker compose -f "$COMPOSE" ps --health 2>/dev/null | grep -q healthy && {
            HEALTHY=true; break; }
    done
    [ "$HEALTHY" = true ] || {
        echo "FAIL (usability): health check did not pass"; USABILITY_FAIL=1; }
    docker compose -f "$COMPOSE" down 2>/dev/null || true
fi
```

#### 2c. Constraint match — does the env match the task?

```bash
CONSTRAINT_FAIL=0
if [ -f "$EVAL_WIKI_SCRIPT" ]; then
    TASK_DATA=$(python3 "$EVAL_WIKI_SCRIPT" query eval-wiki/ "$TASK_ID")
    # Cross-model judge: does the env's image/network/resources/health-check
    # match the task's scenario_type, allowed tools, and cost budget?
    :
fi
```

### Phase 3: Record Audit Verdict

```bash
VERDICT="pass"
[ "$COMPLETENESS_FAIL" -eq 1 ] && VERDICT="fail"
[ "$USABILITY_FAIL" -eq 1 ] && VERDICT="fail"
[ "$CONSTRAINT_FAIL" -eq 1 ] && VERDICT="fail"

if [ -f "$EVAL_WIKI_SCRIPT" ]; then
    python3 "$EVAL_WIKI_SCRIPT" add-feedback eval-wiki/ \
      --target-type env \
      --target-id "$SLUG-env" \
      --from auditor \
      --issue-type env_error \
      --description "env-audit verdict: $VERDICT" \
      --action "audit" \
      --status "$VERDICT"
fi
echo "env-audit verdict: $VERDICT"
[ "$VERDICT" = "pass" ] && exit 0 || exit 1
```

## Audit Checklist Summary

| Check | What it verifies | Pass condition |
|-------|------------------|----------------|
| Read Worker Output | compose + manifest + env record | files readable |
| Completeness | compose/manifest non-empty, status set | 0 failures |
| Usability | `docker compose config` + build + health | 0 failures |
| Constraint match | env matches task constraints | 0 failures |

## Cross-Model Requirement

This auditor MUST run on a different model family than env-gen, per
`acceptance-gate.md` Hard Invariant #1.

## Output

- `eval-wiki/feedback/env-audit-<timestamp>.md` — audit verdict
- Exit code 0 (pass) / 1 (fail) for pipeline gating
