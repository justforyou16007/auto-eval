# Skill Governance

_Adapted from ARIS patterns for the eval-wiki context._

## Structural Constraints on Skills

Skills in the eval-wiki pipeline must follow structural constraints to
ensure consistency, testability, and auditability.

## SKILL.md Frontmatter Requirements

Every SKILL.md must have:

```yaml
---
name: <skill-name>
description: '<human-readable description>'
argument-hint: '<argument pattern>'
allowed-tools: <list of allowed tools>
role: <DRIVE|ACQUIT|TOOL>
depends-on: [<list of dependencies>]
produces: [<list of artifact types>]
audited-by: [<audit skill>]   # for DRIVE workers; ACQUIT skills use `audits:` instead
---
```

> The `DRIVE_ACQUIT` role is deprecated (issue #5). Workers are `DRIVE`;
> their verifiers are separate `ACQUIT` skills. A DRIVE worker declares
> `audited-by: [<audit-skill>]`; an ACQUIT audit skill declares
> `audits: [<worker>]` and `cross-model-required: true`.

## Role Constraints

| Role | Can Self-Judge? | Cross-Model Required? | Example Skills |
|------|----------------|----------------------|----------------|
| DRIVE | Yes | No | task-gen, env-gen, rubric-gen, report-gen, feedback-align, benchmark-compare, benchmark-search |
| ACQUIT | No | Yes | task-audit, env-audit, rubric-audit, report-audit, feedback-audit, scorecard-evaluator, benchmark2-evaluator |
| TOOL | N/A | N/A | eval-wiki |

> **Note.** The `DRIVE_ACQUIT` role is no longer used after the issue #5
> redesign. Every pipeline stage is a pure DRIVE worker, and each has a
> dedicated ACQUIT audit skill (`*-audit`) that verifies it cross-model.
> Workers declare `audited-by: [<audit-skill>]` in their frontmatter.

## Sub-Agent Dispatch Pattern (issue #9 redesign)

A **DRIVE orchestrator** may delegate evaluation to one or more **ACQUIT
sub-skills** via **dispatch**. The orchestrator (DRIVE) does **NOT** perform
evaluation itself; it only dispatches sub-agents, collects their verdicts,
aggregates the results, and writes them to eval-wiki. All scoring dimensions
and quantitative metrics are owned by the ACQUIT sub-agents, whose criteria
are strictly derived from cited papers (never invented).

### Pattern Rules

1. **The orchestrator never judges directly.** A DRIVE orchestrator that
   dispatches ACQUIT sub-agents must not define its own scoring dimensions,
   run grep-based scoring of tasks, or apply hardcoded neutral defaults. It
   only dispatches, collects, and aggregates.
2. **Reviewer independence.** ACQUIT sub-agents receive **raw** benchmark data
   (task files, scenario definitions, run results, score data), never the
   DRIVE worker's self-assessment. Per `reviewer-independence.md`.
3. **Cross-model required.** Dispatched ACQUIT sub-agents declare
   `cross-model-required: true` and `audits: [<orchestrator>]` so the
   orchestrator's output is verified by a different model family. Per
   `acceptance-gate.md`.
4. **Fan-out + degrade.** Dispatch is parallel; if a single sub-agent or a
   single candidate fails, the orchestrator records that result as N/A and
   continues with the remaining sub-agents/candidates. Per
   `fan-out-pattern.md`.
5. **Criteria trace to papers.** Every scoring dimension/metric the ACQUIT
   sub-agent applies must trace to a specific section/definition in a cited
   paper. The sub-agent quotes paper language when defining what it checks.

### Example: benchmark-compare

`benchmark-compare` is a DRIVE orchestrator that dispatches three
sub-agents:

- **scorecard-evaluator** (ACQUIT, cross-model) — judges six BetterBench
  dimensions (arxiv 2411.12990) from raw benchmark data.
- **benchmark2-evaluator** (ACQUIT, cross-model) — computes three
  Benchmark2 metrics (CBRC/DS/CAD, arxiv 2601.03986) from raw run/score
  data.
- **benchmark-search** (DRIVE) — web-searches for top-3 similar benchmarks
  in standalone mode.

The `benchmark-compare` orchestrator itself contains **no** inline scoring;
it only dispatches these sub-agents, aggregates (averages) their verdicts,
and writes the composite result to eval-wiki plus an HTML report.

## Phase Structure

Each SKILL.md must define phases in order:

1. Each phase has a clear entry condition
2. Each phase produces a concrete artifact
3. Phases are numbered sequentially
4. Phase artifacts are validated before proceeding

## Helper Resolution

Each SKILL.md must include the helper resolution chain for
`$EVAL_WIKI_SCRIPT`:

- **Variant A (Hard Fail)**: For `eval-wiki` skill itself
- **Variant B (Warn + Skip)**: For caller skills

## Cross-Reference

- `eval-wiki-helper-resolution.md` — Helper resolution chain
- `acceptance-gate.md` — DRIVE vs ACQUIT roles
- `integration-contract.md` — Six required components
- `output-manifest.md` — Artifact tracking