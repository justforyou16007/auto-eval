#!/usr/bin/env python3
"""
eval-wiki — A persistent knowledge base for an Agent verification pipeline.
Pure Python CLI tool, no external dependencies beyond Python stdlib.
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VALID_EDGE_TYPES = {
    "env_for",
    "rubric_for",
    "tested_by",
    "uses_env",
    "scored_by",
    "supports",
    "invalidates",
    "addresses_gap",
    "evolved_from",
    "revise",
    "scenario_for",
    "derived_from_scenario",
}

ENTITY_DIRS = ["tasks", "environments", "rubrics", "runs", "feedback", "scenarios"]
VALID_DIFFICULTIES = {"lite", "easy", "medium", "hard", "beast"}
VALID_SCENARIO_TYPES = {"single-turn", "multi-turn", "tool-chain", "error-recovery"}
VALID_STATUSES = {
    "draft", "finalized", "running", "completed", "retired",
    "provisioned", "collected", "destroyed", "reviewed", "revised",
    "failed", "timed_out", "open", "applied", "verified", "rejected",
}
VALID_ISSUE_TYPES = {
    "misalignment", "missing_case", "rubric_error", "env_error", "difficulty_mismatch",
}
VALID_ACTIONS = {"revise_task", "revise_rubric", "revise_env", "revise_report"}
VALID_VERDICTS = {"yes", "no", "inconclusive"}
VALID_CONFIDENCES = {"high", "medium", "low"}
VALID_ASSURANCES = {"draft", "submission"}
VALID_FROM_SOURCES = {"user", "auto-audit"}

# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def slugify(title: str) -> str:
    """Convert title to a URL-safe slug."""
    slug = title.lower()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    slug = re.sub(r"^-+|-+$", "", slug)
    return slug


def now_utc_iso() -> str:
    """Return current UTC time as ISO 8601 (without milliseconds)."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def now_utc_date() -> str:
    """Return current UTC date as YYYY-MM-DD."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def now_utc_compact() -> str:
    """Return current UTC timestamp as YYYYMMDDHHmmss."""
    return datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")


def yaml_quote(s) -> str:
    """Quote a string value for YAML frontmatter."""
    if s is None:
        return "null"
    s = str(s)
    s = s.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{s}"'


def split_csv(s: str) -> list:
    """Split a comma-separated string into a list."""
    if not s or not s.strip():
        return []
    return [item.strip() for item in s.split(",") if item.strip()]


def normalize_node_id(target: str, default_prefix: str) -> str:
    """Normalize a node ID by adding prefix if missing."""
    if ":" in target:
        return target
    if re.match(r"^G\d+$", target):
        return f"gap:{target}"
    return f"{default_prefix}:{target}"


def load_yaml_frontmatter(filepath: str) -> dict:
    """Parse YAML frontmatter from a markdown file."""
    if not os.path.isfile(filepath):
        return {}
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()
    if not content.startswith("---"):
        return {}
    end_idx = content.find("---", 3)
    if end_idx == -1:
        return {}
    frontmatter_text = content[3:end_idx].strip()
    return parse_yaml_simple(frontmatter_text)


def parse_yaml_simple(text: str) -> dict:
    """Parse simple YAML frontmatter (key: value pairs, arrays, nested objects)."""
    result = {}
    lines = text.split("\n")
    current_key = None
    current_nested = None
    i = 0
    while i < len(lines):
        line = lines[i]
        # Skip empty lines
        if not line.strip():
            i += 1
            continue

        # Check if this is a nested continuation
        if line.startswith("  ") and current_key:
            stripped = line.strip()
            if current_nested == "array":
                # Array item continuation
                if stripped.startswith("- "):
                    val = stripped[2:].strip()
                    val = val.strip('"')
                    result[current_key].append(val)
            elif current_nested == "object":
                # Object key: value
                if ":" in stripped:
                    k, v = stripped.split(":", 1)
                    k = k.strip()
                    v = v.strip().strip('"')
                    result[current_key][k] = v
            elif current_nested == "array_of_objects":
                if stripped == "-":
                    # Start of new object in array
                    result[current_key].append({})
                elif stripped.startswith("- "):
                    rest = stripped[2:].strip()
                    if ":" in rest:
                        k, v = rest.split(":", 1)
                        k = k.strip()
                        v = v.strip().strip('"')
                        obj = {}
                        obj[k] = v
                        result[current_key].append(obj)
                    else:
                        result[current_key].append(rest.strip('"'))
                elif ":" in stripped:
                    k, v = stripped.split(":", 1)
                    k = k.strip()
                    v = v.strip().strip('"')
                    if result[current_key] and isinstance(result[current_key][-1], dict):
                        result[current_key][-1][k] = v
            i += 1
            continue

        if ":" in line:
            key, value = line.split(":", 1)
            key = key.strip()
            value = value.strip()

            if value == "":
                # Might be start of a nested structure
                # Look ahead
                j = i + 1
                while j < len(lines) and (lines[j].strip() == "" or lines[j].startswith("  ")):
                    j += 1
                if j > i + 1:
                    # Check if array or object
                    next_line = lines[i + 1].strip() if i + 1 < len(lines) else ""
                    if next_line.startswith("- "):
                        # Array of primitives
                        result[key] = []
                        current_nested = "array"
                        current_key = key
                    elif next_line.startswith("  "):
                        # Check if array of objects or plain object
                        sub = lines[i + 1].strip()
                        if sub == "-":
                            result[key] = []
                            current_nested = "array_of_objects"
                            current_key = key
                        elif ":" in sub:
                            result[key] = {}
                            current_nested = "object"
                            current_key = key
                    else:
                        current_key = None
                        current_nested = None
                else:
                    current_key = None
                    current_nested = None
            else:
                # Simple value
                current_key = None
                current_nested = None
                if value.startswith("[") and value.endswith("]"):
                    # Inline JSON array
                    try:
                        result[key] = json.loads(value)
                    except json.JSONDecodeError:
                        # Parse manually
                        inner = value[1:-1]
                        items = []
                        for item in re.findall(r'"([^"]*)"', inner):
                            items.append(item)
                        result[key] = items
                elif value.startswith("{") and value.endswith("}"):
                    # Inline JSON object
                    try:
                        result[key] = json.loads(value)
                    except json.JSONDecodeError:
                        result[key] = value
                elif value in ("true", "false"):
                    result[key] = value == "true"
                elif value == "null":
                    result[key] = None
                else:
                    # Try number
                    try:
                        if "." in value:
                            result[key] = float(value)
                        else:
                            result[key] = int(value)
                    except ValueError:
                        # String, strip quotes
                        result[key] = value.strip('"')
        i += 1

    return result


def render_yaml_frontmatter(fields: dict) -> str:
    """Render YAML frontmatter from a dict."""
    lines = ["---"]
    for key, value in fields.items():
        rendered = render_yaml_value(value)
        lines.append(f"{key}: {rendered}")
    lines.append("---")
    return "\n".join(lines) + "\n"


def render_yaml_value(value) -> str:
    """Render a single YAML value. Complex types use inline JSON for round-trip safety."""
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, list):
        if not value:
            return "[]"
        # Flat list of non-dict items: render as inline array
        if not any(isinstance(item, dict) for item in value):
            items = [yaml_quote(str(v)) for v in value]
            return "[" + ", ".join(items) + "]"
        # List containing dicts: render as inline JSON
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, dict):
        if not value:
            return "{}"
        # Dict: render as inline JSON
        return json.dumps(value, ensure_ascii=False)
    return yaml_quote(str(value))


def warn_if_dangling(wiki_root: str, node_id: str, fn_name: str = ""):
    """Check if a node exists; warn to stderr if not."""
    if ":" not in node_id:
        return
    prefix, slug = node_id.split(":", 1)
    if prefix == "gap":
        # Check gap_map.md
        gap_file = os.path.join(wiki_root, "gap_map.md")
        if not os.path.isfile(gap_file):
            print(f"Warning: gap_map.md not found (checking {node_id})", file=sys.stderr)
            return
        with open(gap_file, "r", encoding="utf-8") as f:
            content = f.read()
        if f"G{slug}" not in content and node_id not in content:
            print(f"Warning: dangling node {node_id} (not found in gap_map.md)", file=sys.stderr)
        return

    dir_map = {
        "task": "tasks",
        "env": "environments",
        "rubric": "rubrics",
        "run": "runs",
        "feedback": "feedback",
    }
    dir_name = dir_map.get(prefix)
    if dir_name is None:
        print(f"Warning: unknown node type prefix '{prefix}' for {node_id}", file=sys.stderr)
        return

    filepath = os.path.join(wiki_root, dir_name, f"{slug}.md")
    if not os.path.isfile(filepath):
        print(f"Warning: dangling node {node_id} (file not found: {filepath})", file=sys.stderr)


def append_log(wiki_root: str, message: str):
    """Append a timestamped entry to log.md."""
    log_path = os.path.join(wiki_root, "log.md")
    if not os.path.isfile(log_path):
        return
    timestamp = now_utc_iso()
    entry = f"- {timestamp} {message}\n"
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(entry)


# ---------------------------------------------------------------------------
# Core functions
# ---------------------------------------------------------------------------

def init_wiki(wiki_root: str):
    """Initialize the eval-wiki directory structure."""
    wiki_root = os.path.abspath(wiki_root)

    # Check if already initialized
    tasks_dir = os.path.join(wiki_root, "tasks")
    if os.path.isdir(tasks_dir):
        print(f"Eval wiki already initialized at {wiki_root}")
        return

    # Create directories
    for d in ENTITY_DIRS:
        os.makedirs(os.path.join(wiki_root, d), exist_ok=True)
    os.makedirs(os.path.join(wiki_root, "graph"), exist_ok=True)

    # Create seed files
    seed_files = {
        "index.md": "# Eval Wiki Index\n\n_Auto-generated. Do not edit._\n",
        "log.md": "# Eval Wiki Log\n\n_Append-only timeline._\n",
        "gap_map.md": "# Gap Map\n\n_Field gaps with stable IDs._\n",
        "query_pack.md": "# Query Pack\n\n_Auto-generated for task-gen and rubric-gen. Max 8000 chars._\n",
    }
    for fname, content in seed_files.items():
        fpath = os.path.join(wiki_root, fname)
        if not os.path.exists(fpath):
            with open(fpath, "w", encoding="utf-8") as f:
                f.write(content)

    # Create empty edges.jsonl
    edges_path = os.path.join(wiki_root, "graph", "edges.jsonl")
    if not os.path.exists(edges_path):
        with open(edges_path, "w", encoding="utf-8") as f:
            f.write("")

    # Append log
    append_log(wiki_root, "Wiki initialized")

    print(f"Eval wiki initialized at {wiki_root}")



def render_scenario_page(name, description, scenario_type, difficulty, capabilities, env_hints):
    """Render a scenario markdown page."""
    fm = {
        "type": "scenario",
        "node_id": f"scenario:{slugify(name)}",
        "name": name,
        "description": description,
        "scenario_type": scenario_type,
        "difficulty": difficulty,
        "capabilities": capabilities if capabilities else [],
        "env_hints": env_hints,
        "status": "draft",
        "added": now_utc_iso(),
    }
    body_lines = [f"# {name}", "", "## Description", description, "", "## Capabilities Tested"]
    for cap in (capabilities or []):
        body_lines.append(f"- {cap}")
    body_lines.extend(["", "## Environment Hints", env_hints or "_TODO: what environment components this scenario needs._"])
    body_lines.extend(["", "## Connections", "_Edges are recorded in `graph/edges.jsonl`; summarize here for human readers._"])
    body = "\n".join(body_lines)
    return render_yaml_frontmatter(fm) + "\n" + body + "\n"


def add_scenario(wiki_root, name, description, scenario_type="multi-turn", difficulty="medium",
                 capabilities=None, env_hints="", update=False):
    """Add a scenario to the wiki."""
    slug = slugify(name)
    filepath = os.path.join(wiki_root, "scenarios", f"{slug}.md")
    if os.path.exists(filepath) and not update:
        print(f"Scenario already ingested: {slug} — skipping.")
        return filepath
    caps = split_csv(capabilities) if capabilities else []
    page = render_scenario_page(name, description, scenario_type, difficulty, caps, env_hints)
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(page)
    rebuild_index(wiki_root)
    rebuild_query_pack(wiki_root)
    append_log(wiki_root, f"Scenario added: scenario:{slug}")
    print(f"Scenario ingested: {filepath}")
    return filepath


def add_task(
    wiki_root: str,
    title: str,
    difficulty: str = "medium",
    cost: float = 0.5,
    scenario_type: str = "single-turn",
    max_turns: int = None,
    allowed_tools: str = None,
    disallowed: str = None,
    expected_behavior: str = None,
    coverage_gap: str = None,
    based_on: str = None,
    status: str = "draft",
    update: bool = False,
    scenario_id: str = None,
    goal: str = None,
    input_spec: str = None,
    preconditions: str = None,
    constraints: str = None,
):
    """Add a task to the wiki.

    Body sections (测试目标 / 输入规格 / 预期输出 / 前置条件 / 边界条件)
    are populated from the corresponding content flags. When a flag is
    omitted, a `_TODO` stub is kept so callers that fill the body later
    (or that rely on the legacy default) are not broken.
    """
    slug = slugify(title)
    filepath = os.path.join(wiki_root, "tasks", f"{slug}.md")

    # Check dedup
    if os.path.exists(filepath) and not update:
        print(f"Task already ingested: {slug} — skipping.")
        return filepath

    # Normalize expected_behavior into a readable string for the body.
    expected_behavior_items = split_csv(expected_behavior) if expected_behavior else []
    expected_behavior_text = "; ".join(expected_behavior_items)

    # Build frontmatter
    fm = {
        "type": "task",
        "node_id": f"task:{slug}",
        "title": title,
        "difficulty": difficulty,
        "cost_budget": cost,
        "scenario_type": scenario_type,
        "agent_constraints": {
            "max_turns": max_turns if max_turns is not None else 0,
            "allowed_tools": split_csv(allowed_tools) if allowed_tools else [],
            "disallowed": split_csv(disallowed) if disallowed else [],
        },
        "expected_behavior": expected_behavior_items,
        "coverage_gaps": [f"gap:{g}" for g in split_csv(coverage_gap)] if coverage_gap else [],
        "status": status,
        "based_on": [normalize_node_id(b, "task") for b in split_csv(based_on)] if based_on else [],
        "scenario_id": normalize_node_id(scenario_id, "scenario") if scenario_id else "",
        "added": now_utc_iso(),
    }

    # Build body — each section is filled from its content flag, falling
    # back to a `_TODO` stub when the caller did not supply that content.
    goal_body = (goal or "").strip() if goal else ""
    goal_section = goal_body if goal_body else "_TODO: this task 要验证 Agent 的什么能力_"

    input_spec_body = (input_spec or "").strip() if input_spec else ""
    input_spec_section = input_spec_body if input_spec_body else "_TODO: Agent 接收的初始输入/prompt_"

    expected_section = expected_behavior_text if expected_behavior_text else "_TODO: 期望的行为描述，非精确输出_"

    preconditions_body = (preconditions or "").strip() if preconditions else ""
    preconditions_section = preconditions_body if preconditions_body else "_TODO: 环境状态、mock 服务配置要求_"

    constraints_body = (constraints or "").strip() if constraints else ""
    constraints_section = constraints_body if constraints_body else "_TODO: Agent 不应做的事情、禁止的行为_"

    body = f"""# {title}

## 测试目标
{goal_section}

## 输入规格
{input_spec_section}

## 预期输出
{expected_section}

## 前置条件
{preconditions_section}

## 边界条件
{constraints_section}

## Connections
_Edges are recorded in `graph/edges.jsonl`; summarize here for human readers._
"""

    # Write file
    content = render_yaml_frontmatter(fm) + "\n" + body
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)

    # Create scenario edges if scenario_id provided
    if scenario_id:
        sid = normalize_node_id(scenario_id, "scenario")
        add_edge_internal(wiki_root, sid, f"task:{slug}", "scenario_for", "")
        add_edge_internal(wiki_root, f"task:{slug}", sid, "derived_from_scenario", "")

    # Rebuild
    rebuild_index(wiki_root)
    rebuild_query_pack(wiki_root)
    append_log(wiki_root, f"Task added: {slug}")

    print(f"Task ingested: {filepath}")
    return filepath


def add_env(
    wiki_root: str,
    task_id: str,
    image: str = "python:3.11",
    dockerfile: str = None,
    volumes: str = None,
    env_vars: str = None,
    network: str = "bridge",
    memory: str = None,
    cpus: float = None,
    mock_service: str = None,
    agent_endpoint: str = None,
    health_check: str = None,
    health_timeout: int = None,
    status: str = "draft",
    update: bool = False,
    scenario_id: str = None,
):
    """Add an environment to the wiki."""
    # Extract task slug from task-id
    task_slug = task_id
    if task_slug.startswith("task:"):
        task_slug = task_slug[5:]
    env_slug = task_slug + "-env"
    filepath = os.path.join(wiki_root, "environments", f"{env_slug}.md")

    # Check dedup
    if os.path.exists(filepath) and not update:
        print(f"Environment already ingested: {env_slug} — skipping.")
        return filepath

    # Parse env vars
    env_vars_dict = {}
    if env_vars:
        for pair in split_csv(env_vars):
            if "=" in pair:
                k, v = pair.split("=", 1)
                env_vars_dict[k.strip()] = v.strip()

    # Parse mock services
    mock_services = []
    if mock_service:
        for svc in split_csv(mock_service):
            parts = svc.split(":")
            if len(parts) >= 3:
                mock_services.append({
                    "name": parts[0],
                    "port": int(parts[1]) if parts[1].isdigit() else parts[1],
                    "script": parts[2],
                })

    # Parse volumes
    volumes_list = split_csv(volumes) if volumes else []

    # Build resource limits
    resource_limits = {}
    if memory:
        resource_limits["memory"] = memory
    if cpus is not None:
        resource_limits["cpus"] = cpus

    fm = {
        "type": "environment",
        "node_id": f"env:{env_slug}",
        "task_id": f"task:{task_slug}",
        "docker": {
            "image": image,
            "dockerfile": dockerfile,
            "build_args": {},
            "volumes": volumes_list,
            "env_vars": env_vars_dict,
            "network": network,
            "resource_limits": resource_limits,
        },
        "mock_services": mock_services,
        "agent_endpoint": agent_endpoint if agent_endpoint else "",
        "health_check": {
            "command": health_check if health_check else "",
            "timeout_seconds": health_timeout if health_timeout is not None else 30,
        },
        "scenario_id": normalize_node_id(scenario_id, "scenario") if scenario_id else "",
        "status": status,
        "added": now_utc_iso(),
    }

    body = f"""# Environment for task:{task_slug}

## Docker Configuration
## Mock Services
## Health Check
"""

    content = render_yaml_frontmatter(fm) + "\n" + body
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)

    # Auto-add edge
    add_edge_internal(wiki_root, f"env:{env_slug}", f"task:{task_slug}", "depends_on")

    # Create scenario edges if scenario_id provided
    if scenario_id:
        sid = normalize_node_id(scenario_id, "scenario")
        add_edge_internal(wiki_root, sid, f"env:{env_slug}", "scenario_for", "")
        add_edge_internal(wiki_root, f"env:{env_slug}", sid, "derived_from_scenario", "")

    rebuild_index(wiki_root)
    rebuild_query_pack(wiki_root)
    append_log(wiki_root, f"Environment added: {env_slug}")

    print(f"Environment ingested: {filepath}")
    return filepath


def add_rubric(
    wiki_root: str,
    task_id: str,
    criteria_json: str,
    status: str = "draft",
    assurance: str = "draft",
    update: bool = False,
    scenario_id: str = None,
):
    """Add a rubric to the wiki."""
    task_slug = task_id
    if task_slug.startswith("task:"):
        task_slug = task_slug[5:]
    rubric_slug = task_slug + "-rubric"
    filepath = os.path.join(wiki_root, "rubrics", f"{rubric_slug}.md")

    if os.path.exists(filepath) and not update:
        print(f"Rubric already ingested: {rubric_slug} — skipping.")
        return filepath

    # Read criteria from JSON file
    with open(criteria_json, "r", encoding="utf-8") as f:
        criteria = json.load(f)

    fm = {
        "type": "rubric",
        "node_id": f"rubric:{rubric_slug}",
        "task_id": f"task:{task_slug}",
        "criteria": criteria,
        "status": status,
        "assurance": assurance,
        "scenario_id": normalize_node_id(scenario_id, "scenario") if scenario_id else "",
        "added": now_utc_iso(),
    }

    # Build body
    body_lines = [f"# Rubric for task:{task_slug}", "", "## Criteria Summary"]
    body_lines.append("| ID | Name | Scoring | Weight | Evaluator |")
    body_lines.append("|----|------|---------|--------|-----------|")
    for c in criteria:
        cid = c.get("id", "")
        cname = c.get("name", "")
        cscore = c.get("scoring", "")
        cweight = c.get("weight", "")
        ceval = c.get("evaluator", "")
        body_lines.append(f"| {cid} | {cname} | {cscore} | {cweight} | {ceval} |")

    body_lines.extend(["", "## Scoring Details"])
    for c in criteria:
        cid = c.get("id", "")
        cname = c.get("name", "")
        body_lines.append(f"### {cid}: {cname}")
        body_lines.append("...")
        body_lines.append("")

    body_lines.extend(["", "## Honest scope"])
    body_lines.append("_What this rubric does NOT evaluate; banned interpretations; flagged edge cases._")
    body_lines.extend(["", "## Connections"])
    body_lines.append("_Edges are recorded in `graph/edges.jsonl`; summarize here for human readers._")
    body = "\n".join(body_lines)

    content = render_yaml_frontmatter(fm) + "\n" + body
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)

    # Create scenario edges if scenario_id provided
    if scenario_id:
        sid = normalize_node_id(scenario_id, "scenario")
        add_edge_internal(wiki_root, sid, f"rubric:{rubric_slug}", "scenario_for", "")
        add_edge_internal(wiki_root, f"rubric:{rubric_slug}", sid, "derived_from_scenario", "")

    rebuild_index(wiki_root)
    rebuild_query_pack(wiki_root)
    append_log(wiki_root, f"Rubric added: {rubric_slug}")

    print(f"Rubric ingested: {filepath}")
    return filepath


def add_run(
    wiki_root: str,
    task_id: str,
    env_id: str,
    rubric_id: str,
    model: str,
    endpoint: str = None,
    temperature: float = 0.0,
    max_tokens: int = 4096,
    verdict: str = "inconclusive",
    confidence: str = "medium",
    scores_json: str = None,
    raw_output_path: str = None,
    provenance: str = None,
    status: str = "running",
):
    """Add a run to the wiki."""
    task_slug = task_id
    if task_slug.startswith("task:"):
        task_slug = task_slug[5:]
    env_slug = env_id
    if env_slug.startswith("env:"):
        env_slug = env_slug[4:]
    rubric_slug = rubric_id
    if rubric_slug.startswith("rubric:"):
        rubric_slug = rubric_slug[7:]

    run_slug = "run-" + now_utc_compact()
    filepath = os.path.join(wiki_root, "runs", f"{run_slug}.md")

    # Parse scores
    scores = {}
    if scores_json:
        with open(scores_json, "r", encoding="utf-8") as f:
            scores = json.load(f)

    # Compute total: load rubric criteria, compute weighted score
    total = 0.0
    rubric_path = os.path.join(wiki_root, "rubrics", f"{rubric_slug}.md")
    if os.path.isfile(rubric_path):
        rubric_fm = load_yaml_frontmatter(rubric_path)
        criteria = rubric_fm.get("criteria", [])
        if criteria:
            weighted_sum = 0.0
            total_weight = 0.0
            for c in criteria:
                cid = c.get("id", "")
                scoring = c.get("scoring", "binary")
                weight = c.get("weight", 0)
                total_weight += weight

                if cid in scores:
                    raw_score = scores[cid]
                    if scoring == "binary":
                        normalized = 1.0 if raw_score in ("PASS", True, 1, "1") else 0.0
                    elif scoring == "scale_1_5":
                        normalized = float(raw_score) / 5.0
                    elif scoring == "percentage":
                        normalized = float(raw_score) / 100.0
                    else:
                        normalized = 0.0
                    weighted_sum += normalized * weight

            if total_weight > 0:
                total = round((weighted_sum / total_weight) * 10, 2)

    fm = {
        "type": "run",
        "node_id": f"run:{run_slug}",
        "task_id": f"task:{task_slug}",
        "env_id": f"env:{env_slug}",
        "rubric_id": f"rubric:{rubric_slug}",
        "agent": {
            "model": model,
            "endpoint": endpoint if endpoint else "",
            "config": {
                "temperature": temperature,
                "max_tokens": max_tokens,
            },
        },
        "verdict": verdict,
        "confidence": confidence,
        "scores": scores,
        "total": total,
        "raw_output_path": raw_output_path if raw_output_path else "",
        "provenance": split_csv(provenance) if provenance else [],
        "status": status,
        "added": now_utc_iso(),
    }

    body = f"""# Run {run_slug}

## Agent
## Results
## Evidence
"""

    content = render_yaml_frontmatter(fm) + "\n" + body
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)

    # Auto-add edges
    add_edge_internal(wiki_root, f"task:{task_slug}", f"run:{run_slug}", "tested_by")
    if verdict == "yes":
        add_edge_internal(wiki_root, f"run:{run_slug}", f"task:{task_slug}", "supports")
    elif verdict == "no":
        add_edge_internal(wiki_root, f"run:{run_slug}", f"task:{task_slug}", "invalidates")

    rebuild_index(wiki_root)
    rebuild_query_pack(wiki_root)
    append_log(wiki_root, f"Run added: {run_slug}")

    print(f"Run ingested: {filepath}")
    return filepath


def add_feedback(
    wiki_root: str,
    target_type: str,
    target_id: str,
    from_source: str,
    issue_type: str,
    description: str,
    action: str,
    field: str = None,
    from_value: str = None,
    to_value: str = None,
):
    """Add feedback to the wiki."""
    fb_slug = "fb-" + now_utc_compact()
    filepath = os.path.join(wiki_root, "feedback", f"{fb_slug}.md")

    proposed_change = {}
    if field is not None:
        proposed_change["field"] = field
    if from_value is not None:
        proposed_change["from"] = from_value
    if to_value is not None:
        proposed_change["to"] = to_value

    fm = {
        "type": "feedback",
        "node_id": f"feedback:{fb_slug}",
        "target_type": target_type,
        "target_id": target_id,
        "from": from_source,
        "issue_type": issue_type,
        "description": description,
        "action": action,
        "proposed_change": proposed_change,
        "status": "open",
        "applied_at": None,
        "verified_by": None,
        "added": now_utc_iso(),
    }

    body = f"""# Feedback: {issue_type}

## Description
{description}

## Proposed Change
## Verification Status
"""

    content = render_yaml_frontmatter(fm) + "\n" + body
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)

    # Auto-add edge
    add_edge_internal(wiki_root, f"feedback:{fb_slug}", target_id, "addresses")

    rebuild_index(wiki_root)
    rebuild_query_pack(wiki_root)
    append_log(wiki_root, f"Feedback added: {fb_slug}")

    print(f"Feedback ingested: {filepath}")
    return filepath


def add_edge_internal(wiki_root: str, from_node: str, to_node: str, edge_type: str, note: str = ""):
    """Internal edge addition (no validation errors, just append)."""
    edges_path = os.path.join(wiki_root, "graph", "edges.jsonl")
    entry = {
        "from": from_node,
        "to": to_node,
        "type": edge_type,
        "note": note,
        "added": now_utc_iso(),
    }
    with open(edges_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


def add_edge_cmd(
    wiki_root: str,
    from_node: str,
    to_node: str,
    edge_type: str,
    note: str = "",
):
    """Add an edge via CLI (with validation)."""
    if edge_type not in VALID_EDGE_TYPES:
        print(f"Error: Invalid edge type '{edge_type}'. Valid types: {', '.join(sorted(VALID_EDGE_TYPES))}",
              file=sys.stderr)
        sys.exit(1)

    # Normalize node IDs
    from_node = normalize_node_id(from_node, "task")
    to_node = normalize_node_id(to_node, "task")

    # Warn if dangling
    warn_if_dangling(wiki_root, from_node, "add-edge")
    warn_if_dangling(wiki_root, to_node, "add-edge")

    add_edge_internal(wiki_root, from_node, to_node, edge_type, note)
    append_log(wiki_root, f"Edge added: {from_node} --{edge_type}--> {to_node}")

    print(f"Edge added: {from_node} --{edge_type}--> {to_node}")


def rebuild_index(wiki_root: str):
    """Regenerate index.md."""
    sections = []

    for entity_dir in ENTITY_DIRS:
        dir_path = os.path.join(wiki_root, entity_dir)
        entity_name = entity_dir.capitalize()
        sections.append(f"## {entity_name}\n")

        if os.path.isdir(dir_path):
            files = sorted([f for f in os.listdir(dir_path) if f.endswith(".md")])
            if files:
                sections.append("| Node ID | Title | Status |")
                sections.append("|---------|-------|--------|")
                for fname in files:
                    fpath = os.path.join(dir_path, fname)
                    fm = load_yaml_frontmatter(fpath)
                    node_id = fm.get("node_id", entity_dir.rstrip("s") + ":" + fname[:-3])
                    title = fm.get("title", fm.get("description", fname[:-3]))
                    status = fm.get("status", "unknown")
                    sections.append(f"| {node_id} | {title} | {status} |")
                sections.append("")
            else:
                sections.append(f"_No {entity_dir} yet._\n")
        else:
            sections.append(f"_No {entity_dir} directory found._\n")

    # Gap map
    sections.append("## Gap Map\n")
    gap_path = os.path.join(wiki_root, "gap_map.md")
    if os.path.isfile(gap_path):
        with open(gap_path, "r", encoding="utf-8") as f:
            gap_content = f.read()
        # Count gaps
        gap_count = len(re.findall(r"G\d+", gap_content))
        sections.append(f"_gap_map.md with {gap_count} gap references found._\n")
    else:
        sections.append("_No gap_map.md found._\n")

    # Graph stats
    sections.append("## Graph\n")
    edges_path = os.path.join(wiki_root, "graph", "edges.jsonl")
    if os.path.isfile(edges_path):
        with open(edges_path, "r", encoding="utf-8") as f:
            edge_count = sum(1 for line in f if line.strip())
        sections.append(f"_edges.jsonl with {edge_count} edge(s)._")
    else:
        sections.append("_No edges.jsonl found._")

    index_content = "# Eval Wiki Index\n\n_Auto-generated. Do not edit._\n\n" + "\n".join(sections) + "\n"
    with open(os.path.join(wiki_root, "index.md"), "w", encoding="utf-8") as f:
        f.write(index_content)


def rebuild_query_pack(wiki_root: str):
    """Regenerate query_pack.md (max 8000 chars)."""
    sections = []

    # 1. Project direction
    eval_config_path = os.path.join(wiki_root, "EVAL_CONFIG.md")
    if os.path.isfile(eval_config_path):
        with open(eval_config_path, "r", encoding="utf-8") as f:
            config_text = f.read()
        sections.append(config_text[:1500])
    else:
        sections.append("No EVAL_CONFIG.md found")

    # 2. Top 5 gaps (ranked by gap_score formula from design doc §9.2)
    sections.append("")
    gap_path = os.path.join(wiki_root, "gap_map.md")
    if os.path.isfile(gap_path):
        with open(gap_path, "r", encoding="utf-8") as f:
            gap_text = f.read()
        # Parse gap IDs from gap_map.md
        import re as _re
        gap_ids = _re.findall(r'(?:^|\s)(G\d+)', gap_text)
        gap_ids = list(dict.fromkeys(gap_ids))  # dedup preserving order

        # Count linked tasks and failed runs per gap
        tasks_dir = os.path.join(wiki_root, "tasks")
        runs_dir = os.path.join(wiki_root, "runs")
        linked_tasks = {gid: 0 for gid in gap_ids}
        failed_runs = {gid: 0 for gid in gap_ids}

        if os.path.isdir(tasks_dir):
            for fname in os.listdir(tasks_dir):
                if fname.endswith(".md"):
                    fm = load_yaml_frontmatter(os.path.join(tasks_dir, fname))
                    for cg in fm.get("coverage_gaps", []):
                        gid = cg.replace("gap:", "")
                        if gid in linked_tasks:
                            linked_tasks[gid] += 1

        if os.path.isdir(runs_dir):
            for fname in os.listdir(runs_dir):
                if fname.endswith(".md"):
                    fm = load_yaml_frontmatter(os.path.join(runs_dir, fname))
                    if fm.get("verdict") == "no":
                        task_id = fm.get("task_id", "")
                        # Find which gaps that task covers
                        task_slug = task_id.replace("task:", "")
                        task_path = os.path.join(tasks_dir, f"{task_slug}.md")
                        if os.path.isfile(task_path):
                            tfm = load_yaml_frontmatter(task_path)
                            for cg in tfm.get("coverage_gaps", []):
                                gid = cg.replace("gap:", "")
                                if gid in failed_runs:
                                    failed_runs[gid] += 1

        # Compute gap_score: (unresolved ? 2 : 0) + (linked_tasks == 0 ? 3 : 0) + (failed_runs > 0 ? 1 : 0)
        scored_gaps = []
        for gid in gap_ids:
            lt = linked_tasks.get(gid, 0)
            fr = failed_runs.get(gid, 0)
            unresolved = lt == 0  # no linked tasks means unresolved
            score = (2 if unresolved else 0) + (3 if lt == 0 else 0) + (1 if fr > 0 else 0)
            scored_gaps.append((gid, score, lt, fr))

        scored_gaps.sort(key=lambda x: -x[1])
        top_gaps = scored_gaps[:5]

        gap_lines = []
        for gid, score, lt, fr in top_gaps:
            gap_lines.append(f"- gap:{gid} (score={score}, tasks={lt}, failed_runs={fr})")
        sections.append("\n".join(gap_lines)[:1200])
    else:
        sections.append("_No gap_map.md found._")

    # 3. Task clusters
    sections.append("")
    task_clusters = {}
    tasks_dir = os.path.join(wiki_root, "tasks")
    if os.path.isdir(tasks_dir):
        for fname in sorted(os.listdir(tasks_dir)):
            if fname.endswith(".md"):
                fpath = os.path.join(tasks_dir, fname)
                fm = load_yaml_frontmatter(fpath)
                st = fm.get("scenario_type", "unknown")
                if st not in task_clusters:
                    task_clusters[st] = []
                task_clusters[st].append(fm.get("title", fname[:-3]))

        cluster_lines = []
        for st, titles in sorted(task_clusters.items()):
            cluster_lines.append(f"**{st}** ({len(titles)} tasks): {', '.join(titles[:5])}")
        sections.append("\n".join(cluster_lines)[:1600])

    # 4. Failed tasks banlist
    sections.append("")
    runs_dir = os.path.join(wiki_root, "runs")
    failed_tasks = set()
    if os.path.isdir(runs_dir):
        for fname in sorted(os.listdir(runs_dir)):
            if fname.endswith(".md"):
                fpath = os.path.join(runs_dir, fname)
                fm = load_yaml_frontmatter(fpath)
                if fm.get("verdict") == "no":
                    task_id = fm.get("task_id", "")
                    failed_tasks.add(task_id)
    if failed_tasks:
        sections.append("Failed tasks: " + ", ".join(sorted(failed_tasks))[:1200])
    else:
        sections.append("No failed tasks.")

    # 5. Active feedback
    sections.append("")
    fb_dir = os.path.join(wiki_root, "feedback")
    active_fb = []
    if os.path.isdir(fb_dir):
        for fname in sorted(os.listdir(fb_dir)):
            if fname.endswith(".md"):
                fpath = os.path.join(fb_dir, fname)
                fm = load_yaml_frontmatter(fpath)
                if fm.get("status") == "open":
                    active_fb.append(f"{fm.get('node_id', fname)}: {fm.get('description', '')[:80]}")
    if active_fb:
        sections.append("\n".join(active_fb)[:1000])
    else:
        sections.append("No active feedback.")

    # 6. Top scenarios
    sections.append("")
    scenarios_dir = os.path.join(wiki_root, "scenarios")
    if os.path.isdir(scenarios_dir):
        scenario_lines = []
        for fname in sorted(os.listdir(scenarios_dir)):
            if fname.endswith(".md"):
                fpath = os.path.join(scenarios_dir, fname)
                fm = load_yaml_frontmatter(fpath)
                name = fm.get("name", fname[:-3])
                desc = fm.get("description", "")[:100]
                scenario_lines.append(f"- {name}: {desc}")
                if len("\n".join(scenario_lines)) > 800:
                    break
        if scenario_lines:
            sections.append("\n".join(scenario_lines)[:800])
        else:
            sections.append("No scenarios yet.")
    else:
        sections.append("No scenarios directory.")

    # 7. Coverage stats
    sections.append("")
    tasks_dir = os.path.join(wiki_root, "tasks")
    runs_dir = os.path.join(wiki_root, "runs")
    total_tasks = 0
    total_verdict_runs = 0
    pass_count = 0
    unique_tasks_with_runs = set()

    if os.path.isdir(tasks_dir):
        total_tasks = len([f for f in os.listdir(tasks_dir) if f.endswith(".md")])

    if os.path.isdir(runs_dir):
        for fname in os.listdir(runs_dir):
            if fname.endswith(".md"):
                fpath = os.path.join(runs_dir, fname)
                fm = load_yaml_frontmatter(fpath)
                verdict = fm.get("verdict", "")
                if verdict in ("yes", "no", "inconclusive"):
                    total_verdict_runs += 1
                if verdict == "yes":
                    pass_count += 1
                task_id = fm.get("task_id", "")
                if task_id:
                    unique_tasks_with_runs.add(task_id)


    pass_rate = f"{(pass_count / total_verdict_runs * 100):.1f}%" if total_verdict_runs > 0 else "N/A"
    coverage = f"{(len(unique_tasks_with_runs) / total_tasks * 100):.1f}%" if total_tasks > 0 else "N/A"

    stats_line = f"Tasks: {total_tasks} | Runs with verdict: {total_verdict_runs} | Pass rate: {pass_rate} | Coverage: {coverage}"
    sections.append(stats_line[:500])

    # Assemble
    full = "\n\n".join(sections)
    full = full[:8000]

    query_pack_path = os.path.join(wiki_root, "query_pack.md")
    with open(query_pack_path, "w", encoding="utf-8") as f:
        f.write(full)


def query_wiki(wiki_root: str, topic: str):
    """Search across all .md files in the wiki."""
    results = []
    topic_lower = topic.lower()

    # Search in root .md files
    for fname in ["gap_map.md"]:
        fpath = os.path.join(wiki_root, fname)
        if os.path.isfile(fpath):
            with open(fpath, "r", encoding="utf-8") as f:
                for idx, line in enumerate(f, 1):
                    if topic_lower in line.lower():
                        results.append((fname, idx, line.rstrip()))

    # Search in entity directories
    for entity_dir in ENTITY_DIRS:
        dir_path = os.path.join(wiki_root, entity_dir)
        if os.path.isdir(dir_path):
            for fname in sorted(os.listdir(dir_path)):
                if fname.endswith(".md"):
                    fpath = os.path.join(dir_path, fname)
                    rel_path = os.path.join(entity_dir, fname)
                    with open(fpath, "r", encoding="utf-8") as f:
                        for idx, line in enumerate(f, 1):
                            if topic_lower in line.lower():
                                results.append((rel_path, idx, line.rstrip()))

    results = results[:50]

    if not results:
        print(f"No matches found for '{topic}'")
        return

    for path, lineno, line in results:
        print(f"{path}:{lineno}: {line}")


def log_wiki(wiki_root: str, message: str = None):
    """View or append to log.md."""
    log_path = os.path.join(wiki_root, "log.md")

    if message:
        if not os.path.isfile(log_path):
            print("Error: log.md not found. Is the wiki initialized?", file=sys.stderr)
            sys.exit(1)
        append_log(wiki_root, message)
        print(f"Log entry added.")
    else:
        if not os.path.isfile(log_path):
            print("Error: log.md not found. Is the wiki initialized?", file=sys.stderr)
            sys.exit(1)
        with open(log_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        # Print last 20 non-empty lines
        content_lines = [l.rstrip() for l in lines if l.strip()]
        for line in content_lines[-20:]:
            print(line)


def stats_wiki(wiki_root: str):
    """Print wiki statistics."""
    counts = {}
    for entity_dir in ENTITY_DIRS:
        dir_path = os.path.join(wiki_root, entity_dir)
        if os.path.isdir(dir_path):
            counts[entity_dir] = len([f for f in os.listdir(dir_path) if f.endswith(".md")])
        else:
            counts[entity_dir] = 0

    # Edge count
    edges_path = os.path.join(wiki_root, "graph", "edges.jsonl")
    edge_count = 0
    if os.path.isfile(edges_path):
        with open(edges_path, "r", encoding="utf-8") as f:
            edge_count = sum(1 for line in f if line.strip())

    # Pass rate
    runs_dir = os.path.join(wiki_root, "runs")
    total_verdict_runs = 0
    pass_count = 0
    unique_tasks_with_runs = set()
    if os.path.isdir(runs_dir):
        for fname in os.listdir(runs_dir):
            if fname.endswith(".md"):
                fpath = os.path.join(runs_dir, fname)
                fm = load_yaml_frontmatter(fpath)
                verdict = fm.get("verdict", "")
                if verdict in ("yes", "no", "inconclusive"):
                    total_verdict_runs += 1
                if verdict == "yes":
                    pass_count += 1
                task_id = fm.get("task_id", "")
                if task_id:
                    unique_tasks_with_runs.add(task_id)

    pass_rate = f"{(pass_count / total_verdict_runs * 100):.1f}%" if total_verdict_runs > 0 else "N/A"

    # Coverage
    total_tasks = counts["tasks"]
    coverage = f"{(len(unique_tasks_with_runs) / total_tasks * 100):.1f}%" if total_tasks > 0 else "N/A"

    print(f"Tasks: {counts['tasks']}")
    print(f"Environments: {counts['environments']}")
    print(f"Rubrics: {counts['rubrics']}")
    print(f"Runs: {counts['runs']}")
    print(f"Feedback: {counts['feedback']}")
    print(f"Edges: {edge_count}")
    print(f"Pass rate: {pass_rate}")
    print(f"Coverage: {coverage}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        prog="eval-wiki",
        description="Persistent knowledge base for Agent verification pipeline",
    )
    subparsers = parser.add_subparsers(dest="command", help="Subcommands")

    # init
    p_init = subparsers.add_parser("init", help="Initialize eval-wiki directory")
    p_init.add_argument("wiki_root", help="Path to wiki root directory")

    # add-task
    p_task = subparsers.add_parser("add-task", help="Add a task")
    p_task.add_argument("wiki_root", help="Path to wiki root")
    p_task.add_argument("--title", required=True, help="Task title")
    p_task.add_argument("--difficulty", default="medium", help="Difficulty level")
    p_task.add_argument("--cost", type=float, default=0.5, help="Cost budget")
    p_task.add_argument("--scenario-type", default="single-turn", help="Scenario type")
    p_task.add_argument("--max-turns", type=int, help="Maximum turns")
    p_task.add_argument("--allowed-tools", help="Allowed tools (CSV)")
    p_task.add_argument("--disallowed", help="Disallowed tools (CSV)")
    p_task.add_argument("--expected-behavior", help="Expected behaviors (CSV)")
    p_task.add_argument("--coverage-gap", help="Coverage gaps (CSV)")
    p_task.add_argument("--based-on", help="Based-on task IDs (CSV)")
    p_task.add_argument("--status", default="draft", help="Task status")
    p_task.add_argument("--scenario-id", default=None, help="Parent scenario ID")
    p_task.add_argument("--goal", default=None, help="Test goal / what Agent capability this task verifies")
    p_task.add_argument("--input-spec", default=None, help="Initial input/prompt the Agent receives")
    p_task.add_argument("--preconditions", default=None, help="Environment state and mock service requirements")
    p_task.add_argument("--constraints", default=None, help="Boundary conditions / prohibited behaviors")
    p_task.add_argument("--update", action="store_true", help="Update existing task")
    p_scenario = subparsers.add_parser("add-scenario", help="Add a scenario")
    p_scenario.add_argument("wiki_root", help="Path to wiki root")
    p_scenario.add_argument("--name", required=True, help="Scenario name")
    p_scenario.add_argument("--description", required=True, help="Scenario description")
    p_scenario.add_argument("--scenario-type", default="multi-turn", help="Scenario type")
    p_scenario.add_argument("--difficulty", default="medium", help="Difficulty level")
    p_scenario.add_argument("--capabilities", default=None, help="Capabilities (CSV)")
    p_scenario.add_argument("--env-hints", default="", help="Environment hints")
    p_scenario.add_argument("--update", action="store_true", help="Update existing scenario")

    # add-env
    p_env = subparsers.add_parser("add-env", help="Add an environment")
    p_env.add_argument("wiki_root", help="Path to wiki root")
    p_env.add_argument("--task-id", required=True, help="Task ID")
    p_env.add_argument("--image", default="python:3.11", help="Docker image")
    p_env.add_argument("--dockerfile", help="Dockerfile path")
    p_env.add_argument("--volumes", help="Volumes (CSV)")
    p_env.add_argument("--env-vars", help="Environment variables (key=val,key=val)")
    p_env.add_argument("--network", default="bridge", help="Network type")
    p_env.add_argument("--memory", help="Memory limit")
    p_env.add_argument("--cpus", type=float, help="CPU limit")
    p_env.add_argument("--mock-service", help="Mock service (name:port:script)")
    p_env.add_argument("--agent-endpoint", help="Agent endpoint URL")
    p_env.add_argument("--health-check", help="Health check command")
    p_env.add_argument("--health-timeout", type=int, help="Health check timeout")
    p_env.add_argument("--status", default="draft", help="Environment status")
    p_env.add_argument("--scenario-id", default=None, help="Parent scenario ID")
    p_env.add_argument("--update", action="store_true", help="Update existing environment")

    # add-rubric
    p_rubric = subparsers.add_parser("add-rubric", help="Add a rubric")
    p_rubric.add_argument("wiki_root", help="Path to wiki root")
    p_rubric.add_argument("--task-id", required=True, help="Task ID")
    p_rubric.add_argument("--criteria-json", required=True, help="Path to criteria JSON file")
    p_rubric.add_argument("--status", default="draft", help="Rubric status")
    p_rubric.add_argument("--assurance", default="draft", help="Assurance level")
    p_rubric.add_argument("--scenario-id", default=None, help="Parent scenario ID")
    p_rubric.add_argument("--update", action="store_true", help="Update existing rubric")

    # add-run
    p_run = subparsers.add_parser("add-run", help="Add a run")
    p_run.add_argument("wiki_root", help="Path to wiki root")
    p_run.add_argument("--task-id", required=True, help="Task ID")
    p_run.add_argument("--env-id", required=True, help="Environment ID")
    p_run.add_argument("--rubric-id", required=True, help="Rubric ID")
    p_run.add_argument("--model", required=True, help="Model name")
    p_run.add_argument("--endpoint", help="Agent endpoint URL")
    p_run.add_argument("--temperature", type=float, default=0.0, help="Temperature")
    p_run.add_argument("--max-tokens", type=int, default=4096, help="Max tokens")
    p_run.add_argument("--verdict", default="inconclusive", help="Verdict")
    p_run.add_argument("--confidence", default="medium", help="Confidence level")
    p_run.add_argument("--scores-json", help="Path to scores JSON file")
    p_run.add_argument("--raw-output-path", help="Raw output path")
    p_run.add_argument("--provenance", help="Provenance (CSV)")
    p_run.add_argument("--status", default="running", help="Run status")

    # add-feedback
    p_fb = subparsers.add_parser("add-feedback", help="Add feedback")
    p_fb.add_argument("wiki_root", help="Path to wiki root")
    p_fb.add_argument("--target-type", required=True, help="Target type")
    p_fb.add_argument("--target-id", required=True, help="Target ID")
    p_fb.add_argument("--from", dest="from_source", required=True, help="Source (user|auto-audit)")
    p_fb.add_argument("--issue-type", required=True, help="Issue type")
    p_fb.add_argument("--description", required=True, help="Description")
    p_fb.add_argument("--action", required=True, help="Action")
    p_fb.add_argument("--field", help="Proposed change field")
    p_fb.add_argument("--from-value", help="Proposed change from value")
    p_fb.add_argument("--to-value", help="Proposed change to value")

    # add-edge
    p_edge = subparsers.add_parser("add-edge", help="Add an edge")
    p_edge.add_argument("wiki_root", help="Path to wiki root")
    p_edge.add_argument("--from", dest="from_node", required=True, help="From node ID")
    p_edge.add_argument("--to", dest="to_node", required=True, help="To node ID")
    p_edge.add_argument("--type", dest="edge_type", required=True, help="Edge type")
    p_edge.add_argument("--note", default="", help="Edge note")

    # rebuild-index
    p_ri = subparsers.add_parser("rebuild-index", help="Rebuild index.md")
    p_ri.add_argument("wiki_root", help="Path to wiki root")

    # rebuild-query-pack
    p_rqp = subparsers.add_parser("rebuild-query-pack", help="Rebuild query_pack.md")
    p_rqp.add_argument("wiki_root", help="Path to wiki root")

    # query
    p_query = subparsers.add_parser("query", help="Search wiki")
    p_query.add_argument("wiki_root", help="Path to wiki root")
    p_query.add_argument("topic", help="Search topic")

    # log
    p_log = subparsers.add_parser("log", help="View or append to log")
    p_log.add_argument("wiki_root", help="Path to wiki root")
    p_log.add_argument("message", nargs="?", default=None, help="Log message to append")

    # stats
    p_stats = subparsers.add_parser("stats", help="Print wiki statistics")
    p_stats.add_argument("wiki_root", help="Path to wiki root")

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(1)

    try:
        if args.command == "init":
            init_wiki(args.wiki_root)

        elif args.command == "add-scenario":
            add_scenario(
                args.wiki_root,
                args.name,
                args.description,
                args.scenario_type,
                args.difficulty,
                args.capabilities,
                args.env_hints,
                args.update,
            )

        elif args.command == "add-task":
            add_task(
                args.wiki_root,
                title=args.title,
                difficulty=args.difficulty,
                cost=args.cost,
                scenario_type=args.scenario_type,
                max_turns=args.max_turns,
                allowed_tools=args.allowed_tools,
                disallowed=args.disallowed,
                expected_behavior=args.expected_behavior,
                coverage_gap=args.coverage_gap,
                based_on=args.based_on,
                status=args.status,
                scenario_id=args.scenario_id,
                update=args.update,
                goal=args.goal,
                input_spec=args.input_spec,
                preconditions=args.preconditions,
                constraints=args.constraints,
            )

        elif args.command == "add-env":
            add_env(
                args.wiki_root,
                task_id=args.task_id,
                image=args.image,
                dockerfile=args.dockerfile,
                volumes=args.volumes,
                env_vars=args.env_vars,
                network=args.network,
                memory=args.memory,
                cpus=args.cpus,
                mock_service=args.mock_service,
                agent_endpoint=args.agent_endpoint,
                health_check=args.health_check,
                health_timeout=args.health_timeout,
                status=args.status,
                scenario_id=args.scenario_id,
                update=args.update,
            )

        elif args.command == "add-rubric":
            add_rubric(
                args.wiki_root,
                task_id=args.task_id,
                criteria_json=args.criteria_json,
                status=args.status,
                assurance=args.assurance,
                scenario_id=args.scenario_id,
                update=args.update,
            )

        elif args.command == "add-run":
            add_run(
                args.wiki_root,
                task_id=args.task_id,
                env_id=args.env_id,
                rubric_id=args.rubric_id,
                model=args.model,
                endpoint=args.endpoint,
                temperature=args.temperature,
                max_tokens=args.max_tokens,
                verdict=args.verdict,
                confidence=args.confidence,
                scores_json=args.scores_json,
                raw_output_path=args.raw_output_path,
                provenance=args.provenance,
                status=args.status,
            )

        elif args.command == "add-feedback":
            add_feedback(
                args.wiki_root,
                target_type=args.target_type,
                target_id=args.target_id,
                from_source=args.from_source,
                issue_type=args.issue_type,
                description=args.description,
                action=args.action,
                field=args.field,
                from_value=args.from_value,
                to_value=args.to_value,
            )

        elif args.command == "add-edge":
            add_edge_cmd(
                args.wiki_root,
                from_node=args.from_node,
                to_node=args.to_node,
                edge_type=args.edge_type,
                note=args.note,
            )

        elif args.command == "rebuild-index":
            rebuild_index(args.wiki_root)
            print(f"Index rebuilt at {os.path.join(args.wiki_root, 'index.md')}")

        elif args.command == "rebuild-query-pack":
            rebuild_query_pack(args.wiki_root)
            print(f"Query pack rebuilt at {os.path.join(args.wiki_root, 'query_pack.md')}")

        elif args.command == "query":
            query_wiki(args.wiki_root, args.topic)

        elif args.command == "log":
            log_wiki(args.wiki_root, args.message)

        elif args.command == "stats":
            stats_wiki(args.wiki_root)

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()