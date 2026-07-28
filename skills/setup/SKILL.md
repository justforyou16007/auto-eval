---
name: setup
description: 'Interactive Q&A setup wizard for new auto-eval projects. Bootstraps eval-wiki, EVAL_CONFIG.md, gap_map.md, and initial task templates from user answers. Resumable, bilingual (en/zh), smart defaults. Use when user says "初始化", "setup project", "配置项目", "eval setup", "new project", or wants to configure a new auto-eval workspace.'
argument-hint: "[project-name] [— language: en|zh]"
allowed-tools: Bash(*), Read, Write, Edit, Grep, Glob, AskUserQuestion
role: DRIVE
depends-on: [eval-wiki]
produces: [eval-wiki, EVAL_CONFIG.md, gap_map.md]
---

# setup Skill

## Overview

Interactive Q&A setup wizard for new auto-eval projects. Bootstraps the
eval-wiki knowledge base, EVAL_CONFIG.md project configuration, gap_map.md
coverage analysis, and initial task templates — all from user answers.

Resumable across 8 phases, bilingual (en/zh), with smart defaults for every
question.

## Helper Resolution Chain

Resolve `$EVAL_WIKI_SCRIPT` via the shared chain (Variant A — hard-fail):

```bash
cd "$(git rev-parse --show-toplevel 2>/dev/null || pwd)" || exit 1

# 1. Check for installed copy in .eval
EVAL_REPO="${EVAL_REPO:-$(awk -F'\t' '$1=="repo_root"{print $2; exit}' .eval/installed-skills.txt 2>/dev/null)}"
EVAL_WIKI_SCRIPT=".eval/dist/tools/eval-wiki.py"

# 2. Fall back to canonical dist path
[ -f "$EVAL_WIKI_SCRIPT" ] || EVAL_WIKI_SCRIPT="dist/tools/eval-wiki.py"

# 3. Fall back to EVAL_REPO
[ -f "$EVAL_WIKI_SCRIPT" ] || { [ -n "${EVAL_REPO:-}" ] && EVAL_WIKI_SCRIPT="$EVAL_REPO/dist/tools/eval-wiki.py"; }

# 4. Hard fail — setup cannot proceed without eval-wiki
if [ ! -f "$EVAL_WIKI_SCRIPT" ]; then
    echo "ERROR: eval-wiki.py not found. Run 'tools/install_eval_wiki.sh' first." >&2
    exit 1
fi
```

## Language Detection

Output language follows `shared-references/output-language.md`:

- All file paths, JSON keys, YAML field names are English regardless of language
- User-facing questions and descriptions follow the detected language
- Language is auto-detected from `$ARGUMENTS` or user message, defaulting to `en`

## Phases

### Phase 0 — Pre-flight & Resume Detection

Check for `.eval/setup-state.json` to detect a previous incomplete run.

```bash
STATE_DIR=".eval"
STATE_FILE="$STATE_DIR/setup-state.json"

if [ -f "$STATE_FILE" ]; then
    LAST_PHASE=$(python3 -c "import sys,json; d=json.load(open('$STATE_FILE')); print(d.get('last_completed_phase', -1))")
    echo "Resume detected: last completed phase was $LAST_PHASE."
    AskUserQuestion "Resume from phase $((LAST_PHASE + 1))? (Y/n)" "Y"
    # If yes, skip to that phase
fi
```

Resolve `$EVAL_WIKI_SCRIPT` via the shared chain above.

### Phase 1 — Project Basics

```bash
AskUserQuestion "What is the project name?" "my-eval-project"
PROJECT_NAME="$ANSWER"

AskUserQuestion "Language (en/zh)?" "en"
LANGUAGE="$ANSWER"

# Slugify project name for directory
PROJECT_DIR=$(echo "$PROJECT_NAME" | tr '[:upper:]' '[:lower:]' | sed 's/[^a-z0-9-]/-/g' | sed 's/--*/-/g' | sed 's/^-//;s/-$//')
```

Save state:
```bash
python3 -c "
import json
state = {'last_completed_phase': 1, 'project_name': '$PROJECT_NAME', 'language': '$LANGUAGE', 'project_dir': '$PROJECT_DIR'}
with open('$STATE_FILE', 'w') as f:
    json.dump(state, f)
"
```

### Phase 2 — Evaluation Scope

```bash
AskUserQuestion "What Agent capabilities should be tested? (e.g. tool use, multi-turn, error recovery, code generation)" "tool use, multi-turn"
CAPABILITIES="$ANSWER"

AskUserQuestion "What target Agent types? (e.g. chat, coding, research, analysis)" "chat, coding"
AGENT_TYPES="$ANSWER"

# Store as structured tags
CAPABILITY_TAGS=$(echo "$CAPABILITIES" | tr ',' '\n' | sed 's/^ *//;s/ *$//' | python3 -c "import sys,json; print(json.dumps([l.strip() for l in sys.stdin if l.strip()]))")
AGENT_TAGS=$(echo "$AGENT_TYPES" | tr ',' '\n' | sed 's/^ *//;s/ *$//' | python3 -c "import sys,json; print(json.dumps([l.strip() for l in sys.stdin if l.strip()]))")
```

Save state:
```bash
python3 -c "
import json
state = json.load(open('$STATE_FILE'))
state['last_completed_phase'] = 2
state['capabilities'] = $CAPABILITY_TAGS
state['agent_types'] = $AGENT_TAGS
with open('$STATE_FILE', 'w') as f:
    json.dump(state, f)
"
```

### Phase 3 — Environment Requirements

```bash
AskUserQuestion "Docker image preference?" "python:3.11"
DOCKER_IMAGE="$ANSWER"

AskUserQuestion "Memory limit (e.g. 512m, 2g)?" "512m"
MEMORY="$ANSWER"

AskUserQuestion "CPU limit?" "1"
CPU="$ANSWER"

AskUserQuestion "Default timeout (seconds)?" "60"
TIMEOUT="$ANSWER"

AskUserQuestion "Mock services needed? (e.g. search, calculator, weather)" "search"
MOCK_SERVICES="$ANSWER"
```

Save state:
```bash
python3 -c "
import json
state = json.load(open('$STATE_FILE'))
state['last_completed_phase'] = 3
state['docker_image'] = '$DOCKER_IMAGE'
state['memory'] = '$MEMORY'
state['cpu'] = '$CPU'
state['timeout'] = $TIMEOUT
state['mock_services'] = '$MOCK_SERVICES'
with open('$STATE_FILE', 'w') as f:
    json.dump(state, f)
"
```

### Phase 4 — Difficulty & Cost Budget

```bash
AskUserQuestion "Default difficulty level? (lite/easy/medium/hard/beast)" "medium"
DIFFICULTY="$ANSWER"

AskUserQuestion "Cost budget? (0.1/0.5/1.0/5.0/unlimited)" "1.0"
COST="$ANSWER"
```

Save state:
```bash
python3 -c "
import json
state = json.load(open('$STATE_FILE'))
state['last_completed_phase'] = 4
state['difficulty'] = '$DIFFICULTY'
state['cost'] = '$COST'
with open('$STATE_FILE', 'w') as f:
    json.dump(state, f)
"
```

### Phase 5 — Initial Gap Map

```bash
AskUserQuestion "What test scenarios are NOT yet covered? List gaps separated by semicolons." ""
GAP_INPUT="$ANSWER"

# Parse gaps into stable IDs
GAP_COUNT=0
GAP_ENTRIES=""
IFS=';' read -ra GAPS <<< "$GAP_INPUT"
for gap in "${GAPS[@]}"; do
    gap=$(echo "$gap" | sed 's/^ *//;s/ *$//')
    if [ -n "$gap" ]; then
        GAP_COUNT=$((GAP_COUNT + 1))
        GAP_ID="G${GAP_COUNT}"
        GAP_ENTRIES="$GAP_ENTRIES
- **${GAP_ID}**: ${gap}"
    fi
done
```

Save state:
```bash
python3 -c "
import json
state = json.load(open('$STATE_FILE'))
state['last_completed_phase'] = 5
state['gaps'] = $(echo "$GAP_INPUT" | python3 -c "import sys,json; print(json.dumps([g.strip() for g in sys.stdin.read().split(';') if g.strip()]))")
with open('$STATE_FILE', 'w') as f:
    json.dump(state, f)
"
```

### Phase 6 — Artifact Generation

```bash
# 1. Initialize eval-wiki
python3 "$EVAL_WIKI_SCRIPT" init eval-wiki/

# 2. Create EVAL_CONFIG.md
cat > EVAL_CONFIG.md << 'EVALEOF'
# Project Configuration

## Problem
Evaluate Agent capabilities for $(python3 -c "import json; print(json.load(open('$STATE_FILE'))['project_name'])") project.

## Constraints
- Docker image: $(python3 -c "import json; print(json.load(open('$STATE_FILE'))['docker_image'])")
- Memory: $(python3 -c "import json; print(json.load(open('$STATE_FILE'))['memory'])")
- CPU: $(python3 -c "import json; print(json.load(open('$STATE_FILE'))['cpu'])")
- Timeout: $(python3 -c "import json; print(json.load(open('$STATE_FILE'))['timeout'])")s
- Default difficulty: $(python3 -c "import json; print(json.load(open('$STATE_FILE'))['difficulty'])")
- Cost budget: $(python3 -c "import json; print(json.load(open('$STATE_FILE'))['cost'])")

## Direction
Test Agent capabilities: $(python3 -c "import json; print(', '.join(json.load(open('$STATE_FILE'))['capabilities']))")
Target Agent types: $(python3 -c "import json; print(', '.join(json.load(open('$STATE_FILE'))['agent_types']))")

## Non-Goals
- Performance benchmarking
- Security auditing
- Production deployment testing

## Domain Knowledge
- Agent types: $(python3 -c "import json; print(', '.join(json.load(open('$STATE_FILE'))['agent_types']))")
- Capabilities under test: $(python3 -c "import json; print(', '.join(json.load(open('$STATE_FILE'))['capabilities']))")
EVALEOF

# 3. Write gap_map.md
cat > gap_map.md << 'GAPEOF'
# Gap Map

## Coverage Gaps

$(python3 -c "
import json
state = json.load(open('$STATE_FILE'))
gaps = state.get('gaps', [])
for i, g in enumerate(gaps, 1):
    print(f'- **G{i}**: {g}')
")
GAPEOF

# 4. Create .gitignore with eval-wiki entries
cat >> .gitignore << 'GITEOF'
eval-wiki/
.eval/
reports/
evaluators/
GITEOF

# 5. Write setup-state.json for resumability
python3 -c "
import json
state = json.load(open('$STATE_FILE'))
state['last_completed_phase'] = 6
state['artifacts'] = ['EVAL_CONFIG.md', 'gap_map.md', 'eval-wiki/']
with open('$STATE_FILE', 'w') as f:
    json.dump(state, f)
"
```

### Phase 7 — Summary & Next Steps

```bash
echo "=========================================="
echo "  Auto-Eval Setup Complete"
echo "=========================================="
echo ""
echo "Project: $(python3 -c "import json; print(json.load(open('$STATE_FILE'))['project_name'])")"
echo "Language: $(python3 -c "import json; print(json.load(open('$STATE_FILE'))['language'])")"
echo ""
echo "Created artifacts:"
echo "  - EVAL_CONFIG.md       (project configuration)"
echo "  - gap_map.md           (coverage gap analysis)"
echo "  - eval-wiki/           (eval knowledge base)"
echo "  - .gitignore           (updated with eval-wiki entries)"
echo "  - .eval/setup-state.json  (resumable state)"
echo ""
echo "Next steps:"
echo "  1. Review EVAL_CONFIG.md and adjust as needed"
echo "  2. Review gap_map.md and add more gaps"
echo "  3. Run /auto-eval-pipeline to start evaluation"
echo "  4. Or run individual skills: /task-gen, /env-gen, etc."
echo "=========================================="
```

## Key Design Patterns

- **Resumable**: State saved to `.eval/setup-state.json` after each phase completion.
- **Language detection**: `$ARGUMENTS` → user message language → default `en`.
- **Smart defaults**: Every `AskUserQuestion` provides a default value.
- **English markers**: All file paths, JSON keys, YAML field names are English regardless of language.
- **`$EVAL_WIKI_SCRIPT` resolution chain**: Variant A (hard-fail) — setup cannot proceed without eval-wiki.
- **Output language**: Follows `shared-references/output-language.md`.