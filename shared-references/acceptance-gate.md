# Acceptance Gate: DRIVE vs ACQUIT

Adapted from ARIS `acceptance-gate.md`.

## Principle

The DRIVE vs ACQUIT principle separates tasks that can be judged by the
same model (DRIVE) from tasks that MUST be cross-model (ACQUIT).

## DRIVE Roles

DRIVE skills generate artifacts. They can be performed by the same model
because they are creative/constructive, not evaluative.

| Skill | DRIVE Aspect |
|-------|-------------|
| `task-gen` | Generate task specifications |
| `env-gen` | Generate Docker environment configurations |
| `report-gen` | Generate HTML verification reports |

**Script evaluators** in `rubric-gen` are also DRIVE — mechanical checks
(e.g., output format, tool call correctness) do not require a different
model.

## ACQUIT Roles

ACQUIT skills define quality or correctness. They MUST use a different
model family than the one that generated the artifact.

| Skill | ACQUIT Aspect |
|-------|--------------|
| `rubric-gen` | Rubric quality criteria (what is "correct") |
| `feedback-align` | Change verification (did the change resolve the issue) |

**LLM judge evaluators** in `rubric-gen` are ACQUIT — they must be
cross-model per the acceptance gate.

## Hard Invariants

1. **Cross-model review always on**: Any ACQUIT evaluation must use a
   different model family than the DRIVE generation.
2. **Reviewer independence always on**: The evaluating model must not have
   been involved in the original generation.
3. **Script evaluators can self-judge**: Mechanical checks (exit code,
   format validation) are deterministic and do not require a different model.
4. **LLM judge evaluators cannot self-judge**: Any evaluation involving
   semantic judgment must be cross-model.

## Verification

For ACQUIT operations, the verifying agent must:
- Be from a different model family (e.g., if task-gen used Claude, rubric-gen
  must use GPT or another model)
- Report which model family performed the verification
- Record the verification result in the artifact metadata