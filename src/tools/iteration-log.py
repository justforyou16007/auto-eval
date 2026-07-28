#!/usr/bin/env python3
"""
iteration-log.py — Tracks convergence of feedback loops.

CLI:
    python3 iteration-log.py record <wiki-root> --issues <N> --phase <phase>
    python3 iteration-log.py trend <wiki-root>

Returns JSON with {"converging": true/false, "trend": [...], "current_issues": N}
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone


def get_log_path(wiki_root: str) -> str:
    return os.path.join(wiki_root, ".eval", "iteration-log.jsonl")


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def cmd_record(args):
    wiki_root = args.wiki_root
    issues = args.issues
    phase = args.phase

    log_path = get_log_path(wiki_root)
    os.makedirs(os.path.dirname(log_path), exist_ok=True)

    record = {
        "timestamp": now_utc_iso(),
        "issues": issues,
        "phase": phase,
    }

    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")

    print(json.dumps(record, indent=2))


def cmd_trend(args):
    wiki_root = args.wiki_root
    log_path = get_log_path(wiki_root)

    if not os.path.exists(log_path):
        result = {"converging": True, "trend": [], "current_issues": 0}
        print(json.dumps(result, indent=2))
        return

    records = []
    with open(log_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    continue

    # Take last 10 records
    last_10 = records[-10:]

    if len(last_10) < 2:
        converging = True
    else:
        # Check if issues are decreasing (converging)
        first_issues = last_10[0].get("issues", 0)
        last_issues = last_10[-1].get("issues", 0)
        converging = last_issues < first_issues

    current_issues = last_10[-1].get("issues", 0) if last_10 else 0

    result = {
        "converging": converging,
        "trend": last_10,
        "current_issues": current_issues,
    }
    print(json.dumps(result, indent=2))


def main():
    parser = argparse.ArgumentParser(description="Track convergence of feedback loops")
    subparsers = parser.add_subparsers(dest="command", help="Subcommands")

    # record
    p_record = subparsers.add_parser("record", help="Record an iteration log entry")
    p_record.add_argument("wiki_root", help="Path to wiki root")
    p_record.add_argument("--issues", type=int, required=True, help="Number of issues")
    p_record.add_argument("--phase", required=True, help="Phase name")

    # trend
    p_trend = subparsers.add_parser("trend", help="Show convergence trend")
    p_trend.add_argument("wiki_root", help="Path to wiki root")

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(1)

    try:
        if args.command == "record":
            cmd_record(args)
        elif args.command == "trend":
            cmd_trend(args)
        else:
            parser.print_help()
            sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()