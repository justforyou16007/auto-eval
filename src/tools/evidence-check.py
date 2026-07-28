#!/usr/bin/env python3
"""
evidence-check.py — Verifies that run evidence files exist and are non-empty.

CLI: python3 evidence-check.py <run_dir>

Checks:
- trace.jsonl exists and > 0 bytes
- output.txt exists and > 0 bytes
- Any provenance paths listed in the run markdown exist

Returns JSON: {"valid": true/false, "missing": [...], "empty": [...]}
Exit 0 if valid, 1 if issues.
"""

import argparse
import json
import os
import sys
import re


def find_provenance_paths(run_dir: str) -> list:
    """Extract provenance paths from run markdown files."""
    paths = []
    run_md_files = [f for f in os.listdir(run_dir) if f.endswith(".md")]
    for fname in run_md_files:
        fpath = os.path.join(run_dir, fname)
        with open(fpath, "r", encoding="utf-8") as f:
            content = f.read()
        # Find provenance paths in YAML frontmatter or body
        # Look for provenance: [...], raw_output_path, etc.
        for m in re.finditer(r'(?:provenance|raw_output_path|evidence)\s*[:=]\s*"([^"]+)"', content):
            paths.append(m.group(1))
        # Also look for inline arrays
        for m in re.finditer(r'provenance\s*:\s*\[([^\]]+)\]', content):
            inner = m.group(1)
            for item in re.findall(r'"([^"]+)"', inner):
                paths.append(item)
    return paths


def check_run_dir(run_dir: str) -> dict:
    """Check evidence files in a run directory."""
    missing = []
    empty = []

    # Check trace.jsonl
    trace_path = os.path.join(run_dir, "trace.jsonl")
    if not os.path.exists(trace_path):
        missing.append("trace.jsonl")
    elif os.path.getsize(trace_path) == 0:
        empty.append("trace.jsonl")

    # Check output.txt
    output_path = os.path.join(run_dir, "output.txt")
    if not os.path.exists(output_path):
        missing.append("output.txt")
    elif os.path.getsize(output_path) == 0:
        empty.append("output.txt")

    # Check provenance paths from run markdown
    provenance_paths = find_provenance_paths(run_dir)
    for p in provenance_paths:
        abs_p = os.path.join(run_dir, p) if not os.path.isabs(p) else p
        if not os.path.exists(abs_p):
            missing.append(p)
        elif os.path.getsize(abs_p) == 0:
            empty.append(p)

    valid = len(missing) == 0 and len(empty) == 0
    return {"valid": valid, "missing": missing, "empty": empty}


def main():
    parser = argparse.ArgumentParser(
        description="Verify run evidence files exist and are non-empty"
    )
    parser.add_argument("run_dir", help="Path to run directory")
    args = parser.parse_args()

    if not os.path.isdir(args.run_dir):
        print(f"Error: {args.run_dir} is not a directory", file=sys.stderr)
        sys.exit(1)

    result = check_run_dir(args.run_dir)
    print(json.dumps(result, indent=2))
    sys.exit(0 if result["valid"] else 1)


if __name__ == "__main__":
    main()