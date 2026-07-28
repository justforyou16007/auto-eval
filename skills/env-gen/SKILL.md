---
name: env-gen
description: 'Generate Docker environment for Agent verification. DRIVE role. Depends on task. Use when user says "生成环境", "generate env", "setup docker", or wants to create a test environment.'
argument-hint: "[task-id] [dry-run]"
allowed-tools: Bash(*), Read, Write, Edit, Grep, Glob
role: DRIVE
depends-on: [eval-wiki, task]
produces: [environment]
---

# env-gen Skill

## Overview

Reads task constraints, generates a docker-compose.yml file, provisions the
container, and records the environment in eval-wiki. This is a DRIVE role
skill — environment configuration is mechanical/constructive.

## Helper Resolution

Resolve `$EVAL_WIKI_SCRIPT` via the shared chain (Variant B — warn + skip):

```bash
cd "$(git rev-parse --show-toplevel 2>/dev/null || pwd)" || exit 1
EVAL_REPO="${EVAL_REPO:-$(awk -F'\t' '$1=="repo_root"{print $2; exit}' .eval/installed-skills.txt 2>/dev/null)}"
EVAL_WIKI_SCRIPT=".eval/dist/tools/eval-wiki.py"
[ -f "$EVAL_WIKI_SCRIPT" ] || EVAL_WIKI_SCRIPT="dist/tools/eval-wiki.py"
[ -f "$EVAL_WIKI_SCRIPT" ] || { [ -n "${EVAL_REPO:-}" ] && EVAL_WIKI_SCRIPT="$EVAL_REPO/dist/tools/eval-wiki.py"; }

if [ ! -f "$EVAL_WIKI_SCRIPT" ]; then
    echo "WARNING: eval-wiki.py not found. Skipping eval-wiki write." >&2
fi
```

## Phases

### Phase 1: Read Task File

Read the task from eval-wiki to get constraints:

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

Parse the task's agent_constraints, scenario_type, allowed_tools, and
max_turns to determine the environment requirements.

### Phase 2: Generate docker-compose.yml

Generate a docker-compose configuration based on task requirements:

- **Image selection**: Based on task requirements (python:3.11, python:3.12, etc.)
- **Volume mounts**: For mock tools and test data
- **Network configuration**: Bridge network, port mappings
- **Resource limits**: Memory and CPU from task cost/difficulty

```yaml
version: '3.8'
services:
  agent-<slug>:
    image: <image>
    network_mode: <network>
    mem_limit: <memory>
    cpus: <cpus>
    environment:
      - AGENT_ENDPOINT=<endpoint>
    volumes:
      - ./mock-tools:/mock-tools
    healthcheck:
      test: ["CMD", "curl", "-f", "<health-check>"]
      interval: 5s
      timeout: 3s
      retries: 6
```

### Phase 3: Write Environment to eval-wiki

```bash
if [ -f "$EVAL_WIKI_SCRIPT" ]; then
    python3 "$EVAL_WIKI_SCRIPT" add-env eval-wiki/ \
      --task-id "$TASK_ID" \
      --image "$IMAGE" \
      --network "$NETWORK" \
      --memory "$MEMORY" \
      --cpus "$CPUS" \
      --agent-endpoint "$ENDPOINT" \
      --health-check "$HEALTH_CHECK"
fi
```

### Phase 4: Provision Container (skip if `--dry-run`)

```bash
if [ "${DRY_RUN:-}" != "true" ]; then
    docker compose -f "docker-compose-${SLUG}.yml" up -d

    # Wait for health check to pass (max 30s)
    for i in $(seq 1 30); do
        if docker compose -f "docker-compose-${SLUG}.yml" ps --health 2>/dev/null | grep -q "healthy"; then
            echo "Container healthy after ${i}s"
            break
        fi
        sleep 1
    done

    # If health check fails, record env status as provision_failed
    if ! docker compose -f "docker-compose-${SLUG}.yml" ps --health 2>/dev/null | grep -q "healthy"; then
        echo "WARNING: Health check failed for ${SLUG}"
        # Record failure status
    fi
fi
```

### Phase 5: Update Environment Status

After provisioning, update the environment status:

```bash
if [ -f "$EVAL_WIKI_SCRIPT" ] && [ "${DRY_RUN:-}" != "true" ]; then
    python3 "$EVAL_WIKI_SCRIPT" add-env eval-wiki/ \
      --task-id "$TASK_ID" \
      --image "$IMAGE" \
      --network "$NETWORK" \
      --memory "$MEMORY" \
      --cpus "$CPUS" \
      --agent-endpoint "$ENDPOINT" \
      --health-check "$HEALTH_CHECK" \
      --status "provisioned" \
      --update
fi
```

## Output

- `docker-compose-<slug>.yml` — Docker Compose configuration
- `eval-wiki/environments/<task-id>-env.md` — Environment metadata