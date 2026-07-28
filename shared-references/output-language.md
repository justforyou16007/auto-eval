# Output Language

_Adapted from ARIS patterns for the eval-wiki context._

## Machine Markers, Not Localized

All structured output in the eval-wiki pipeline uses machine-readable markers
that are NOT localized. This ensures that automated tools can parse output
regardless of the human language context.

## Principles

1. **English markers**: All status codes, phase names, and structured data
   keys are in English.
2. **No localization**: Task content, rubrics, and feedback may be in any
   human language, but the machine-readable markers are always English.
3. **Consistent casing**: Status values use lowercase (e.g., "running",
   "done", "failed").
4. **JSON everywhere**: All structured data interchange uses JSON, not
   localized formats.

## Marker Examples

| Context | Marker | Language | Notes |
|---------|--------|----------|-------|
| Phase status | `pending`, `running`, `done`, `failed`, `skipped` | English | Not localized |
| Edge types | `tested_by`, `supports`, `invalidates` | English | Not localized |
| Run verdict | `yes`, `no`, `inconclusive` | English | Not localized |
| Confidence | `high`, `medium`, `low` | English | Not localized |
| Difficulty | `lite`, `easy`, `medium`, `hard`, `beast` | English | Not localized |
| Assurance | `draft`, `submission` | English | Not localized |
| Task body | Chinese or other languages | Any | Localized content OK |
| Rubric criteria | Chinese or other languages | Any | Localized content OK |

## Rationale

Using consistent English markers across all pipelines ensures:

1. Automated tools can parse output regardless of the evaluation language
2. Cross-model review works correctly (markers are not language-dependent)
3. Trace files are machine-readable across different locales
4. Pipeline scripts can use `grep`, `jq`, and other tools reliably

## Cross-Reference

- `run-state.py` — Status values use English markers
- `capture-filter.py` — Pattern matching is case-insensitive English
- `evidence-check.py` — JSON output uses English keys