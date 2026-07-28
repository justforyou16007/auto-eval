#!/usr/bin/env python3
"""
env-gen — Generate Docker environment for a task and provision the container.

Python stdlib only. Invokes eval-wiki.py via importlib.
"""

import argparse
import json
import os
import subprocess
import sys
import time
import importlib.util


def load_eval_wiki(wiki_root):
    """Load eval-wiki.py from the repo root as a module."""
    repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    wiki_path = os.path.join(repo_root, "eval-wiki.py")
    if not os.path.isfile(wiki_path):
        print(f"Error: eval-wiki.py not found at {wiki_path}", file=sys.stderr)
        sys.exit(1)

    spec = importlib.util.spec_from_file_location("eval_wiki", wiki_path)
    ew = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ew)
    return ew


def read_task_file(wiki_root, task_slug):
    """Read task file from eval-wiki to get agent_constraints."""
    task_path = os.path.join(wiki_root, "tasks", f"{task_slug}.md")
    if not os.path.isfile(task_path):
        print(f"Error: task file not found at {task_path}", file=sys.stderr)
        sys.exit(1)

    ew = load_eval_wiki(wiki_root)
    fm = ew.load_yaml_frontmatter(task_path)
    return fm


def generate_docker_compose(task_slug, image, network, memory, cpus, agent_endpoint):
    """Generate docker-compose.yml content."""
    compose = {
        "version": "3.8",
        "services": {
            f"agent-{task_slug}": {
                "image": image,
                "container_name": f"eval-{task_slug}",
                "network_mode": network if network != "bridge" else "bridge",
                "deploy": {
                    "resources": {
                        "limits": {}
                    }
                },
                "environment": [
                    f"AGENT_ENDPOINT={agent_endpoint}",
                    "PYTHONUNBUFFERED=1",
                ],
                "healthcheck": {
                    "test": ["CMD", "curl", "-f", f"{agent_endpoint}/health"],
                    "interval": "30s",
                    "timeout": "10s",
                    "retries": 3,
                    "start_period": "10s",
                }
            }
        }
    }

    if memory:
        compose["services"][f"agent-{task_slug}"]["deploy"]["resources"]["limits"]["memory"] = memory
    if cpus:
        compose["services"][f"agent-{task_slug}"]["deploy"]["resources"]["limits"]["cpus"] = str(cpus)

    return json.dumps(compose, indent=2)


def generate_env_markdown(task_slug, image, network, memory, cpus, agent_endpoint, task_fm):
    """Generate environment markdown content."""
    constraints = task_fm.get("agent_constraints", {})
    lines = [
        f"# Environment for task:{task_slug}",
        "",
        "## Overview",
        f"- **Task:** {task_fm.get('title', task_slug)}",
        f"- **Scenario:** {task_fm.get('scenario_type', 'unknown')}",
        f"- **Max Turns:** {constraints.get('max_turns', 0)}",
        f"- **Allowed Tools:** {', '.join(constraints.get('allowed_tools', []))}",
        "",
        "## Docker Configuration",
        f"- **Image:** {image}",
        f"- **Network:** {network}",
        f"- **Memory:** {memory or 'default'}",
        f"- **CPUs:** {cpus or 'default'}",
        f"- **Agent Endpoint:** {agent_endpoint}",
        "",
        "## Health Check",
        "- Status: pending",
        "- Last checked: N/A",
        "",
    ]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Generate Docker environment for a task")
    parser.add_argument("--wiki-root", required=True, help="Path to eval-wiki root")
    parser.add_argument("--task-id", required=True, help="Task ID (slug or task:slug)")
    parser.add_argument("--image", default="python:3.11", help="Docker image")
    parser.add_argument("--network", default="bridge", help="Docker network")
    parser.add_argument("--memory", default="2g", help="Memory limit")
    parser.add_argument("--cpus", default=2, type=int, help="CPU limit")
    parser.add_argument("--agent-endpoint", default="http://localhost:3000", help="Agent endpoint")
    parser.add_argument("--dry-run", action="store_true", help="Skip actual Docker commands")

    args = parser.parse_args()

    # Normalize task slug
    task_slug = args.task_id
    if task_slug.startswith("task:"):
        task_slug = task_slug[5:]

    # Read task constraints
    task_fm = read_task_file(args.wiki_root, task_slug)

    # Generate docker-compose.yml
    compose_yaml = generate_docker_compose(
        task_slug, args.image, args.network, args.memory, args.cpus, args.agent_endpoint
    )

    # Generate environment markdown
    env_md = generate_env_markdown(
        task_slug, args.image, args.network, args.memory, args.cpus, args.agent_endpoint, task_fm
    )

    # Write config files
    env_dir = os.path.join(args.wiki_root, "environments")
    os.makedirs(env_dir, exist_ok=True)

    compose_path = os.path.join(args.wiki_root, f"docker-compose-{task_slug}.yml")
    with open(compose_path, "w", encoding="utf-8") as f:
        f.write(compose_yaml)
    print(f"Generated: {compose_path}")

    # Write environment to eval-wiki
    ew = load_eval_wiki(args.wiki_root)
    env_filepath = ew.add_env(
        wiki_root=args.wiki_root,
        task_id=task_slug,
        image=args.image,
        network=args.network,
        memory=args.memory,
        cpus=args.cpus,
        agent_endpoint=args.agent_endpoint,
        status="draft",
    )
    print(f"Environment ingested: {env_filepath}")

    if args.dry_run:
        print("\n[Dry-run] Would run Docker commands:")
        print(f"  docker info")
        print(f"  docker run -d --name eval-{task_slug} {args.image}")
        print(f"  docker inspect eval-{task_slug}")
        print("\n[Dry-run] Environment markdown:")
        print(env_md)
        return

    # ---- Real Docker operations ----
    try:
        # Check Docker is running
        result = subprocess.run(["docker", "info"], capture_output=True, text=True, timeout=30)
        if result.returncode != 0:
            print(f"Error: Docker is not available: {result.stderr.strip()}", file=sys.stderr)
            sys.exit(1)
        print("Docker daemon is running.")
    except FileNotFoundError:
        print("Error: docker command not found. Is Docker installed?", file=sys.stderr)
        sys.exit(1)
    except subprocess.TimeoutExpired:
        print("Error: docker info timed out", file=sys.stderr)
        sys.exit(1)

    # Start container
    container_name = f"eval-{task_slug}"
    try:
        result = subprocess.run(
            ["docker", "run", "-d", "--name", container_name, args.image,
             "sleep", "infinity"],
            capture_output=True, text=True, timeout=60,
        )
        if result.returncode != 0:
            print(f"Error starting container: {result.stderr.strip()}", file=sys.stderr)
            sys.exit(1)
        container_id = result.stdout.strip()
        print(f"Container started: {container_id[:12]}")
    except subprocess.TimeoutExpired:
        print("Error: docker run timed out", file=sys.stderr)
        sys.exit(1)

    # Poll health check
    max_retries = 5
    for i in range(max_retries):
        try:
            result = subprocess.run(
                ["docker", "inspect", "--format={{.State.Status}}", container_name],
                capture_output=True, text=True, timeout=15,
            )
            status = result.stdout.strip()
            if status == "running":
                print(f"Container health check passed (attempt {i+1}/{max_retries})")
                break
            print(f"Container status: {status} (attempt {i+1}/{max_retries})")
        except subprocess.TimeoutExpired:
            print(f"Health check timed out (attempt {i+1}/{max_retries})")
        time.sleep(2)
    else:
        print(f"Warning: Container did not reach running state within {max_retries} attempts", file=sys.stderr)

    print(f"Environment provisioned: {container_name}")


if __name__ == "__main__":
    main()