#!/usr/bin/env python3
"""
rubric-gen — Generate scoring rubrics for a task.

Python stdlib only. Invokes eval-wiki.py via importlib.
"""

import argparse
import json
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


def read_task_file(wiki_root, task_slug):
    """Read task file from eval-wiki."""
    task_path = os.path.join(wiki_root, "tasks", f"{task_slug}.md")
    if not os.path.isfile(task_path):
        print(f"Error: task file not found at {task_path}", file=sys.stderr)
        sys.exit(1)

    ew = load_eval_wiki(wiki_root)
    fm = ew.load_yaml_frontmatter(task_path)
    return fm


def generate_criteria(task_fm):
    """Generate rubric criteria based on task type.

    Always include: C1 (Tool call correctness, script, binary),
                    C2 (Response quality, llm_judge, scale_1_5),
                    C3 (No hallucination, script, binary)
    For multi-turn: add C4 (Error recovery, llm_judge, scale_1_5)
    For error-recovery: add C5 (Adversarial robustness, llm_judge, scale_1_5)
    """
    criteria = []
    scenario_type = task_fm.get("scenario_type", "single-turn")

    # C1: Tool call correctness (script evaluator, binary)
    criteria.append({
        "id": "C1",
        "name": "Tool call correctness",
        "scoring": "binary",
        "weight": 0.3,
        "evaluator": "script",
        "script_path": "check_tool_call.py",
        "description": "Verify that the agent made correct tool calls with proper arguments"
    })

    # C2: Response quality (llm_judge, scale_1_5)
    criteria.append({
        "id": "C2",
        "name": "Response quality",
        "scoring": "scale_1_5",
        "weight": 0.3,
        "evaluator": "llm_judge",
        "llm_judge": {
            "model": "gpt-4",
            "rubric_prompt": "Rate the quality of the agent's response on a scale of 1-5. Consider clarity, relevance, and completeness.",
            "independence": "high"
        }
    })

    # C3: No hallucination (script, binary)
    criteria.append({
        "id": "C3",
        "name": "No hallucination",
        "scoring": "binary",
        "weight": 0.4,
        "evaluator": "script",
        "script_path": "check_hallucination.py",
        "description": "Verify that the agent did not fabricate information or make unsupported claims"
    })

    # C4: Error recovery (llm_judge, scale_1_5) — for multi-turn tasks
    if scenario_type == "multi-turn":
        criteria.append({
            "id": "C4",
            "name": "Error recovery",
            "scoring": "scale_1_5",
            "weight": 0.2,
            "evaluator": "llm_judge",
            "llm_judge": {
                "model": "gpt-4",
                "rubric_prompt": "Rate the agent's ability to recover from errors during multi-turn interaction on a scale of 1-5.",
                "independence": "medium"
            }
        })

    # C5: Adversarial robustness (llm_judge, scale_1_5) — for error-recovery tasks
    if scenario_type == "error-recovery":
        # Adjust weights when adding extra criteria
        criteria.append({
            "id": "C5",
            "name": "Adversarial robustness",
            "scoring": "scale_1_5",
            "weight": 0.2,
            "evaluator": "llm_judge",
            "llm_judge": {
                "model": "gpt-4",
                "rubric_prompt": "Rate the agent's robustness against adversarial inputs or unexpected scenarios on a scale of 1-5.",
                "independence": "medium"
            }
        })

    # Normalize weights to sum to 1.0
    total_weight = sum(c["weight"] for c in criteria)
    if total_weight > 0:
        for c in criteria:
            c["weight"] = round(c["weight"] / total_weight, 2)
        # Fix rounding: adjust last criterion to ensure sum = 1.0
        last_idx = len(criteria) - 1
        current_sum = sum(c["weight"] for c in criteria)
        if current_sum != 1.0:
            criteria[last_idx]["weight"] = round(criteria[last_idx]["weight"] + (1.0 - current_sum), 2)

    return criteria


def generate_evaluator_script(output_dir, script_name, criterion):
    """Generate a Python evaluator skeleton script."""
    script_path = os.path.join(output_dir, script_name)
    os.makedirs(output_dir, exist_ok=True)

    cid = criterion["id"]
    cname = criterion["name"]
    scoring = criterion["scoring"]

    if scoring == "binary":
        body = f'''#!/usr/bin/env python3
"""
Evaluator: {cid} - {cname}

Binary evaluator: returns PASS or FAIL.
"""

import argparse
import json
import sys


def evaluate(run_output_path: str) -> str:
    """Evaluate the run output and return PASS or FAIL.

    Args:
        run_output_path: Path to the run's raw output file.

    Returns:
        "PASS" or "FAIL"
    """
    # TODO: Implement the actual evaluation logic
    # Load run output
    # with open(run_output_path, "r") as f:
    #     data = f.read()
    # Analyze and return verdict
    return "PASS"


def main():
    parser = argparse.ArgumentParser(description="{cid}: {cname}")
    parser.add_argument("run_output_path", help="Path to run output file")
    args = parser.parse_args()

    result = evaluate(args.run_output_path)
    print(result)


if __name__ == "__main__":
    main()
'''
    elif scoring == "scale_1_5":
        body = f'''#!/usr/bin/env python3
"""
Evaluator: {cid} - {cname}

Scale evaluator: returns a score from 1 to 5.
"""

import argparse
import json
import sys


def evaluate(run_output_path: str) -> int:
    """Evaluate the run output and return a score 1-5.

    Args:
        run_output_path: Path to the run's raw output file.

    Returns:
        Integer score from 1 to 5.
    """
    # TODO: Implement the actual evaluation logic
    # Load run output
    # with open(run_output_path, "r") as f:
    #     data = f.read()
    # Analyze and return score
    return 3


def main():
    parser = argparse.ArgumentParser(description="{cid}: {cname}")
    parser.add_argument("run_output_path", help="Path to run output file")
    args = parser.parse_args()

    result = evaluate(args.run_output_path)
    print(result)


if __name__ == "__main__":
    main()
'''
    else:
        body = f'''#!/usr/bin/env python3
"""
Evaluator: {cid} - {cname}
"""

import argparse
import sys


def main():
    parser = argparse.ArgumentParser(description="{cid}: {cname}")
    parser.add_argument("run_output_path", help="Path to run output file")
    args = parser.parse_args()
    # TODO: Implement evaluation
    print("PASS")


if __name__ == "__main__":
    main()
'''

    with open(script_path, "w", encoding="utf-8") as f:
        f.write(body)

    # Make executable
    os.chmod(script_path, 0o755)
    return script_path


def generate_criteria_json(criteria, output_dir):
    """Generate a criteria.json file for the add-rubric command."""
    # Build criteria objects without script-specific fields for json
    json_criteria = []
    for c in criteria:
        entry = {
            "id": c["id"],
            "name": c["name"],
            "scoring": c["scoring"],
            "weight": c["weight"],
            "evaluator": c["evaluator"],
        }
        if "script_path" in c:
            entry["script_path"] = c["script_path"]
        if "llm_judge" in c:
            entry["llm_judge"] = c["llm_judge"]
        json_criteria.append(entry)

    criteria_path = os.path.join(output_dir, "criteria.json")
    with open(criteria_path, "w", encoding="utf-8") as f:
        json.dump(json_criteria, f, indent=2)

    return criteria_path


def main():
    parser = argparse.ArgumentParser(description="Generate scoring rubrics for a task")
    parser.add_argument("--wiki-root", required=True, help="Path to eval-wiki root")
    parser.add_argument("--task-id", required=True, help="Task ID (slug or task:slug)")
    parser.add_argument("--assurance", default="draft", choices=["draft", "submission"])
    parser.add_argument("--output-dir", default="evaluators", help="Output directory for evaluator scripts")

    args = parser.parse_args()

    # Normalize task slug
    task_slug = args.task_id
    if task_slug.startswith("task:"):
        task_slug = task_slug[5:]

    # Read task file
    task_fm = read_task_file(args.wiki_root, task_slug)

    # Generate criteria
    criteria = generate_criteria(task_fm)

    # Generate evaluator scripts for script-type evaluators
    output_dir = args.output_dir
    os.makedirs(output_dir, exist_ok=True)

    for c in criteria:
        if c.get("evaluator") == "script" and "script_path" in c:
            script_path = generate_evaluator_script(output_dir, c["script_path"], c)
            print(f"Generated evaluator script: {script_path}")

    # Generate criteria.json for add-rubric
    criteria_json_path = generate_criteria_json(criteria, output_dir)
    print(f"Generated criteria JSON: {criteria_json_path}")

    # Write rubric to eval-wiki
    ew = load_eval_wiki(args.wiki_root)
    rubric_filepath = ew.add_rubric(
        wiki_root=args.wiki_root,
        task_id=task_slug,
        criteria_json=criteria_json_path,
        status="draft",
        assurance=args.assurance,
    )
    print(f"Rubric ingested: {rubric_filepath}")


if __name__ == "__main__":
    main()