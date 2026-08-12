---
name: benchmark-search
description: 'DRIVE sub-agent that searches the internet for publicly known benchmarks sharing similar capabilities/domain with the auto-eval benchmark. Extracts metadata, ranks candidates by domain similarity, and returns top-3 with similarity rationale. Dispatched by benchmark-compare in standalone mode.'
argument-hint: "[--benchmark <path>] [--domain <capability-domain>] [--top 3]"
allowed-tools: Bash(*), Read, Write, Edit, Grep, Glob, WebSearch, WebFetch
role: DRIVE
depends-on: [eval-wiki]
produces: [benchmark-candidates]
---

# benchmark-search Skill

## Overview

**DRIVE sub-agent** dispatched by the `benchmark-compare` orchestrator in
**standalone mode (Mode B)**. It uses **web search** to find publicly known
benchmarks that share similar capabilities/domain with the auto-eval
benchmark, extracts metadata for each candidate, ranks them by domain
similarity, and returns the **top-3** candidates with a similarity rationale.

This skill is a DRIVE role — it performs search and curation (constructive
work), not evaluation. The actual evaluation of the candidates is delegated to
the ACQUIT sub-skills (`scorecard-evaluator`, `benchmark2-evaluator`) by the
orchestrator.

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

## Constants

| Constant | Value | Description |
|----------|-------|-------------|
| `DEFAULT_TOP` | 3 | Number of top candidates to return |
| `CAPABILITY_DOMAINS` | math, reasoning, coding, knowledge, instruction-following, safety, … | LLM capability domains used for search |

## Phases

### Phase 0: Receive Dispatch

The `benchmark-compare` orchestrator dispatches this sub-agent with the
auto-eval benchmark path and (optionally) the capability domain to search for.

```bash
BENCHMARK_PATH="${1:-}"
DOMAIN="${DOMAIN:-}"
TOP="${TOP:-3}"

# If domain not provided, infer it from the benchmark's task files.
if [ -z "$DOMAIN" ] && [ -d "$BENCHMARK_PATH" ]; then
    DOMAIN=$(grep -roh 'capability[: ].*' "$BENCHMARK_PATH" 2>/dev/null \
        | head -1 | sed 's/capability[: ]*//')
fi
```

### Phase 1: Web Search for Candidate Benchmarks

Use **web search** to find candidate benchmarks by LLM capability domain
(math, reasoning, coding, knowledge, instruction-following, safety, etc.).

```bash
# Search the internet for publicly known benchmarks in the same domain.
# For each candidate, collect: name, year, task count, capability domain,
# and model ranking data if available.
#
# Example search queries:
#   "LLM benchmark <DOMAIN> 2024"
#   "public benchmark <DOMAIN> evaluation"
#   "leaderboard <DOMAIN> language models"
#
# The search produces a candidate list with metadata for each entry.
```

### Phase 2: Extract Metadata

For each candidate benchmark, extract the following metadata:

| Field | Description |
|-------|-------------|
| `name` | Benchmark name |
| `year` | Publication / release year |
| `task_count` | Number of tasks/items in the benchmark |
| `capability_domain` | Capability domain (math, reasoning, coding, …) |
| `ranking_data` | Model ranking data if available |

### Phase 3: Rank Candidates by Domain Similarity

Rank candidates by domain similarity:

- **Same domain** (exact capability match) = highest similarity
- **Overlapping** (multiple shared capabilities) = medium similarity
- **Adjacent** (related but not identical domain) = low similarity

### Phase 4: Return Top-3 with Similarity Rationale

Return the top-3 candidates, each with a similarity rationale explaining why
it was selected.

```bash
# Write the top-3 candidates with metadata + similarity rationale.
mkdir -p "${BENCHMARK_PATH:-.}/candidates"
cat > "${BENCHMARK_PATH:-.}/candidates/top-3.json" <<JSONEOF
{
  "domain": "$DOMAIN",
  "top_3": [
    {
      "name": "<candidate-1>",
      "year": "<year>",
      "task_count": "<count>",
      "capability_domain": "<domain>",
      "similarity": "same|overlapping|adjacent",
      "rationale": "<why this candidate was selected>"
    }
  ]
}
JSONEOF
echo "benchmark-search: returned top-3 candidates for domain '$DOMAIN'"
```

## Failure Handling (Degrade)

If web search returns fewer than 3 candidates, or a candidate's metadata
cannot be extracted, record that candidate as **N/A** and continue with the
remaining candidates, per `fan-out-pattern.md`. The orchestrator will degrade
gracefully across the top-3 set.

## Output

- `<benchmark>/candidates/top-3.json` — top-3 candidate benchmarks with
  metadata and similarity rationale.
- Exit code 0 (candidates returned) / non-zero (degrade — fewer than 3).

## References

- `shared-references/fan-out-pattern.md` — parallel dispatch + degrade
- `shared-references/eval-wiki-helper-resolution.md` — helper resolution
