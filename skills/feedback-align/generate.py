#!/usr/bin/env python3
"""
feedback-align — Process user feedback to align task/rubric/env/report with
user expectations.

Python stdlib only. Invokes eval-wiki.py via importlib.
"""

import argparse
import os
import sys
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


def resolve_target_target(target_type, target_id):
    """Resolve the target file path based on type and ID."""
    prefix_map = {
        "task": "tasks",
        "rubric": "rubrics",
        "environment": "environments",
        "run": "runs",
    }
    dir_name = prefix_map.get(target_type)
    if dir_name is None:
        print(f"Error: unknown target type '{target_type}'", file=sys.stderr)
        sys.exit(1)

    # Strip prefix if present
    slug = target_id
    for prefix in ["task:", "rubric:", "env:", "run:"]:
        if slug.startswith(prefix):
            slug = slug[len(prefix):]
            break

    return dir_name, slug


def apply_change(wiki_root, target_type, target_id, field, from_value, to_value):
    """Apply a change to a target entity file."""
    ew = load_eval_wiki(wiki_root)
    dir_name, slug = resolve_target_target(target_type, target_id)

    filepath = os.path.join(wiki_root, dir_name, f"{slug}.md")
    if not os.path.isfile(filepath):
        print(f"Error: target file not found at {filepath}", file=sys.stderr)
        return None

    # Read the current frontmatter
    fm = ew.load_yaml_frontmatter(filepath)
    if not fm:
        print(f"Error: could not parse frontmatter from {filepath}", file=sys.stderr)
        return None

    # Navigate to the field and update it
    if field not in fm:
        print(f"Warning: field '{field}' not found in frontmatter, adding it", file=sys.stderr)

    # Convert from_value and to_value to appropriate types
    typed_to = to_value
    if to_value is not None:
        # Try to preserve type from existing value
        existing = fm.get(field)
        if existing is not None:
            if isinstance(existing, bool):
                typed_to = to_value.lower() in ("true", "1", "yes")
            elif isinstance(existing, int):
                try:
                    typed_to = int(to_value)
                except ValueError:
                    pass
            elif isinstance(existing, float):
                try:
                    typed_to = float(to_value)
                except ValueError:
                    pass
            elif isinstance(existing, list):
                typed_to = [v.strip() for v in to_value.split(",")] if to_value else []
            elif isinstance(existing, dict):
                # For dicts, try JSON parse
                import json
                try:
                    typed_to = json.loads(to_value)
                except json.JSONDecodeError:
                    typed_to = to_value
        elif from_value is not None:
            # Try to match type of from_value
            pass

    fm[field] = typed_to

    # Read the original file content
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    # Find frontmatter boundaries
    if not content.startswith("---"):
        print(f"Error: file does not start with frontmatter: {filepath}", file=sys.stderr)
        return None

    end_idx = content.find("---", 3)
    if end_idx == -1:
        print(f"Error: could not find end of frontmatter in {filepath}", file=sys.stderr)
        return None

    # Rebuild frontmatter
    new_fm = ew.render_yaml_frontmatter(fm)

    # Preserve body after frontmatter
    body = content[end_idx + 3:]
    if body.startswith("\n"):
        body = body[1:]
    if body.startswith("\n"):
        body = body[1:]

    new_content = new_fm + "\n" + body

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(new_content)

    print(f"Updated field '{field}' in {filepath}")
    print(f"  From: {from_value}")
    print(f"  To: {to_value}")

    return filepath


def update_feedback_status(wiki_root, feedback_slug, new_status, verified_by=None):
    """Update the status of a feedback entry."""
    ew = load_eval_wiki(wiki_root)
    fb_path = os.path.join(wiki_root, "feedback", f"{feedback_slug}.md")

    if not os.path.isfile(fb_path):
        print(f"Warning: feedback file not found at {fb_path}", file=sys.stderr)
        return

    fm = ew.load_yaml_frontmatter(fb_path)
    if not fm:
        return

    fm["status"] = new_status
    if new_status == "applied":
        fm["applied_at"] = ew.now_utc_iso()
    if verified_by:
        fm["verified_by"] = verified_by

    new_fm = ew.render_yaml_frontmatter(fm)

    with open(fb_path, "r", encoding="utf-8") as f:
        content = f.read()

    end_idx = content.find("---", 3)
    body = content[end_idx + 3:]
    if body.startswith("\n"):
        body = body[1:]
    if body.startswith("\n"):
        body = body[1:]

    with open(fb_path, "w", encoding="utf-8") as f:
        f.write(new_fm + "\n" + body)


def main():
    parser = argparse.ArgumentParser(
        description="Process user feedback to align task/rubric/env/report"
    )
    parser.add_argument("--wiki-root", required=True, help="Path to eval-wiki root")
    parser.add_argument("--target-type", required=True,
                        choices=["task", "rubric", "environment", "run"],
                        help="Type of target entity")
    parser.add_argument("--target-id", required=True, help="Target entity ID")
    parser.add_argument("--from", dest="from_source", default="user",
                        choices=["user", "auto-audit"],
                        help="Source of feedback")
    parser.add_argument("--issue-type", required=True,
                        choices=["misalignment", "missing_case", "rubric_error",
                                 "env_error", "difficulty_mismatch"],
                        help="Type of issue")
    parser.add_argument("--description", required=True, help="Feedback description")
    parser.add_argument("--action", required=True,
                        choices=["revise_task", "revise_rubric", "revise_env",
                                 "revise_report"],
                        help="Action to take")
    parser.add_argument("--field", help="Field to change in the target entity")
    parser.add_argument("--from-value", help="Current value of the field")
    parser.add_argument("--to-value", help="New value of the field")
    parser.add_argument("--apply", action="store_true",
                        help="Apply the proposed change and mark feedback as applied")

    args = parser.parse_args()

    ew = load_eval_wiki(args.wiki_root)

    # 1. Record feedback via eval-wiki
    fb_filepath = ew.add_feedback(
        wiki_root=args.wiki_root,
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
    print(f"Feedback recorded: {fb_filepath}")

    # Extract feedback slug from the filepath
    fb_slug = os.path.basename(fb_filepath).replace(".md", "")

    # 2. If --apply, modify the target entity
    applied = False
    if args.apply:
        if not args.field or args.to_value is None:
            print("Error: --field and --to-value are required when --apply is set",
                  file=sys.stderr)
            sys.exit(1)

        result = apply_change(
            wiki_root=args.wiki_root,
            target_type=args.target_type,
            target_id=args.target_id,
            field=args.field,
            from_value=args.from_value,
            to_value=args.to_value,
        )

        if result:
            # Update feedback status to applied
            update_feedback_status(args.wiki_root, fb_slug, "applied", verified_by="feedback-align")
            print(f"Feedback status updated to 'applied'")
            applied = True
        else:
            print("Error: failed to apply change", file=sys.stderr)
            sys.exit(1)

    # 3. Summary
    print("\n--- Summary ---")
    print(f"Feedback ID: feedback:{fb_slug}")
    print(f"Target: {args.target_type}:{args.target_id}")
    print(f"Issue: {args.issue_type}")
    print(f"Description: {args.description}")
    print(f"Action: {args.action}")
    print(f"Status: {'applied' if applied else 'open'}")
    if args.field:
        print(f"Change: {args.field} = {args.from_value} -> {args.to_value}")


if __name__ == "__main__":
    main()