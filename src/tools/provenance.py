#!/usr/bin/env python3
"""
provenance.py — Validates provenance links in reports.

CLI: python3 provenance.py check <wiki-root>

For each run in runs/, checks that all provenance paths exist.
Returns JSON: {"total_runs": N, "valid_runs": M, "broken": [{"run": ..., "path": ...}]}
"""

import argparse
import json
import os
import re
import sys


def load_yaml_frontmatter_simple(filepath: str) -> dict:
    """Minimal YAML frontmatter parser for provenance extraction."""
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
    result = {}
    for line in frontmatter_text.split("\n"):
        line = line.strip()
        if ":" in line:
            key, value = line.split(":", 1)
            result[key.strip()] = value.strip().strip('"').strip("'")
    return result


def check_provenance(wiki_root: str) -> dict:
    """Check all provenance paths in runs/."""
    runs_dir = os.path.join(wiki_root, "runs")
    if not os.path.isdir(runs_dir):
        return {"total_runs": 0, "valid_runs": 0, "broken": []}

    total_runs = 0
    valid_runs = 0
    broken = []

    for fname in sorted(os.listdir(runs_dir)):
        if not fname.endswith(".md"):
            continue
        total_runs += 1
        fpath = os.path.join(runs_dir, fname)
        fm = load_yaml_frontmatter_simple(fpath)

        # Check raw_output_path
        raw_path = fm.get("raw_output_path", "")
        if raw_path:
            abs_path = os.path.join(wiki_root, raw_path) if not os.path.isabs(raw_path) else raw_path
            if not os.path.exists(abs_path):
                broken.append({"run": fname[:-3], "path": raw_path})

        # Check provenance
        provenance_line = None
        with open(fpath, "r", encoding="utf-8") as f:
            content = f.read()
            for m in re.finditer(r'provenance\s*:\s*\[([^\]]*)\]', content):
                provenance_line = m.group(1)
                break

        if provenance_line:
            for item in re.findall(r'"([^"]+)"', provenance_line):
                abs_path = os.path.join(wiki_root, item) if not os.path.isabs(item) else item
                if not os.path.exists(abs_path):
                    broken.append({"run": fname[:-3], "path": item})

        if not any(b["run"] == fname[:-3] for b in broken):
            valid_runs += 1

    return {"total_runs": total_runs, "valid_runs": valid_runs, "broken": broken}


def main():
    parser = argparse.ArgumentParser(description="Validate provenance links in reports")
    subparsers = parser.add_subparsers(dest="command", help="Subcommands")
    p_check = subparsers.add_parser("check", help="Check provenance links")
    p_check.add_argument("wiki_root", help="Path to wiki root")
    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(1)

    try:
        if args.command == "check":
            result = check_provenance(args.wiki_root)
            print(json.dumps(result, indent=2))
            sys.exit(0 if result["total_runs"] == 0 or result["valid_runs"] == result["total_runs"] else 1)
        else:
            parser.print_help()
            sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()