#!/usr/bin/env python3
"""
run-state.py — State machine tool for pipeline orchestration.

Stores state files in `.eval/runs/<run_id>.json`. Each run has phases:
[task-gen, env-gen, rubric-gen, agent-exec, report-gen, feedback-align].

Usage:
    python3 run-state.py init-run <run_id> [--phases "a,b,c"]
    python3 run-state.py set-status <run_id> <phase> <status> [--artifact <path>]
    python3 run-state.py accept <run_id> <phase> <verdict_id> <reviewer> [--force]
    python3 run-state.py get-state <run_id>
    python3 run-state.py list-runs
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone


DEFAULT_PHASES = [
    "task-gen", "env-gen", "rubric-gen", "agent-exec", "report-gen", "feedback-align"
]
VALID_STATUSES = {"pending", "running", "done", "failed", "skipped"}


def get_runs_dir():
    """Get the .eval/runs directory, creating if needed."""
    base = os.path.join(os.getcwd(), ".eval", "runs")
    os.makedirs(base, exist_ok=True)
    return base


def get_run_path(run_id: str) -> str:
    return os.path.join(get_runs_dir(), f"{run_id}.json")


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def cmd_init_run(args):
    run_id = args.run_id
    phases = args.phases.split(",") if args.phases else DEFAULT_PHASES

    # Validate phases
    for p in phases:
        if p not in DEFAULT_PHASES:
            print(f"Error: Unknown phase '{p}'. Valid phases: {', '.join(DEFAULT_PHASES)}", file=sys.stderr)
            sys.exit(1)

    state = {
        "run_id": run_id,
        "created": now_utc_iso(),
        "updated": now_utc_iso(),
        "phases": {p: {"status": "pending", "artifact": None, "accepted": False} for p in phases},
        "accepted_phases": {},
    }

    path = get_run_path(run_id)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)

    print(f"Run {run_id} initialized with phases: {', '.join(phases)}")


def cmd_set_status(args):
    run_id = args.run_id
    phase = args.phase
    status = args.status
    artifact = args.artifact

    if phase not in DEFAULT_PHASES:
        print(f"Error: Unknown phase '{phase}'. Valid phases: {', '.join(DEFAULT_PHASES)}", file=sys.stderr)
        sys.exit(1)

    if status not in VALID_STATUSES:
        print(f"Error: Invalid status '{status}'. Valid: {', '.join(sorted(VALID_STATUSES))}", file=sys.stderr)
        sys.exit(1)

    path = get_run_path(run_id)
    if not os.path.exists(path):
        print(f"Error: Run {run_id} not found. Initialize first.", file=sys.stderr)
        sys.exit(1)

    with open(path, "r", encoding="utf-8") as f:
        state = json.load(f)

    if phase not in state["phases"]:
        print(f"Error: Phase '{phase}' not in run. Available: {', '.join(state['phases'].keys())}", file=sys.stderr)
        sys.exit(1)

    state["phases"][phase]["status"] = status
    if artifact:
        state["phases"][phase]["artifact"] = artifact
    state["updated"] = now_utc_iso()

    with open(path, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)

    print(f"Run {run_id}: phase '{phase}' status set to '{status}'")


def cmd_accept(args):
    run_id = args.run_id
    phase = args.phase
    verdict_id = args.verdict_id
    reviewer = args.reviewer
    force = args.force

    if phase not in DEFAULT_PHASES:
        print(f"Error: Unknown phase '{phase}'", file=sys.stderr)
        sys.exit(1)

    path = get_run_path(run_id)
    if not os.path.exists(path):
        print(f"Error: Run {run_id} not found.", file=sys.stderr)
        sys.exit(1)

    with open(path, "r", encoding="utf-8") as f:
        state = json.load(f)

    # Self-acquit guard: reject if reviewer name contains "claude"
    if "claude" in reviewer.lower() and not force:
        print(
            f"Warning: Reviewer name '{reviewer}' contains 'claude' (self-acquit guard). "
            f"Use --force to override.",
            file=sys.stderr,
        )
        sys.exit(1)

    if phase not in state["phases"]:
        print(f"Error: Phase '{phase}' not in run.", file=sys.stderr)
        sys.exit(1)

    state["phases"][phase]["accepted"] = True
    state["accepted_phases"][phase] = {
        "verdict_id": verdict_id,
        "reviewer": reviewer,
        "accepted_at": now_utc_iso(),
    }
    state["updated"] = now_utc_iso()

    with open(path, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)

    print(f"Run {run_id}: phase '{phase}' accepted by {reviewer}")


def cmd_get_state(args):
    run_id = args.run_id
    path = get_run_path(run_id)

    if not os.path.exists(path):
        print(f"Run {run_id} not found.", file=sys.stderr)
        sys.exit(1)

    with open(path, "r", encoding="utf-8") as f:
        state = json.load(f)

    print(json.dumps(state, indent=2))


def cmd_list_runs(args):
    runs_dir = get_runs_dir()
    files = sorted([f for f in os.listdir(runs_dir) if f.endswith(".json")])

    if not files:
        print("[]")
        return

    runs = []
    for fname in files:
        try:
            with open(os.path.join(runs_dir, fname), "r", encoding="utf-8") as f:
                state = json.load(f)
            runs.append({
                "run_id": state.get("run_id", fname[:-5]),
                "created": state.get("created", ""),
                "updated": state.get("updated", ""),
                "phases": list(state.get("phases", {}).keys()),
            })
        except (json.JSONDecodeError, OSError):
            runs.append({"run_id": fname[:-5], "error": "corrupt"})

    print(json.dumps(runs, indent=2))


def main():
    parser = argparse.ArgumentParser(description="State machine tool for pipeline orchestration")
    subparsers = parser.add_subparsers(dest="command", help="Subcommands")

    # init-run
    p_init = subparsers.add_parser("init-run", help="Initialize a run state file")
    p_init.add_argument("run_id", help="Run identifier")
    p_init.add_argument("--phases", help=f"Comma-separated phase list (default: {','.join(DEFAULT_PHASES)})")

    # set-status
    p_set = subparsers.add_parser("set-status", help="Set phase status")
    p_set.add_argument("run_id", help="Run identifier")
    p_set.add_argument("phase", help="Phase name")
    p_set.add_argument("status", choices=sorted(VALID_STATUSES), help="Status value")
    p_set.add_argument("--artifact", help="Path to artifact file")

    # accept
    p_accept = subparsers.add_parser("accept", help="Accept a phase")
    p_accept.add_argument("run_id", help="Run identifier")
    p_accept.add_argument("phase", help="Phase name")
    p_accept.add_argument("verdict_id", help="Verdict identifier")
    p_accept.add_argument("reviewer", help="Reviewer name (rejected if contains 'claude')")
    p_accept.add_argument("--force", action="store_true", help="Override self-acquit guard")

    # get-state
    p_get = subparsers.add_parser("get-state", help="Print run state as JSON")
    p_get.add_argument("run_id", help="Run identifier")

    # list-runs
    subparsers.add_parser("list-runs", help="List all run state files")

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(1)

    try:
        if args.command == "init-run":
            cmd_init_run(args)
        elif args.command == "set-status":
            cmd_set_status(args)
        elif args.command == "accept":
            cmd_accept(args)
        elif args.command == "get-state":
            cmd_get_state(args)
        elif args.command == "list-runs":
            cmd_list_runs(args)
        else:
            parser.print_help()
            sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()