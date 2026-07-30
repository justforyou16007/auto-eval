#!/usr/bin/env python3
"""
env-component-manager — Tree-based environment component manager with lazy loading.

Two-layer tree structure:
- Layer 1: infra/ — hardware & OS infrastructure (Docker base images, runtime environments)
- Layer 2: app/ — application components (e-commerce backends, search engines, file systems, mock services)

Lazy loading: tree.json is a lightweight index always loaded; actual component files
(Dockerfiles, source code) are loaded only during assemble/info/fork operations.

Pure Python CLI, no external dependencies beyond Python stdlib.
"""

import argparse
import json
import os
import re
import shutil
import sys
from datetime import datetime, timezone


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TREE_YAML_FILENAME = "tree.json"
COMPONENT_YAML_FILENAME = "component.yaml"
VALID_LAYERS = {"infra", "app"}


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def now_utc_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def slugify(name: str) -> str:
    slug = name.lower()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    slug = re.sub(r"^-+|-+$", "", slug)
    return slug


def split_csv(s: str) -> list:
    if not s or not s.strip():
        return []
    return [item.strip() for item in s.split(",") if item.strip()]


def yaml_quote(s) -> str:
    if s is None:
        return "null"
    s = str(s)
    s = s.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{s}"'


def load_yaml_simple(filepath: str) -> dict:
    """Load simple YAML-like key: value file (no external deps)."""
    if not os.path.isfile(filepath):
        return {}
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()
    return parse_yaml_simple(content)


def parse_yaml_simple(text: str) -> dict:
    """Parse simple YAML (key: value, nested lists, nested objects)."""
    result = {}
    lines = text.split("\n")
    current_key = None
    current_nested = None
    i = 0
    while i < len(lines):
        line = lines[i]
        if not line.strip():
            i += 1
            continue

        if line.startswith("  ") and current_key:
            stripped = line.strip()
            if current_nested == "array":
                if stripped.startswith("- "):
                    val = stripped[2:].strip()
                    val = val.strip('"')
                    result[current_key].append(val)
            elif current_nested == "object":
                if ":" in stripped:
                    k, v = stripped.split(":", 1)
                    k = k.strip()
                    v = v.strip().strip('"')
                    result[current_key][k] = v
            elif current_nested == "array_of_objects":
                if stripped.startswith("- "):
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
                j = i + 1
                while j < len(lines) and (lines[j].strip() == "" or lines[j].startswith("  ")):
                    j += 1
                if j > i + 1:
                    next_line = lines[i + 1].strip() if i + 1 < len(lines) else ""
                    if next_line.startswith("- "):
                        result[key] = []
                        current_nested = "array"
                        current_key = key
                    elif next_line.startswith("  "):
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
                current_key = None
                current_nested = None
                if value.startswith("[") and value.endswith("]"):
                    try:
                        result[key] = json.loads(value)
                    except json.JSONDecodeError:
                        items = []
                        for item in re.findall(r'"([^"]*)"', value):
                            items.append(item)
                        result[key] = items
                elif value.startswith("{") and value.endswith("}"):
                    try:
                        result[key] = json.loads(value)
                    except json.JSONDecodeError:
                        result[key] = value
                elif value in ("true", "false"):
                    result[key] = value == "true"
                elif value == "null":
                    result[key] = None
                else:
                    try:
                        if "." in value:
                            result[key] = float(value)
                        else:
                            result[key] = int(value)
                    except ValueError:
                        result[key] = value.strip('"')
        i += 1
    return result


def render_yaml_value(value) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, list):
        if not value:
            return "[]"
        if not any(isinstance(item, dict) for item in value):
            items = [yaml_quote(str(v)) for v in value]
            return "[" + ", ".join(items) + "]"
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, dict):
        if not value:
            return "{}"
        return json.dumps(value, ensure_ascii=False)
    return yaml_quote(str(value))


def render_yaml_frontmatter(fields: dict) -> str:
    lines = ["---"]
    for key, value in fields.items():
        lines.append(f"{key}: {render_yaml_value(value)}")
    lines.append("---")
    return "\n".join(lines) + "\n"


def render_yaml_kv(key: str, value) -> str:
    return f"{key}: {render_yaml_value(value)}"


def render_yaml_list(items: list) -> str:
    return "\n".join(f"  - {render_yaml_value(item)}" for item in items)


def render_component_yaml(comp: dict) -> str:
    """Render a component.yaml file from a dict."""
    lines = []
    for key in ("name", "layer", "tags", "description"):
        if key in comp:
            lines.append(render_yaml_kv(key, comp[key]))

    # depends_on
    if "depends_on" in comp and comp["depends_on"]:
        lines.append("depends_on:")
        for dep in comp["depends_on"]:
            lines.append(f"  - {yaml_quote(dep)}")

    for key in ("entrypoint",):
        if key in comp:
            lines.append(render_yaml_kv(key, comp[key]))

    # ports
    if "ports" in comp and comp["ports"]:
        lines.append("ports:")
        for p in comp["ports"]:
            lines.append(f"  - {yaml_quote(p)}")

    # env_vars
    if "env_vars" in comp and comp["env_vars"]:
        lines.append("env_vars:")
        for k, v in comp["env_vars"].items():
            lines.append(f"  {k}: {yaml_quote(v)}")

    # volumes
    if "volumes" in comp and comp["volumes"]:
        lines.append("volumes:")
        for v in comp["volumes"]:
            lines.append(f"  - {yaml_quote(v)}")

    # health_check
    if "health_check" in comp and comp["health_check"]:
        lines.append("health_check:")
        for k, v in comp["health_check"].items():
            lines.append(f"  {k}: {render_yaml_value(v)}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Tree operations
# ---------------------------------------------------------------------------

def _tree_path(components_dir: str) -> str:
    return os.path.join(components_dir, TREE_YAML_FILENAME)


def _load_tree(components_dir: str) -> dict:
    """Load tree.json. Returns dict with version and components list."""
    path = _tree_path(components_dir)
    if not os.path.isfile(path):
        return {"version": 1, "components": []}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, IOError):
        return {"version": 1, "components": []}
    if not isinstance(data, dict):
        return {"version": 1, "components": []}
    if not isinstance(data.get("components"), list):
        data["components"] = []
    return data


def _save_tree(components_dir: str, tree: dict):
    """Save tree.json (JSON format for reliable round-trip)."""
    path = _tree_path(components_dir)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(tree, f, indent=2, ensure_ascii=False)
        f.write("\n")


def _component_path(components_dir: str, rel_path: str) -> str:
    return os.path.join(components_dir, rel_path)


def _component_yaml_path(components_dir: str, rel_path: str) -> str:
    return os.path.join(components_dir, rel_path, COMPONENT_YAML_FILENAME)


def _find_component_in_tree(tree: dict, name: str) -> dict:
    """Find a component by name in the tree."""
    for comp in tree.get("components", []):
        if comp["name"] == name:
            return comp
    return None


def _find_component_by_path(tree: dict, rel_path: str) -> dict:
    """Find a component by path in the tree."""
    for comp in tree.get("components", []):
        if comp["path"] == rel_path:
            return comp
    return None


# ---------------------------------------------------------------------------
# CLI commands
# ---------------------------------------------------------------------------

def cmd_init(components_dir: str):
    """Initialize components/ directory structure."""
    components_dir = os.path.abspath(components_dir)

    tree_path = _tree_path(components_dir)
    if os.path.isfile(tree_path):
        print(f"Component manager already initialized at {components_dir}")
        return

    # Create directories
    os.makedirs(os.path.join(components_dir, "infra"), exist_ok=True)
    os.makedirs(os.path.join(components_dir, "app"), exist_ok=True)

    # Create empty tree.json
    _save_tree(components_dir, {"version": 1, "components": []})

    print(f"Component manager initialized at {components_dir}")
    print(f"  infra/ directory: {os.path.join(components_dir, 'infra')}")
    print(f"  app/ directory: {os.path.join(components_dir, 'app')}")
    print(f"  tree.json: {tree_path}")


def cmd_register(components_dir: str, name: str, layer: str, path: str,
                 tags: str, description: str):
    """Register an existing component into tree.json."""
    components_dir = os.path.abspath(components_dir)
    tree = _load_tree(components_dir)

    # Validate layer
    if layer not in VALID_LAYERS:
        print(f"Error: Invalid layer '{layer}'. Must be one of: {', '.join(sorted(VALID_LAYERS))}",
              file=sys.stderr)
        sys.exit(1)

    # Check the component.yaml exists
    comp_yaml_path = _component_yaml_path(components_dir, path)
    if not os.path.isfile(comp_yaml_path):
        print(f"Error: component.yaml not found at {comp_yaml_path}",
              file=sys.stderr)
        sys.exit(1)

    # Check for duplicate name
    existing = _find_component_in_tree(tree, name)
    if existing:
        print(f"Error: Component '{name}' already exists in tree at {existing['path']}",
              file=sys.stderr)
        sys.exit(1)

    # Parse tags
    tag_list = split_csv(tags)

    # Add to tree
    tree["components"].append({
        "name": name,
        "layer": layer,
        "path": path,
        "tags": tag_list,
        "description": description,
    })
    _save_tree(components_dir, tree)

    print(f"Component '{name}' registered in tree.json")
    print(f"  Layer: {layer}")
    print(f"  Path: {path}")
    print(f"  Tags: {tag_list}")
    print(f"  Description: {description}")


def cmd_list(components_dir: str, layer: str = None, tag: str = None):
    """List components from tree.json (lazy index, fast)."""
    components_dir = os.path.abspath(components_dir)
    tree = _load_tree(components_dir)
    components = tree.get("components", [])

    if not components:
        print("No components registered.")
        return

    # Filter by layer
    if layer:
        if layer not in VALID_LAYERS:
            print(f"Error: Invalid layer '{layer}'", file=sys.stderr)
            sys.exit(1)
        components = [c for c in components if c["layer"] == layer]

    # Filter by tag
    if tag:
        components = [c for c in components if tag in c.get("tags", [])]

    if not components:
        print("No matching components found.")
        return

    # Print header
    print(f"{'Name':<30} {'Layer':<8} {'Tags':<30} Description")
    print("-" * 100)
    for comp in sorted(components, key=lambda c: (c["layer"], c["name"])):
        tags_str = ", ".join(comp.get("tags", []))
        desc = comp.get("description", "")
        print(f"{comp['name']:<30} {comp['layer']:<8} {tags_str:<30} {desc[:50]}")


def cmd_search(components_dir: str, query: str, layer: str = None):
    """Simple text search in tree.json descriptions and tags."""
    components_dir = os.path.abspath(components_dir)
    tree = _load_tree(components_dir)
    components = tree.get("components", [])

    if not components:
        print("No components registered.")
        return

    query_lower = query.lower()
    results = []

    for comp in components:
        if layer and comp["layer"] != layer:
            continue

        # Search in description
        desc = comp.get("description", "").lower()
        if query_lower in desc:
            results.append(comp)
            continue

        # Search in tags
        tags = [t.lower() for t in comp.get("tags", [])]
        if any(query_lower in t for t in tags):
            results.append(comp)
            continue

        # Search in name
        name = comp["name"].lower()
        if query_lower in name:
            results.append(comp)
            continue

    if not results:
        print(f"No components found matching '{query}'.")
        return

    print(f"Found {len(results)} component(s) matching '{query}':")
    print()
    for comp in sorted(results, key=lambda c: (c["layer"], c["name"])):
        print(f"  {comp['name']:<30} ({comp['layer']}, {comp['path']})")
        print(f"    Tags: {', '.join(comp.get('tags', []))}")
        print(f"    Description: {comp.get('description', '')}")
        print()


def cmd_assemble(components_dir: str, infra_ids: str, app_ids: str,
                 output: str):
    """Assemble components into a docker-compose.yml + manifest."""
    components_dir = os.path.abspath(components_dir)
    tree = _load_tree(components_dir)

    infra_names = [n.strip() for n in infra_ids.split(",") if n.strip()]
    app_names = [n.strip() for n in app_ids.split(",") if n.strip()]

    assembled_infra = []
    assembled_app = []
    all_assembled = []

    # Resolve infra components
    for name in infra_names:
        comp = _find_component_in_tree(tree, name)
        if not comp:
            print(f"Error: Infra component '{name}' not found in tree", file=sys.stderr)
            sys.exit(1)
        if comp["layer"] != "infra":
            print(f"Error: '{name}' is not an infra component", file=sys.stderr)
            sys.exit(1)
        # Load actual component.yaml
        comp_yaml = load_yaml_simple(_component_yaml_path(components_dir, comp["path"]))
        assembled_infra.append({
            "tree_entry": comp,
            "component_yaml": comp_yaml,
        })
        all_assembled.append(comp["name"])

    # Resolve app components
    for name in app_names:
        comp = _find_component_in_tree(tree, name)
        if not comp:
            print(f"Error: App component '{name}' not found in tree", file=sys.stderr)
            sys.exit(1)
        if comp["layer"] != "app":
            print(f"Error: '{name}' is not an app component", file=sys.stderr)
            sys.exit(1)
        comp_yaml = load_yaml_simple(_component_yaml_path(components_dir, comp["path"]))
        assembled_app.append({
            "tree_entry": comp,
            "component_yaml": comp_yaml,
        })
        all_assembled.append(comp["name"])

    # Generate docker-compose.yml
    compose = {"version": "3.8", "services": {}}

    for item in assembled_infra:
        comp = item["component_yaml"]
        name = comp.get("name", item["tree_entry"]["name"])
        service = _build_service(comp, is_infra=True)
        compose["services"][name] = service

    for item in assembled_app:
        comp = item["component_yaml"]
        name = comp.get("name", item["tree_entry"]["name"])
        service = _build_service(comp, is_infra=False)
        compose["services"][name] = service

    # Write docker-compose.yml
    if output:
        output_path = output
    else:
        output_path = "docker-compose.yml"
    output_path = os.path.abspath(output_path)

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(_render_docker_compose(compose))

    # Write manifest
    manifest_dir = os.path.dirname(output_path)
    manifest_path = os.path.join(manifest_dir, "component-manifest.json")
    manifest = {
        "assembled_at": now_utc_iso(),
        "components": all_assembled,
        "infra": [c["tree_entry"]["name"] for c in assembled_infra],
        "app": [c["tree_entry"]["name"] for c in assembled_app],
        "docker_compose": output_path,
    }
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    print(f"Docker Compose written to {output_path}")
    print(f"Manifest written to {manifest_path}")
    print(f"Assembled components: {', '.join(all_assembled)}")


def _build_service(comp: dict, is_infra: bool) -> dict:
    """Build a docker-compose service definition from component.yaml."""
    service = {}

    # Image (from Dockerfile or base_image)
    base_image = comp.get("base_image", "")
    if base_image:
        service["image"] = base_image
    else:
        # Build from Dockerfile
        service["build"] = {"context": ".", "dockerfile": "Dockerfile"}

    # Ports
    ports = comp.get("ports", [])
    if ports:
        service["ports"] = list(ports)

    # Environment variables
    env_vars = comp.get("env_vars", {})
    if env_vars:
        env_list = []
        for k, v in env_vars.items():
            env_list.append(f"{k}={v}")
        service["environment"] = env_list

    # Volumes
    volumes = comp.get("volumes", [])
    if volumes:
        service["volumes"] = list(volumes)

    # Health check
    hc = comp.get("health_check", {})
    if hc:
        healthcheck = {
            "test": ["CMD", "curl", "-f", hc.get("command", "http://localhost:8000/health")],
            "interval": f"{hc.get('interval', 10)}s",
            "timeout": f"{hc.get('timeout', 5)}s",
            "retries": hc.get("retries", 3),
        }
        service["healthcheck"] = healthcheck

    # Entrypoint
    entrypoint = comp.get("entrypoint", "")
    if entrypoint:
        service["entrypoint"] = entrypoint

    # Networks
    network = comp.get("network", "")
    if network:
        service["networks"] = [network]
    elif not is_infra:
        service["networks"] = ["app-network"]

    return service


def _render_docker_compose(compose: dict) -> str:
    """Render a docker-compose dict to YAML string."""
    lines = [f"version: '{compose.get('version', '3.8')}'", "", "services:"]

    for svc_name, svc_config in compose.get("services", {}).items():
        lines.append(f"  {svc_name}:")
        for key, value in svc_config.items():
            if isinstance(value, list):
                lines.append(f"    {key}:")
                for item in value:
                    lines.append(f"      - {yaml_quote(item)}")
            elif isinstance(value, dict):
                lines.append(f"    {key}:")
                for k, v in value.items():
                    if isinstance(v, list):
                        lines.append(f"      {k}:")
                        for item in v:
                            lines.append(f"        - {yaml_quote(item)}")
                    else:
                        lines.append(f"      {k}: {yaml_quote(v)}")
            elif isinstance(value, bool):
                lines.append(f"    {key}: {'true' if value else 'false'}")
            else:
                lines.append(f"    {key}: {yaml_quote(value)}")
        lines.append("")

    # Networks
    if any("networks" in svc for svc in compose.get("services", {}).values()):
        lines.append("networks:")
        lines.append("  app-network:")
        lines.append("    driver: bridge")

    return "\n".join(lines)


def cmd_fork(components_dir: str, source: str, new_name: str, new_path: str):
    """Copy an existing component to a new path and register it."""
    components_dir = os.path.abspath(components_dir)
    tree = _load_tree(components_dir)

    # Find source component
    source_comp = _find_component_by_path(tree, source)
    if not source_comp:
        # Try by name
        source_comp = _find_component_in_tree(tree, source)
    if not source_comp:
        print(f"Error: Source component '{source}' not found in tree", file=sys.stderr)
        sys.exit(1)

    source_rel_path = source_comp["path"]
    source_abs_path = _component_path(components_dir, source_rel_path)
    new_abs_path = _component_path(components_dir, new_path)

    if not os.path.isdir(source_abs_path):
        print(f"Error: Source component directory not found: {source_abs_path}", file=sys.stderr)
        sys.exit(1)

    if os.path.exists(new_abs_path):
        print(f"Error: Target path already exists: {new_abs_path}", file=sys.stderr)
        sys.exit(1)

    # Copy the component directory
    shutil.copytree(source_abs_path, new_abs_path)

    # Update component.yaml with new name
    comp_yaml_path = os.path.join(new_abs_path, COMPONENT_YAML_FILENAME)
    if os.path.isfile(comp_yaml_path):
        comp_data = load_yaml_simple(comp_yaml_path)
        comp_data["name"] = new_name
        with open(comp_yaml_path, "w", encoding="utf-8") as f:
            f.write(render_component_yaml(comp_data) + "\n")

    # Register in tree
    new_entry = {
        "name": new_name,
        "layer": source_comp["layer"],
        "path": new_path,
        "tags": source_comp.get("tags", []),
        "description": f"Forked from {source_comp['name']}",
    }
    tree["components"].append(new_entry)
    _save_tree(components_dir, tree)

    print(f"Component '{source_comp['name']}' forked to '{new_name}'")
    print(f"  Source: {source_abs_path}")
    print(f"  New path: {new_abs_path}")
    print(f"  Registered in tree.json as '{new_name}'")
    print(f"  Modify the forked component files at {new_abs_path}")


def cmd_info(components_dir: str, path: str):
    """Load and display full component.yaml details."""
    components_dir = os.path.abspath(components_dir)

    # Try to find by path or name
    tree = _load_tree(components_dir)
    comp = _find_component_by_path(tree, path)
    if not comp:
        comp = _find_component_in_tree(tree, path)
    if not comp:
        # Try as literal path
        comp_yaml_path = _component_yaml_path(components_dir, path)
        if os.path.isfile(comp_yaml_path):
            # Extract from tree by path
            if path.startswith("infra/") or path.startswith("app/"):
                for c in tree.get("components", []):
                    if c["path"] == path:
                        comp = c
                        break
        if not comp:
            print(f"Error: Component not found at '{path}'", file=sys.stderr)
            sys.exit(1)

    rel_path = comp["path"]
    comp_yaml_path = _component_yaml_path(components_dir, rel_path)
    comp_data = load_yaml_simple(comp_yaml_path)

    print(f"Name: {comp_data.get('name', comp['name'])}")
    print(f"Layer: {comp_data.get('layer', comp['layer'])}")
    print(f"Path: {rel_path}")
    print(f"Tags: {', '.join(comp_data.get('tags', comp.get('tags', [])))}")
    print(f"Description: {comp_data.get('description', comp.get('description', ''))}")

    depends_on = comp_data.get("depends_on", [])
    if depends_on:
        print(f"Depends on: {', '.join(depends_on)}")

    entrypoint = comp_data.get("entrypoint", "")
    if entrypoint:
        print(f"Entrypoint: {entrypoint}")

    ports = comp_data.get("ports", [])
    if ports:
        print(f"Ports: {', '.join(str(p) for p in ports)}")

    env_vars = comp_data.get("env_vars", {})
    if env_vars:
        print("Environment variables:")
        for k, v in env_vars.items():
            print(f"  {k}={v}")

    volumes = comp_data.get("volumes", [])
    if volumes:
        print(f"Volumes: {', '.join(volumes)}")

    base_image = comp_data.get("base_image", "")
    if base_image:
        print(f"Base image: {base_image}")

    hc = comp_data.get("health_check", {})
    if hc:
        print(f"Health check: {hc}")

    # Check for Dockerfile
    dockerfile_path = os.path.join(components_dir, rel_path, "Dockerfile")
    if os.path.isfile(dockerfile_path):
        print(f"Dockerfile: {dockerfile_path}")

    # Check for source files
    src_dir = os.path.join(components_dir, rel_path, "src")
    if os.path.isdir(src_dir):
        src_files = [f for f in os.listdir(src_dir) if not f.startswith(".")]
        if src_files:
            print(f"Source files: {', '.join(src_files)}")


def cmd_tree(components_dir: str):
    """Display the component tree as a visual tree."""
    components_dir = os.path.abspath(components_dir)
    tree = _load_tree(components_dir)
    components = tree.get("components", [])

    print("components/")
    print("├── tree.json")

    # Group by layer
    infra_comps = [c for c in components if c["layer"] == "infra"]
    app_comps = [c for c in components if c["layer"] == "app"]

    print("├── infra/")

    if infra_comps:
        for i, comp in enumerate(sorted(infra_comps, key=lambda c: c["name"])):
            prefix = "│   ├──" if i < len(infra_comps) - 1 else "│   └──"
            dockerfile_path = os.path.join(components_dir, comp["path"], "Dockerfile")
            has_dockerfile = os.path.isfile(dockerfile_path)
            dockerfile_marker = " [Dockerfile]" if has_dockerfile else ""
            print(f"{prefix} {comp['name']}/{dockerfile_marker}")
    else:
        print("│   └── (empty)")

    print("├── app/")

    if app_comps:
        # Group app components by top-level category
        categories = {}
        for comp in app_comps:
            parts = comp["path"].split("/")
            category = parts[1] if len(parts) > 1 else "other"
            if category not in categories:
                categories[category] = []
            categories[category].append(comp)

        cat_keys = sorted(categories.keys())
        for ci, cat in enumerate(cat_keys):
            cat_prefix = "│   ├──" if ci < len(cat_keys) - 1 else "│   └──"
            print(f"{cat_prefix} {cat}/")
            sub_comps = sorted(categories[cat], key=lambda c: c["name"])
            for si, comp in enumerate(sub_comps):
                sub_prefix = "│   │   ├──" if si < len(sub_comps) - 1 else "│   │   └──"
                print(f"{sub_prefix} {comp['name']}/")
    else:
        print("│   └── (empty)")

    print(f"")
    print(f"Total: {len(components)} component(s) registered")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        prog="env-component-manager",
        description="Tree-based environment component manager with lazy loading",
    )
    subparsers = parser.add_subparsers(dest="command", help="Subcommands")

    # init
    p_init = subparsers.add_parser("init", help="Initialize components directory structure")
    p_init.add_argument("components_dir", nargs="?", default="components",
                        help="Path to components directory (default: components)")

    # register
    p_reg = subparsers.add_parser("register", help="Register an existing component in tree.json")
    p_reg.add_argument("components_dir", nargs="?", default="components",
                       help="Path to components directory")
    p_reg.add_argument("--name", required=True, help="Component name")
    p_reg.add_argument("--layer", required=True, choices=["infra", "app"],
                       help="Component layer")
    p_reg.add_argument("--path", required=True, help="Relative path to component directory")
    p_reg.add_argument("--tags", default="", help="Comma-separated tags")
    p_reg.add_argument("--description", default="", help="Component description")

    # list
    p_list = subparsers.add_parser("list", help="List components from tree.json")
    p_list.add_argument("components_dir", nargs="?", default="components",
                        help="Path to components directory")
    p_list.add_argument("--layer", choices=["infra", "app"], help="Filter by layer")
    p_list.add_argument("--tag", help="Filter by tag")

    # search
    p_search = subparsers.add_parser("search", help="Search components in tree.json")
    p_search.add_argument("components_dir", nargs="?", default="components",
                          help="Path to components directory")
    p_search.add_argument("--query", required=True, help="Search text")
    p_search.add_argument("--layer", choices=["infra", "app"], help="Filter by layer")

    # assemble
    p_assemble = subparsers.add_parser("assemble", help="Assemble components into docker-compose")
    p_assemble.add_argument("components_dir", nargs="?", default="components",
                            help="Path to components directory")
    p_assemble.add_argument("--infra", required=True, help="Comma-separated infra component IDs")
    p_assemble.add_argument("--app", required=True, help="Comma-separated app component IDs")
    p_assemble.add_argument("--output", default="docker-compose.yml",
                            help="Output docker-compose path")

    # fork
    p_fork = subparsers.add_parser("fork", help="Fork a component to a new path")
    p_fork.add_argument("components_dir", nargs="?", default="components",
                        help="Path to components directory")
    p_fork.add_argument("--source", required=True, help="Source component path or name")
    p_fork.add_argument("--new-name", required=True, help="New component name")
    p_fork.add_argument("--new-path", required=True, help="New component relative path")

    # info
    p_info = subparsers.add_parser("info", help="Display component details")
    p_info.add_argument("components_dir", nargs="?", default="components",
                        help="Path to components directory")
    p_info.add_argument("--path", required=True, help="Component path or name")

    # tree
    p_tree = subparsers.add_parser("tree", help="Display component tree")
    p_tree.add_argument("components_dir", nargs="?", default="components",
                        help="Path to components directory")

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(1)

    try:
        if args.command == "init":
            cmd_init(args.components_dir)
        elif args.command == "register":
            cmd_register(args.components_dir, args.name, args.layer,
                         args.path, args.tags, args.description)
        elif args.command == "list":
            cmd_list(args.components_dir, args.layer, args.tag)
        elif args.command == "search":
            cmd_search(args.components_dir, args.query, args.layer)
        elif args.command == "assemble":
            cmd_assemble(args.components_dir, args.infra, args.app, args.output)
        elif args.command == "fork":
            cmd_fork(args.components_dir, args.source, args.new_name, args.new_path)
        elif args.command == "info":
            cmd_info(args.components_dir, args.path)
        elif args.command == "tree":
            cmd_tree(args.components_dir)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()