# Component Assembly Contract

## Purpose

Defines the contract for how `env-gen` uses the `env-component-manager` to assemble, fine-tune, and register environment components for Agent evaluation tasks.

## Activation Predicate

`task` entity status == `finalized`

## Canonical Helper

`$COMPONENT_MANAGER_SCRIPT`

Resolved via the same chain pattern as `$EVAL_WIKI_SCRIPT`:

```bash
cd "$(git rev-parse --show-toplevel 2>/dev/null || pwd)" || exit 1

# 1. Project-level installed copy
COMPONENT_MANAGER_SCRIPT=".eval/dist/tools/env-component-manager.py"

# 2. Fall back to legacy dist path
[ -f "$COMPONENT_MANAGER_SCRIPT" ] || COMPONENT_MANAGER_SCRIPT="dist/tools/env-component-manager.py"

# 3. Fall back to EVAL_REPO
[ -f "$COMPONENT_MANAGER_SCRIPT" ] || {
    EVAL_REPO="${EVAL_REPO:-$(awk -F'\t' '$1=="repo_root"{print $2; exit}' .eval/installed-skills.txt 2>/dev/null)}"
    [ -n "${EVAL_REPO:-}" ] && COMPONENT_MANAGER_SCRIPT="$EVAL_REPO/dist/tools/env-component-manager.py"
}

if [ ! -f "$COMPONENT_MANAGER_SCRIPT" ]; then
    echo "WARNING: env-component-manager.py not found. Skipping component assembly." >&2
fi
```

## Artifacts

- `environments/<slug>.md` — Environment metadata in eval-wiki
- `docker-compose-<slug>.yml` — Docker Compose configuration
- `component-manifest.json` — JSON listing all assembled components, their versions, and fork lineage

## Failure Policy

**Policy B (Side-Effect)** — Environment failure does not block the task. If provisioning fails, the environment is marked with `env_status: missing` and the task continues without a live environment.

## Verifier

Health check must pass within 60 seconds (poll every 5s, max 12 retries). If the health check passes, the environment is considered `provisioned`. If it fails, the environment is marked `provision_failed`.

## Component Reuse Protocol

The component reuse protocol follows a strict search→fork→fine-tune→register-back cycle:

1. **Search**: Query `tree.yaml` via `$COMPONENT_MANAGER_SCRIPT search` for matching infra and app components based on task requirements.

2. **Fork** (if exact match found): If a close match is found, fork the component via `$COMPONENT_MANAGER_SCRIPT fork` to create a starting point for agent fine-tuning.

3. **Fine-tune**: The agent modifies the forked component files:
   - Adjust Dockerfile (add packages, change base image)
   - Modify app code (add/remove API endpoints, change business logic)
   - Update database schema (add tables, modify columns)
   - Configure mock services (add new mock endpoints)

4. **Register back**: Register the fine-tuned component back into the tree via `$COMPONENT_MANAGER_SCRIPT register`.

5. **Assemble**: Use `$COMPONENT_MANAGER_SCRIPT assemble` to generate the final docker-compose.yml from the fine-tuned components.

## Two-Layer Tree Model

The component tree has two layers:

- **infra/** — Hardware & OS infrastructure (Docker base images, runtime environments)
  - Examples: ubuntu-22.04, python-3.12, node-20
  - Each infra component has a Dockerfile and component.yaml

- **app/** — Application components (e-commerce backends, search engines, file systems, mock services)
  - Examples: e-commerce backend, search engine, file system
  - Each app component has source code, requirements.txt, and component.yaml
  - App components declare `depends_on` listing required infra components

## Lazy Loading Guarantee

- `tree.yaml` is the lightweight index — always loaded, always the source of truth for component discovery.
- Actual component files (Dockerfiles, source code, schema.sql) are ONLY loaded during:
  - `assemble` — to generate docker-compose.yml
  - `info` — to display full component details
  - `fork` — to copy component files for fine-tuning
- When a new component is registered (via `fork` or `register`), only `tree.yaml` is updated immediately; the component files are written to disk.

## Component Registration

Components are stored at the project-root `components/` directory (NOT inside eval-wiki/). eval-wiki only stores references to components via the environment manifest, not the components themselves.