#!/usr/bin/env python3
"""
report-gen — Generate HTML verification report from eval-wiki data.

Python stdlib only. Reads all entities from eval-wiki and produces a
single self-contained HTML file.
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


def read_all_entities(wiki_root):
    """Read all entities from eval-wiki, returning dicts keyed by entity type."""
    ew = load_eval_wiki(wiki_root)
    entities = {
        "tasks": [],
        "environments": [],
        "rubrics": [],
        "runs": [],
        "feedback": [],
    }

    for etype in entities:
        dir_path = os.path.join(wiki_root, etype)
        if not os.path.isdir(dir_path):
            continue
        for fname in sorted(os.listdir(dir_path)):
            if fname.endswith(".md"):
                fpath = os.path.join(dir_path, fname)
                fm = ew.load_yaml_frontmatter(fpath)
                if fm:
                    fm["_file"] = fname
                    entities[etype].append(fm)

    return entities


def compute_stats(entities, wiki_root):
    """Compute overview statistics from entities."""
    tasks = entities["tasks"]
    runs = entities["runs"]
    feedback = entities["feedback"]

    total_tasks = len(tasks)
    total_runs = len(runs)

    # Pass rate
    pass_count = sum(1 for r in runs if r.get("verdict") == "yes")
    fail_count = sum(1 for r in runs if r.get("verdict") == "no")
    inconclusive_count = sum(1 for r in runs if r.get("verdict") == "inconclusive")
    total_verdict_runs = pass_count + fail_count + inconclusive_count
    pass_rate = f"{(pass_count / total_verdict_runs * 100):.1f}%" if total_verdict_runs > 0 else "N/A"

    # Coverage
    tasks_with_runs = set()
    for r in runs:
        tid = r.get("task_id", "")
        if tid:
            tasks_with_runs.add(tid)
    coverage = f"{(len(tasks_with_runs) / total_tasks * 100):.1f}%" if total_tasks > 0 else "N/A"

    # Gap map summary
    gap_path = os.path.join(wiki_root, "gap_map.md")
    gap_count = 0
    if os.path.isfile(gap_path):
        with open(gap_path, "r", encoding="utf-8") as f:
            gap_content = f.read()
        gap_count = len([m for m in gap_content.split() if m.startswith("G") and m[1:].isdigit()])

    # Feedback summary
    open_fb = [f for f in feedback if f.get("status") == "open"]
    applied_fb = [f for f in feedback if f.get("status") == "applied"]

    return {
        "total_tasks": total_tasks,
        "total_runs": total_runs,
        "pass_count": pass_count,
        "fail_count": fail_count,
        "inconclusive_count": inconclusive_count,
        "pass_rate": pass_rate,
        "coverage": coverage,
        "tasks_with_runs": len(tasks_with_runs),
        "gap_count": gap_count,
        "open_feedback": len(open_fb),
        "applied_feedback": len(applied_fb),
    }


def build_html(entities, stats, wiki_root):
    """Build the complete HTML report."""
    task_sections = []
    for task in entities["tasks"]:
        task_id = task.get("node_id", "")
        task_slug = task_id.split(":")[-1] if ":" in task_id else task.get("_file", "").replace(".md", "")

        # Find matching environment
        env = None
        for e in entities["environments"]:
            if e.get("task_id", "").endswith(task_slug):
                env = e
                break

        # Find matching rubric
        rubric = None
        for r in entities["rubrics"]:
            if r.get("task_id", "").endswith(task_slug):
                rubric = r
                break

        # Find runs for this task
        task_runs = [r for r in entities["runs"] if r.get("task_id", "").endswith(task_slug)]

        # Find feedback for this task
        task_feedback = [f for f in entities["feedback"] if f.get("target_id", "").endswith(task_slug)]

        section = build_task_section(task, env, rubric, task_runs, task_feedback)
        task_sections.append(section)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Agent Verification Report</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333; background: #f5f7fa; }}
.container {{ display: flex; min-height: 100vh; }}
.sidebar {{ width: 280px; background: #1a1d23; color: #ccc; padding: 20px; position: fixed; top: 0; left: 0; height: 100vh; overflow-y: auto; }}
.sidebar h2 {{ color: #fff; font-size: 16px; margin-bottom: 15px; border-bottom: 1px solid #333; padding-bottom: 8px; }}
.sidebar a {{ display: block; color: #8ab4f8; text-decoration: none; padding: 5px 0; font-size: 13px; }}
.sidebar a:hover {{ color: #fff; }}
.sidebar .stat {{ padding: 4px 0; font-size: 12px; color: #999; }}
.content {{ margin-left: 280px; padding: 30px; flex: 1; }}
h1 {{ font-size: 28px; margin-bottom: 20px; color: #1a1d23; }}
h2 {{ font-size: 22px; margin: 25px 0 15px; color: #2c3e50; border-bottom: 2px solid #e0e0e0; padding-bottom: 8px; }}
h3 {{ font-size: 18px; margin: 15px 0 10px; color: #34495e; }}
.stats-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 15px; margin-bottom: 25px; }}
.stat-card {{ background: #fff; border-radius: 8px; padding: 15px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
.stat-card .label {{ font-size: 12px; color: #666; text-transform: uppercase; letter-spacing: 0.5px; }}
.stat-card .value {{ font-size: 24px; font-weight: bold; color: #1a1d23; margin-top: 5px; }}
.stat-card .value.green {{ color: #27ae60; }}
.stat-card .value.red {{ color: #e74c3c; }}
.stat-card .value.orange {{ color: #f39c12; }}
.task-section {{ background: #fff; border-radius: 8px; padding: 20px; margin-bottom: 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
.task-section h3 {{ margin-top: 0; }}
table {{ width: 100%; border-collapse: collapse; margin: 10px 0; }}
th, td {{ padding: 8px 12px; text-align: left; border-bottom: 1px solid #e0e0e0; font-size: 14px; }}
th {{ background: #f8f9fa; font-weight: 600; color: #555; }}
tr:hover {{ background: #f8f9fa; }}
.score-pass {{ background: #d4edda; color: #155724; font-weight: bold; }}
.score-fail {{ background: #f8d7da; color: #721c24; font-weight: bold; }}
.score-unknown {{ background: #fff3cd; color: #856404; }}
.tag {{ display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 600; margin-right: 4px; }}
.tag-draft {{ background: #e2e3e5; color: #383d41; }}
.tag-finalized {{ background: #cce5ff; color: #004085; }}
.tag-pass {{ background: #d4edda; color: #155724; }}
.tag-fail {{ background: #f8d7da; color: #721c24; }}
.tag-running {{ background: #fff3cd; color: #856404; }}
.meta-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 8px; margin: 10px 0; }}
.meta-item {{ font-size: 13px; }}
.meta-item strong {{ color: #555; }}
ul {{ padding-left: 20px; margin: 8px 0; }}
li {{ font-size: 14px; margin-bottom: 4px; }}
.feedback-item {{ border-left: 3px solid #f39c12; padding: 10px; margin: 8px 0; background: #fffef5; border-radius: 0 4px 4px 0; font-size: 13px; }}
.feedback-item.applied {{ border-left-color: #27ae60; background: #f0faf0; }}
.footer {{ text-align: center; padding: 20px; color: #999; font-size: 12px; }}
</style>
</head>
<body>
<div class="container">
<div class="sidebar">
<h2>Navigation</h2>
<div class="stat">Generated: {load_eval_wiki(wiki_root).now_utc_iso()}</div>
<div class="stat" style="margin-top:10px;"><strong>Overview</strong></div>
<a href="#overview">Overview</a>
<div class="stat" style="margin-top:10px;"><strong>Tasks</strong></div>
"""

    # Add nav links for each task
    for task in entities["tasks"]:
        task_id = task.get("node_id", "")
        task_slug = task_id.split(":")[-1] if ":" in task_id else task.get("_file", "").replace(".md", "")
        title = task.get("title", task_slug)
        html += f'<a href="#task-{task_slug}">{title}</a>\n'

    html += """</div>
<div class="content">
<h1>Agent Verification Report</h1>
"""

    # Overview section
    html += f"""<section id="overview">
<h2>Overview</h2>
<div class="stats-grid">
<div class="stat-card"><div class="label">Total Tasks</div><div class="value">{stats['total_tasks']}</div></div>
<div class="stat-card"><div class="label">Total Runs</div><div class="value">{stats['total_runs']}</div></div>
<div class="stat-card"><div class="label">Pass Rate</div><div class="value green">{stats['pass_rate']}</div></div>
<div class="stat-card"><div class="label">Coverage</div><div class="value">{stats['coverage']}</div></div>
<div class="stat-card"><div class="label">Passed</div><div class="value green">{stats['pass_count']}</div></div>
<div class="stat-card"><div class="label">Failed</div><div class="value red">{stats['fail_count']}</div></div>
<div class="stat-card"><div class="label">Inconclusive</div><div class="value orange">{stats['inconclusive_count']}</div></div>
<div class="stat-card"><div class="label">Tasks with Runs</div><div class="value">{stats['tasks_with_runs']}</div></div>
<div class="stat-card"><div class="label">Gap Map Entries</div><div class="value">{stats['gap_count']}</div></div>
<div class="stat-card"><div class="label">Open Feedback</div><div class="value orange">{stats['open_feedback']}</div></div>
<div class="stat-card"><div class="label">Applied Feedback</div><div class="value green">{stats['applied_feedback']}</div></div>
</div>
</section>
"""

    # Per-task sections
    html += "".join(task_sections)

    html += f"""<div class="footer">
Generated by report-gen | Eval Wiki: {wiki_root}
</div>
</div>
</div>
</body>
</html>"""
    return html


def build_task_section(task, env, rubric, runs, feedback):
    """Build HTML for a single task section."""
    task_id = task.get("node_id", "")
    task_slug = task_id.split(":")[-1] if ":" in task_id else task.get("_file", "").replace(".md", "")
    title = task.get("title", task_slug)
    difficulty = task.get("difficulty", "unknown")
    scenario_type = task.get("scenario_type", "unknown")
    status = task.get("status", "unknown")
    constraints = task.get("agent_constraints", {})
    expected = task.get("expected_behavior", [])

    # Status tag
    tag_class = f"tag-{status}" if status in ("draft", "finalized") else "tag-draft"

    html = f"""<section id="task-{task_slug}" class="task-section">
<h3>{title} <span class="tag {tag_class}">{status}</span></h3>
<div class="meta-grid">
<div class="meta-item"><strong>Task ID:</strong> {task_id}</div>
<div class="meta-item"><strong>Difficulty:</strong> {difficulty}</div>
<div class="meta-item"><strong>Scenario:</strong> {scenario_type}</div>
<div class="meta-item"><strong>Max Turns:</strong> {constraints.get('max_turns', 'N/A')}</div>
</div>
"""

    # Expected behavior
    if expected:
        html += "<div><strong>Expected Behavior:</strong><ul>\n"
        for b in expected:
            html += f"<li>{b}</li>\n"
        html += "</ul></div>\n"

    # Allowed tools
    allowed = constraints.get("allowed_tools", [])
    if allowed:
        html += f"<div><strong>Allowed Tools:</strong> {', '.join(allowed)}</div>\n"

    # Environment
    if env:
        docker = env.get("docker", {})
        html += f"""<h4>Environment</h4>
<div class="meta-grid">
<div class="meta-item"><strong>Image:</strong> {docker.get('image', 'N/A')}</div>
<div class="meta-item"><strong>Network:</strong> {docker.get('network', 'N/A')}</div>
<div class="meta-item"><strong>Memory:</strong> {docker.get('resource_limits', {}).get('memory', 'N/A')}</div>
<div class="meta-item"><strong>CPUs:</strong> {docker.get('resource_limits', {}).get('cpus', 'N/A')}</div>
</div>
"""

    # Rubric
    if rubric:
        criteria = rubric.get("criteria", [])
        html += f"""<h4>Rubric Criteria</h4>
<table>
<tr><th>ID</th><th>Name</th><th>Scoring</th><th>Weight</th><th>Evaluator</th></tr>
"""
        for c in criteria:
            html += f"<tr><td>{c.get('id', '')}</td><td>{c.get('name', '')}</td><td>{c.get('scoring', '')}</td><td>{c.get('weight', '')}</td><td>{c.get('evaluator', '')}</td></tr>\n"
        html += "</table>\n"

    # Runs
    if runs:
        html += f"""<h4>Run Results ({len(runs)})</h4>
<table>
<tr><th>Run ID</th><th>Model</th><th>Verdict</th><th>Total</th><th>Status</th></tr>
"""
        for r in runs:
            run_id = r.get("node_id", "")
            verdict = r.get("verdict", "unknown")
            total = r.get("total", "N/A")
            run_status = r.get("status", "unknown")
            agent = r.get("agent", {})
            model = agent.get("model", "N/A")

            verdict_class = "score-pass" if verdict == "yes" else ("score-fail" if verdict == "no" else "score-unknown")
            status_class = f"tag-{run_status}" if run_status in ("pass", "fail", "running") else "tag-draft"

            html += f'<tr><td>{run_id}</td><td>{model}</td><td class="{verdict_class}">{verdict}</td><td>{total}</td><td><span class="tag {status_class}">{run_status}</span></td></tr>\n'
        html += "</table>\n"

        # Scores detail
        has_scores = any(r.get("scores") for r in runs)
        if has_scores:
            html += "<h5>Score Details</h5>\n<table>\n<tr><th>Run ID</th>"
            # Collect all criterion IDs
            all_cids = set()
            for r in runs:
                if r.get("scores"):
                    all_cids.update(r["scores"].keys())
            all_cids = sorted(all_cids)

            for cid in all_cids:
                html += f"<th>{cid}</th>"
            html += "</tr>\n"

            for r in runs:
                run_id = r.get("node_id", "")
                html += f"<tr><td>{run_id}</td>"
                scores = r.get("scores", {})
                for cid in all_cids:
                    score = scores.get(cid, "-")
                    html += f"<td>{score}</td>"
                html += "</tr>\n"
            html += "</table>\n"

    # Feedback
    if feedback:
        html += f"<h4>Feedback ({len(feedback)})</h4>\n"
        for f in feedback:
            fb_status = f.get("status", "open")
            fb_class = "feedback-item" + (" applied" if fb_status == "applied" else "")
            html += f"""<div class="{fb_class}">
<strong>{f.get('issue_type', '')}</strong> ({f.get('from', '')}) - {f.get('description', '')}
<br><em>Action: {f.get('action', '')} | Status: {fb_status}</em>
</div>
"""

    html += "</section>\n"
    return html


def main():
    parser = argparse.ArgumentParser(description="Generate HTML verification report")
    parser.add_argument("--wiki-root", required=True, help="Path to eval-wiki root")
    parser.add_argument("--output", default="reports/report.html", help="Output HTML file path")

    args = parser.parse_args()

    # Read all entities
    entities = read_all_entities(args.wiki_root)

    # Compute stats
    stats = compute_stats(entities, args.wiki_root)

    # Build HTML
    html = build_html(entities, stats, args.wiki_root)

    # Write output
    output_path = args.output
    os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"Report generated: {output_path}")


if __name__ == "__main__":
    main()