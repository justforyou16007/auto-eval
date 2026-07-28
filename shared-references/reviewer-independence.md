# Reviewer Independence

_Adapted from ARIS patterns for the eval-wiki context._

## Principle

LLM judges must only receive raw output paths, never agent self-interpretation.
This prevents the evaluator from being biased by the agent's own claims about
its performance.

## The Problem

When an agent generates a task, environment, rubric, or report, it may also
produce a self-assessment or explanation of its work. If that self-assessment
is included in the evaluation material, the LLM judge may be influenced by it
rather than evaluating the actual output.

## The Rule

**The evaluator (LLM judge) receives only:**

1. Raw output files (stdout, stderr, trace.jsonl)
2. The rubric criteria
3. The task specification
4. Evidence files (logs, screenshots, output samples)

**The evaluator NEVER receives:**

1. The agent's own commentary on its work
2. The agent's self-assessment
3. The agent's explanations or justifications
4. Any "summary" written by the agent being evaluated

## Implementation

In the eval-wiki pipeline, reviewer independence is enforced by:

- `capture-filter.py` strips agent self-references from captured output
- `evidence-check.py` verifies that only raw evidence paths are referenced
- Run records store `raw_output_path` (not agent commentary)
- `accept` subcommand in `run-state.py` provides self-acquit guard (rejects
  reviewer names containing "claude" unless `--force` is used)

## Cross-Reference

- `acceptance-gate.md` — ACQUIT roles must be cross-model
- `capture-antipatterns.md` — negative-tool-claim patterns
- `run-state.py` — self-acquit guard in accept command