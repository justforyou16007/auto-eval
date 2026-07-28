Build a TypeScript CLI tool called `eval-wiki` — a persistent knowledge base for an Agent verification pipeline. This is the foundational data layer that manages test tasks, environments, rubrics, run records, and feedback. It must be a single-file CLI tool (Node.js, no external dependencies beyond Node built-ins) with full test coverage.

## Directory Structure

When initialized via `init <path>`, creates:
```
eval-wiki/
├── index.md          (auto-generated categorical index)
├── log.md            (append-only timeline)
├── gap_map.md        (field gaps with stable IDs: G1, G2, ...)
├── query_pack.md     (compressed context for LLM, max 8000 chars)
├── tasks/
├── environments/
├── rubrics/
├── runs/
├── feedback/
└── graph/
    └── edges.jsonl   (one JSON object per line)
```

Seed file contents:
- index.md: "# Eval Wiki Index\n\n_Auto-generated. Do not edit._\n"
- log.md: "# Eval Wiki Log\n\n_Append-only timeline._\n"
- gap_map.md: "# Gap Map\n\n_Field gaps with stable IDs._\n"
- query_pack.md: "# Query Pack\n\n_Auto-generated for task-gen and rubric-gen. Max 8000 chars._\n"
- graph/edges.jsonl: "" (empty file)

## Entity Schemas

Each entity is a Markdown file with YAML frontmatter + body.

### Task (tasks/<slug>.md)

Frontmatter fields:
- type: task
- node_id: task:<slug>
- title: "human readable title"
- difficulty: lite | easy | medium | hard | beast
- cost_budget: number (e.g. 0.5)
- scenario_type: single-turn | multi-turn | tool-chain | error-recovery
- agent_constraints: object with max_turns (number), allowed_tools (string array), disallowed (string array)
- expected_behavior: string array
- coverage_gaps: string array (gap IDs like ["gap:G1"])
- status: draft | finalized | running | completed | retired
- based_on: string array (task node IDs)
- added: ISO 8601 timestamp

Body sections:
```
# <title>

## Description
_DESCRIPTION_

## Setup
_TODO: environment requirements_

## Expected Flow
_TODO: step-by-step expected agent behavior_
```

### Environment (environments/<slug>.md)

Frontmatter:
- type: environment
- node_id: env:<slug>
- task_id: task:<slug>
- docker: object with image (string), dockerfile (string, optional), build_args (object), volumes (string array), env_vars (object), network (string: none|bridge|host), resource_limits (object with memory, cpus)
- mock_services: array of {name, port, script}
- agent_endpoint: string (URL)
- health_check: object with command (string), timeout_seconds (number)
- status: draft | provisioned | running | collected | destroyed
- added: ISO timestamp

Body:
```
# Environment for <task_id>

## Docker Configuration
## Mock Services
## Health Check
```

### Rubric (rubrics/<slug>.md)

Frontmatter:
- type: rubric
- node_id: rubric:<slug>
- task_id: task:<slug>
- criteria: array of criterion objects, each with:
  - id: string (e.g. "C1")
  - name: string
  - scoring: binary | scale_1_5 | percentage
  - weight: number (0-1)
  - evaluator: script | llm_judge | hybrid
  - script_path: string (optional, when evaluator includes script)
  - llm_judge: object with model, rubric_prompt, independence (optional, when evaluator includes llm_judge)
- status: draft | reviewed | finalized | revised
- assurance: draft | submission
- added: ISO timestamp

Body:
```
# Rubric for <task_id>

## Criteria Summary
| ID | Name | Scoring | Weight | Evaluator |
...

## Scoring Details
### C1: <name>
...
```

### Run (runs/<slug>.md)

Frontmatter:
- type: run
- node_id: run:<slug>
- task_id: task:<slug>
- env_id: env:<slug>
- rubric_id: rubric:<slug>
- agent: object with model (string), endpoint (string), config (object with temperature, max_tokens)
- verdict: yes | no | inconclusive
- confidence: high | medium | low
- scores: object mapping criterion_id to score (number for scale, "PASS"/"FAIL" for binary)
- total: number (weighted total, 0-10 scale)
- raw_output_path: string
- provenance: string array (file paths)
- status: running | completed | failed | timed_out
- added: ISO timestamp

Body:
```
# Run <slug>

## Agent
## Results
## Evidence
```

### Feedback (feedback/<slug>.md)

Frontmatter:
- type: feedback
- node_id: feedback:<slug>
- target_type: task | rubric | environment | run
- target_id: string (node ID)
- from: user | auto-audit
- issue_type: misalignment | missing_case | rubric_error | env_error | difficulty_mismatch
- description: string
- action: revise_task | revise_rubric | revise_env | revise_report
- proposed_change: object (field, from, to)
- status: open | applied | verified | rejected
- applied_at: string (ISO timestamp or null)
- verified_by: string (model name or null)
- added: ISO timestamp

Body:
```
# Feedback: <issue_type>

## Description
## Proposed Change
## Verification Status
```

## CLI Commands

All commands are subcommands of the main program. Use a simple CLI parser (no external deps). The program name is "eval-wiki".

### init <wiki-root>
- Create directory structure (6 dirs: tasks, environments, rubrics, runs, feedback, graph)
- Create 4 seed files + empty edges.jsonl if they don't exist
- Create the 5 entity directories with { recursive: true }
- Append log entry "Wiki initialized"
- Print "Eval wiki initialized at <path>"
- If already initialized (tasks/ exists), print message and exit 0 (idempotent)

### add-task <wiki-root> --title <title> --difficulty <level> [--cost <number>] [--scenario-type <type>] [--max-turns <n>] [--allowed-tools <csv>] [--disallowed <csv>] [--expected-behavior <csv>] [--coverage-gap <csv>] [--based-on <csv>] [--status <status>] [--update]
- Default difficulty: medium
- Default cost: 0.5
- Default scenario-type: single-turn
- Default status: draft
- slug = slugify(title) — lowercase, replace [^a-z0-9]+ with -, trim leading/trailing -
- If file exists and no --update: skip, print "Task already ingested: <slug> — skipping.", return path
- Render frontmatter + body template
- After write: call rebuildIndex, rebuildQueryPack, appendLog
- Print "Task ingested: <path>"
- Return the file path

### add-env <wiki-root> --task-id <task:slug> [--image <image>] [--dockerfile <path>] [--volumes <csv>] [--env-vars <key=val,key=val>] [--network <network>] [--memory <mem>] [--cpus <n>] [--mock-service <name:port:script>] [--agent-endpoint <url>] [--health-check <cmd>] [--health-timeout <sec>] [--status <status>] [--update]
- Extract task slug from task-id (strip "task:" prefix if present)
- env slug = task-slug + "-env"
- Default image: "python:3.11"
- Default network: "bridge"
- Default status: "draft"
- Dedup with --update flag (same as add-task pattern)
- After write: rebuildIndex, rebuildQueryPack, appendLog
- Automatically add edge: env:<slug> --depends_on--> task:<slug>

### add-rubric <wiki-root> --task-id <task:slug> --criteria-json <path> [--status <status>] [--assurance <level>] [--update]
- Extract task slug from task-id
- rubric slug = task-slug + "-rubric"
- Read criteria from JSON file (array of criterion objects)
- Default status: "draft"
- Default assurance: "draft"
- Dedup with --update
- After write: rebuildIndex, rebuildQueryPack, appendLog

### add-run <wiki-root> --task-id <task:slug> --env-id <env:slug> --rubric-id <rubric:slug> --model <model> [--endpoint <url>] [--temperature <n>] [--max-tokens <n>] [--verdict <verdict>] [--confidence <level>] [--scores-json <path>] [--raw-output-path <path>] [--provenance <csv>] [--status <status>]
- run slug = auto-generated timestamp-based: "run-" + YYYYMMDDHHmmss
- Default verdict: "inconclusive"
- Default confidence: "medium"
- Default status: "running"
- Default temperature: 0.0
- Default max-tokens: 4096
- Parse scores from JSON file if provided
- Compute total: for each criterion in the linked rubric, multiply normalized score by weight, sum, scale to 0-10
  - binary: PASS=1.0, FAIL=0.0
  - scale_1_5: score/5.0
  - percentage: score/100.0
- After write: rebuildIndex, rebuildQueryPack, appendLog
- Auto-add edge: task:<slug> --tested_by--> run:<slug>
- If verdict=yes: auto-add edge run:<slug> --supports--> task:<slug>
- If verdict=no: auto-add edge run:<slug> --invalidates--> task:<slug>

### add-feedback <wiki-root> --target-type <type> --target-id <id> --from <source> --issue-type <type> --description <text> --action <action> [--field <field>] [--from-value <val>] [--to-value <val>]
- feedback slug = "fb-" + YYYYMMDDHHmmss
- Default status: "open"
- proposed_change object built from --field, --from-value, --to-value
- After write: rebuildIndex, rebuildQueryPack, appendLog
- Auto-add edge: feedback:<slug> --addresses--> <target_id>

### add-edge <wiki-root> --from <node-id> --to <node-id> --type <edge-type> [--note <text>]
- Validate edge type against VALID_EDGE_TYPES set
- Normalize node IDs (add prefix if missing: task: env: rubric: run: feedback: gap:)
- Call warnIfDangling for both nodes (warn but don't fail)
- Append JSON line: {"from":"...","to":"...","type":"...","note":"...","added":"..."}
- Also append log entry

### rebuild-index <wiki-root>
- Scan all 5 entity directories
- Generate index.md with sections: ## Tasks, ## Environments, ## Rubrics, ## Runs, ## Feedback
- Each section lists entities as markdown table or list with node_id + title/status
- Also list gap_map.md and graph stats

### rebuild-query-pack <wiki-root>
- Generate query_pack.md with max 8000 chars total
- Sections with char budgets:
  1. Project direction: read EVAL_CONFIG.md if exists (first 1500 chars), else "No EVAL_CONFIG.md found"
  2. Top 5 gaps: read gap_map.md (max 1200 chars)
  3. Task clusters: group tasks by scenario_type, 2-3 sentences each (max 1600 chars)
  4. Failed tasks banlist: runs with verdict=no, list task slug + reason (max 1200 chars)
  5. Active feedback: feedback with status=open (max 1000 chars)
  6. Coverage stats: total tasks / completed runs / pass rate / scenario coverage (max 500 chars)
- Truncate each section to its budget, truncate total to 8000
- Write to query_pack.md

### query <wiki-root> "<topic>"
- Search across all .md files in the wiki (tasks, environments, rubrics, runs, feedback, gap_map.md)
- Case-insensitive substring match
- Return matching lines with file path and line number
- Limit to 50 results

### log <wiki-root> [message]
- If message provided: append timestamped line to log.md
- If no message: print last 20 lines of log.md

### stats <wiki-root>
- Print counts: tasks, environments, rubrics, runs, feedback, edges
- Print pass rate: runs with verdict=yes / total completed runs
- Print coverage: unique tasks with at least 1 run / total tasks

## Edge Types (VALID_EDGE_TYPES)

```
extends       (task -> task)       — builds on prior task
covers_gap    (task -> gap)        — task covers a scenario gap
tested_by     (task -> run)        — task was tested by a run
depends_on    (env -> task)        — environment depends on task definition
scored_by     (run -> rubric)      — run was scored by rubric
supports      (run -> task)        — run verdict=yes supports task validity
invalidates   (run -> task)        — run verdict=no invalidates task
addresses     (feedback -> *)      — feedback addresses an entity
supersedes    (task -> task)       — newer task replaces older
```

## Helper Functions

- slugify(title): lowercase, replace /[^a-z0-9]+/g with "-", replace /^-+|-+$/g with ""
- nowUtcIso(): new Date().toISOString().replace(/\.\d{3}Z$/, "Z")
- nowUtcDate(): new Date().toISOString().slice(0, 10)
- yamlQuote(s): if s is null/undefined return "null"; wrap in double quotes, escape inner double quotes and backslashes
- splitCsv(s): split by comma, trim, filter empty
- normalizeNodeId(target, defaultPrefix): if already has ":", return as-is; if matches gap pattern G\d+, prefix with "gap:"; else prefix with defaultPrefix
- warnIfDangling(wikiRoot, nodeId, fnName): check if node file exists in the appropriate directory; if not, print warning to stderr (do NOT throw)
- appendLog(wikiRoot, message): append "- <ISO timestamp> <message>\n" to log.md
- rebuildIndex(wikiRoot): regenerate index.md
- rebuildQueryPack(wikiRoot): regenerate query_pack.md

## YAML Frontmatter Rendering

For rendering frontmatter, output:
```
---
type: <type>
node_id: <id>
<field>: <value>
...
---
```

String values: wrap in double quotes via yamlQuote
Number values: output as-is
Boolean values: output as-is
Array values: output as "[item1, item2, ...]" with each item yamlQuoted
Object values: output as nested YAML (indent 2 spaces) or JSON inline

## Testing Requirements

Write comprehensive tests (using Node's built-in test runner or a simple custom test harness) covering:

1. init: creates correct directory structure and seed files
2. init: is idempotent (running twice doesn't error)
3. add-task: creates valid markdown file with correct frontmatter fields
4. add-task: slug generation is deterministic (same title = same slug)
5. add-task: dedup without --update skips and prints message
6. add-task: with --update overwrites existing file
7. add-task: after adding, index.md and query_pack.md are rebuilt
8. add-task: log.md gets a new entry
9. add-env: creates environment linked to task_id
10. add-env: default values are correct (image, network, status)
11. add-rubric: creates rubric with criteria from JSON file
12. add-rubric: criteria array is correctly rendered in frontmatter
13. add-run: computes total score from weighted criteria correctly
14. add-run: binary scoring (PASS=1.0, FAIL=0.0) works
15. add-run: scale_1_5 scoring normalizes correctly
16. add-run: auto-adds tested_by edge
17. add-run: verdict=yes auto-adds supports edge
18. add-run: verdict=no auto-adds invalidates edge
19. add-feedback: creates feedback with correct fields
20. add-feedback: auto-adds addresses edge
21. add-edge: validates edge types (invalid type throws error)
22. add-edge: warns on dangling nodes but doesn't fail
23. rebuild-index: lists all entities correctly
24. rebuild-query-pack: stays under 8000 chars
25. rebuild-query-pack: includes all sections when data exists
26. query: returns matching results
27. query: returns empty for no matches
28. stats: prints correct counts
29. stats: computes pass rate correctly
30. Edge cases: empty wiki, missing directories, special characters in titles

## Technical Requirements

- Pure Node.js TypeScript, no external npm dependencies
- Use only Node built-in modules: fs, path, child_process (if needed), crypto (if needed)
- Single file: eval-wiki.ts (can be compiled to eval-wiki.js with tsc or run with tsx)
- CLI entry point: parse process.argv for subcommand and flags
- Use execSync-style synchronous file I/O (this is a CLI tool, not a server)
- Exit codes: 0 for success, 1 for errors
- All output to stdout, warnings to stderr

## Output

Create:
1. eval-wiki.ts — the main CLI tool
2. eval-wiki.test.ts — comprehensive test suite
3. tsconfig.json — TypeScript config for compilation
4. package.json — with scripts: "build": "tsc", "test": "node --test dist/eval-wiki.test.js"
5. A sample criteria.json fixture for testing add-rubric