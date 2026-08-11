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
| DRIVE | Yes | No | task-gen, env-gen, rubric-gen, report-gen, feedback-align |
| ACQUIT | No | Yes | task-audit, env-audit, rubric-audit, report-audit, feedback-audit |
| TOOL | N/A | N/A | eval-wiki |

> **Note.** The `DRIVE_ACQUIT` role is no longer used after the issue #5
> redesign. Every pipeline stage is a pure DRIVE worker, and each has a
> dedicated ACQUIT audit skill (`*-audit`) that verifies it cross-model.
> Workers declare `audited-by: [<audit-skill>]` in their frontmatter.

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