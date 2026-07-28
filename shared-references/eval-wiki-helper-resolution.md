# eval-wiki Helper Resolution Chain

Adapted from ARIS `wiki-helper-resolution.md`.

## Purpose

All skills that depend on `eval-wiki` must resolve the `$EVAL_WIKI_SCRIPT`
path to the `eval-wiki.py` tool. This document defines the canonical
resolution chain.

## Resolution Chain

The resolution chain checks paths in priority order. The first match wins.

```bash
cd "$(git rev-parse --show-toplevel 2>/dev/null || pwd)" || exit 1

# 1. Project-level installed copy (created by install_eval_wiki.sh)
#    This is the primary path when the script was installed into the
#    target project via `bash /path/to/auto-eval/tools/install_eval_wiki.sh`
EVAL_WIKI_SCRIPT=".eval/dist/tools/eval-wiki.py"

# 2. Fall back to legacy dist path (within the auto-eval repo itself)
[ -f "$EVAL_WIKI_SCRIPT" ] || EVAL_WIKI_SCRIPT="dist/tools/eval-wiki.py"

# 3. Fall back to AUTOEVAL_REPO environment variable or auto-detected repo
[ -f "$EVAL_WIKI_SCRIPT" ] || {
    EVAL_REPO="${AUTOEVAL_REPO:-}"
    # Auto-detect by walking up parent directories
    if [ -z "$EVAL_REPO" ]; then
        CANDIDATE="$(pwd)"
        while [ "$CANDIDATE" != "/" ]; do
            [ -f "$CANDIDATE/src/tools/eval-wiki.py" ] && { EVAL_REPO="$CANDIDATE"; break; }
            CANDIDATE="$(dirname "$CANDIDATE")"
        done
    fi
    [ -n "$EVAL_REPO" ] && EVAL_WIKI_SCRIPT="$EVAL_REPO/dist/tools/eval-wiki.py"
}
```

## Variants

### Variant A — Hard Fail (for `eval-wiki` skill itself)

The eval-wiki skill IS the tool. If the script is not found, the skill
cannot operate:

```bash
if [ ! -f "$EVAL_WIKI_SCRIPT" ]; then
    echo "ERROR: eval-wiki.py not found. Run 'tools/install_eval_wiki.sh' first." >&2
    exit 1
fi
```

### Variant B — Warn + Skip (for caller skills)

Caller skills (task-gen, env-gen, rubric-gen, report-gen, feedback-align)
can operate without the wiki (e.g., dry-run mode). If the script is not
found, warn and skip the wiki write:

```bash
if [ ! -f "$EVAL_WIKI_SCRIPT" ]; then
    echo "WARNING: eval-wiki.py not found at $EVAL_WIKI_SCRIPT. Skipping eval-wiki write." >&2
    # Continue without wiki write
fi
```

## Usage in SKILL.md

Each skill's SKILL.md must include the resolution block near the top of its
bash code sections, using the appropriate variant. The resolved
`$EVAL_WIKI_SCRIPT` variable is then used for all `eval-wiki.py` invocations.