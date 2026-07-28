#!/usr/bin/env python3
"""
capture-filter.py — Prevents runtime noise from being persisted as valid tasks/rubrics/feedback.

Reads text from a file (use - for stdin), checks for noise patterns, and returns
JSON output with findings.

Usage:
    python3 capture-filter.py <text-file> [--strict]
    echo "some text" | python3 capture-filter.py - [--strict]

Exit 0 if clean, 1 if findings.
"""

import argparse
import json
import re
import sys


PATTERNS = [
    {
        "name": "env-failure",
        "patterns": [
            r"no\s+module\s+named",
            r"importerror",
            r"modulenotfounderror",
            r"pip\s+install",
        ],
        "severity": "high",
    },
    {
        "name": "transient-error",
        "patterns": [
            r"timeout",
            r"connection\s+refused",
            r"rate\s+limit",
            r"\b503\b",
            r"\b502\b",
        ],
        "severity": "medium",
    },
    {
        "name": "negative-tool-claim",
        "patterns": [
            r"can't\s+do",
            r"unable\s+to",
            r"i\s+cannot",
            r"not\s+possible\s+to",
        ],
        "severity": "high",
    },
]


def check_text(text: str, strict: bool = False) -> dict:
    """Check text against known noise patterns."""
    findings = []
    text_lower = text.lower()

    for category in PATTERNS:
        for pattern in category["patterns"]:
            matches = list(re.finditer(pattern, text_lower, re.IGNORECASE))
            if matches:
                for m in matches:
                    findings.append({
                        "pattern": category["name"],
                        "match": m.group().strip(),
                        "severity": category["severity"],
                    })

    # Deduplicate findings
    seen = set()
    unique_findings = []
    for f in findings:
        key = (f["pattern"], f["match"], f["severity"])
        if key not in seen:
            seen.add(key)
            unique_findings.append(f)

    clean = len(unique_findings) == 0
    return {"clean": clean, "findings": unique_findings}


def main():
    parser = argparse.ArgumentParser(
        description="Filter runtime noise from eval artifacts"
    )
    parser.add_argument("text_file", help="Path to text file, or '-' for stdin")
    parser.add_argument("--strict", action="store_true", help="Enable strict mode")
    args = parser.parse_args()

    if args.text_file == "-":
        text = sys.stdin.read()
    else:
        with open(args.text_file, "r", encoding="utf-8") as f:
            text = f.read()

    result = check_text(text, strict=args.strict)
    print(json.dumps(result, indent=2))

    sys.exit(0 if result["clean"] else 1)


if __name__ == "__main__":
    main()