# Auto-Eval: Agent 自动验证系统

> **Automated Agent Verification Pipeline** — 5 pluggable stages for generating, executing, scoring, and iterating on Agent evaluation tasks.

[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow)](LICENSE)

---

## 📖 Overview

**Auto-Eval** is an automated **Agent verification pipeline** consisting of 5 pluggable stages. Each stage is a replaceable skill module that can be independently developed, tested, and swapped. The system is built on the **eval-wiki** — a persistent, git-tracked knowledge base that accumulates tasks, environments, rubrics, runs, and feedback across the entire eval lifecycle.

The project is inspired by the **ARIS (Agent Runtime Integration Specification)** architecture and is designed to be provider-independent — it works with any LLM/Agent runtime.

### Core Design Principles

| Principle | Description |
|-----------|-------------|
| **DRIVE vs ACQUIT** | One system can **DRIVE** its own progress but must **never ACQUIT** its own quality. ACQUIT requires cross-model verification. |
| **Human-in-the-Loop** | User feedback drives iterative improvement of eval artifacts. |
| **Knowledge Compounding** | The eval-wiki compounds knowledge across the eval lifecycle — every task, run, and feedback enriches the next cycle. |
| **Pluggable Stages** | Each stage is a replaceable skill module with a defined contract (SKILL.md). Swap any stage without affecting the rest. |

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    Layer 3: Skills                                           │
│  setup  │  auto-eval-pipeline  │  task-gen  │  env-gen  │  env-component-   │
│ (DRIVE) │     (DRIVE)          │  (DRIVE)   │  (DRIVE)  │  manager (DRIVE)  │
│  rubric-gen  │  report-gen  │  feedback-align  │  eval-wiki                │
│  (ACQUIT)    │  (DRIVE)     │  (DRIVE+ACQUIT)  │  (TOOL)                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                    Layer 2: Tools                                            │
│  eval-wiki.py  │  env-component-manager.py  │  capture-filter.py  │ ...     │
│  (8 CLI tools in src/tools/)                                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                    Layer 1: Contracts                                        │
│  shared-references/  (23 contract .md files)                                │
│  integration-contract, acceptance-gate, output-versioning…                  │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Layer 1: Contracts (`shared-references/`)

22 shared-reference documents define the integration contracts between all components:

- **Core Governance**: `integration-contract.md`, `skill-governance.md`, `assurance-contract.md`
- **Quality Gates**: `acceptance-gate.md`, `reviewer-independence.md`, `review-tracing.md`
- **Output Standards**: `output-composition.md`, `output-language.md`, `output-versioning.md`, `output-manifest.md`
- **Security & Hygiene**: `injection-hygiene.md`, `capture-antipatterns.md`
- **Operational**: `debug-mode.md`, `evidence-precheck.md`, `experiment-integrity.md`, `external-cadence.md`, `fan-out-pattern.md`, `resumable-runs.md`, `reviewer-routing.md`
- **Cost & Difficulty**: `difficulty-cost-contract.md`, `effort-contract.md`
- **Eval-Wiki**: `eval-wiki-helper-resolution.md`

### Layer 2: Tools (`src/tools/`)

8 CLI tools that power the pipeline:

| Tool | Purpose |
|------|---------|
| `eval-wiki.py` | Persistent knowledge base CLI (init, add-task, add-scenario, add-env, add-rubric, add-run, add-feedback, add-edge, query, stats, log) |
| `env-component-manager.py` | Tree-based environment component manager with lazy loading (init, register, list, search, assemble, fork, info, tree) |
| `capture-filter.py` | Prevents runtime noise from being persisted as valid eval artifacts |
| `evidence-check.py` | Verifies run evidence files exist and are non-empty |
| `iteration-log.py` | Tracks convergence of feedback loops |
| `provenance.py` | Validates provenance links in reports |
| `run-state.py` | State machine for pipeline orchestration (6 phases) |
| `watchdog.py` | Monitors Docker containers for timeout/abnormal exit |

### Layer 3: Skills (`skills/`)

9 skill modules, each with a `SKILL.md` defining its interface, phases, and contracts:

- `setup` (DRIVE) — Interactive Q&A setup wizard for new auto-eval projects
- `auto-eval-pipeline` (DRIVE) — End-to-end pipeline driver (task-gen → env-gen → rubric-gen → report-gen)
- `task-gen` (DRIVE) — Generate Agent eval tasks (AWM-style two-stage: scenario generation → task generation)
- `env-gen` (DRIVE) — Generate Docker environments via component assembly + agent fine-tuning
- `env-component-manager` (DRIVE) — Tree-based environment component manager with lazy loading
- `rubric-gen` (ACQUIT) — Generate scoring rubrics + evaluator scripts
- `report-gen` (DRIVE) — Generate HTML verification reports
- `feedback-align` (DRIVE+ACQUIT) — User feedback alignment loop
- `eval-wiki` (TOOL) — Knowledge base helper

---

## 🎯 The 5 Stages (Pipeline)

### Stage 1: 🟢 task-gen — Generate Tasks

**Role**: DRIVE | **Depends on**: eval-wiki | **Produces**: Scenario, Task

Uses AWM-style two-stage generation (arxiv 2602.10090):
1. **Scenario Generation**: Reads `query_pack.md` (gap analysis, failed tasks, coverage stats) and generates diverse scenario descriptions as seeds.
2. **Task Generation**: For each scenario, generates M concrete tasks (default M=3). Each task references its parent scenario via `scenario_id`.

Each task specifies difficulty, scenario type (single-turn, multi-turn, tool-chain, error-recovery), allowed tools, expected behavior, and cost budget.

### Stage 2: 🟢 env-gen — Generate Environments

**Role**: DRIVE | **Depends on**: task, env-component-manager | **Produces**: Environment

Reads task constraints, queries the component manager for matching components, assembles them into a `docker-compose.yml` via the component manager, fine-tunes components as needed (adjusting Dockerfiles, app code, database schemas, mock services), provisions containers, configures health checks, and records the environment metadata in eval-wiki. Uses the component reuse protocol: search → fork → fine-tune → register back.

### Stage 3: 🔴 rubric-gen — Generate Rubrics

**Role**: **ACQUIT** | **Depends on**: task | **Produces**: Rubric + Evaluator Scripts

Generates scoring criteria (binary, scale_1_5, percentage) and evaluator scripts. **This is an ACQUIT role** — the rubric must be verified by a cross-model judge (different model family). Script evaluators (mechanical checks) are DRIVE, while LLM judge evaluators are ACQUIT.

### Stage 4: 🟢 report-gen — Generate Reports

**Role**: DRIVE | **Depends on**: run | **Produces**: Report

Reads all runs, rubrics, and tasks from eval-wiki and generates a single-page HTML verification report with stat cards, per-task results, color-coded verdicts (green/red/yellow), and provenance links.

### Stage 5: 🟢🔴 feedback-align — Feedback Loop

**Role**: **DRIVE+ACQUIT** | **Depends on**: eval-wiki | **Produces**: Feedback

Records user feedback, classifies issue types (misalignment, missing_case, rubric_error, env_error, difficulty_mismatch), applies changes, and verifies them cross-model. The DRIVE part proposes changes; the ACQUIT part verifies them.

---

## 📊 eval-wiki Entity Schema

### Entities

| Entity | Directory | Node ID Prefix | Description |
|--------|-----------|---------------|-------------|
| **Scenario** | `scenarios/` | `scenario:` | Evaluation scenario description (seed for task generation) |
| **Task** | `tasks/` | `task:` | Evaluation task specification |
| **Environment** | `environments/` | `env:` | Docker container configuration |
| **Rubric** | `rubrics/` | `rubric:` | Scoring criteria + evaluator scripts |
| **Run** | `runs/` | `run:` | Agent execution result |
| **Feedback** | `feedback/` | `feedback:` | User or auto-audit feedback |

### Edge Types (12 types)

| Edge Type | Direction | Purpose |
|-----------|-----------|---------|
| `scenario_for` | Scenario → Task | Task is derived from this scenario |
| `derived_from_scenario` | Task → Scenario | Reverse edge of scenario_for |
| `env_for` | Env → Task | Environment is configured for a task |
| `rubric_for` | Rubric → Task | Rubric scores a task |
| `tested_by` | Task → Run | Run tests a task |
| `uses_env` | Run → Env | Run uses an environment |
| `scored_by` | Run → Rubric | Run is scored by a rubric |
| `supports` | Run → Task | Run provides supporting evidence |
| `invalidates` | Run → Task | Run invalidates a task |
| `addresses_gap` | Task → Gap | Task addresses a coverage gap |
| `evolved_from` | Task/Rubric/Env → Task/Rubric/Env | Entity evolved from another |
| `revise` | Feedback → Entity | Feedback revises an entity |

### Gap Map (`gap_map.md`)

Tracks coverage gaps with stable IDs (G1, G2, ...). Each gap is scored by:
- `gap_score = (unresolved ? 2 : 0) + (no_linked_tasks ? 3 : 0) + (failed_runs > 0 ? 1 : 0)`

---

## 🚀 Quick Start

### Prerequisites

- Python 3.12+
- Docker (for env-gen stage)
- Git
- An agent harness (Claude Code, Codex CLI, Cursor, or any compatible agent)

### 1. Install

```bash
# Clone the auto-eval repository (one-time)
git clone <repo-url> ~/auto-eval

# Then install into your target project directory
cd my-project
bash ~/auto-eval/tools/install_eval_wiki.sh

# Or specify the target project directly:
#   bash ~/auto-eval/tools/install_eval_wiki.sh /path/to/my-project

# The script creates:
#   - .claude/skills/<skill-name> symlinks (9 skills)
#   - .eval/dist/tools/<tool-name> symlinks (8 tools)
#   - .eval/installed-skills.txt manifest
```

The repo becomes a set of skills loadable by any agent harness. No direct CLI usage is required — all interaction happens through skill invocations inside the agent.

### 2. Setup

In your agent harness, invoke the **`setup`** skill (e.g. type "初始化" or "setup project"). This runs an interactive 8-phase Q&A wizard that bootstraps:

- `eval-wiki/` directory — the persistent knowledge base
- `EVAL_CONFIG.md` — project configuration (difficulty, cost, scope, etc.)
- `gap_map.md` — initial coverage gap analysis
- Initial task templates
- `.eval/setup-state.json` — resumable state for interrupted sessions

The wizard is bilingual (en/zh) and provides smart defaults for every question. If interrupted, it resumes from the last completed phase.

### 3. Run Pipeline

In your agent harness, invoke the **`auto-eval-pipeline`** skill (e.g. type "开始验证" or "run evaluation"). This drives the full 5-stage pipeline end-to-end:

1. **task-gen** — Generate Agent evaluation tasks from gap analysis
2. **env-gen** — Generate Docker environments for each task
3. **rubric-gen** — Generate scoring rubrics and evaluator scripts
4. **(Agent runs)** — Agent executes tasks in the provisioned environments
5. **report-gen** — Generate a single-page HTML verification report

Optionally iterate with **`feedback-align`** for user feedback alignment. The pipeline uses `run-state.py` for phase orchestration and resumability.

---

## 📁 Project Structure

```
eval-wiki/
├── criteria.json                    # Sample scoring criteria (C1-C3)
├── eval-wiki.py                     # Root CLI entry point (symlink to src/tools/)
├── pyproject.toml                   # Python project config
├── .gitignore                       # Ignores eval-wiki/, __pycache__/, *.pyc
│
├── shared-references/               # Layer 1: Contracts (23 files)
	│   ├── acceptance-gate.md           #   Cross-model ACQUIT verification
	│   ├── assurance-contract.md        #   Draft vs Submission assurance levels
	│   ├── capture-antipatterns.md      #   Anti-pattern detection
	│   ├── component-assembly-contract.md #   Component assembly contract
	│   ├── debug-mode.md
│   ├── difficulty-cost-contract.md  #   Cost/difficulty mapping
│   ├── effort-contract.md
│   ├── eval-wiki-helper-resolution.md
│   ├── evidence-precheck.md
│   ├── experiment-integrity.md
│   ├── external-cadence.md
│   ├── fan-out-pattern.md
│   ├── injection-hygiene.md
│   ├── integration-contract.md      #   Core integration contract
│   ├── output-composition.md
│   ├── output-language.md
│   ├── output-manifest.md
│   ├── output-versioning.md
│   ├── resumable-runs.md
│   ├── reviewer-independence.md
│   ├── reviewer-routing.md
│   ├── review-tracing.md
│   └── skill-governance.md
│
├── src/
	│   └── tools/                       # Layer 2: Tools (8 CLI tools)
	│       ├── eval-wiki.py             #   Core knowledge base CLI
	│       ├── env-component-manager.py #   Tree-based component manager
	│       ├── capture-filter.py        #   Runtime noise filter
	│       ├── evidence-check.py        #   Evidence file validator
	│       ├── iteration-log.py         #   Feedback loop convergence tracker
	│       ├── provenance.py            #   Provenance link validator
	│       ├── run-state.py             #   Pipeline state machine
	│       └── watchdog.py              #   Docker container monitor
│
├── skills/                          # Layer 3: Skills (9 modules)
	│   ├── auto-eval-pipeline/
	│   │   └── SKILL.md                 #   🟢 DRIVE — End-to-end pipeline driver
	│   ├── env-component-manager/
	│   │   └── SKILL.md                 #   🟢 DRIVE — Tree-based component manager
	│   ├── env-gen/
	│   │   └── SKILL.md                 #   🟢 DRIVE — Generate Docker environments
	│   ├── eval-wiki/
	│   │   └── SKILL.md                 #   ⚙️ TOOL — Knowledge base helper
	│   ├── feedback-align/
	│   │   └── SKILL.md                 #   🟢🔴 DRIVE+ACQUIT — Feedback loop
	│   ├── report-gen/
	│   │   └── SKILL.md                 #   🟢 DRIVE — Generate HTML reports
	│   ├── rubric-gen/
	│   │   └── SKILL.md                 #   🔴 ACQUIT — Generate scoring rubrics
	│   ├── setup/
	│   │   └── SKILL.md                 #   🟢 DRIVE — Interactive setup wizard
	│   └── task-gen/
	│       └── SKILL.md                 #   🟢 DRIVE — Generate eval tasks
│
├── dist/tools/
│   └── eval-wiki.py -> ../../src/tools/eval-wiki.py  # Symlink
│
├── tests/
│   └── test_skill_structure.py      # Skill architecture tests
│
└── tools/
    └── install_eval_wiki.sh         # Installation script
```

---

## ⚖️ Design Principles

### DRIVE vs ACQUIT (Dual-Axis Separation)

The separation of **DRIVE** (驱动) and **ACQUIT** (验证) is the foundational design principle of Auto-Eval.

| Aspect | 🟢 DRIVE (驱动) | 🔴 ACQUIT (验证) |
|--------|-----------------|-------------------|
| **Role** | Constructive — generate, assemble, compose | Evaluative — score, judge, verify |
| **Can be same model?** | ✅ Yes — one model can drive its own progress | ❌ No — must be cross-model (different family) |
| **Examples** | task-gen, env-gen, report-gen | rubric-gen, change verification |
| **Mechanical checks** | Script evaluators (binary checks) | LLM judge evaluators (cross-model) |
| **Trust model** | Trust-but-verify | Trust-nobody — independent verification |
| **Output** | Artifacts (tasks, envs, reports) | Verdicts (yes/no/inconclusive) |

### Proof Axis vs Empirical Axis

- **Proof Axis** (DRIVE): Formal, mechanical, deterministic — script evaluators, structural checks, format validation
- **Empirical Axis** (ACQUIT): Subjective, judgment-based, probabilistic — LLM judge evaluations, quality scoring, alignment assessment

### Knowledge Compounding

The eval-wiki compounds knowledge across the eval lifecycle:
1. **task-gen** writes tasks → eval-wiki tracks coverage gaps
2. **rubric-gen** reads tasks + gaps → generates targeted rubrics
3. **runs** produce verdicts → eval-wiki records supports/invalidates edges
4. **feedback-align** applies user corrections → evaluation quality improves
5. **query_pack.md** is rebuilt → next cycle starts with richer context

---

## 🧩 Stage Details

| Stage | Role | Depends On | Produces | Description |
|-------|------|-----------|----------|-------------|
| **task-gen** | 🟢 DRIVE | eval-wiki | Scenario, Task | Generates Agent eval tasks using AWM two-stage generation: scenario generation → task generation |
| **env-gen** | 🟢 DRIVE | task, eval-wiki, env-component-manager | Environment | Assembles components via component manager, fine-tunes as needed, provisions docker-compose environment |
| **rubric-gen** | 🔴 ACQUIT | task, eval-wiki | Rubric + Evaluator Scripts | Generates scoring criteria (binary/scale/percentage), evaluator scripts, and LLM judge prompts |
| **report-gen** | 🟢 DRIVE | run, eval-wiki | HTML Report | Reads all runs/rubrics/tasks, generates a single-page HTML report with stats cards and color-coded results |
| **feedback-align** | 🟢🔴 DRIVE+ACQUIT | eval-wiki | Feedback | Records feedback, classifies issue types, applies changes (DRIVE), then verifies cross-model (ACQUIT) |

---

## 🤝 Contributing

### Adding a New Skill

Each skill is a directory under `skills/` with a `SKILL.md` file. The integration contract requires 6 components:

1. **Frontmatter** — YAML frontmatter with fields:
   - `name`: Unique skill name (e.g., `my-skill`)
   - `description`: Human-readable description
   - `argument-hint`: CLI argument hint for the skill
   - `allowed-tools`: Tools the skill may use (e.g., `Bash(*), Read, Write, Edit, Grep, Glob`)
   - `role`: One of `DRIVE`, `ACQUIT`, `DRIVE_ACQUIT`, or `TOOL`
   - `depends-on`: Array of skill dependencies
   - `produces`: Array of artifact types

2. **Overview** — What the skill does and when to use it

3. **Helper Resolution** — How to resolve the eval-wiki script path (Variant B: warn + skip)

4. **Phases** — Step-by-step phases with shell commands

5. **Output** — What artifacts the skill produces

6. **Verification** — How to verify the skill's output

### Skill Interface Requirements

```yaml
---
name: my-skill
description: 'Description of what this skill does'
argument-hint: '[args]'
allowed-tools: Bash(*), Read, Write, Edit, Grep, Glob
role: DRIVE          # DRIVE | ACQUIT | DRIVE_ACQUIT | TOOL
depends-on: [eval-wiki]
produces: [artifact]
---
```

### Pluggability Matrix

| Component | Replaceable? | Swap Mechanism |
|-----------|-------------|----------------|
| task-gen | ✅ Yes | Swap `skills/task-gen/SKILL.md` |
| env-gen | ✅ Yes | Swap `skills/env-gen/SKILL.md` |
| env-component-manager | ✅ Yes | Swap `src/tools/env-component-manager.py` |
| rubric-gen | ✅ Yes | Swap `skills/rubric-gen/SKILL.md` |
| report-gen | ✅ Yes | Swap `skills/report-gen/SKILL.md` |
| feedback-align | ✅ Yes | Swap `skills/feedback-align/SKILL.md` |
| eval-wiki | ✅ Yes | Swap `src/tools/eval-wiki.py` |
| Shared contracts | ⚠️ With care | Update `shared-references/*.md` |

---

## 📜 License

MIT — See [LICENSE](LICENSE) for details.

---

*Built with 🦐 for the Agent Verification community.*
