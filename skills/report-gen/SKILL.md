---
name: report-gen
description: Generate HTML verification report from eval-wiki data
argument-hint: [wiki-root]
allowed-tools: Bash(*), Read, Write
---

# report-gen

Generates an HTML verification report from all eval-wiki entities. Produces
a single self-contained HTML file with overview section and per-task detail
sections with anchor navigation.

## Workflow

1. Read ALL entities from eval-wiki (tasks, environments, rubrics, runs, feedback)
2. Generate a single HTML file with:
   - Overview section (stats, pass rate, coverage, gap map, feedback summary)
   - Per-task detail sections (task metadata, env config, rubric criteria, runs, feedback)
   - Navigation sidebar or top nav with anchor links
   - Clean CSS styling (inline, no external deps)
   - Color-coded score tables (green=pass, red=fail)
3. Write to --output path