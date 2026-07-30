---
name: env-component-manager
description: 'Tree-based environment component manager with lazy loading. Two layers: infra (OS/runtime) and app (application services). Use when user says "组件管理", "component manager", "register component", or wants to manage reusable environment components.'
argument-hint: '[subcommand: init|register|list|search|assemble|fork|info|tree]'
allowed-tools: Bash(*), Read, Write, Edit, Grep, Glob
role: DRIVE
depends-on: []
produces: [component]
---

# env-component-manager Skill

## Overview

Tree-based environment component manager with lazy loading. Manages reusable
environment components across two layers:
- **infra/** — hardware & OS infrastructure (Docker base images, runtime environments)
- **app/** — application components (e-commerce backends, search engines, file systems, mock services)

Use this skill when the user wants to manage or query reusable environment
components, or when env-gen needs to assemble components for a task.

## Two-Layer Tree Model

```
components/
├── tree.yaml         # Lightweight index (always loaded)
├── infra/            # Layer 1: OS & runtime
│   ├── ubuntu-22.04/ # Dockerfile + component.yaml
│   └── python-3.12/
└── app/              # Layer 2: Application services
    ├── e-commerce/
    │   ├── backend/  # src/ + requirements.txt + component.yaml
    │   ├── frontend/
    │   └── database/ # schema.sql + component.yaml
    └── search-engine/
```

## Lazy Loading Philosophy

- `tree.yaml` is the lightweight index — always loaded, always the source of truth.
- Actual component files (Dockerfiles, source code) are ONLY loaded when a component
  is assembled into an environment (via `assemble`, `info`, or `fork`).
- When a new component is registered (via `fork` or `register`), only `tree.yaml`
  is updated immediately; the component files are written to disk.

## Helper Resolution

Resolve `$COMPONENT_MANAGER_SCRIPT` via the shared chain:

```bash
cd "$(git rev-parse --show-toplevel 2>/dev/null || pwd)" || exit 1
EVAL_REPO="${EVAL_REPO:-$(awk -F'\t' '$1=="repo_root"{print $2; exit}' .eval/installed-skills.txt 2>/dev/null)}"
COMPONENT_MANAGER_SCRIPT=".eval/dist/tools/env-component-manager.py"
[ -f "$COMPONENT_MANAGER_SCRIPT" ] || COMPONENT_MANAGER_SCRIPT="dist/tools/env-component-manager.py"
[ -f "$COMPONENT_MANAGER_SCRIPT" ] || { [ -n "${EVAL_REPO:-}" ] && COMPONENT_MANAGER_SCRIPT="$EVAL_REPO/dist/tools/env-component-manager.py"; }

if [ ! -f "$COMPONENT_MANAGER_SCRIPT" ]; then
    echo "WARNING: env-component-manager.py not found. Skipping component operations." >&2
fi
```

## Phases

### Phase 1: Initialize (if needed)

If the components/ directory doesn't exist, initialize it:

```bash
if [ ! -f "components/tree.yaml" ]; then
    python3 "$COMPONENT_MANAGER_SCRIPT" init components/
fi
```

### Phase 2: Execute Command

Depending on the user's intent, run one of the subcommands:

**List components:**
```bash
python3 "$COMPONENT_MANAGER_SCRIPT" list components/ [--layer infra|app] [--tag <tag>]
```

**Search components:**
```bash
python3 "$COMPONENT_MANAGER_SCRIPT" search components/ --query "<text>" [--layer infra|app]
```

**Register a component:**
```bash
python3 "$COMPONENT_MANAGER_SCRIPT" register components/ \
  --name "<name>" --layer <infra|app> --path "<path>" \
  --tags "<csv>" --description "<desc>"
```

**Assemble components:**
```bash
python3 "$COMPONENT_MANAGER_SCRIPT" assemble components/ \
  --infra "<comma-sep-infra-ids>" --app "<comma-sep-app-ids>" \
  --output "docker-compose-<slug>.yml"
```

**Fork a component:**
```bash
python3 "$COMPONENT_MANAGER_SCRIPT" fork components/ \
  --source "<component-path>" --new-name "<name>" --new-path "<path>"
```

**Show component info:**
```bash
python3 "$COMPONENT_MANAGER_SCRIPT" info components/ --path "<component-path>"
```

**Display tree:**
```bash
python3 "$COMPONENT_MANAGER_SCRIPT" tree components/
```

## Fork-Based Reuse Pattern

The fork-based reuse pattern is the key innovation:

1. **Search**: Find matching components via `search` command
2. **Fork**: Copy an existing component via `fork` command
3. **Fine-tune**: Modify the forked component files (Dockerfile, source code, schema)
4. **Register back**: Register the fine-tuned component via `register` command
5. **Assemble**: Generate docker-compose.yml with the fine-tuned components

This allows agents to reuse existing components as starting points and
fine-tune them for specific task requirements.

## Integration with env-gen

The env-gen skill calls this component manager to assemble environments:
1. env-gen reads task requirements
2. env-gen calls `$COMPONENT_MANAGER_SCRIPT search` to find matching components
3. If needed, env-gen forks components for fine-tuning
4. env-gen calls `$COMPONENT_MANAGER_SCRIPT assemble` to generate docker-compose.yml
5. env-gen records the component manifest in eval-wiki

## Output

- `components/tree.yaml` — updated index
- Component files under `components/infra/` or `components/app/`
- `docker-compose.yml` — assembled Docker Compose configuration
- `component-manifest.json` — manifest of assembled components