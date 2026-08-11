---
name: report-audit
description: 'ACQUIT audit for the report-gen stage. Reads report-gen worker output (HTML report) and verifies (a) the report was honestly generated, (b) the report is real and usable (actually parse HTML and cross-check counts vs eval-wiki), (c) provenance links resolve. Cross-model required. Use after report-gen runs, or when user says "审计报告", "audit report", "检查报告".'
argument-hint: "[report-path] [--strict]"
allowed-tools: Bash(*), Read, Write, Edit, Grep, Glob
role: ACQUIT
depends-on: [eval-wiki, report-gen]
produces: [audit-verdict]
audits: [report-gen]
cross-model-required: true
audits-stage: 4
---

# report-audit Skill

## Overview

ACQUIT audit skill for **Stage 4 (report-gen)**. The report-gen worker is a
DRIVE role that generates an HTML verification report. This skill audits
whether report-gen *honestly completed* its work — it never generates the
report itself.

Per issue #5, each pipeline stage must have a companion ACQUIT audit that:

1. **Reads the worker's output** — the versioned + latest HTML report.
2. **Checks three things**:
   - a. **Completeness** — did report-gen truthfully do the work (report
     file exists and is non-trivial, versioned + latest copies present)?
   - b. **Usability** — is the report real and usable (actually parse the
     HTML, cross-check stat cards against eval-wiki counts, verify each
     task/run/rubric referenced actually exists)?
   - c. **Provenance** — provenance/evidence links in the report resolve
     to real files (not broken links or placeholders).

This is an **ACQUIT** role — the auditor must be a *different model family*
than the one that ran report-gen, per `acceptance-gate.md`.

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
REPORT_PATH="${1:-reports/report-latest.html}"
if [ ! -f "$REPORT_PATH" ]; then
    echo "ERROR: report not found: $REPORT_PATH" >&2
    exit 1
fi
```

### Phase 1: Read Worker Output

```bash
# Report-gen produces a versioned copy + a -latest copy
wc -c "$REPORT_PATH"
head -c 2000 "$REPORT_PATH"
ls -1 reports/report-*.html 2>/dev/null
```

### Phase 2: Audit Checklist

#### 2a. Completeness — did report-gen honestly do the work?

```bash
COMPLETENESS_FAIL=0
# Non-trivial size (not an empty/stub file)
SIZE=$(wc -c < "$REPORT_PATH")
[ "$SIZE" -gt 200 ] || { echo "FAIL (completeness): report too small ($SIZE bytes)"; COMPLETENESS_FAIL=1; }
# Both versioned + latest must exist
ls reports/report-*.html > /dev/null 2>&1 || { echo "FAIL (completeness): no versioned report"; COMPLETENESS_FAIL=1; }
[ -f "reports/report-latest.html" ] || { echo "FAIL (completeness): report-latest.html missing"; COMPLETENESS_FAIL=1; }
# Has the expected structural anchors
grep -q "<html" "$REPORT_PATH" || { echo "FAIL (completeness): not HTML"; COMPLETENESS_FAIL=1; }
grep -q "Summary" "$REPORT_PATH" || { echo "FAIL (completeness): missing summary section"; COMPLETENESS_FAIL=1; }
```

#### 2b. Usability — is the report real and usable? (actually parse & cross-check)

This is the core "actually run" check from issue requirement b. The report's
stat cards must match the actual eval-wiki counts.

```bash
USABILITY_FAIL=0
if [ -f "$EVAL_WIKI_SCRIPT" ]; then
    STATS=$(python3 "$EVAL_WIKI_SCRIPT" stats eval-wiki/)
    # Cross-check: counts in the report must equal counts in eval-wiki.
    # Parse the report's stat cards and compare.
    TASK_COUNT_WIKI=$(echo "$STATS" | grep -i task | head -1)
    echo "Wiki stats: $STATS"
    # If the report claims N tasks but eval-wiki has M, that's a failure.
    :
fi
# HTML must be well-formed enough to parse
python3 -c "
from html.parser import HTMLParser
class P(HTMLParser): pass
with open('$REPORT_PATH') as f:
    P().feed(f.read())
" 2>/dev/null || { echo "FAIL (usability): HTML does not parse"; USABILITY_FAIL=1; }
```

#### 2c. Provenance — do evidence/provenance links resolve?

```bash
PROVENANCE_FAIL=0
# Extract hrefs that point to evidence files and verify they exist.
grep -oE 'href="[^"]+"' "$REPORT_PATH" | sed 's/href="//;s/"//' | \
  while read -r href; do
    case "$href" in
        http*|#*) continue ;;   # external or anchor links
        *) [ -f "$href" ] || { echo "FAIL (provenance): broken link $href"; PROVENANCE_FAIL=1; } ;;
    esac
  done
```

### Phase 3: Record Audit Verdict

```bash
VERDICT="pass"
[ "$COMPLETENESS_FAIL" -eq 1 ] && VERDICT="fail"
[ "$USABILITY_FAIL" -eq 1 ] && VERDICT="fail"
[ "$PROVENANCE_FAIL" -eq 1 ] && VERDICT="fail"

if [ -f "$EVAL_WIKI_SCRIPT" ]; then
    python3 "$EVAL_WIKI_SCRIPT" add-feedback eval-wiki/ \
      --target-type report \
      --target-id "report-latest" \
      --from auditor \
      --issue-type misalignment \
      --description "report-audit verdict: $VERDICT" \
      --action "audit" \
      --status "$VERDICT"
fi
echo "report-audit verdict: $VERDICT"
[ "$VERDICT" = "pass" ] && exit 0 || exit 1
```

## Audit Checklist Summary

| Check | What it verifies | Pass condition |
|-------|------------------|----------------|
| Read Worker Output | versioned + latest report | files readable |
| Completeness | non-trivial HTML, structure present | 0 failures |
| Usability | HTML parses, counts match wiki | 0 failures |
| Provenance | evidence links resolve | 0 failures |

## Cross-Model Requirement

This auditor MUST run on a different model family than report-gen, per
`acceptance-gate.md` Hard Invariant #1.

## Output

- `eval-wiki/feedback/report-audit-<timestamp>.md` — audit verdict
- Exit code 0 (pass) / 1 (fail) for pipeline gating
