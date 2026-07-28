# eval-wiki Helper Resolution Chain

Adapted from ARIS `wiki-helper-resolution.md`.

## Purpose

All skills that depend on `eval-wiki` must resolve the `$EVAL_WIKI_SCRIPT`
path to the `eval-wiki.py` tool. This document defines the canonical
resolution chain.

## Resolution Chain

```bash
cd "$(git rev-parse --show-toplevel 2>/dev/null || pwd)" || exit 1

# 1. Check for installed copy via .eval/installed-skills.txt
EVAL_REPO="${EVAL_REPO:-$(awk -F'\t' '$1=="repo_root"{print $2; exit}' .eval/installed-skills.txt 2>/dev/null)}"

# 2. Check .eval/dist/tools/eval-wiki.py (installed via install_eval_wiki.sh)
EVAL_WIKI_SCRIPT=".eval/dist/tools/eval-wiki.py"

# 3. Fall back to canonical dist path
[ -f "$EVAL_WIKI_SCRIPT" ] || EVAL_WIKI_SCRIPT="dist/tools/eval-wiki.py"

# 4. Fall back to EVAL_REPO path
[ -f "$EVAL_WIKI_SCRIPT" ] || { [ -n "${EVAL_REPO:-}" ] && EVAL_WIKI_SCRIPT="$EVAL_REPO/dist/tools/eval-wiki.py"; }
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