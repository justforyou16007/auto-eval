# Integration Contract

Adapted from ARIS `integration-contract.md`.

## Six Required Components

Every cross-skill integration in the eval-wiki architecture must define
these six components:

### 1. Activation Predicate

The condition that triggers a downstream skill. For example:

- `task-gen` → `env-gen`: activated when a task with `status: finalized` exists
- `task-gen` → `rubric-gen`: activated when a task with `scenario_type` is set
- `report-gen`: activated when runs exist with verdicts
- `feedback-align`: activated when a user or auto-audit submits feedback

### 2. Canonical Helper

The tool or script that performs the integration action. For eval-wiki,
this is always `$EVAL_WIKI_SCRIPT` (resolved via the helper resolution
chain in `eval-wiki-helper-resolution.md`).

### 3. Concrete Artifact

The file or data structure produced by the integration. Examples:

- Task file: `eval-wiki/tasks/<slug>.md`
- Environment file: `eval-wiki/environments/<slug>.md`
- Rubric file: `eval-wiki/rubrics/<slug>.md`
- Run file: `eval-wiki/runs/<slug>.md`
- Feedback file: `eval-wiki/feedback/<slug>.md`
- Report: `reports/report-<timestamp>.html`

### 4. Output Manifest

A record of what was produced, including:

- Path to the concrete artifact
- Timestamp of creation
- Entity ID (node_id)
- Status (draft, finalized, provisioned, etc.)

### 5. Fallback Strategy

When a skill cannot complete its integration, one of these fallback
strategies applies:

| Strategy | Code | Behavior |
|----------|------|----------|
| **Gate** | A | Block execution; hard fail |
| **Side-effect** | B | Continue with warning; skip write |
| **Forensic** | C | Write failure artifact with diagnostic info |
| **Cascade** | D | Notify downstream skills of partial failure |
| **Diagnostic** | E | Collect failure details for later analysis |

- **Variant A (Gate)**: Used by `eval-wiki` skill itself
- **Variant B (Side-effect)**: Used by caller skills (task-gen, env-gen, etc.)
- **Variant C (Forensic)**: Used by `feedback-align` when verification fails
- **Variant D (Cascade)**: Used by `report-gen` when data is incomplete
- **Variant E (Diagnostic)**: Used by `rubric-gen` when evaluator scripts fail verification

### 6. Verifier

The mechanism that confirms the integration succeeded. Examples:

- File existence check: `[ -f "$artifact_path" ]`
- Frontmatter validation: check YAML frontmatter for required fields
- Script execution: `python3 <script> --help` returns 0
- Health check: endpoint returns 200
- Cross-model verification: different model family confirms the result