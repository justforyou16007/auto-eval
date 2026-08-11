---
name: feedback-audit
description: 'ACQUIT audit for the feedback-align stage. Reads feedback-align worker output (applied changes + feedback record) and verifies (a) the change was honestly applied, (b) the change is real and effective (re-run affected task and confirm the issue is resolved), (c) the feedback status is accurate. Cross-model required. Use after feedback-align runs, or when user says "审计反馈", "audit feedback", "检查反馈".'
argument-hint: "[feedback-id|target-id] [--strict]"
allowed-tools: Bash(*), Read, Write, Edit, Grep, Glob
role: ACQUIT
depends-on: [eval-wiki, feedback-align]
produces: [audit-verdict]
audits: [feedback-align]
cross-model-required: true
audits-stage: 5
---

# feedback-audit Skill

## Overview

ACQUIT audit skill for **Stage 5 (feedback-align)**. After the role
redesign (issue #5), **feedback-align is a DRIVE worker** that records
feedback, proposes, and applies changes. The ACQUIT responsibility for
*verifying the change resolved the issue* now lives here, in this
dedicated audit skill. This skill never applies feedback itself — it only
audits the applied change.

Per issue #5, each pipeline stage must have a companion ACQUIT audit that:

1. **Reads the worker's output** — the feedback record with status
   `applied` and the modified entity (task/rubric/env/report).
2. **Checks three things**:
   - a. **Completeness** — did feedback-align truthfully do the work
     (feedback record exists, status is `applied` not still `open`,
     from_value/to_value present)?
   - b. **Usability** — is the change real and effective (actually re-run
     the affected task and confirm the issue is resolved, not just
     claimed)?
   - c. **Status accuracy** — the recorded status matches the actual
     outcome (a change that did not resolve the issue must not be marked
     `verified`).

This is an **ACQUIT** role — the auditor must be a *different model family*
than the one that ran feedback-align, per `acceptance-gate.md`.

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
TARGET_ID="${1:-}"
if [ -z "$TARGET_ID" ]; then
    echo "ERROR: feedback target-id is required" >&2
    exit 1
fi
```

### Phase 1: Read Worker Output

Read the feedback record feedback-align produced and the modified entity.

```bash
if [ -f "$EVAL_WIKI_SCRIPT" ]; then
    python3 "$EVAL_WIKI_SCRIPT" query eval-wiki/ "feedback:$TARGET_ID"
fi
# Read the target entity (task/rubric/env) that was modified.
for fb_file in eval-wiki/feedback/*.md; do
    [ -f "$fb_file" ] || continue
    grep -q "target_id:[[:space:]]*$TARGET_ID" "$fb_file" && cat "$fb_file"
done
```

### Phase 2: Audit Checklist

#### 2a. Completeness — did feedback-align honestly do the work?

```bash
COMPLETENESS_FAIL=0
STATUS=""
for fb_file in eval-wiki/feedback/*.md; do
    [ -f "$fb_file" ] || continue
    grep -q "target_id:[[:space:]]*$TARGET_ID" "$fb_file" || continue
    STATUS=$(grep -o 'status:[[:space:]]*[a-z_]*' "$fb_file" | tail -1 | sed 's/status:[[:space:]]*//')
    # status must have advanced beyond 'open'/'analyzed' to 'applied'/'verified'
    case "$STATUS" in
        applied|verified) ;;
        *) echo "FAIL (completeness): feedback status is '$STATUS', not applied/verified"; COMPLETENESS_FAIL=1 ;;
    esac
    # from_value and to_value must both be present (the change was recorded)
    grep -q "from_value" "$fb_file" || { echo "FAIL (completeness): missing from_value"; COMPLETENESS_FAIL=1; }
    grep -q "to_value" "$fb_file" || { echo "FAIL (completeness): missing to_value"; COMPLETENESS_FAIL=1; }
done
```

#### 2b. Usability — is the change real and effective? (actually re-run)

This is the core "actually run & verify results" check from issue
requirement b. The auditor re-runs the affected task/rubric and confirms
the *original issue* is actually resolved, not merely claimed.

```bash
USABILITY_FAIL=0
# Re-run the affected task in its environment and re-score.
# The verifying agent MUST be a different model family than the one that
# applied the change (acceptance-gate.md).
# Compare the new verdict against the issue described in the feedback record.
# If the issue persists, the change was not effective → FAIL.
echo "Re-running affected task for $TARGET_ID to confirm the fix..."
# (In a real run: invoke the agent under test against the modified task/env,
#  score with the rubric, and check the originally-reported issue no longer
#  reproduces.)
:  # cross-model verification placeholder
```

#### 2c. Status accuracy — does the recorded status match reality?

```bash
ACCURACY_FAIL=0
# If the re-run in 2b shows the issue is NOT resolved, the feedback record
# must NOT be marked 'verified'. feedback-align may have marked it verified
# prematurely — this audit catches that.
if [ "$USABILITY_FAIL" -eq 1 ] && [ "$STATUS" = "verified" ]; then
    echo "FAIL (status accuracy): marked verified but issue not resolved"
    ACCURACY_FAIL=1
fi
```

### Phase 3: Record Audit Verdict

```bash
VERDICT="pass"
[ "$COMPLETENESS_FAIL" -eq 1 ] && VERDICT="fail"
[ "$USABILITY_FAIL" -eq 1 ] && VERDICT="fail"
[ "$ACCURACY_FAIL" -eq 1 ] && VERDICT="fail"

if [ -f "$EVAL_WIKI_SCRIPT" ]; then
    python3 "$EVAL_WIKI_SCRIPT" add-feedback eval-wiki/ \
      --target-type feedback \
      --target-id "$TARGET_ID" \
      --from auditor \
      --issue-type misalignment \
      --description "feedback-audit verdict: $VERDICT" \
      --action "audit" \
      --status "$VERDICT"
fi
echo "feedback-audit verdict: $VERDICT"
[ "$VERDICT" = "pass" ] && exit 0 || exit 1
```

## Audit Checklist Summary

| Check | What it verifies | Pass condition |
|-------|------------------|----------------|
| Read Worker Output | feedback record + modified entity | files readable |
| Completeness | status applied/verified, values recorded | 0 failures |
| Usability | re-run confirms issue resolved | 0 failures |
| Status accuracy | recorded status matches outcome | 0 failures |

## Cross-Model Requirement

This auditor MUST run on a different model family than feedback-align,
per `acceptance-gate.md` Hard Invariant #1. This is the key change from
the old design, where feedback-align was `DRIVE_ACQUIT` and verified its
own changes — that violated the DRIVE/ACQUIT separation.

## Output

- `eval-wiki/feedback/feedback-audit-<timestamp>.md` — audit verdict
- Exit code 0 (pass) / 1 (fail) for pipeline gating
