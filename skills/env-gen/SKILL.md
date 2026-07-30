---
name: env-gen
description: 'Generate Docker environment for Agent verification using component assembly. DRIVE role. Depends on task and env-component-manager. Use when user says "生成环境", "generate env", "setup docker", or wants to create a test environment.'
argument-hint: "[task-id] [dry-run]"
allowed-tools: Bash(*), Read, Write, Edit, Grep, Glob
role: DRIVE
depends-on: [eval-wiki, task, env-component-manager]
produces: [environment]
---

# env-gen Skill

## Overview

Reads task requirements, queries the component manager for matching components,
assembles them into a docker-compose.yml via the component manager, fine-tunes
components as needed, provisions the container, and records the environment in
eval-wiki.

This replaces the previous "generate docker-compose from scratch" approach with
a component-based assembly methodology inspired by MEnvAgent (arxiv 2601.22859).

## Helper Resolution

Resolve `$EVAL_WIKI_SCRIPT` AND `$COMPONENT_MANAGER_SCRIPT`:

```bash
cd "$(git rev-parse --show-toplevel 2>/dev/null || pwd)" || exit 1
EVAL_REPO="${EVAL_REPO:-$(awk -F'\t' '$1=="repo_root"{print $2; exit}' .eval/installed-skills.txt 2>/dev/null)}"

# Resolve eval-wiki script
EVAL_WIKI_SCRIPT=".eval/dist/tools/eval-wiki.py"
[ -f "$EVAL_WIKI_SCRIPT" ] || EVAL_WIKI_SCRIPT="dist/tools/eval-wiki.py"
[ -f "$EVAL_WIKI_SCRIPT" ] || { [ -n "${EVAL_REPO:-}" ] && EVAL_WIKI_SCRIPT="$EVAL_REPO/dist/tools/eval-wiki.py"; }
if [ ! -f "$EVAL_WIKI_SCRIPT" ]; then
    echo "WARNING: eval-wiki.py not found. Skipping eval-wiki write." >&2
fi

# Resolve component manager script
COMPONENT_MANAGER_SCRIPT=".eval/dist/tools/env-component-manager.py"
[ -f "$COMPONENT_MANAGER_SCRIPT" ] || COMPONENT_MANAGER_SCRIPT="dist/tools/env-component-manager.py"
[ -f "$COMPONENT_MANAGER_SCRIPT" ] || { [ -n "${EVAL_REPO:-}" ] && COMPONENT_MANAGER_SCRIPT="$EVAL_REPO/dist/tools/env-component-manager.py"; }
if [ ! -f "$COMPONENT_MANAGER_SCRIPT" ]; then
    echo "WARNING: env-component-manager.py not found. Skipping component assembly." >&2
fi
```

## Phases

### Phase 1: Read Task Requirements

Read the task file from eval-wiki to get constraints:

```bash
TASK_ID="${1:-}"
if [ -z "$TASK_ID" ]; then
    echo "ERROR: task-id is required" >&2
    exit 1
fi

if [ -f "$EVAL_WIKI_SCRIPT" ]; then
    TASK_DATA=$(python3 "$EVAL_WIKI_SCRIPT" query eval-wiki/ "$TASK_ID")
    echo "Task data: $TASK_DATA"
fi
```

Extract from the task:
- `scenario_type` — to determine the type of environment
- `agent_constraints` — allowed tools, max turns
- `expected_behavior` — what the agent should do
- `scenario_id` — if present, read the parent scenario for environment hints

If `scenario_id` is present, read the parent scenario:

```bash
if [ -n "$SCENARIO_ID" ]; then
    python3 "$EVAL_WIKI_SCRIPT" query eval-wiki/ "$SCENARIO_ID"
fi
```

### Phase 2: Query Component Manager for Matching Components

Use the component manager to find matching infra and app components:

```bash
# Search for matching infra components (based on required runtime, OS)
if [ -f "$COMPONENT_MANAGER_SCRIPT" ]; then
    python3 "$COMPONENT_MANAGER_SCRIPT" search components/ --query "<runtime>" --layer infra
    python3 "$COMPONENT_MANAGER_SCRIPT" search components/ --query "<domain>" --layer app
fi
```

Decision matrix:
- **Exact match found** → proceed to assembly (Phase 3)
- **Partial match found** → fork the closest component for fine-tuning (Phase 4)
- **No match found** → register a new base component, then proceed to assembly

### Phase 3: Assemble Base Components

```bash
if [ -f "$COMPONENT_MANAGER_SCRIPT" ]; then
    python3 "$COMPONENT_MANAGER_SCRIPT" assemble components/ \
      --infra "$INFRA_IDS" \
      --app "$APP_IDS" \
      --output "docker-compose-${SLUG}.yml"
fi
```

This generates:
- `docker-compose-<slug>.yml` — Docker Compose configuration
- `component-manifest.json` — manifest of all assembled components

### Phase 4: Agent Fine-Tuning (key innovation)

Compare task requirements against the assembled environment. Identify gaps:

- Missing API endpoints
- Wrong data schema
- Missing mock services
- Incorrect business logic

For each gap, the agent modifies the forked component files:

```bash
# Adjust Dockerfile (add packages, change base image)
# Modify app code (add/remove API endpoints, change business logic)
# Update database schema (add tables, modify columns)
# Configure mock services (add new mock endpoints)

# After fine-tuning, register the modified component
if [ -f "$COMPONENT_MANAGER_SCRIPT" ]; then
    python3 "$COMPONENT_MANAGER_SCRIPT" register components/ \
      --name "<fine-tuned-name>" \
      --layer app \
      --path "<fine-tuned-path>" \
      --tags "<tags>" \
      --description "<description>"
fi

# Regenerate docker-compose.yml with the fine-tuned components
python3 "$COMPONENT_MANAGER_SCRIPT" assemble components/ \
  --infra "$INFRA_IDS" \
  --app "$APP_IDS_WITH_FINETUNED" \
  --output "docker-compose-${SLUG}.yml"
```

### Phase 5: Docker Build + Health Check

```bash
if [ "${DRY_RUN:-}" != "true" ]; then
    docker compose -f "docker-compose-${SLUG}.yml" build
    docker compose -f "docker-compose-${SLUG}.yml" up -d

    # Wait for health check to pass (max 60s, poll every 5s)
    HEALTHY=false
    for i in $(seq 1 12); do
        sleep 5
        if docker compose -f "docker-compose-${SLUG}.yml" ps --health 2>/dev/null | grep -q "healthy"; then
            echo "Container healthy after $((i * 5))s"
            HEALTHY=true
            break
        fi
    done

    if [ "$HEALTHY" != "true" ]; then
        echo "WARNING: Health check failed for ${SLUG}"
        # Record env status as provision_failed
        ENV_STATUS="provision_failed"
    else
        ENV_STATUS="provisioned"
    fi
fi
```

### Phase 6: Write to eval-wiki

```bash
if [ -f "$EVAL_WIKI_SCRIPT" ]; then
    python3 "$EVAL_WIKI_SCRIPT" add-env eval-wiki/ \
      --task-id "$TASK_ID" \
      --image "$IMAGE" \
      --network "$NETWORK" \
      --memory "$MEMORY" \
      --cpus "$CPUS" \
      --agent-endpoint "$ENDPOINT" \
      --health-check "$HEALTH_CHECK" \
      --status "$ENV_STATUS"
fi
```

Include the component manifest in the environment record. The manifest
documents which components were used, what was forked, and what was modified.

## Failure Policy

Following the component-assembly-contract.md (Policy B — Side-Effect):
- Environment failure does NOT block the task
- If provisioning fails, mark env_status as `provision_failed` or `missing`
- The task continues without a live environment

## Output

- `docker-compose-<slug>.yml` — Docker Compose configuration
- `component-manifest.json` — Component assembly manifest
- `eval-wiki/environments/<task-id>-env.md` — Environment metadata
- `components/tree.yaml` — Updated with any new forked/registered components
- Modified component files under `components/` — Fine-tuned components